"""Opt-in Queensland source-report calendar; no emergency or satellite events."""
from datetime import UTC, datetime, time, timedelta
from functools import partial
import logging
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .monitoring import resolve_monitored_locations
from .official_sources.models import RecordKind
from .official_sources.presentation import project_reports
from .official_sources.qld_client import QfdSnapshot

_LOGGER = logging.getLogger(__name__)
SOURCE_ZONE = ZoneInfo("Australia/Brisbane")


def _render(snapshot, locations, now, start, end, zone, hu):
    projection = project_reports(snapshot, locations, now=now)
    events = []
    for item in projection.relevant:
        record = item.report
        stamp = record.event_updated_at or record.published_at
        if stamp is None:
            continue  # Do not invent a calendar date from retrieval time.
        day = stamp.astimezone(SOURCE_ZONE).date()
        next_day = day + timedelta(days=1)
        if datetime.combine(day,time.min,zone) >= end or datetime.combine(next_day,time.min,zone) <= start:
            continue
        kind = ("Figyelmeztetés" if hu else "Warning") if record.kind == RecordKind.WARNING else ("Incidensjelentés" if hu else "Incident report")
        labels = {"source_expiry_elapsed": "Elmúlt forrásoldali lejárat" if hu else "Source expiry elapsed",
                  "uncertain_source_time": "Bizonytalan időadat" if hu else "Uncertain source time",
                  "source_expiry_not_elapsed": "Forrás szerinti időablak" if hu else "Source time window"}
        matches = []
        unknown = []
        for loc in item.locations:
            if loc.relation == "source_point_in_radius":
                matches.append(f"{loc.location_name} ({loc.distance_km:.1f} km)")
            elif loc.relation == "warning_area_intersects":
                matches.append(f"{loc.location_name} (" + ("figyelmeztetési terület" if hu else "warning area") + ")")
            else:
                unknown.append(loc.location_name)
        note = ("A nap a jelentés queenslandi dátuma, nem a tűz kezdete vagy időtartama. "
                "A figyelmeztetési terület nem tűzperem. Nincs műholdas összekapcsolás. "
                "Az elmúlt forrásoldali lejárat nem bizonyítja a tűz lezárását. "
                "Ez a feed pillanatképe, nem tartós archívum. Az aktuális hatósági tájékoztatást kövesd."
                if hu else "Day is the Queensland source-report date, not ignition time or duration. "
                "A warning area is not a fire perimeter. No satellite matching. "
                "Elapsed source expiry does not establish fire closure. Current feed snapshot, not a persistent archive. "
                "Follow current official advice.")
        def date_text(value):
            return value.isoformat() if value else ("ismeretlen" if hu else "unknown")
        lines = ["Queensland Fire Department",record.source_url,note,
            f"{'Helyszínek' if hu else 'Locations'}: {', '.join(matches)}",
            f"{'Bizonytalan helyszíni kapcsolat' if hu else 'Unknown location relation'}: {', '.join(unknown) or '—'}",
            f"{'Típus' if hu else 'Type'}: {record.raw_type}",
            f"{'Státusz' if hu else 'Status'}: {record.raw_status or '—'}",
            f"{'Forrás figyelmeztetési szintje' if hu else 'Source warning level'}: {record.raw_warning_level}",
            f"{'Időadat' if hu else 'Time assessment'}: {labels[item.time_category]}",
            f"{'Esemény frissítése' if hu else 'Event revision'}: {date_text(record.event_updated_at)}",
            f"{'Közzététel' if hu else 'Publication'}: {date_text(record.published_at)}",
            f"{'Forrásoldali lejárat' if hu else 'Source expiry'}: {date_text(record.expires_at)}",
            f"{'Dátum alapja' if hu else 'Date basis'}: {'event_revision' if record.event_updated_at else 'publication_fallback'}",
            f"Feed: {snapshot.status}",record.attribution]
        qualifiers = [labels[item.time_category]]
        if snapshot.status != "available":
            qualifiers.append(snapshot.status)
        if record.planned_burn:
            qualifiers.append("Tervezett égetés" if hu else "Planned burn")
            lines.append("Nem némít műholdas riasztást." if hu else "Does not suppress satellite alerts.")
        events.append(CalendarEvent(summary=f"QFD · {kind} · {record.title} [{'; '.join(qualifiers)}]",
            start=day,end=next_day,description="\n".join(lines),uid=record.uid))
    return sorted(events,key=lambda e:(e.start,e.uid)), projection


class QfdCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:fire-alert"

    def __init__(self, hass, entry, client):
        self._entry = entry
        self._client = client
        self._projection = None
        async def update():
            if not any(loc.enabled for loc in resolve_monitored_locations(hass,entry)):
                return QfdSnapshot(status="not_requested")
            return await client.async_get_reports()
        coordinator = DataUpdateCoordinator(hass,_LOGGER,name="Queensland QFD reports",
            config_entry=entry,update_method=update,update_interval=timedelta(minutes=30))
        super().__init__(coordinator,context=entry.entry_id)
        self._attr_unique_id = f"{entry.entry_id}_qfd_reports"
        self._attr_name = "Jelentések — Queensland QFD" if hass.config.language == "hu" else "Reports — Queensland QFD"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN,entry.entry_id)})

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        await self.coordinator.async_request_refresh()

    @property
    def event(self):
        return None  # Report context is not an active emergency boolean.

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or QfdSnapshot()
        parsed = data.parsed
        return {"feed_status":data.status,
                "last_success":data.last_success.isoformat() if data.last_success else None,
                "failure_code":data.failure_code,
                "invalid_records":parsed.invalid_count if parsed else 0,
                "filtered_records":parsed.filtered_count if parsed else 0,
                "conflicted_ids":parsed.conflicted_ids if parsed else 0,
                "unresolved_reports_last_query":len(self._projection.unresolved) if self._projection else None,
                "undated_reports_last_query":sum(not (item.report.event_updated_at or item.report.published_at) for item in self._projection.relevant) if self._projection else None,
                "retention":"current_feed_snapshot_only",
                "calendar_date_zone":"Australia/Brisbane"}

    async def async_get_events(self,hass,start_date,end_date):
        await self.coordinator.async_request_refresh()
        data = self.coordinator.data
        if not self.coordinator.last_update_success or data is None or data.status == "unavailable":
            raise HomeAssistantError("Queensland QFD reports are temporarily unavailable")
        locations = tuple(resolve_monitored_locations(hass,self._entry))
        # Geometry and rendering operate on immutable snapshots outside the HA loop.
        events, self._projection = await hass.async_add_executor_job(partial(
            _render,data,locations,datetime.now(UTC),start_date,end_date,
            ZoneInfo(hass.config.time_zone),hass.config.language == "hu"))
        return events
