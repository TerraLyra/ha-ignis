"""Immutable source context, separate from satellite evidence and HA entities."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class RecordKind(StrEnum):
    INCIDENT = "incident"
    WARNING = "warning"


class GeometryRole(StrEnum):
    INCIDENT_POINT = "incident_point"
    WARNING_AREA = "warning_area"


@dataclass(frozen=True, slots=True)
class OfficialGeometry:
    """Source geometry, structurally checked; polygon topology is not certified."""
    role: GeometryRole
    coordinates: tuple


@dataclass(frozen=True, slots=True)
class OfficialReport:
    provider: str
    source_id: str
    kind: RecordKind
    jurisdiction: str
    title: str
    source_url: str
    attribution: str
    geometry: OfficialGeometry
    raw_type: str
    raw_status: str
    raw_warning_level: str
    planned_burn: bool | None
    retrieved_at: datetime
    event_updated_at: datetime | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None
    source_date: date | None = None
    raw_updated: str = ""
    agency: str = ""
    location: str = ""
    reported_size: str = ""

    def __post_init__(self):
        for value in (self.retrieved_at, self.event_updated_at, self.published_at, self.expires_at):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("Official report timestamps must be timezone-aware")

    @property
    def uid(self) -> str:
        return f"{self.provider}:{self.source_id}"

    def expired_at(self, now: datetime) -> bool | None:
        """Explicit source expiry only; missing expiry does not establish currency."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Expiry comparison requires timezone-aware time")
        return now >= self.expires_at if self.expires_at else None


@dataclass(frozen=True, slots=True)
class ParsedReports:
    records: tuple[OfficialReport, ...]
    fetched_count: int
    filtered_count: int
    invalid_count: int
    conflicted_ids: int
