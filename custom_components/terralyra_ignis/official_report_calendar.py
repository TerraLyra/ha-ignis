"""Opt-in RSS publication calendar, separate from satellite incident history."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import IgnisConfigEntry
from .const import DOMAIN
from .official_reports import OfficialReportClient
from .report_link_display import LABELS, active_links, link_lines
from .report_relevance import classify_report

_LOGGER = logging.getLogger(__name__)

PUBLICATION_NOTES = {
    "en": "Publication time, not incident start or duration. Not matched to satellite detections. Local retention: 30 days / 1000 notices; not a complete archive. Filtered by fire-related wording, not official classification; relevant notices may be missed.",
    "hu": "Közzétételi idő, nem az esemény kezdete vagy időtartama. Nincs műholdas észleléshez párosítva. Helyi megőrzés: 30 nap / 1000 közlemény; nem teljes archívum. Tűzesetre utaló szöveg alapján szűrve, nem hivatalos besorolás; releváns hírek is kimaradhatnak.",
    "de": "Veröffentlichungszeit, nicht Beginn oder Dauer des Ereignisses. Keine Zuordnung zu Satellitenerkennungen. Lokale Speicherung: 30 Tage / 1000 Meldungen; kein vollständiges Archiv. Textfilter für Brandmeldungen, keine amtliche Einstufung; relevante Meldungen können fehlen.",
    "es": "Hora de publicación, no inicio ni duración del suceso. Sin vinculación a detecciones por satélite. Conservación local: 30 días / 1000 avisos; no es un archivo completo. Filtro textual de incendios, no clasificación oficial; puede omitir avisos relevantes.",
    "fr": "Heure de publication, pas le début ni la durée de l’événement. Aucune association aux détections satellitaires. Conservation locale : 30 jours / 1000 avis ; archives incomplètes. Filtre textuel des incendies, non officiel ; des avis pertinents peuvent être omis.",
    "it": "Ora di pubblicazione, non inizio o durata dell’evento. Nessuna associazione ai rilevamenti satellitari. Conservazione locale: 30 giorni / 1000 avvisi; archivio incompleto. Filtro testuale degli incendi, non classificazione ufficiale; può omettere avvisi pertinenti.",
}


class OfficialReportCalendar(CoordinatorEntity, CalendarEntity):
    """Fetch only when enabled; share the manual action's bounded RSS client."""

    _attr_has_entity_name = True
    _attr_translation_key = "official_reports"
    _attr_icon = "mdi:newspaper-variant-outline"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, hass: HomeAssistant, entry: IgnisConfigEntry, client: OfficialReportClient
    ) -> None:
        async def update() -> dict:
            result = await client.async_get_archived_notices()
            if result["status"] != "available":
                raise UpdateFailed("BM OKF RSS is temporarily unavailable")
            return result

        coordinator = DataUpdateCoordinator(
            hass, _LOGGER, name="BM OKF publication notices",
            config_entry=entry, update_method=update,
            update_interval=timedelta(minutes=15),
        )
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_official_reports"
        self._entry = entry
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Disabled entities are never added, and therefore never start polling.
        await self.coordinator.async_request_refresh()

    @property
    def event(self) -> CalendarEvent | None:
        # Publication entries are not active emergencies or notification triggers.
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        await self.coordinator.async_request_refresh()
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            raise HomeAssistantError("BM OKF RSS is temporarily unavailable")
        notes = PUBLICATION_NOTES.get(hass.config.language, PUBLICATION_NOTES["en"])
        runtime = getattr(self._entry, "runtime_data", None)
        data = runtime.coordinator.data if runtime is not None else None
        links = await active_links(hass, self._entry.entry_id,
                                   data.incident_history if data is not None else [],
                                   self.coordinator.data["notices"])
        events = []
        for notice in self.coordinator.data["notices"]:
            relevance = classify_report(notice)
            if relevance["category"] != "fire_related":
                continue
            published = datetime.fromisoformat(notice["published_at"])
            end = published + timedelta(minutes=1)
            if published >= end_date or end <= start_date:
                continue
            matching = [link for link in links if link["review"]["report_url"] == notice["url"]]
            event_notes = notes
            if matching:
                event_notes = notes.replace(LABELS.get(hass.config.language, LABELS["en"])[1], "").strip()
                event_notes += "\n\n" + "\n\n".join("\n".join(link_lines(link, hass.config.language)) for link in matching)
            events.append(CalendarEvent(
                summary=f"BM OKF · {notice['title']}",
                start=published,
                end=end,
                description=(f"{notice['publisher']}\n{notice['url']}\n\n{notice.get('description', '')}\n\n{event_notes}"
                             f"\nArchive origin: {notice.get('archive_origin', 'rss')}"
                             f"\nRelevance: {relevance['reason']}"
                             f"\nLive RSS: {self.coordinator.data.get('feed_status', 'available')}"),
                uid=notice["url"],
            ))
        return sorted(events, key=lambda event: event.start)
