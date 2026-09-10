"""HTTP failures and pagination never erase the GDACS context archive."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from unittest.mock import AsyncMock

import pytest

from custom_components.terralyra_ignis.gdacs_archive import GdacsArchive
from custom_components.terralyra_ignis.gdacs_client import GdacsClient
from custom_components.terralyra_ignis.gdacs_reports import MAX_BYTES, parse_page

NOW = datetime(2026, 9, 10, tzinfo=UTC)


def payload(ids=(1,), episode=1):
    return json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [21, 47]},
        "properties": {"eventtype": "WF", "eventid": i, "episodeid": episode,
            "name": "Synthetic test", "fromdate": "2026-09-01T00:00:00",
            "todate": "2026-09-02T00:00:00", "datemodified": "2026-09-10T00:00:00",
            "iscurrent": "false", "istemporary": "false"},
    } for i in ids]}).encode()


class Store:
    def __init__(self):
        self.saved = None
        self.async_save = AsyncMock(side_effect=self.save)

    async def async_load(self):
        return deepcopy(self.saved)

    async def save(self, data):
        self.saved = deepcopy(data)


class Response:
    def __init__(self, data=b"", status=200):
        self.data, self.status = data, status
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        for start in range(0, len(self.data), size):
            yield self.data[start:start + size]


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def setup(*responses):
    store, session = Store(), Session(*responses)
    archive = GdacsArchive(store, clock=lambda: NOW)
    tick = [1.0]
    client = GdacsClient(session, archive, clock=lambda: NOW, timer=lambda: tick[0])
    return client, session, archive, store, tick


async def test_concurrent_requests_share_cache_and_cannot_mutate_it():
    client, session, archive, store, tick = setup(Response(payload()))
    first, second = await asyncio.gather(client.async_get_events(), client.async_get_events())
    assert len(session.calls) == 1 and first == second
    assert first["status"] == "available"
    first["events"][0]["title"] = "mutated"
    assert (await client.async_get_events())["events"][0]["title"] == "Synthetic test"
    assert session.calls[0][1]["allow_redirects"] is False
    assert session.calls[0][1]["params"]["pageNumber"] == 1


async def test_later_page_failure_is_atomic_and_backed_off():
    client, session, archive, store, tick = setup(Response(payload(range(2, 102))), Response(status=500))
    await archive.async_merge(parse_page(payload()))
    before = deepcopy(store.saved)
    result = await client.async_get_events()
    assert result["status"] == "stale" and not result["fetch_complete"]
    assert [e["event_id"] for e in result["events"]] == [1]
    assert store.saved == before
    await client.async_get_events()
    assert len(session.calls) == 2


async def test_pagination_and_terminal_204():
    client, session, archive, store, tick = setup(Response(payload(range(1, 101))), Response(status=204))
    result = await client.async_get_events()
    assert result["fetch_complete"] and len(result["events"]) == 100
    assert session.calls[1][1]["params"]["pageNumber"] == 2


async def test_empty_success_preserves_archive():
    client, session, archive, store, tick = setup(Response(status=204))
    await archive.async_merge(parse_page(payload()))
    result = await client.async_get_events()
    assert result["status"] == "available" and result["fetched_count"] == 0
    assert len(result["events"]) == 1


@pytest.mark.parametrize("response", [Response(b"broken"), Response(b"x" * (MAX_BYTES + 1)), Response(status=302)])
async def test_invalid_responses_not_cached_as_available(response):
    client, *_ = setup(response)
    result = await client.async_get_events()
    assert result["status"] == "unavailable" and not result["fetch_complete"]


async def test_repeating_pages_and_page_limit_are_incomplete():
    client, *_ = setup(Response(payload(range(1, 101))), Response(payload(range(1, 101))))
    assert (await client.async_get_events())["status"] == "unavailable"
    client, *_ = setup(*(Response(payload(range(p * 100 + 1, p * 100 + 101))) for p in range(5)))
    assert not (await client.async_get_events())["fetch_complete"]


async def test_failure_then_recovery():
    client, session, archive, store, tick = setup(Response(status=503), Response(payload()))
    assert (await client.async_get_events())["status"] == "unavailable"
    tick[0] += 301
    assert (await client.async_get_events())["status"] == "available"
    assert len(session.calls) == 2


async def test_archive_restart_revision_retention_and_safe_reload():
    store = Store()
    moment = [NOW]
    archive = GdacsArchive(store, clock=lambda: moment[0])
    await archive.async_merge(parse_page(payload(episode=2)))
    await archive.async_merge(parse_page(payload(episode=1)))
    assert (await archive.async_merge())[0]["episode_id"] == 2
    store.saved["events"][0]["url"] = "http://localhost/private"
    restored = GdacsArchive(store, clock=lambda: moment[0])
    assert (await restored.async_merge())[0]["url"].startswith("https://www.gdacs.org/")
    moment[0] += timedelta(days=30)
    assert await restored.async_merge() == []


async def test_failed_store_write_does_not_commit_memory():
    store = Store()
    archive = GdacsArchive(store, clock=lambda: NOW)
    store.async_save.side_effect = OSError("disk full")
    with pytest.raises(OSError):
        await archive.async_merge(parse_page(payload()))
    store.async_save.side_effect = store.save
    assert await archive.async_merge() == []


async def test_optional_geometry_survives_archive_restart():
    geometry = json.dumps({"type": "FeatureCollection", "features": [{
        "properties": {"eventtype": "WF", "eventid": 1, "episodeid": 1, "Class": "Poly_area"},
        "geometry": {"type": "Polygon", "coordinates": [[[20, 46], [22, 46], [22, 48], [20, 46]]]},
    }]}).encode()
    store = Store()
    archive = GdacsArchive(store, clock=lambda: NOW)
    session = Session(Response(payload()), Response(geometry))
    client = GdacsClient(session, archive, clock=lambda: NOW, fetch_geometry=True)
    result = await client.async_get_events()
    assert result["events"][0]["area_bounds"] == [20, 46, 22, 48]
    assert (await GdacsArchive(store, clock=lambda: NOW).async_merge())[0]["area_bounds"] == [20, 46, 22, 48]
    assert session.calls[1][1]["params"] == {"eventtype": "WF", "eventid": 1, "episodeid": 1}


async def test_geometry_failure_keeps_event_but_not_invented_area():
    store = Store()
    client = GdacsClient(Session(Response(payload()), Response(status=500)), GdacsArchive(store, clock=lambda: NOW),
                         clock=lambda: NOW, fetch_geometry=True)
    result = await client.async_get_events()
    assert result["status"] == "available"
    assert "area_bounds" not in result["events"][0]
