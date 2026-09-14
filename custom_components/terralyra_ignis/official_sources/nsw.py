"""Pure conversion of already accepted NSW records; existing calendar untouched."""
from datetime import date, datetime
from ..nsw_rfs import ATTRIBUTION, PUBLIC_URL
from .models import GeometryRole, OfficialGeometry, OfficialReport, RecordKind


def from_nsw_event(event: dict, *, retrieved_at: datetime) -> OfficialReport:
    """Accept the existing parser contract, not raw upstream input."""
    prefix, source_id = event["uid"].split(":", 1)
    if prefix != "nsw_rfs" or not source_id.isdecimal():
        raise ValueError("Invalid normalized NSW identity")
    return OfficialReport(
        provider=prefix, source_id=source_id, kind=RecordKind.INCIDENT,
        jurisdiction="AU-NSW", title=event["title"], source_url=PUBLIC_URL,
        attribution=ATTRIBUTION,
        geometry=OfficialGeometry(GeometryRole.INCIDENT_POINT,
                                  (event["longitude"], event["latitude"])),
        raw_type=event["type"], raw_status=event["status"],
        raw_warning_level=event["alert_level"], planned_burn=False,
        retrieved_at=retrieved_at, source_date=date.fromisoformat(event["date"]),
        raw_updated=event["updated_raw"], agency=event["agency"],
        location=event["location"], reported_size=event["size"],
    )
