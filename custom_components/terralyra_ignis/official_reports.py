"""Bounded, on-demand BM OKF RSS discovery; never a fire-detection source."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from time import monotonic

import aiohttp
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from .report_time import hungarian_start_hint

FEED_URL = "https://www.katasztrofavedelem.hu/10466/RSS_VESZ"
ATTRIBUTION = "BM Országos Katasztrófavédelmi Főigazgatóság (BM OKF)"
MAX_BYTES = 256_000
MAX_ITEMS = 100
CACHE_SECONDS = 300
MAX_DESCRIPTION_CHARS = 4000
NOTICE_URL = re.compile(
    r"https://www\.katasztrofavedelem\.hu/modules/vesz/esemeny/[0-9]+"
)


class ReportFeedError(Exception):
    """The feed could not be safely read; no user Repair is needed."""


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(value: str, limit: int = 500) -> str:
    parser = _PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())[:limit]


def parse_notices(payload: bytes) -> list[dict[str, str]]:
    """Keep attributed RSS text and review-only hints, never guessed coordinates."""
    if len(payload) > MAX_BYTES:
        raise ReportFeedError("Official report feed exceeds the size limit")
    try:
        root = ElementTree.fromstring(payload, forbid_dtd=True)
    except (ElementTree.ParseError, DefusedXmlException, ValueError, LookupError) as err:
        raise ReportFeedError("Invalid official report feed") from err
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise ReportFeedError("Unexpected official report feed format")
    notices: dict[str, dict[str, str]] = {}
    for item in channel.findall("item")[:MAX_ITEMS]:
        url = (item.findtext("link") or "").strip()
        title = _text(item.findtext("title") or "")
        if not NOTICE_URL.fullmatch(url) or not title:
            continue
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo is None:
                continue
            published_at = published.astimezone(UTC).isoformat()
        except (TypeError, ValueError, OverflowError):
            continue
        description = _text(item.findtext("description") or "", MAX_DESCRIPTION_CHARS + 1)
        truncated = len(description) > MAX_DESCRIPTION_CHARS
        notices[url] = {
            "title": title,
            "url": url,
            "publisher": ATTRIBUTION,
            "language": "hu",
            "published_at": published_at,
            "association": "not_matched",
            "description": description[:MAX_DESCRIPTION_CHARS],
            "description_status": "truncated" if truncated else "complete",
            **({"event_time_status": "unknown"} if truncated else hungarian_start_hint(description, published)),
        }
    return list(notices.values())


class OfficialReportClient:
    """Share a five-minute cache and failure cooldown across manual calls."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._lock = asyncio.Lock()
        self._next_attempt = 0.0
        self._notices: list[dict[str, str]] | None = None
        self._fetched_at: str | None = None
        self._failed = False

    async def async_get_notices(self) -> dict:
        async with self._lock:
            cached = monotonic() < self._next_attempt
            if not cached:
                try:
                    async with asyncio.timeout(20):
                        async with self._session.get(
                            FEED_URL, allow_redirects=False,
                            headers={"Accept": "application/rss+xml, application/xml, text/xml"},
                        ) as response:
                            if response.status != 200:
                                raise ReportFeedError("Official report feed unavailable")
                            payload = bytearray()
                            async for chunk in response.content.iter_chunked(16384):
                                payload.extend(chunk)
                                if len(payload) > MAX_BYTES:
                                    raise ReportFeedError("Official report feed exceeds the size limit")
                    self._notices = parse_notices(bytes(payload))
                    self._fetched_at = datetime.now(UTC).isoformat()
                    self._failed = False
                except (aiohttp.ClientError, TimeoutError, ReportFeedError):
                    self._failed = True
                self._next_attempt = monotonic() + CACHE_SECONDS
            return {
                "status": "unavailable" if self._failed else "available",
                "cached": cached,
                "fetched_at": self._fetched_at,
                "publisher": ATTRIBUTION,
                "feed_url": FEED_URL,
                "scope": "Current emergency notices, not a complete fire archive",
                "association": "not_matched_no_coordinates",
                # Never return an old successful response as current during failure.
                "notices": [] if self._failed else [dict(n) for n in self._notices or ()],
            }
