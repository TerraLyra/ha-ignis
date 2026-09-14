"""Conservative source-time diagnostics, not assertions about fire lifecycle."""
from dataclasses import dataclass
from datetime import datetime
from .models import OfficialReport


@dataclass(frozen=True, slots=True)
class ReportTimeAssessment:
    source_expiry: str
    event_time: str
    publication_time: str
    inconsistent_interval: bool
    # No 'active', 'safe', or 'officially closed' interpretation is implied.


def assess_report_time(report: OfficialReport, *, now: datetime) -> ReportTimeAssessment:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Assessment time must be timezone-aware")
    expiry = report.expired_at(now)
    return ReportTimeAssessment(
        "unknown" if expiry is None else "elapsed" if expiry else "not_elapsed",
        "unknown" if report.event_updated_at is None else
        "future" if report.event_updated_at > now else "at_or_before_now",
        "unknown" if report.published_at is None else
        "future" if report.published_at > now else "at_or_before_now",
        bool(report.event_updated_at and report.expires_at and
             report.expires_at < report.event_updated_at),
    )
