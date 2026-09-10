"""Separate bounded GDACS context store, using local retrieval time for retention."""

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json

from .gdacs_reports import parse_page
from .gdacs_geometry import validate_bounds

MAX_RECORDS = 1000
RETENTION = timedelta(days=30)


def clean_event(raw):
    """Revalidate stored normalized data with the same rules as network data."""
    props = {
        "eventtype": "WF", "eventid": raw["event_id"], "episodeid": raw["episode_id"],
        "name": raw["title"], "fromdate": raw["fromdate_raw"], "todate": raw["todate_raw"],
        "datemodified": raw["modified_raw"], "iscurrent": raw["is_current"],
        "istemporary": raw["is_temporary"], "source": raw["upstream_source"],
        "country": raw["country"], "alertlevel": raw["alert_level"],
    }
    page = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": props,
        "geometry": {"type": "Point", "coordinates": [raw["longitude"], raw["latitude"]]},
    }]}
    result = parse_page(json.dumps(page).encode())[0]
    bounds = raw.get("area_bounds")
    if bounds is not None:
        result["area_bounds"] = validate_bounds(bounds)
    return result


class GdacsArchive:
    """Inject an HA Store; no network and no BM OKF storage access here."""

    def __init__(self, store, *, clock=None):
        self._store = store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()
        self._records = None

    async def async_merge(self, events=()):
        """Only a complete validated fetch should supply events to this method."""
        async with self._lock:
            now = self._clock()
            if self._records is None:
                saved = await self._store.async_load()
                raw_records = saved.get("events", []) if isinstance(saved, dict) else []
                self._records = raw_records if isinstance(raw_records, list) else []
            records = {}
            for raw in self._records[:MAX_RECORDS]:
                try:
                    record = clean_event(raw)
                    first = datetime.fromisoformat(raw["first_retrieved_at"])
                    last = datetime.fromisoformat(raw["last_retrieved_at"])
                    if first.tzinfo is None or last.tzinfo is None or not first <= last <= now:
                        continue
                    if last <= now - RETENTION:
                        continue
                    record.update(first_retrieved_at=first.isoformat(), last_retrieved_at=last.isoformat())
                    records[record["uid"]] = record
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
            if len(events) > MAX_RECORDS:
                raise ValueError("Too many GDACS archive inputs")
            for raw in events:
                record = clean_event(raw)
                previous = records.get(record["uid"])
                # An older cached episode cannot replace a newer stored episode.
                if previous and record["episode_id"] < previous["episode_id"]:
                    continue
                record.update(
                    first_retrieved_at=previous["first_retrieved_at"] if previous else now.isoformat(),
                    last_retrieved_at=now.isoformat(),
                )
                records[record["uid"]] = record
            result = sorted(records.values(), key=lambda r: (r["last_retrieved_at"], r["uid"]), reverse=True)[:MAX_RECORDS]
            if result != self._records:
                await self._store.async_save({"events": result})
                self._records = result
            return deepcopy(result)
