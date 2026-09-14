"""On-demand QFD transport; deliberately not registered with Home Assistant yet."""
import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import monotonic

import aiohttp

from .models import ParsedReports
from .queensland import MAX_BYTES, parse_feed

FEED_URL = "https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json"
CACHE_SECONDS = 1800


@dataclass(frozen=True, slots=True)
class QfdSnapshot:
    """Transport success and record currency are independent."""
    parsed: ParsedReports | None = None
    status: str = "unavailable"
    last_checked: datetime | None = None
    last_success: datetime | None = None
    failure_code: str | None = None


def _validator(value):
    if isinstance(value, str) and 0 < len(value) <= 512 and not any(ord(c) < 32 or ord(c) == 127 for c in value):
        return value
    return None


def _status(parsed):
    return "partial" if (parsed.invalid_count or parsed.conflicted_ids or parsed.filtered_count) else "available"


class QfdClient:
    """One shared instance per future installation, serialized bounded requests."""

    def __init__(self, session, *, timer=monotonic, clock=None):
        self._session = session
        self._timer = timer
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._snapshot = QfdSnapshot()
        self._next_attempt = 0.0
        self._attempted = False
        self._failures = 0
        self._etag = self._modified = None

    async def async_get_reports(self):
        async with self._lock:
            if self._attempted and self._timer() < self._next_attempt:
                return self._snapshot
            retry_after = 0
            code = "network_error"
            try:
                async with asyncio.timeout(30):
                    headers = {"Accept": "application/geo+json, application/json"}
                    if self._etag:
                        headers["If-None-Match"] = self._etag
                    if self._modified:
                        headers["If-Modified-Since"] = self._modified
                    async with self._session.get(
                        FEED_URL, headers=headers, allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=25),
                    ) as response:
                        if response.status == 304:
                            code = "unexpected_not_modified"
                            if self._snapshot.parsed is None or not (self._etag or self._modified):
                                raise ValueError(code)
                            parsed = self._snapshot.parsed
                            etag = _validator(response.headers.get("ETag")) or self._etag
                            modified = _validator(response.headers.get("Last-Modified")) or self._modified
                        elif response.status == 200:
                            body = bytearray()
                            code = "response_too_large"
                            async for chunk in response.content.iter_chunked(65536):
                                body.extend(chunk)
                                if len(body) > MAX_BYTES:
                                    raise ValueError(code)
                            code = "invalid_response"
                            parsed = await asyncio.to_thread(
                                parse_feed, bytes(body), retrieved_at=self._clock()
                            )
                            etag = _validator(response.headers.get("ETag"))
                            modified = _validator(response.headers.get("Last-Modified"))
                        else:
                            code = "rate_limited" if response.status == 429 else "http_error"
                            value = response.headers.get("Retry-After", "")
                            if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 6:
                                retry_after = min(3600, int(value))
                            raise ValueError(code)
            except TimeoutError:
                code = "timeout"
                self._failed(code, retry_after)
            except (aiohttp.ClientError, OSError):
                self._failed("network_error", retry_after)
            except (ValueError, RecursionError):
                self._failed(code, retry_after)
            else:
                self._etag, self._modified = etag, modified
                self._failures = 0
                self._attempted = True
                self._next_attempt = self._timer() + CACHE_SECONDS
                now = self._clock()
                self._snapshot = QfdSnapshot(parsed, _status(parsed), now, now)
            return self._snapshot

    def _failed(self, code, retry_after):
        self._failures = min(4, self._failures + 1)
        delay = max(retry_after, min(1800, 300 * 2 ** (self._failures - 1)))
        self._next_attempt = self._timer() + delay
        self._attempted = True
        self._snapshot = replace(
            self._snapshot, status="stale" if self._snapshot.parsed is not None else "unavailable",
            last_checked=self._clock(), failure_code=code,
        )
