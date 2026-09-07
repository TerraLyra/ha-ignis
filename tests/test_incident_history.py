"""Tests for the bounded local fire-incident archive."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.terralyra_ignis.incident_history import (
    HISTORY_RETENTION,
    MAX_HISTORY_INCIDENTS,
    update_incident_history,
)
from custom_components.terralyra_ignis.monitoring import MonitoredLocation

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
HOME = MonitoredLocation("home", "Home", 46.25, 20.15, 250, True, "manual")


def _incident(index: int, *, seen: datetime = NOW) -> dict[str, object]:
    return {
        "track_id": f"fire-{index}",
        "latitude": 46.25,
        "longitude": 20.15,
        "first_seen": (seen - timedelta(hours=1)).isoformat(),
        "last_seen": seen.isoformat(),
        "maximum_frp_mw": 12.5,
        "maximum_confidence": 0.8,
        "maximum_pixel_count": 3,
        "detections_total": 5,
        "providers": ["nasa_firms"],
        "satellites": ["N21"],
        "nearest_settlement": "Szeged",
    }


def test_history_keeps_incident_after_it_leaves_live_tracks() -> None:
    history = update_incident_history([], [_incident(1)], (HOME,), now=NOW)
    retained = update_incident_history(
        history, [], (HOME,), now=NOW + timedelta(days=2)
    )

    assert len(retained) == 1
    assert retained[0]["nearest_settlement"] == "Szeged"
    assert retained[0]["locations"] == [
        {"id": "home", "name": "Home", "distance_km": 0.0}
    ]


def test_history_updates_existing_incident_without_duplicates() -> None:
    old = _incident(1, seen=NOW - timedelta(hours=2))
    current = _incident(1)
    current["maximum_frp_mw"] = 25.0

    history = update_incident_history([old], [current], (HOME,), now=NOW)

    assert len(history) == 1
    assert history[0]["maximum_frp_mw"] == 25.0


def test_history_removes_old_and_out_of_scope_incidents() -> None:
    expired = _incident(1, seen=NOW - HISTORY_RETENTION - timedelta(minutes=1))
    outside = _incident(2)
    outside["latitude"] = 0.0
    outside["longitude"] = 0.0

    assert update_incident_history([expired, outside], [], (HOME,), now=NOW) == []


def test_history_is_size_bounded() -> None:
    incidents = [
        _incident(index, seen=NOW - timedelta(minutes=index))
        for index in range(MAX_HISTORY_INCIDENTS + 25)
    ]

    history = update_incident_history([], incidents, (HOME,), now=NOW)

    assert len(history) == MAX_HISTORY_INCIDENTS
    assert history[0]["track_id"] == "fire-0"
