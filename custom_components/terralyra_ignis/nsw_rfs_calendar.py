"""Opt-in NSW RFS report dates; no automatic incident links or public alerts."""

from datetime import date, datetime, time, timedelta
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .clustering import haversine_km
from .const import DOMAIN
from .monitoring import resolve_monitored_locations
from .nsw_rfs import ATTRIBUTION, PUBLIC_URL

_LOGGER = logging.getLogger(__name__)
NAMES = {"en": "Reports — NSW RFS fires", "hu": "Jelentések — NSW RFS tűzesetek"}


class NswRfsCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:fire-alert"

    def __init__(self, hass, entry, client):
        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name="NSW RFS fire reports", config_entry=entry,
            update_method=client.async_get_events, update_interval=timedelta(minutes=30),
        )
        super().__init__(coordinator, context=entry.entry_id)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_nsw_rfs_reports"
        self._attr_name = NAMES.get(hass.config.language, NAMES["en"])
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    @property
    def event(self):
        return None  # Calendar context, not an active emergency or notification trigger.

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"feed_status": data.get("status", "unknown"),
                "last_success": data.get("last_success"),
                "fetched_records": data.get("fetched_count", 0),
                "filtered_records": data.get("filtered_records", 0),
                "unmapped_records_omitted": data.get("unmapped_records", 0),
                "invalid_records_omitted": data.get("invalid_records", 0),
                "spatial_filter": "publisher_point_within_enabled_location_radius",
                "retention": "current_feed_snapshot_only"}

    async def async_get_events(self, hass, start_date, end_date):
        await self.coordinator.async_request_refresh()
        data = self.coordinator.data
        if not self.coordinator.last_update_success or not data or data["status"] == "unavailable":
            raise HomeAssistantError("NSW RFS reports are temporarily unavailable")
        locations = [loc for loc in resolve_monitored_locations(hass, self._entry) if loc.enabled]
        zone = ZoneInfo(hass.config.time_zone)
        result = []
        for record in data["events"]:
            matches = []
            for loc in locations:
                distance = haversine_km(loc.latitude, loc.longitude, record["latitude"], record["longitude"])
                if distance <= loc.radius_km:
                    matches.append((loc.name, distance))
            if not matches:
                continue
            start = date.fromisoformat(record["date"])
            end = start + timedelta(days=1)
            timed = bool(record.get("updated_at"))
            if timed:
                start = datetime.fromisoformat(record["updated_at"])
                end = start + timedelta(minutes=1)
            range_start = start if timed else datetime.combine(start, time.min, zone)
            range_end = end if timed else datetime.combine(end, time.min, zone)
            if range_start >= end_date or range_end <= start_date:
                continue
            hu = hass.config.language == "hu"
            note = ("A jelentés forrás szerinti frissítési napja, nem a tűz kezdete vagy időtartama.\n"
                    "A forrás térképi pontja alapján szűrve; nem tűzterület-határ. Nem kapcsoltuk műholdas észleléshez.\n"
                    "Hiányos lefedettség; személyes biztonsági döntéshez az aktuális hatósági tájékoztatást kövesd."
                    if hu else "Publisher's report update date, not ignition time or fire duration.\n"
                    "Filtered by the publisher's map point, not a fire perimeter. Not linked to satellite detections.\n"
                    "Incomplete coverage; use current official advice for personal safety decisions.")
            description = (
                f"NSW Rural Fire Service\n{PUBLIC_URL}\n\n{note}\n"
                f"Locations: {', '.join(f'{name} ({distance:.1f} km)' for name, distance in matches)}\n"
                f"Type: {record['type']}\nAlert level: {record['alert_level']}\nStatus: {record['status']}\n"
                f"Location: {record['location']}\nReported size: {record['size']}\nAgency: {record['agency']}\n"
                f"Publisher update: {record['updated_raw']}\nFeed: {data['status']}\n"
                f"Current feed snapshot only; not a historical archive.\nIncident ID: {record['uid']}\n\n{ATTRIBUTION}"
            )
            if timed:
                description += "\nReport update time; one-minute display slot, not fire duration."
            else:
                description += "\nAll-day fallback: exact update timezone could not be verified."
            result.append(CalendarEvent(summary=f"NSW RFS · {record['title']}", start=start, end=end,
                                        description=description, uid=record["uid"]))
        return sorted(result, key=lambda event: (
            event.start if isinstance(event.start, datetime) else datetime.combine(event.start, time.min, zone), event.uid))
