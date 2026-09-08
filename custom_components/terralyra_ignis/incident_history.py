"""Bounded local archive of detected fire incidents."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from .clustering import haversine_km
from .monitoring import MonitoredLocation

HISTORY_RETENTION = timedelta(days=30)
MAX_HISTORY_INCIDENTS = 500

_TEXT_FIELDS = (
    "place_name",
    "nearest_settlement",
    "location_description",
    "place_attribution",
    "confirmation_level",
    "source_url",
)
_NUMBER_FIELDS = (
    "maximum_frp_mw",
    "maximum_confidence",
    "maximum_pixel_count",
    "detections_total",
    "incident_extent_km",
)


def update_incident_history(
    history: list[dict[str, Any]],
    tracks: list[dict[str, Any]],
    locations: tuple[MonitoredLocation, ...],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Merge current tracks into a size- and age-bounded incident archive."""
    current = _as_utc(now)
    cutoff = current - HISTORY_RETENTION
    superseded_track_ids = {
        source_id
        for track in tracks
        for source_id in _source_track_ids(track)
        if source_id != str(track.get("track_id", ""))
    }
    merged: dict[str, dict[str, Any]] = {}
    for candidate in [*history, *tracks]:
        normalized = _normalize(candidate, locations)
        if normalized is None or _parse_dt(normalized["last_seen"]) < cutoff:
            continue
        track_id = normalized["track_id"]
        if track_id in superseded_track_ids:
            continue
        previous = merged.get(track_id)
        if previous is None or _parse_dt(normalized["last_seen"]) >= _parse_dt(
            previous["last_seen"]
        ):
            merged[track_id] = normalized
    return sorted(
        merged.values(),
        key=lambda item: (_parse_dt(item["last_seen"]), item["track_id"]),
        reverse=True,
    )[:MAX_HISTORY_INCIDENTS]


def _source_track_ids(incident: dict[str, Any]) -> tuple[str, ...]:
    values = incident.get("source_track_ids", [])
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip()[:128] for value in values if str(value).strip())


def _normalize(
    incident: dict[str, Any], locations: tuple[MonitoredLocation, ...]
) -> dict[str, Any] | None:
    try:
        track_id = str(incident["track_id"]).strip()[:128]
        latitude = float(incident["latitude"])
        longitude = float(incident["longitude"])
        first_seen = _parse_dt(incident["first_seen"])
        last_seen = _parse_dt(incident["last_seen"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not track_id
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
        or first_seen == datetime.min.replace(tzinfo=UTC)
        or last_seen < first_seen
    ):
        return None

    result: dict[str, Any] = {
        "track_id": track_id,
        "latitude": latitude,
        "longitude": longitude,
        "first_seen": first_seen.isoformat(),
        "last_seen": last_seen.isoformat(),
    }
    for field in _TEXT_FIELDS:
        value = incident.get(field)
        if isinstance(value, str) and value:
            result[field] = value[:512]
    for field in _NUMBER_FIELDS:
        try:
            value = float(incident.get(field, 0))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value >= 0:
            result[field] = (
                int(value)
                if field in {"maximum_pixel_count", "detections_total"}
                else value
            )
    for field in ("providers", "satellites"):
        values = incident.get(field, [])
        if isinstance(values, (list, tuple)):
            result[field] = [
                str(value)[:128] for value in values[:12] if str(value).strip()
            ]
    source_track_ids = _source_track_ids(incident)[:12]
    if source_track_ids:
        result["source_track_ids"] = list(source_track_ids)
        result["source_track_count"] = len(result["source_track_ids"])

    matches = []
    for location in locations:
        if not location.enabled:
            continue
        distance = haversine_km(
            location.latitude, location.longitude, latitude, longitude
        )
        if distance <= location.radius_km:
            matches.append(
                {
                    "id": location.id[:128],
                    "name": location.name[:128],
                    "distance_km": round(distance, 1),
                }
            )
    if not matches:
        return None
    result["locations"] = sorted(
        matches, key=lambda item: (item["distance_km"], item["id"])
    )
    return result


def _parse_dt(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
        return _as_utc(parsed)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=UTC)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
