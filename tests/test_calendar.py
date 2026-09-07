"""Tests for fire calendars."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.terralyra_ignis.calendar import FireIncidentHistoryCalendar


def test_incident_history_calendar_exposes_auditable_details() -> None:
    entity = object.__new__(FireIncidentHistoryCalendar)
    entity.hass = SimpleNamespace(config=SimpleNamespace(language="hu"))
    incident = {
        "track_id": "fire-1",
        "latitude": 46.64091,
        "longitude": 20.23379,
        "first_seen": "2026-09-05T11:10:00+00:00",
        "last_seen": "2026-09-05T11:25:00+00:00",
        "nearest_settlement": "Szentes",
        "locations": [{"id": "home", "name": "Otthon", "distance_km": 120.1}],
        "providers": ["nasa_firms"],
        "satellites": ["N21"],
        "maximum_frp_mw": 28.44,
        "maximum_pixel_count": 3,
        "detections_total": 3,
    }

    event = entity._calendar_event(incident)

    assert event.summary == "Tűz észlelve Szentes közelében"
    assert event.start.isoformat() == "2026-09-05T11:10:00+00:00"
    assert event.end.isoformat() == "2026-09-05T11:26:00+00:00"
    assert "Érintett figyelt helyek: Otthon" in event.description
    assert "Források: NASA FIRMS" in event.description
    assert "Műholdak: N21" in event.description
    assert "Csúcs-FRP: 28.4 MW" in event.description
