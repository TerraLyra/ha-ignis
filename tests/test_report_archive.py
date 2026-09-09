"""Persistence, retention and the saved Egyek report, without a live feed."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from custom_components.terralyra_ignis.report_archive import ReportArchive
from custom_components.terralyra_ignis.report_review import review_notice

NOW = datetime(2026, 9, 9, 21, tzinfo=UTC)


def record(number=1, **kwargs):
    return {"url": f"https://www.katasztrofavedelem.hu/modules/vesz/esemeny/{number}",
            "title": "Notice", "published_at": NOW.isoformat(), **kwargs}


class MemoryStore:
    def __init__(self, data=None):
        self.data = data
        self.async_save = AsyncMock(side_effect=self.save)

    async def async_load(self):
        return deepcopy(self.data)

    async def save(self, data):
        self.data = deepcopy(data)


@pytest.fixture(autouse=True)
def archive_clock():
    with patch("custom_components.terralyra_ignis.report_archive.datetime") as clock:
        clock.now.return_value = NOW
        clock.fromisoformat.side_effect = datetime.fromisoformat
        yield clock


async def test_retention_restart_dedup_and_no_unchanged_writes():
    store = MemoryStore()
    archive = ReportArchive(store)
    await archive.async_merge([record(), record()])
    assert len(await archive.async_merge([])) == 1
    store.async_save.assert_awaited_once()
    restored = ReportArchive(store)
    assert (await restored.async_merge())[0]["archive_origin"] == "rss"
    await restored.async_import(record(title="Manual must not overwrite RSS"))
    assert (await restored.async_merge())[0]["title"] == "Notice"


async def test_bounds_expiry_and_corrupt_records():
    data = [record(n) for n in range(1100)]
    store = MemoryStore({"notices": data})
    archive = ReportArchive(store)
    assert len(await archive.async_merge()) == 1000
    old = record(published_at=(NOW - timedelta(days=31)).isoformat())
    store = MemoryStore({"notices": [old, None, {"url": []}, record(2)]})
    assert len(await ReportArchive(store).async_merge()) == 1


@pytest.mark.parametrize("changes", [
    {"url": "https://example.org/123"}, {"title": ""},
    {"published_at": "2026-09-09T12:00:00"},
    {"published_at": "2026-08-01T12:00:00Z"},
    {"published_at": "2026-09-10T12:00:00Z"},
])
async def test_invalid_import_rejected(changes):
    store = MemoryStore()
    with pytest.raises(ValueError):
        await ReportArchive(store).async_import(record(**changes))
    store.async_save.assert_not_called()


async def test_saved_egyek_survives_restart_and_matches_reviewed_history():
    example = Path(__file__).parents[1] / "examples/egyek-report-import.yaml"
    saved = yaml.safe_load(example.read_text())["data"]
    store = MemoryStore()
    result = await ReportArchive(store).async_import(saved)
    assert result["changes_to_incidents"] is False
    notice, = await ReportArchive(store).async_merge([])  # missing from the live feed
    assert notice["archive_origin"] == "manual_import"
    assert notice["reported_start_date_hint"] == "2026-09-08"
    assert "BM OKF" in notice["publisher"]
    history = [
        {"track_id": "egyek-night-test", "latitude": 47.61131, "longitude": 21.00241,
         "first_seen": "2026-09-09T03:05:00+02:00", "last_seen": "2026-09-09T03:06:00+02:00"},
        {"track_id": "egyek-day-test", "latitude": 47.61845, "longitude": 20.98932,
         "first_seen": "2026-09-09T12:38:00+02:00", "last_seen": "2026-09-09T16:09:00+02:00"},
    ]
    original = deepcopy(history)
    kwargs = {"latitude": 47.61705258844659, "longitude": 21.002554893493656,
              "location_uncertainty_km": 5}
    published_only = review_notice(history, notice, **kwargs)
    assert len(published_only["candidates"]) == 1
    reviewed = review_notice(history, notice, **kwargs,
                             event_start="2026-09-08T00:00:00+02:00",
                             event_end="2026-09-09T14:21:00+02:00")
    assert [n["distance_km"] for n in reviewed["candidates"]] == [0.639, 1.004]
    assert all(n["relation"] == "possible" for n in reviewed["candidates"])
    assert reviewed["changes_applied"] is False
    assert history == original
