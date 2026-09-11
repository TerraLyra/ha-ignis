"""Bounded, restart-safe counts of distinct source observations."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from .models import FireDetection

VERSION = 1
WINDOW = timedelta(hours=6)
MAX_RECORDS = 20000


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Observation time must be timezone-aware")
    return parsed.astimezone(UTC)


def _stored_time(stored: dict[str, Any], key: str, fallback: datetime) -> datetime:
    try:
        return _time(stored[key])
    except (KeyError, TypeError, ValueError):
        return fallback


def update_counts(
    stored: dict[str, Any], detections: Iterable[FireDetection], *, now: datetime
) -> dict[str, Any]:
    """Keep unique acquisitions, never converting legacy aggregate counts."""
    now = now.astimezone(UTC)
    if stored.get("version") != VERSION:
        stored = {}
    try:
        now = max(now, _time(stored["updated_at"]))
    except (KeyError, TypeError, ValueError):
        pass
    cutoff = now - WINDOW
    records: dict[str, str] = {}
    raw_records = stored.get("records", [])
    if not isinstance(raw_records, list):
        raw_records = []
    for record in raw_records[:MAX_RECORDS]:
        try:
            key, raw_time = record
            acquired = _time(raw_time)
            if isinstance(key, str) and len(key) == 64 and cutoff < acquired <= now:
                records[key] = acquired.isoformat()
        except (TypeError, ValueError):
            continue
    for detection in detections:
        acquired = detection.timestamp.astimezone(UTC)
        if not cutoff < acquired <= now:
            continue
        identity = (
            detection.provider, detection.satellite, acquired.isoformat(),
            detection.source_detection_id or (
                round(detection.latitude, 5), round(detection.longitude, 5)
            ),
        )
        key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        records[key] = acquired.isoformat()
    truncated = len(records) > MAX_RECORDS
    # Keep newest acquisitions. Persist a conservative six-hour warning after
    # any eviction so repeated input cannot conceal an incomplete window.
    limited_until = _stored_time(stored, "limited_until", now)
    if truncated:
        limited_until = now + WINDOW
    return {
        "version": VERSION,
        "started_at": min(now, _stored_time(stored, "started_at", now)).isoformat(),
        "updated_at": now.isoformat(),
        "limited_until": limited_until.isoformat() if limited_until > now else None,
        "records": sorted(records.items(), key=lambda item: (item[1], item[0]))[-MAX_RECORDS:],
    }


def summarize_counts(stored: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    """Return counts and explicit collection/retention limitations."""
    clean = update_counts(stored, (), now=now)
    now = _time(clean["updated_at"])
    started = _time(clean["started_at"])
    limited = bool(clean["limited_until"] and _time(clean["limited_until"]) > now)
    return {
        "counts": {
            hours: sum(now - timedelta(hours=hours) < _time(time) <= now
                       for _, time in clean["records"])
            for hours in (1, 3, 6)
        },
        "counting_method": "unique_source_observations_by_acquisition_time",
        "collection_started_at": started.isoformat(),
        "retention_limited": limited,
        "window_collection_complete": {
            str(hours): not limited and now - started >= timedelta(hours=hours)
            for hours in (1, 3, 6)
        },
        "coverage_note": "collected_observations_not_complete_satellite_coverage",
    }
