"""Location value objects and validation without HA or I/O dependencies.

Persisted field names and source labels are retained for compatibility.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

LOCATION_ID = "id"
LOCATION_NAME = "name"
LOCATION_LATITUDE = "latitude"
LOCATION_LONGITUDE = "longitude"
LOCATION_RADIUS_KM = "radius_km"
LOCATION_ENABLED = "enabled"
LOCATION_SOURCE = "source"
LOCATION_SOURCE_HOME_ASSISTANT = "home_assistant"
LOCATION_SOURCE_MANUAL = "manual"
MIN_RADIUS_KM = 1.0
MAX_RADIUS_KM = 500.0


@dataclass(frozen=True, slots=True)
class MonitoredLocation:
    """One locally configured place relevant to hazard monitoring."""

    id: str
    name: str
    latitude: float
    longitude: float
    radius_km: float
    enabled: bool
    source: str

    def as_dict(self) -> dict[str, str | float | bool]:
        """Return the stable config-entry representation."""
        return {
            LOCATION_ID: self.id,
            LOCATION_NAME: self.name,
            LOCATION_LATITUDE: self.latitude,
            LOCATION_LONGITUDE: self.longitude,
            LOCATION_RADIUS_KM: self.radius_km,
            LOCATION_ENABLED: self.enabled,
            LOCATION_SOURCE: self.source,
        }


def validate_monitored_location(location: MonitoredLocation) -> None:
    """Reject unsafe or ambiguous local monitored-location records."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", location.id):
        raise ValueError("Monitored-location ID has an invalid format")
    validate_monitoring_center(location.latitude, location.longitude, location.name)
    if not math.isfinite(location.radius_km) or not (
        MIN_RADIUS_KM <= location.radius_km <= MAX_RADIUS_KM
    ):
        raise ValueError("Monitored-location radius is out of range")
    if location.source not in {
        LOCATION_SOURCE_HOME_ASSISTANT,
        LOCATION_SOURCE_MANUAL,
    }:
        raise ValueError("Unknown monitored-location source")


def monitored_location_from_dict(values: dict[str, object]) -> MonitoredLocation:
    """Validate and deserialize one config-entry location record."""
    if type(values[LOCATION_ENABLED]) is not bool:
        raise ValueError("Monitored-location enabled state must be boolean")
    location = MonitoredLocation(
        id=str(values[LOCATION_ID]).strip(),
        name=str(values[LOCATION_NAME]).strip(),
        latitude=float(values[LOCATION_LATITUDE]),
        longitude=float(values[LOCATION_LONGITUDE]),
        radius_km=float(values[LOCATION_RADIUS_KM]),
        enabled=values[LOCATION_ENABLED],
        source=str(values[LOCATION_SOURCE]),
    )
    validate_monitored_location(location)
    return location


def validate_monitored_locations(
    locations: tuple[MonitoredLocation, ...],
) -> None:
    """Validate a deterministic local list and reject duplicate IDs."""
    seen: set[str] = set()
    for location in locations:
        validate_monitored_location(location)
        if location.id in seen:
            raise ValueError("Duplicate monitored-location ID")
        seen.add(location.id)


@dataclass(frozen=True, slots=True)
class MonitoringCenter:
    """One validated center used by active-fire providers and calculations."""

    name: str
    latitude: float
    longitude: float
    custom: bool

    @property
    def storage_key(self) -> str:
        """Stable key used to prevent tracks crossing between centers."""
        return f"{self.latitude:.6f}:{self.longitude:.6f}"


def validate_monitoring_center(latitude: float, longitude: float, name: str) -> None:
    """Reject unsafe coordinates and unusable labels."""
    if not all(math.isfinite(value) for value in (latitude, longitude)):
        raise ValueError("Monitoring-center coordinates must be finite")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Monitoring-center coordinates are out of range")
    if not name.strip() or len(name.strip()) > 64:
        raise ValueError("Monitoring-center name must contain 1 to 64 characters")
