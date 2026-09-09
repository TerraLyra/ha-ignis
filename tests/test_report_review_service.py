"""Review action validates entry, source selection and explicit fire consent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.report_review_service import (
    register_report_review,
)


@pytest.fixture
def review_action(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.runtime_data = SimpleNamespace(coordinator=SimpleNamespace(data=SimpleNamespace(incident_history=[])))
    client = AsyncMock()
    client.async_get_notices.return_value = {"status": "available", "notices": [{
        "url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
        "title": "Test", "publisher": "BM OKF", "published_at": "2026-09-09T14:21:00+02:00",
    }]}
    register_report_review(hass, client)
    return client, {
        "config_entry_id": entry.entry_id,
        "report_url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
        "confirm_fire_report": True, "latitude": 47.6, "longitude": 21,
        "location_uncertainty_km": 5,
    }


async def test_response_only_review(hass, review_action):
    client, data = review_action
    result = await hass.services.async_call("terralyra_ignis", "review_official_report", data, blocking=True, return_response=True)
    assert result["candidates"] == []
    assert result["changes_applied"] is False
    client.async_get_notices.assert_awaited_once_with()


@pytest.mark.parametrize("change", [
    {"config_entry_id": "missing"}, {"report_url": "https://example.org/report"},
])
async def test_invalid_selection_makes_no_network_request(hass, review_action, change):
    client, data = review_action
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data | change, blocking=True, return_response=True)
    client.async_get_notices.assert_not_called()


async def test_fire_confirmation_required(hass, review_action):
    client, data = review_action
    with pytest.raises(vol.Invalid):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data | {"confirm_fire_report": False}, blocking=True, return_response=True)
    client.async_get_notices.assert_not_called()


@pytest.mark.parametrize("response", [
    {"status": "unavailable", "notices": []}, {"status": "available", "notices": []},
])
async def test_failed_or_expired_feed_does_not_match(hass, review_action, response):
    client, data = review_action
    client.async_get_notices.return_value = response
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data, blocking=True, return_response=True)
