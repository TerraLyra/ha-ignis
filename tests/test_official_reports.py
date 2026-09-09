"""RSS discovery never invents satellite associations or fire classifications."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.terralyra_ignis.official_reports import (
    ATTRIBUTION,
    FEED_URL,
    MAX_BYTES,
    OfficialReportClient,
    ReportFeedError,
    parse_notices,
)

ITEM = """<item><title>Karambol a tesztúton</title>
<link>https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123</link>
<pubDate>Wed, 09 Sep 2026 11:13:00 +0200</pubDate></item>"""


def feed(items=ITEM):
    return f"<rss><channel>{items}</channel></rss>".encode()


def test_metadata_attribution_and_no_false_fire_classification():
    notice, = parse_notices(feed())
    assert notice["publisher"] == ATTRIBUTION
    assert notice["published_at"] == "2026-09-09T09:13:00+00:00"
    assert notice["association"] == "not_matched"
    assert "latitude" not in notice
    assert "description" not in notice
    assert parse_notices(feed(ITEM * 2)) == [notice]
    assert parse_notices(feed("")) == []


@pytest.mark.parametrize("payload", [
    b"<html/>", b"<rss>", b"x" * (MAX_BYTES + 1),
    b'<!DOCTYPE rss [<!ENTITY a "unsafe">]><rss><channel/></rss>',
])
def test_invalid_or_unsafe_payload(payload):
    with pytest.raises(ReportFeedError):
        parse_notices(payload)


@pytest.mark.parametrize("old,new", [
    ("https://www.katasztrofavedelem.hu", "https://example.org"),
    ("/123</link>", "/123?redirect=elsewhere</link>"),
    ("Wed, 09 Sep 2026 11:13:00 +0200", "invalid"),
    ("Wed, 09 Sep 2026 11:13:00 +0200", "Wed, 09 Sep 2026 11:13:00"),
    ("Karambol a tesztúton", ""),
])
def test_incomplete_or_untrusted_items_skipped(old, new):
    assert parse_notices(feed(ITEM.replace(old, new))) == []


def test_title_is_plain_text():
    notice, = parse_notices(feed(ITEM.replace(
        "Karambol a tesztúton", "&lt;b&gt;Teszt&lt;/b&gt; &amp; hír"
    )))
    assert notice["title"] == "Teszt & hír"


class Response:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = feed() if payload is None else payload
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def iter_chunked(self, size):
        for index in range(0, len(self.payload), size):
            yield self.payload[index:index + size]


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


@pytest.mark.asyncio
async def test_concurrent_requests_share_cache_and_fixed_destination():
    session = Session(Response())
    client = OfficialReportClient(session)
    first, second = await asyncio.gather(
        client.async_get_notices(), client.async_get_notices()
    )
    assert first["status"] == "available"
    assert not first["cached"] and second["cached"]
    assert len(session.calls) == 1
    assert session.calls[0][0] == FEED_URL
    assert session.calls[0][1]["allow_redirects"] is False
    first["notices"][0]["title"] = "mutated"
    assert (await client.async_get_notices())["notices"][0]["title"] != "mutated"


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [Response(302), Response(429), Response(500),
    Response(payload=b"x" * (MAX_BYTES + 1)), Response(payload=b"<html/>")])
async def test_failures_are_cooled_down_without_repairs(response):
    session = Session(response)
    client = OfficialReportClient(session)
    assert (await client.async_get_notices())["status"] == "unavailable"
    assert (await client.async_get_notices())["notices"] == []
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_refresh_failure_does_not_present_old_notices_as_current():
    session = Session(Response())
    client = OfficialReportClient(session)
    with patch("custom_components.terralyra_ignis.official_reports.monotonic", return_value=1):
        assert (await client.async_get_notices())["notices"]
    session.response = Response(503)
    with patch("custom_components.terralyra_ignis.official_reports.monotonic", return_value=302):
        result = await client.async_get_notices()
    assert result["status"] == "unavailable"
    assert result["notices"] == []


@pytest.mark.asyncio
async def test_action_returns_attributed_response(hass):
    from custom_components.terralyra_ignis import async_setup

    response = {"status": "available", "notices": parse_notices(feed())}
    with patch(
        "custom_components.terralyra_ignis.OfficialReportClient.async_get_notices",
        new=AsyncMock(return_value=response),
    ):
        await async_setup(hass, {})
        result = await hass.services.async_call(
            "terralyra_ignis", "get_official_reports", {},
            blocking=True, return_response=True,
        )
    assert result == response
