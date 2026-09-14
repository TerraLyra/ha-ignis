"""Bounded, on-demand NSW RFS current fire reports, independent of detections."""

import asyncio
from copy import deepcopy
from datetime import UTC, date, datetime
from html import unescape
import json
import math
import re
from time import monotonic

import aiohttp

FEED_URL = "https://www.rfs.nsw.gov.au/feeds/majorIncidents.json"
PUBLIC_URL = "https://www.rfs.nsw.gov.au/fire-information/fires-near-me"
ATTRIBUTION = (
    "© State of New South Wales (NSW Rural Fire Service). "
    "For current information go to www.rfs.nsw.gov.au."
)
MAX_BYTES = 8 * 1024 * 1024
MAX_ITEMS = 2000
CACHE_SECONDS = 1800
# Explicit upstream types: a fire alarm or smoke report is not a confirmed fire.
FIRE_TYPES = frozenset({
    "bush fire", "grass fire", "structure fire", "haystack fire",
    "vehicle/equipment fire", "car fire", "vehicle fire",
})
MONTHS = {name: index for index, name in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1
)}


def _text(value, limit=1000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("Invalid NSW RFS text field")
    # Render upstream markup only as text, never as active HTML.
    return " ".join(re.sub(r"<[^>]*>", "", unescape(value)).split())


def _point(geometry):
    """Use the supplied incident point, never a polygon corner or LGA guess."""
    if not isinstance(geometry, dict):
        return None
    if geometry.get("type") == "GeometryCollection":
        geometries = geometry.get("geometries")
        if not isinstance(geometries, list):
            return None
        points = [item for item in geometries if isinstance(item, dict) and item.get("type") == "Point"]
        return _point(points[0]) if len(points) == 1 else None
    if geometry.get("type") != "Point":
        return None
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 2:
        return None
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in coordinates):
        return None
    lon, lat = coordinates
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def parse_feed(body):
    """Normalize the official GeoJSON shape; expose omissions, not false matches."""
    if len(body) > MAX_BYTES:
        raise ValueError("NSW RFS response too large")
    document = json.loads(body)
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("Invalid NSW RFS collection")
    features = document.get("features")
    if not isinstance(features, list) or len(features) > MAX_ITEMS:
        raise ValueError("Invalid NSW RFS feature count")
    events = {}
    counts = {"filtered_records": 0, "unmapped_records": 0, "invalid_records": 0}
    for feature in features:
        try:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise ValueError("Invalid feature")
            props = feature.get("properties")
            if not isinstance(props, dict):
                raise ValueError("Invalid properties")
            raw = props.get("description")
            if not isinstance(raw, str) or len(raw) > 16000:
                raise ValueError("Invalid description")
            fields = {}
            for line in re.split(r"<br\s*/?>", raw, flags=re.I):
                key, separator, value = _text(line, 16000).partition(":")
                if separator:
                    if key.strip().upper() in fields:
                        raise ValueError("Duplicate description field")
                    fields[key.strip().upper()] = value.strip()
            kind = fields.get("TYPE", "")
            if not kind or "FIRE" not in fields:
                raise ValueError("Missing classification")
            category = _text(props.get("category", ""))
            if (kind.casefold() not in FIRE_TYPES or fields["FIRE"].casefold() != "yes"
                    or category.casefold() == "planned burn"
                    or fields.get("ALERT LEVEL", "").casefold() == "planned burn"):
                counts["filtered_records"] += 1
                continue
            title = _text(props.get("title"))
            guid = props.get("guid")
            match = re.fullmatch(r"https://incidents\.rfs\.nsw\.gov\.au/api/v1/incidents/(\d{1,20})", guid or "")
            if not title or not match:
                raise ValueError("Missing incident identity")
            point = _point(feature.get("geometry"))
            if "unmapped incident" in title.casefold() or point is None:
                counts["unmapped_records"] += 1
                continue
            # UPDATED is the publisher's human-readable local date. Do not guess
            # the timezone of the offset-free pubDate or invent an ignition time.
            stamp = fields.get("UPDATED", "")
            day, month, year, clock = stamp.split()
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
                raise ValueError("Invalid update time")
            update_date = date(int(year), MONTHS[month], int(day)).isoformat()
            if not 2000 <= int(year) <= 9998:
                raise ValueError("Invalid update year")
            uid = f"nsw_rfs:{match[1]}"
            event = {"uid": uid, "title": title, "latitude": point[0], "longitude": point[1],
                     "date": update_date, "update_order": f"{update_date}T{clock}",
                     "updated_raw": stamp, "type": kind, "alert_level": category,
                     "status": fields.get("STATUS", "Unknown"),
                     "location": fields.get("LOCATION", ""), "size": fields.get("SIZE", ""),
                     "agency": fields.get("RESPONSIBLE AGENCY", "NSW RFS")}
            if uid not in events or event["update_order"] > events[uid]["update_order"]:
                events[uid] = event
        except (ValueError, TypeError, KeyError, AttributeError):
            counts["invalid_records"] += 1
    if features and counts["invalid_records"] == len(features):
        raise ValueError("No readable NSW RFS records")
    return {"events": sorted(events.values(), key=lambda event: event["uid"]),
            "fetched_count": len(features), **counts}


class NswRfsClient:
    """One shared fetch per installation, only while a calendar is enabled/used.

    This is a current-feed snapshot, not an archive. Failure retains the previous
    in-memory snapshot and marks it stale; a successful empty feed replaces it.
    """

    def __init__(self, session, *, timer=None, clock=None):
        self._session = session
        self._timer = timer or monotonic
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._result = None
        self._next_attempt = 0.0
        self._failures = 0

    async def async_get_events(self):
        async with self._lock:
            if self._result is not None and self._timer() < self._next_attempt:
                return deepcopy(self._result)
            try:
                async with self._session.get(
                    FEED_URL, allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=25),
                    headers={"Accept": "application/geo+json, application/json"},
                ) as response:
                    if response.status != 200:
                        raise ValueError("NSW RFS HTTP failure")
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise ValueError("NSW RFS response too large")
                result = await asyncio.to_thread(parse_feed, bytes(body))
            except (aiohttp.ClientError, TimeoutError, ValueError, OSError, RecursionError):
                self._failures += 1
                self._next_attempt = self._timer() + min(1800, 300 * 2 ** min(self._failures - 1, 3))
                self._result = {**(self._result or {"events": [], "last_success": None}),
                                "status": "stale" if self._result and self._result.get("last_success") else "unavailable"}
            else:
                self._failures = 0
                self._next_attempt = self._timer() + CACHE_SECONDS
                self._result = {**result, "status": "partial" if result["invalid_records"] else "available",
                                "last_success": self._clock().isoformat()}
            return deepcopy(self._result)
