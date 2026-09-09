"""Fire-risk forecast and local incident-history calendars."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IgnisConfigEntry
from .const import DOMAIN
from .coverage import SOURCE_DISPLAY_NAMES
from .entity import IgnisEntity, IgnisFireRiskEntity
from .official_report_calendar import OfficialReportCalendar
from .products.fire_risk import FireRiskDay

RISK_LABELS = {
    "en": {
        "low": "Low",
        "moderate": "Moderate",
        "high": "High",
        "very_high": "Very high",
        "extreme": "Extreme",
        "unknown": "Unknown",
        "title": "Fire risk",
        "description": "LSA SAF FRMv3 fire-risk forecast near Home",
    },
    "hu": {
        "low": "Alacsony",
        "moderate": "Mérsékelt",
        "high": "Magas",
        "very_high": "Nagyon magas",
        "extreme": "Szélsőséges",
        "unknown": "Ismeretlen",
        "title": "Tűzkockázat",
        "description": "LSA SAF FRMv3 tűzkockázati előrejelzés az otthon közelében",
    },
    "de": {
        "low": "Niedrig",
        "moderate": "Mäßig",
        "high": "Hoch",
        "very_high": "Sehr hoch",
        "extreme": "Extrem",
        "unknown": "Unbekannt",
        "title": "Waldbrandgefahr",
        "description": "LSA SAF FRMv3-Waldbrandgefahrenvorhersage in der Nähe von Zuhause",
    },
    "es": {
        "low": "Bajo",
        "moderate": "Moderado",
        "high": "Alto",
        "very_high": "Muy alto",
        "extreme": "Extremo",
        "unknown": "Desconocido",
        "title": "Riesgo de incendio",
        "description": "Previsión LSA SAF FRMv3 del riesgo de incendio cerca de Casa",
    },
    "fr": {
        "low": "Faible",
        "moderate": "Modéré",
        "high": "Élevé",
        "very_high": "Très élevé",
        "extreme": "Extrême",
        "unknown": "Inconnu",
        "title": "Risque d’incendie",
        "description": "Prévision LSA SAF FRMv3 du risque d’incendie près du domicile",
    },
    "it": {
        "low": "Basso",
        "moderate": "Moderato",
        "high": "Alto",
        "very_high": "Molto alto",
        "extreme": "Estremo",
        "unknown": "Sconosciuto",
        "title": "Rischio di incendio",
        "description": "Previsione LSA SAF FRMv3 del rischio di incendio vicino a Casa",
    },
}

HISTORY_LABELS = {
    "en": {
        "title": "Fire detected near {place}",
        "coordinates": "Coordinates",
        "locations": "Monitored locations",
        "sources": "Sources",
        "satellites": "Satellites",
        "peak_frp": "Peak FRP",
        "pixels": "Maximum pixels",
        "detections": "Detection samples",
    },
    "hu": {
        "title": "Tűz észlelve {place} közelében",
        "coordinates": "Koordináták",
        "locations": "Érintett figyelt helyek",
        "sources": "Források",
        "satellites": "Műholdak",
        "peak_frp": "Csúcs-FRP",
        "pixels": "Legnagyobb pixelszám",
        "detections": "Észlelési minták",
    },
    "de": {
        "title": "Brand nahe {place} erkannt",
        "coordinates": "Koordinaten",
        "locations": "Überwachte Orte",
        "sources": "Quellen",
        "satellites": "Satelliten",
        "peak_frp": "Spitzen-FRP",
        "pixels": "Maximale Pixelzahl",
        "detections": "Erkennungsproben",
    },
    "es": {
        "title": "Incendio detectado cerca de {place}",
        "coordinates": "Coordenadas",
        "locations": "Ubicaciones vigiladas",
        "sources": "Fuentes",
        "satellites": "Satélites",
        "peak_frp": "FRP máximo",
        "pixels": "Píxeles máximos",
        "detections": "Muestras de detección",
    },
    "fr": {
        "title": "Feu détecté près de {place}",
        "coordinates": "Coordonnées",
        "locations": "Lieux surveillés",
        "sources": "Sources",
        "satellites": "Satellites",
        "peak_frp": "FRP maximale",
        "pixels": "Nombre maximal de pixels",
        "detections": "Échantillons de détection",
    },
    "it": {
        "title": "Incendio rilevato vicino a {place}",
        "coordinates": "Coordinate",
        "locations": "Località monitorate",
        "sources": "Fonti",
        "satellites": "Satelliti",
        "peak_frp": "FRP massimo",
        "pixels": "Pixel massimi",
        "detections": "Campioni di rilevamento",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IgnisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [
            FireRiskForecastCalendar(entry),
            FireIncidentHistoryCalendar(entry),
            OfficialReportCalendar(
                hass, entry, hass.data[DOMAIN]["official_report_client"]
            ),
        ]
    )


class FireRiskForecastCalendar(IgnisFireRiskEntity, CalendarEntity):
    """Expose all forecast days in Home Assistant's native calendar UI."""

    _attr_translation_key = "fire_risk_forecast"
    _attr_icon = "mdi:calendar-alert"

    def __init__(self, entry: IgnisConfigEntry) -> None:
        IgnisFireRiskEntity.__init__(self, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_risk_forecast"

    @property
    def event(self) -> CalendarEvent | None:
        data = self.coordinator.data
        return self._calendar_event(data.days[0]) if data and data.days else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        data = self.coordinator.data
        if data is None:
            return []
        return [
            self._calendar_event(day)
            for day in data.days
            if day.valid_date < end_date.date()
            and day.valid_date + timedelta(days=1) > start_date.date()
        ]

    def _calendar_event(self, day: FireRiskDay) -> CalendarEvent:
        labels = RISK_LABELS.get(self.hass.config.language, RISK_LABELS["en"])
        return CalendarEvent(
            summary=f"{labels['title']}: {labels[day.risk]}",
            start=day.valid_date,
            end=day.valid_date + timedelta(days=1),
            description=labels["description"],
        )


class FireIncidentHistoryCalendar(IgnisEntity, CalendarEntity):
    """Expose the bounded local archive as a searchable HA calendar."""

    _attr_translation_key = "fire_incident_history"
    _attr_icon = "mdi:fire-clock"

    def __init__(self, entry: IgnisConfigEntry) -> None:
        IgnisEntity.__init__(self, entry)
        self._attr_unique_id = f"{entry.entry_id}_fire_incident_history"

    @property
    def event(self) -> CalendarEvent | None:
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        data = self.coordinator.data
        if data is None:
            return []
        events = []
        for incident in data.incident_history:
            event = self._calendar_event(incident)
            if event.end > start_date and event.start < end_date:
                events.append(event)
        return sorted(events, key=lambda event: event.start)

    def _calendar_event(self, incident: dict[str, Any]) -> CalendarEvent:
        labels = HISTORY_LABELS.get(self.hass.config.language, HISTORY_LABELS["en"])
        first_seen = _parse_history_time(incident["first_seen"])
        last_seen = _parse_history_time(incident["last_seen"])
        end = max(last_seen, first_seen) + timedelta(minutes=1)
        place = (
            incident.get("nearest_settlement")
            or incident.get("place_name")
            or f"{float(incident['latitude']):.4f}, {float(incident['longitude']):.4f}"
        )
        location_names = [
            str(item.get("name"))
            for item in incident.get("locations", [])
            if isinstance(item, dict) and item.get("name")
        ]
        lines = [
            (
                f"{labels['coordinates']}: {float(incident['latitude']):.5f}, "
                f"{float(incident['longitude']):.5f}"
            ),
        ]
        _append_list(lines, labels["locations"], location_names)
        _append_list(
            lines,
            labels["sources"],
            [
                SOURCE_DISPLAY_NAMES.get(str(provider), str(provider))
                for provider in incident.get("providers", [])
            ],
        )
        _append_list(lines, labels["satellites"], incident.get("satellites", []))
        if "maximum_frp_mw" in incident:
            lines.append(
                f"{labels['peak_frp']}: {float(incident['maximum_frp_mw']):.1f} MW"
            )
        if "maximum_pixel_count" in incident:
            lines.append(f"{labels['pixels']}: {int(incident['maximum_pixel_count'])}")
        if "detections_total" in incident:
            lines.append(f"{labels['detections']}: {int(incident['detections_total'])}")
        return CalendarEvent(
            summary=labels["title"].format(place=place),
            start=first_seen,
            end=end,
            description="\n".join(lines),
        )


def _append_list(lines: list[str], label: str, values: Any) -> None:
    if isinstance(values, (list, tuple)) and values:
        lines.append(f"{label}: {', '.join(str(value) for value in values)}")


def _parse_history_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
