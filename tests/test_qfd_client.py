"""QFD transport recovery, cache and time semantics without live networking."""
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.terralyra_ignis.official_sources.qld_client import QfdClient, CACHE_SECONDS
from custom_components.terralyra_ignis.official_sources import qld_client
from custom_components.terralyra_ignis.official_sources.temporal import assess_report_time

NOW = datetime(2026, 9, 14, 20, tzinfo=UTC)


def body():
    return json.dumps({"type":"FeatureCollection", "features":[{"type":"Feature",
        "geometry":{"type":"Point","coordinates":[150,-25]},
        "properties":{"UniqueID":"QF-TEST", "EventType":"Fire", "GroupedType":"FIRE VEGETATION",
            "WarningLevel":"Information", "WarningTitle":"Synthetic test",
            "ItemDateTimeLocal_ISO":"2026-08-01T00:00:00+10:00",
            "ItemExpiryDateTimeLocal_ISO":"2026-08-02T00:00:00+10:00",
            "PublishDateLocal_ISO":"2026-09-15T05:00:00+10:00"}}]}).encode()


class Response:
    def __init__(self, status=200, data=None, headers=None, error=None):
        self.status, self.headers = status, headers or {}
        self.data, self.error = body() if data is None else data, error
        self.content = self

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        for start in range(0, len(self.data), size):
            yield self.data[start:start+size]


def setup(*responses):
    state = SimpleNamespace(tick=0, now=NOW)
    session = SimpleNamespace(get=Mock(side_effect=responses))
    client = QfdClient(session, timer=lambda:state.tick, clock=lambda:state.now)
    return client, session, state


async def test_shared_cache_and_conditional_304_preserve_record_receipt_and_expiry():
    client, session, state = setup(Response(headers={"ETag":'"v1"', "Last-Modified":"Mon, 14 Sep 2026 19:00:00 GMT"}), Response(304))
    first, second = await asyncio.gather(client.async_get_reports(), client.async_get_reports())
    assert first == second
    assert session.get.call_count == 1
    state.tick = CACHE_SECONDS
    state.now += timedelta(minutes=30)
    fresh = await client.async_get_reports()
    assert fresh.status == "available"
    assert fresh.last_success == state.now
    assert fresh.parsed is first.parsed
    assert fresh.parsed.records[0].retrieved_at == NOW
    assert assess_report_time(fresh.parsed.records[0], now=state.now).source_expiry == "elapsed"
    kwargs = session.get.call_args.kwargs
    assert kwargs['headers']['If-None-Match'] == '"v1"'
    assert kwargs['allow_redirects'] is False
    assert kwargs['timeout'].total == 25


async def test_outage_retains_snapshot_backoff_and_empty_recovery():
    empty = b'{"type":"FeatureCollection","features":[]}'
    client, session, state = setup(Response(), Response(503), Response(data=empty))
    original = await client.async_get_reports()
    state.tick = 1800
    stale = await client.async_get_reports()
    assert stale.status == "stale" and stale.parsed is original.parsed
    assert stale.last_success == original.last_success
    await client.async_get_reports()
    assert session.get.call_count == 2
    state.tick = 2100
    recovered = await client.async_get_reports()
    assert recovered.status == "available" and recovered.parsed.records == ()
    assert recovered.failure_code is None


@pytest.mark.parametrize('response,code', [(Response(302),'http_error'), (Response(304),'unexpected_not_modified'),
    (Response(data=b'not json'),'invalid_response'), (Response(error=TimeoutError()),'timeout')])
async def test_first_failure_unavailable_and_safe_code(response, code):
    client, session, state = setup(response)
    snapshot = await client.async_get_reports()
    assert snapshot.status == 'unavailable' and snapshot.parsed is None
    assert snapshot.failure_code == code
    assert snapshot.last_success is None
    assert await client.async_get_reports() == snapshot
    assert session.get.call_count == 1


async def test_size_limit_and_bounded_retry(monkeypatch):
    monkeypatch.setattr(qld_client, 'MAX_BYTES', 10)
    client, session, state = setup(Response(), Response(429, headers={'Retry-After':'3600'}))
    assert (await client.async_get_reports()).failure_code == 'response_too_large'
    state.tick = 300
    assert (await client.async_get_reports()).failure_code == 'rate_limited'
    state.tick = 3899
    await client.async_get_reports()
    assert session.get.call_count == 2


async def test_long_failure_sequence_saturates_and_bad_validators_are_ignored():
    client, session, state = setup(*([Response(500)] * 50), Response(headers={'ETag':'bad\r\nheader'}), Response(304))
    for _ in range(50):
        assert (await client.async_get_reports()).status == 'unavailable'
        state.tick += 1800
    assert (await client.async_get_reports()).status == 'available'
    state.tick += 1800
    assert (await client.async_get_reports()).failure_code == 'unexpected_not_modified'
    assert 'If-None-Match' not in session.get.call_args.kwargs['headers']


async def test_cancellation_propagates_and_does_not_poison_next_request():
    client, session, state = setup(Response(error=asyncio.CancelledError()), Response())
    with pytest.raises(asyncio.CancelledError):
        await client.async_get_reports()
    assert (await client.async_get_reports()).status == 'available'


async def test_partial_snapshot_survives_304():
    doc = json.loads(body())
    doc['features'].append({})
    client, session, state = setup(Response(data=json.dumps(doc).encode(), headers={'ETag':'"v"'}), Response(304))
    first = await client.async_get_reports()
    assert first.status == 'partial' and first.parsed.invalid_count == 1
    state.tick = 1800
    assert (await client.async_get_reports()).status == 'partial'


async def test_temporal_assessment_does_not_invent_lifecycle():
    client, _, _ = setup(Response())
    record = (await client.async_get_reports()).parsed.records[0]
    assert assess_report_time(record, now=NOW).source_expiry == 'elapsed'
    uncertain = replace(record, event_updated_at=None, expires_at=None, published_at=None)
    report = assess_report_time(uncertain, now=NOW)
    assert report.source_expiry == report.event_time == report.publication_time == 'unknown'
    future = replace(record, event_updated_at=NOW+timedelta(hours=2),
                     expires_at=NOW+timedelta(hours=1), published_at=NOW+timedelta(hours=2))
    report = assess_report_time(future, now=NOW)
    assert report.inconsistent_interval
    assert report.event_time == report.publication_time == 'future'
    with pytest.raises(ValueError):
        assess_report_time(record, now=NOW.replace(tzinfo=None))
