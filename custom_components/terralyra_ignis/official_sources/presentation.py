"""Pure location/time projection; no HA entities, alerts or persisted mutations."""
from dataclasses import dataclass
from datetime import datetime
import math

from ..clustering import haversine_km
from .geometry import check_area, circle_relation
from ..monitoring import MonitoredLocation
from .models import GeometryRole, OfficialReport
from .qld_client import QfdSnapshot
from .temporal import ReportTimeAssessment, assess_report_time


@dataclass(frozen=True, slots=True)
class ReportLocation:
    location_id: str
    location_name: str
    relation: str
    distance_km: float | None = None


@dataclass(frozen=True, slots=True)
class PresentedReport:
    report: OfficialReport
    locations: tuple[ReportLocation, ...]
    time: ReportTimeAssessment
    time_category: str
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportPresentation:
    feed_status: str
    relevant: tuple[PresentedReport, ...]
    unresolved: tuple[PresentedReport, ...]
    outside_count: int
    input_count: int
    filtered_count: int
    invalid_count: int
    conflicted_ids: int


def _validate_locations(locations):
    enabled = tuple(location for location in locations if location.enabled)
    if len({loc.id for loc in enabled}) != len(enabled):
        raise ValueError("Duplicate enabled location identity")
    for loc in enabled:
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in (loc.latitude, loc.longitude, loc.radius_km)):
            raise ValueError("Invalid monitoring coordinates")
        if not (-90 <= loc.latitude <= 90 and -180 <= loc.longitude <= 180 and 0 <= loc.radius_km <= 20000):
            raise ValueError("Monitoring coordinates out of range")
    return enabled


def _relations(report, locations):
    if report.geometry.role == GeometryRole.INCIDENT_POINT:
        lon, lat = report.geometry.coordinates[:2]
        matches = []
        for loc in locations:
            distance = haversine_km(loc.latitude, loc.longitude, lat, lon)
            if distance <= loc.radius_km:
                matches.append(ReportLocation(loc.id, loc.name, "source_point_in_radius", distance))
        return tuple(matches)
    if report.geometry.role == GeometryRole.WARNING_AREA:
        area = check_area(report.geometry.coordinates)
        relations = []
        for loc in locations:
            relation = circle_relation(area, loc.latitude, loc.longitude, loc.radius_km)
            if relation != "outside":
                relations.append(ReportLocation(loc.id, loc.name,
                    "warning_area_intersects" if relation == "intersects" else "geometry_unknown"))
        return tuple(relations)
    return tuple(ReportLocation(loc.id, loc.name, "geometry_unknown") for loc in locations)


def project_reports(snapshot: QfdSnapshot, locations: tuple[MonitoredLocation, ...],
                    *, now: datetime) -> ReportPresentation:
    """Deduplicate by source identity upstream; preserve every location per record.

    Relevant contains source-point matches and validated warning-area intersections.
    Unsupported or numerically ambiguous geometries remain unresolved.
    Expiry is a label, not deletion or an assertion that an incident has closed.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Presentation time must be timezone-aware")
    enabled = _validate_locations(locations)
    relevant, unresolved = [], []
    outside = 0
    parsed = snapshot.parsed
    for report in parsed.records if parsed else ():
        relations = _relations(report, enabled)
        if not relations:
            outside += 1
            continue
        time = assess_report_time(report, now=now)
        notes = []
        if snapshot.status not in ("available", "partial"):
            notes.append("feed_not_current")
        if snapshot.status == "partial":
            notes.append("feed_has_omissions")
        if time.inconsistent_interval or time.event_time == "future" or time.publication_time == "future":
            category = "uncertain_source_time"
        elif time.source_expiry == "elapsed":
            category = "source_expiry_elapsed"
        elif time.source_expiry == "unknown" or time.event_time == "unknown":
            category = "uncertain_source_time"
        else:
            category = "source_expiry_not_elapsed"
        if report.planned_burn is True:
            notes.append("planned_burn_context_only")
        if report.geometry.role == GeometryRole.WARNING_AREA:
            notes.append("warning_area_not_fire_perimeter")
            if any(r.relation == "geometry_unknown" for r in relations):
                notes.append("some_location_relations_unknown")
        notes.append("not_satellite_confirmation_or_active_fire_count")
        item = PresentedReport(report, relations, time, category, tuple(notes))
        target = relevant if any(r.relation in ("source_point_in_radius", "warning_area_intersects") for r in relations) else unresolved
        target.append(item)
    return ReportPresentation(snapshot.status, tuple(relevant), tuple(unresolved), outside,
        len(parsed.records) if parsed else 0, parsed.filtered_count if parsed else 0,
        parsed.invalid_count if parsed else 0, parsed.conflicted_ids if parsed else 0)
