"""Shared on-demand GDACS HTTP cache; not registered with HA platforms yet."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from time import monotonic

import aiohttp

from .gdacs_reports import GdacsDataError, MAX_BYTES, MAX_ITEMS, parse_page
from .gdacs_geometry import area_bounds

SEARCH_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/search"
CACHE_SECONDS = 3600
RETRY_SECONDS = 300
MAX_PAGES = 5


class GdacsClient:
    """One instance per HA installation, shared by future location calendars."""

    def __init__(self, session, archive, *, clock=None, timer=None, fetch_geometry=False):
        self._session = session
        self._archive = archive
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timer = timer or monotonic
        self._lock = asyncio.Lock()
        self._next_attempt = 0.0
        self._result = None
        self._failures = 0
        self._last_success = None
        self._fetch_geometry = fetch_geometry

    async def async_get_events(self):
        async with self._lock:
            if self._result is not None and self._timer() < self._next_attempt:
                return deepcopy(self._result)
            now = self._clock()
            try:
                async with asyncio.timeout(60):
                    events = await self._fetch(now)
                if self._fetch_geometry:
                    await self._enrich_geometry(events)
                archived = await self._archive.async_merge(events)
            except (aiohttp.ClientError, TimeoutError, GdacsDataError, OSError, ValueError):
                self._failures += 1
                delay = min(CACHE_SECONDS, RETRY_SECONDS * 2 ** min(self._failures - 1, 4))
                self._next_attempt = self._timer() + delay
                # Do not merge a partial page set or destroy earlier observations.
                archived = await self._archive.async_merge()
                self._result = {
                    "status": "stale" if archived else "unavailable", "events": archived,
                    "fetch_complete": False, "last_success": self._last_success,
                }
            else:
                self._last_success = now.isoformat()
                self._failures = 0
                self._next_attempt = self._timer() + CACHE_SECONDS
                self._result = {
                    "status": "available", "events": archived,
                    "fetch_complete": True, "last_success": self._last_success,
                    "fetched_count": len(events),
                }
            return deepcopy(self._result)

    async def _enrich_geometry(self, events):
        # Geometry is optional context. Bound global workload, not one call per location.
        try:
            async with asyncio.timeout(30):
                for event in events[:10]:
                    try:
                        async with self._session.get(
                            "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry",
                            params={"eventtype": "WF", "eventid": event["event_id"], "episodeid": event["episode_id"]},
                            allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10),
                            headers={"Accept": "application/json"},
                        ) as response:
                            if response.status != 200:
                                continue
                            body = bytearray()
                            async for chunk in response.content.iter_chunked(65536):
                                body.extend(chunk)
                                if len(body) > MAX_BYTES:
                                    raise GdacsDataError("Geometry too large")
                            bounds = area_bounds(bytes(body), event["event_id"], event["episode_id"])
                            if bounds is not None:
                                event["area_bounds"] = bounds
                    except (aiohttp.ClientError, TimeoutError, GdacsDataError):
                        continue
        except TimeoutError:
            pass  # Missing geometry is explicitly unknown, never an exclusion proof.

    async def _fetch(self, now):
        records = {}
        for page in range(1, MAX_PAGES + 1):
            params = {
                "eventlist": "WF", "fromDate": (now - timedelta(days=30)).date().isoformat(),
                "toDate": now.date().isoformat(), "pageSize": MAX_ITEMS, "pageNumber": page,
            }
            async with self._session.get(
                SEARCH_URL, params=params, allow_redirects=False,
                headers={"Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status not in (200, 204):
                    raise GdacsDataError("GDACS HTTP failure")
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise GdacsDataError("GDACS response too large")
                events = parse_page(bytes(body), response.status)
            new_ids = 0
            for event in events:
                old = records.get(event["uid"])
                new_ids += old is None
                if old is None or event["episode_id"] > old["episode_id"]:
                    records[event["uid"]] = event
            if events and not new_ids:
                raise GdacsDataError("GDACS pagination repeated a page")
            if len(events) < MAX_ITEMS:
                return list(records.values())
        raise GdacsDataError("GDACS page limit reached; incomplete result")
