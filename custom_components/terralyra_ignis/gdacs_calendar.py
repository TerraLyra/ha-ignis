"""Opt-in all-day GDACS context; dates are not ignition/extinction timestamps."""

from datetime import datetime, timedelta, time
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .gdacs_geometry import location_relation
from .monitoring import resolve_monitored_locations

_LOGGER = logging.getLogger(__name__)
NAMES = {"en": "Reports — GDACS wildfire context", "hu": "Jelentések — GDACS tűzesemények",
         "de": "Meldungen — GDACS Waldbrandkontext", "es": "Informes — Contexto de incendios GDACS",
         "fr": "Rapports — Contexte des incendies GDACS", "it": "Rapporti — Contesto incendi GDACS"}


class GdacsCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:earth"

    def __init__(self, hass, entry, client):
        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name="GDACS wildfire context", config_entry=entry,
            update_method=client.async_get_events, update_interval=timedelta(minutes=15),
        )
        super().__init__(coordinator, context=entry.entry_id)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gdacs_reports"
        self._attr_name = NAMES.get(hass.config.language, NAMES["en"])
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._spatial_unknown = 0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    @property
    def event(self):
        return None  # Not an active emergency and not a notification trigger.

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"feed_status": data.get("status", "unknown"),
                "last_success": data.get("last_success"),
                "spatially_uncertain_records_omitted": self._spatial_unknown,
                "spatial_filter": "affected_area_bounding_box_candidates_only"}

    async def async_get_events(self, hass, start_date, end_date):
        await self.coordinator.async_request_refresh()
        data = self.coordinator.data
        if not self.coordinator.last_update_success or not data or data["status"] == "unavailable":
            raise HomeAssistantError("GDACS context is temporarily unavailable")
        locations = [loc for loc in resolve_monitored_locations(hass, self._entry) if loc.enabled]
        result = []
        self._spatial_unknown = 0
        for record in data["events"]:
            relations = [(loc.name, location_relation(record.get("area_bounds"), loc.latitude, loc.longitude, loc.radius_km)) for loc in locations]
            names = [name for name, relation in relations if relation == "possible"]
            if not names:
                self._spatial_unknown += any(relation == "unknown" for _, relation in relations)
                continue
            # Use upstream calendar dates as all-day context, never guess a timezone.
            start = datetime.fromisoformat(record["fromdate_raw"]).date()
            end = datetime.fromisoformat(record["todate_raw"]).date() + timedelta(days=1)
            zone = ZoneInfo(hass.config.time_zone)
            if datetime.combine(start, time.min, zone) >= end_date or datetime.combine(end, time.min, zone) <= start_date:
                continue
            hu = hass.config.language == "hu"
            note = ("Lehetséges területi egyezés; csak befoglaló tartomány alapján. Nem független megerősítés.\n"
                    "A GDACS napjai; nem pontos tűzkezdet vagy kialvás. Nem hatósági riasztás."
                    if hu else "Possible area match; bounding-box prefilter only. Not independent confirmation.\n"
                    "GDACS calendar dates, not precise ignition or extinction. Not an official public warning.")
            description = (f"{record['publisher']}\n{record['url']}\n\n{note}\n"
                           f"Locations: {', '.join(names)}\nSource: {record['upstream_source']}\n"
                           f"GDACS alert level: {record['alert_level']}\nFeed: {data['status']}\n"
                           "Incomplete coverage; records without usable area geometry may be omitted.")
            result.append(CalendarEvent(summary=f"GDACS · {record['title']}", start=start, end=end,
                                        description=description, uid=record["uid"]))
        return sorted(result, key=lambda event: (event.start, event.uid))
