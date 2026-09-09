"""Explicit, non-mutating Home Assistant report review action."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .official_reports import NOTICE_URL, OfficialReportClient
from .report_review import review_notice


def register_report_review(hass: HomeAssistant, client: OfficialReportClient) -> None:
    """Register a response-only action; coordinates never go to the provider."""
    async def review(call: ServiceCall) -> ServiceResponse:
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("Select a loaded TerraLyra IGNIS entry")
        url = call.data["report_url"]
        if not NOTICE_URL.fullmatch(url):
            raise ServiceValidationError("Select an original BM OKF event URL")
        data = entry.runtime_data.coordinator.data
        if data is None:
            raise ServiceValidationError("Incident history is not available yet")
        result = await client.async_get_archived_notices()
        if result["status"] != "available":
            raise ServiceValidationError("BM OKF RSS is temporarily unavailable")
        notice = next((item for item in result["notices"] if item["url"] == url), None)
        if notice is None:
            raise ServiceValidationError("The selected notice is not in the local 30-day archive or current RSS snapshot")
        try:
            response = review_notice(
                data.incident_history, notice,
                latitude=call.data["latitude"], longitude=call.data["longitude"],
                location_uncertainty_km=call.data["location_uncertainty_km"],
                event_start=call.data.get("event_start"), event_end=call.data.get("event_end"),
            )
            return {**response, "archive_origin": notice.get("archive_origin", "rss"),
                    "feed_status": result.get("feed_status", result["status"])}
        except (KeyError, TypeError, ValueError) as err:
            raise ServiceValidationError(
                "Invalid review input: use valid coordinates and timezone-aware ISO event times; end requires start"
            ) from err

    hass.services.async_register(
        DOMAIN, "review_official_report", review,
        schema=vol.Schema({
            vol.Required("config_entry_id"): cv.string,
            vol.Required("report_url"): cv.string,
            vol.Required("confirm_fire_report"): vol.All(cv.boolean, vol.In([True])),
            vol.Required("latitude"): cv.latitude,
            vol.Required("longitude"): cv.longitude,
            vol.Required("location_uncertainty_km"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=25)),
            vol.Optional("event_start"): cv.string,
            vol.Optional("event_end"): cv.string,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    async def import_report(call: ServiceCall) -> ServiceResponse:
        if client.archive is None:
            raise ServiceValidationError("Report archive is not configured")
        try:
            return await client.archive.async_import(dict(call.data))
        except (KeyError, TypeError, ValueError, OverflowError) as err:
            raise ServiceValidationError("Use an original BM OKF URL, title and timezone-aware publication time within the last 30 days") from err

    hass.services.async_register(
        DOMAIN, "import_official_report", import_report,
        schema=vol.Schema({
            vol.Required("url"): vol.All(cv.string, vol.Length(max=200)),
            vol.Required("title"): vol.All(cv.string, vol.Length(min=1, max=500)),
            vol.Required("published_at"): vol.All(cv.string, vol.Length(max=50)),
            vol.Optional("description", default=""): vol.All(cv.string, vol.Length(max=4000)),
        }),
        supports_response=SupportsResponse.ONLY,
    )
