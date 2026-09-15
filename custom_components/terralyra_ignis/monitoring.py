"""Local monitored-location models and single-center compatibility helpers."""
from __future__ import annotations

from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .core.locations import (
    MonitoredLocation,
    MonitoringCenter,
    monitored_location_from_dict,
    validate_monitored_location,
    validate_monitored_locations,
    validate_monitoring_center,
)

from .const import (
    CONF_MONITORED_LOCATIONS,
    CONF_MONITORING_CENTER_NAME,
    CONF_MONITORING_LATITUDE,
    CONF_MONITORING_LONGITUDE,
    CONF_RADIUS_KM,
    CONF_USE_CUSTOM_MONITORING_CENTER,
    DEFAULT_MONITORING_CENTER_NAME,
    DEFAULT_RADIUS_KM,
    DEFAULT_USE_CUSTOM_MONITORING_CENTER,
    HOME_LOCATION_ID,
    LEGACY_CUSTOM_LOCATION_ID,
    LOCATION_ENABLED,
    LOCATION_ID,
    LOCATION_LATITUDE,
    LOCATION_LONGITUDE,
    LOCATION_NAME,
    LOCATION_RADIUS_KM,
    LOCATION_SOURCE,
    LOCATION_SOURCE_HOME_ASSISTANT,
    LOCATION_SOURCE_MANUAL,
    MAX_RADIUS_KM,
    MIN_RADIUS_KM,
)


def new_manual_location_id() -> str:
    """Return an opaque local ID that contains no name or coordinates."""
    return f"manual-{uuid4().hex}"


def monitored_location_from_center(
    center: MonitoringCenter,
    radius_km: float,
    *,
    manual_id: str | None = None,
) -> MonitoredLocation:
    """Convert the single-center model into one monitored location."""
    location = MonitoredLocation(
        id=(
            (manual_id or new_manual_location_id())
            if center.custom
            else HOME_LOCATION_ID
        ),
        name=center.name,
        latitude=center.latitude,
        longitude=center.longitude,
        radius_km=float(radius_km),
        enabled=True,
        source=(
            LOCATION_SOURCE_MANUAL
            if center.custom
            else LOCATION_SOURCE_HOME_ASSISTANT
        ),
    )
    validate_monitored_location(location)
    return location


def update_primary_location_radius(
    options: dict[str, object], radius_km: float
) -> None:
    """Keep the transition radius entity and first location synchronized."""
    configured = options.get(CONF_MONITORED_LOCATIONS)
    if not isinstance(configured, list) or not configured:
        return
    validate_radius = MonitoredLocation(
        id=HOME_LOCATION_ID,
        name=DEFAULT_MONITORING_CENTER_NAME,
        latitude=0.0,
        longitude=0.0,
        radius_km=float(radius_km),
        enabled=True,
        source=LOCATION_SOURCE_HOME_ASSISTANT,
    )
    validate_monitored_location(validate_radius)
    updated = [
        dict(item) if isinstance(item, dict) else item for item in configured
    ]
    index = next(
        (
            item_index
            for item_index, item in enumerate(updated)
            if isinstance(item, dict) and item.get(LOCATION_ENABLED) is True
        ),
        0,
    )
    if not isinstance(updated[index], dict):
        raise ValueError("Monitored-location list contains an invalid record")
    updated[index][LOCATION_RADIUS_KM] = float(radius_km)
    options[CONF_MONITORED_LOCATIONS] = updated


def resolve_monitored_locations(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[MonitoredLocation, ...]:
    """Resolve a stored list or adapt the current single-center options."""
    configured = entry.options.get(CONF_MONITORED_LOCATIONS)
    if isinstance(configured, list):
        if not all(isinstance(item, dict) for item in configured):
            raise ValueError("Monitored-location list contains an invalid record")
        locations = tuple(monitored_location_from_dict(item) for item in configured)
        locations = tuple(
            MonitoredLocation(
                id=location.id,
                name=location.name,
                latitude=float(hass.config.latitude),
                longitude=float(hass.config.longitude),
                radius_km=location.radius_km,
                enabled=location.enabled,
                source=location.source,
            )
            if location.source == LOCATION_SOURCE_HOME_ASSISTANT
            else location
            for location in locations
        )
        validate_monitored_locations(locations)
        return locations

    center = resolve_monitoring_center(hass, entry)
    radius_km = float(entry.options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM))
    return (
        monitored_location_from_center(
            center,
            radius_km,
            manual_id=LEGACY_CUSTOM_LOCATION_ID,
        ),
    )


def resolve_monitoring_center(
    hass: HomeAssistant, entry: ConfigEntry
) -> MonitoringCenter:
    """Return Home or a validated custom active-fire monitoring center."""
    configured = entry.options.get(CONF_MONITORED_LOCATIONS)
    if isinstance(configured, list):
        locations = resolve_monitored_locations(hass, entry)
        enabled = next(
            (location for location in locations if location.enabled), None
        )
        if enabled is None:
            raise ValueError("At least one monitored location must be enabled")
        return MonitoringCenter(
            name=enabled.name,
            latitude=enabled.latitude,
            longitude=enabled.longitude,
            custom=enabled.source == LOCATION_SOURCE_MANUAL,
        )
    custom = bool(
        entry.options.get(
            CONF_USE_CUSTOM_MONITORING_CENTER,
            DEFAULT_USE_CUSTOM_MONITORING_CENTER,
        )
    )
    if custom:
        latitude = float(entry.options[CONF_MONITORING_LATITUDE])
        longitude = float(entry.options[CONF_MONITORING_LONGITUDE])
        name = str(
            entry.options.get(
                CONF_MONITORING_CENTER_NAME,
                DEFAULT_MONITORING_CENTER_NAME,
            )
        ).strip()
    else:
        latitude = float(hass.config.latitude)
        longitude = float(hass.config.longitude)
        name = DEFAULT_MONITORING_CENTER_NAME
    validate_monitoring_center(latitude, longitude, name)
    return MonitoringCenter(name=name, latitude=latitude, longitude=longitude, custom=custom)
