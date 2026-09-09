"""Read-only association of a manually reviewed notice with local history."""

from datetime import datetime
from typing import Any

from .report_context import MAX_INCIDENTS, FireReport, IncidentContext, match_reports


def review_notice(
    history: list[dict[str, Any]], notice: dict[str, str], *,
    latitude: float, longitude: float, location_uncertainty_km: float,
    event_start: str | None = None, event_end: str | None = None,
) -> dict[str, Any]:
    """Use explicit input, never promote an automatically extracted date hint."""
    if len(history) > MAX_INCIDENTS:
        raise ValueError("Incident history exceeds review limit")
    report = FireReport(
        url=notice["url"], publisher=notice["publisher"],
        published_at=datetime.fromisoformat(notice["published_at"]), language="hu",
        latitude=latitude, longitude=longitude,
        location_uncertainty_km=location_uncertainty_km, source_kind="official",
        event_start=datetime.fromisoformat(event_start) if event_start else None,
        event_end=datetime.fromisoformat(event_end) if event_end else None,
    )
    incidents = []
    skipped = 0
    seen = set()
    for record in history:
        try:
            incident = IncidentContext(
                incident_id=record["track_id"],
                latitude=float(record["latitude"]), longitude=float(record["longitude"]),
                first_seen=datetime.fromisoformat(record["first_seen"]),
                last_seen=datetime.fromisoformat(record["last_seen"]),
            )
            if incident.incident_id in seen:
                raise ValueError("Duplicate history identity")
            seen.add(incident.incident_id)
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        incidents.append(incident)
    matches = match_reports(tuple(incidents), (report,))
    return {
        "status": "review_required",
        "report_url": report.url,
        "publisher": report.publisher,
        "title": notice["title"],
        "coordinate_basis": "user_supplied_not_rss",
        "location_uncertainty_km": location_uncertainty_km,
        "time_basis": "user_supplied_interval" if event_start else "publication_only",
        "event_start": event_start,
        "event_end": event_end,
        "history_records_checked": len(incidents),
        "history_records_skipped": skipped,
        "changes_applied": False,
        "candidates": [
            {
                "incident_id": match.incident_id,
                "distance_km": round(match.distance_km, 3),
                "relation": match.relation,
                "reasons": list(match.reasons),
            }
            for match in sorted(matches, key=lambda item: (item.distance_km, item.incident_id))
        ],
    }
