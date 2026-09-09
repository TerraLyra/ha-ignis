"""Local report association; never modifies satellite evidence or incidents.

Adapters must supply reviewed coordinates and provenance. Publication time is
not an event time, and a matching report does not prove a satellite detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from .clustering import haversine_km

MAX_REPORTS = 100
MAX_INCIDENTS = 500
MATCH_WINDOW = timedelta(hours=6)
MAX_DISTANCE_KM = 8.0


def _url(value: str) -> str:
    parts = urlsplit(value)
    if (
        len(value) > 2048 or parts.scheme != "https" or not parts.hostname
        or parts.username is not None or parts.password is not None
        or any(char.isspace() for char in value)
    ):
        raise ValueError("Report links must be credential-free HTTPS URLs")
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, parts.query, ""))


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Report matching requires timezone-aware timestamps")


def _position(latitude: float, longitude: float) -> None:
    if not (
        math.isfinite(latitude) and math.isfinite(longitude)
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    ):
        raise ValueError("Invalid report or incident coordinates")


@dataclass(frozen=True, slots=True)
class FireReport:
    """One fire-specific report, with uncertainty supplied by its adapter.

    origin_url identifies the original notice when an article republishes it.
    Coordinates must describe the reported site, not the publisher or a broad
    region. location_uncertainty_km records the precision of that attribution.
    """

    url: str
    publisher: str
    published_at: datetime
    language: str
    latitude: float
    longitude: float
    location_uncertainty_km: float
    source_kind: str = "news"
    event_start: datetime | None = None
    event_end: datetime | None = None
    origin_url: str | None = None

    def __post_init__(self) -> None:
        _url(self.url)
        if self.origin_url is not None:
            _url(self.origin_url)
        _time(self.published_at)
        _position(self.latitude, self.longitude)
        if self.source_kind not in ("official", "news"):
            raise ValueError("Unknown report source kind")
        if not self.publisher.strip() or not self.language.strip():
            raise ValueError("Report publisher and language are required")
        if not math.isfinite(self.location_uncertainty_km) or not 0 <= self.location_uncertainty_km <= 25:
            raise ValueError("Report location is too imprecise")
        if self.event_end is not None and self.event_start is None:
            raise ValueError("Event end requires an event start")
        if self.event_start is not None:
            _time(self.event_start)
            _time(self.event_end or self.event_start)
            if (self.event_end or self.event_start) < self.event_start:
                raise ValueError("Invalid report event interval")


@dataclass(frozen=True, slots=True)
class IncidentContext:
    """Read-only view of an existing satellite incident."""

    incident_id: str
    latitude: float
    longitude: float
    first_seen: datetime
    last_seen: datetime

    def __post_init__(self) -> None:
        _position(self.latitude, self.longitude)
        _time(self.first_seen)
        _time(self.last_seen)
        if not self.incident_id or self.last_seen < self.first_seen:
            raise ValueError("Invalid incident identity or interval")


@dataclass(frozen=True, slots=True)
class ReportMatch:
    """One report family associated with an incident, not a confirmation."""

    incident_id: str
    origin_url: str
    reports: tuple[FireReport, ...]
    relation: str
    reasons: tuple[str, ...]
    distance_km: float


def match_reports(
    incidents: tuple[IncidentContext, ...], reports: tuple[FireReport, ...],
) -> tuple[ReportMatch, ...]:
    """Associate bounded input without network access or evidence upgrades.

    Multiple candidate incidents, imprecise locations, or publication-only
    dates always produce a possible relationship. Syndicated reports share
    one result per incident and retain their individual publisher metadata.
    """
    if len(incidents) > MAX_INCIDENTS or len(reports) > MAX_REPORTS:
        raise ValueError("Report matching input exceeds its processing limit")
    if len({item.incident_id for item in incidents}) != len(incidents):
        raise ValueError("Incident IDs must be unique")
    grouped: dict[tuple[str, str], list[tuple[FireReport, float, tuple[str, ...]]]] = {}
    for report in reports:
        start = report.event_start or report.published_at
        end = report.event_end or start
        candidates = []
        for incident in incidents:
            if start > incident.last_seen + MATCH_WINDOW or end < incident.first_seen - MATCH_WINDOW:
                continue
            distance = haversine_km(incident.latitude, incident.longitude, report.latitude, report.longitude)
            if distance > MAX_DISTANCE_KM:
                continue
            candidates.append((incident, distance))
        for incident, distance in candidates:
            reasons = ["nearby_location", "compatible_time"]
            if report.event_start is None:
                reasons.append("publication_time_only")
            if end - start > MATCH_WINDOW:
                reasons.append("imprecise_event_time")
            if report.location_uncertainty_km > 1 or distance > 3:
                reasons.append("imprecise_location_match")
            if len(candidates) > 1:
                reasons.append("multiple_candidate_incidents")
            key = (incident.incident_id, _url(report.origin_url or report.url))
            grouped.setdefault(key, []).append((report, distance, tuple(reasons)))

    results = []
    for (incident_id, origin), members in sorted(grouped.items()):
        reasons = tuple(sorted({reason for _, _, items in members for reason in items}))
        unique_reports = {_url(report.url): report for report, _, _ in members}
        results.append(ReportMatch(
            incident_id, origin,
            tuple(unique_reports[url] for url in sorted(unique_reports)),
            "probable" if len(reasons) == 2 else "possible",
            reasons, min(distance for _, distance, _ in members),
        ))
    return tuple(results)
