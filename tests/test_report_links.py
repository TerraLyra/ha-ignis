"""Manual provenance survives restarts without changing satellite evidence."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.terralyra_ignis.report_links import ReportLinks, resolve_links
from custom_components.terralyra_ignis.report_review import review_notice

NOW = datetime(2026, 9, 10, tzinfo=UTC)
NOTICE = {
    "url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
    "title": "Synthetic fire", "publisher": "BM OKF", "description": "Test",
    "published_at": "2026-09-09T14:00:00+02:00",
}
HISTORY = [{
    "track_id": "one", "latitude": 47.6, "longitude": 21.0,
    "first_seen": "2026-09-09T12:00:00+02:00", "last_seen": "2026-09-09T12:30:00+02:00",
    "providers": ["nasa_firms"], "satellites": ["N20"],
}]
INPUT = {"latitude": 47.6, "longitude": 21.0, "location_uncertainty_km": 5.0}


class MemoryStore:
    def __init__(self, data=None):
        self.data = data
        self.async_save = AsyncMock(side_effect=self.save)

    async def async_load(self):
        return deepcopy(self.data)

    async def save(self, data):
        self.data = deepcopy(data)


@pytest.fixture(autouse=True)
def clock():
    with patch("custom_components.terralyra_ignis.report_links.datetime") as clock:
        clock.now.return_value = NOW
        clock.fromisoformat.side_effect = datetime.fromisoformat
        yield clock


def candidate(history=HISTORY):
    return review_notice(history, NOTICE, **INPUT)["candidates"][0]


async def test_restart_idempotence_isolation_undo_and_input_unchanged():
    store = MemoryStore()
    links = ReportLinks(store)
    original = deepcopy(HISTORY)
    first = await links.async_add("entry", NOTICE, INPUT, candidate())
    assert (await links.async_add("entry", NOTICE, INPUT, candidate())) == first
    store.async_save.assert_awaited_once()
    restored = ReportLinks(store)
    assert await restored.async_list("entry") == [first]
    assert await restored.async_list("other") == []
    assert not await restored.async_remove("other", first["link_id"])
    assert await restored.async_remove("entry", first["link_id"])
    assert not await restored.async_remove("entry", first["link_id"])
    assert await ReportLinks(store).async_list("entry") == []
    assert HISTORY == original
    assert first["review"]["candidate"]["relation"] == "possible"
    assert first["approval"] == "manual_review_not_official_confirmation"


async def test_concurrent_adds_do_not_lose_links():
    links = ReportLinks(MemoryStore())
    await asyncio.gather(*(links.async_add(f"entry_{n}", NOTICE, INPUT, candidate()) for n in range(10)))
    assert len(await links.async_list("entry_5")) == 1
    assert len(links._store.data["links"]) == 10


async def test_expiry_corruption_and_unknown_fields(clock):
    store = MemoryStore()
    links = ReportLinks(store)
    first = await links.async_add("entry", NOTICE, INPUT, candidate())
    store.data["links"] += [None, {}, {"config_entry_id": []}]
    store.data["links"][0]["untrusted"] = "discard"
    assert await ReportLinks(store).async_list("entry") == [first]
    clock.now.return_value = NOW + timedelta(days=31)
    assert await ReportLinks(store).async_list("entry") == []
    assert store.data == {"links": []}


async def test_cap_rejects_new_link_without_evicting_manual_work():
    links = ReportLinks(MemoryStore())
    await links.async_add("entry", NOTICE, INPUT, candidate())
    with patch("custom_components.terralyra_ignis.report_links.MAX_LINKS", 1), pytest.raises(ValueError, match="limit"):
        await links.async_add("other", NOTICE, INPUT, candidate())
    assert len(await links.async_list("entry")) == 1


@pytest.mark.parametrize("change", [
    {"latitude": float("nan")}, {"distance_km": float("inf")}, {"providers": "invalid"},
    {"first_seen": "2026-09-09T12:00:00"}, {"reasons": ["officially_confirmed"]},
])
async def test_invalid_persisted_candidate_rejected(change):
    store = MemoryStore()
    await ReportLinks(store).async_add("entry", NOTICE, INPUT, candidate())
    store.data["links"][0]["review"]["candidate"].update(change)
    assert await ReportLinks(store).async_list("entry") == []


async def test_missing_changed_and_reused_incident_are_not_active():
    links = ReportLinks(MemoryStore())
    first = await links.async_add("entry", NOTICE, INPUT, candidate())
    assert resolve_links([first], HISTORY, [NOTICE])[0]["status"] == "active"
    assert resolve_links([first], [], [NOTICE])[0]["status"] == "incident_missing"
    assert resolve_links([first], HISTORY, [])[0]["status"] == "report_missing"
    assert resolve_links([first], HISTORY, [NOTICE | {"description": "Revised"}])[0]["status"] == "report_changed"
    reused = [HISTORY[0] | {"first_seen": "2026-09-10T12:00:00+02:00"}]
    assert resolve_links([first], reused, [NOTICE])[0]["status"] == "incident_identity_changed"


def test_review_metadata_and_stale_token_changes():
    first = candidate()
    assert first["providers"] == ["nasa_firms"]
    assert first["satellites"] == ["N20"]
    assert first["first_seen"] == HISTORY[0]["first_seen"]
    assert first["last_seen"] == HISTORY[0]["last_seen"]
    updated = candidate([HISTORY[0] | {"last_seen": "2026-09-09T12:35:00+02:00"}])
    assert first["review_token"] != updated["review_token"]
    report_changed = review_notice(HISTORY, NOTICE | {"description": "Changed"}, **INPUT)["candidates"][0]
    assert first["review_token"] != report_changed["review_token"]
