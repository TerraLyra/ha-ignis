"""Review action validates entry, source selection and explicit fire consent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.report_links import ReportLinks
from custom_components.terralyra_ignis.report_review_service import (
    register_report_review,
)

HISTORY = [{
    "track_id": "one", "latitude": 47.6, "longitude": 21.0,
    "first_seen": "2026-09-09T12:00:00+02:00", "last_seen": "2026-09-09T12:30:00+02:00",
    "providers": ["nasa_firms"], "satellites": ["N20"],
}]


@pytest.fixture
def review_action(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.runtime_data = SimpleNamespace(coordinator=SimpleNamespace(data=SimpleNamespace(incident_history=[])))
    client = AsyncMock()
    client.async_get_archived_notices.return_value = {"status": "available", "notices": [{
        "url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
        "title": "Test", "publisher": "BM OKF", "published_at": "2026-09-09T14:21:00+02:00",
    }]}
    store = AsyncMock()
    store.async_load.return_value = None
    links = ReportLinks(store)
    hass.data["test_report_links"] = links
    register_report_review(hass, client, links)
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
    client.async_get_archived_notices.assert_awaited_once_with()


async def test_archived_report_review_during_feed_outage(hass, review_action):
    client, data = review_action
    client.async_get_archived_notices.return_value["feed_status"] = "unavailable"
    client.async_get_archived_notices.return_value["notices"][0]["archive_origin"] = "manual_import"
    result = await hass.services.async_call("terralyra_ignis", "review_official_report", data, blocking=True, return_response=True)
    assert result["feed_status"] == "unavailable"
    assert result["archive_origin"] == "manual_import"
    assert result["changes_applied"] is False


async def test_import_only_writes_archive(hass, review_action):
    client, _ = review_action
    client.archive.async_import.return_value = {"status": "archived"}
    data = {"url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/91803",
            "title": "Saved report", "published_at": "2026-09-09T14:21:00+02:00"}
    result = await hass.services.async_call("terralyra_ignis", "import_official_report", data, blocking=True, return_response=True)
    assert result["status"] == "archived"
    client.archive.async_import.assert_awaited_once_with(data | {"description": ""})
    client.async_get_archived_notices.assert_not_called()


@pytest.mark.parametrize("change", [
    {"config_entry_id": "missing"}, {"report_url": "https://example.org/report"},
])
async def test_invalid_selection_makes_no_network_request(hass, review_action, change):
    client, data = review_action
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data | change, blocking=True, return_response=True)
    client.async_get_archived_notices.assert_not_called()


async def test_fire_confirmation_required(hass, review_action):
    client, data = review_action
    with pytest.raises(vol.Invalid):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data | {"confirm_fire_report": False}, blocking=True, return_response=True)
    client.async_get_archived_notices.assert_not_called()


@pytest.mark.parametrize("response", [
    {"status": "unavailable", "notices": []}, {"status": "available", "notices": []},
])
async def test_failed_or_expired_feed_does_not_match(hass, review_action, response):
    client, data = review_action
    client.async_get_archived_notices.return_value = response
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("terralyra_ignis", "review_official_report", data, blocking=True, return_response=True)


async def _candidate_call(hass, data):
    entry = hass.config_entries.async_get_entry(data["config_entry_id"])
    entry.runtime_data.coordinator.data.incident_history = HISTORY
    response = await hass.services.async_call("terralyra_ignis", "review_official_report", data, blocking=True, return_response=True)
    candidate = response["candidates"][0]
    return data | {"incident_id": candidate["incident_id"], "review_token": candidate["review_token"],
                   "confirm_association": True}


async def test_save_one_and_undo_does_not_change_incidents(hass, review_action, freezer):
    from copy import deepcopy

    freezer.move_to("2026-09-10T00:00:00Z")
    client, data = review_action
    save = await _candidate_call(hass, data)
    original = deepcopy(HISTORY)
    response = await hass.services.async_call("terralyra_ignis", "save_official_report_link", save, blocking=True, return_response=True)
    assert response["status"] == "saved"
    assert response["changes_to_incidents"] is False
    assert HISTORY == original
    client.archive.async_merge.return_value = client.async_get_archived_notices.return_value["notices"]
    client.async_get_archived_notices.reset_mock()
    listing = await hass.services.async_call("terralyra_ignis", "list_official_report_links",
                                             {"config_entry_id": data["config_entry_id"]}, blocking=True, return_response=True)
    assert len(listing["links"]) == 1
    assert listing["links"][0]["status"] == "active"
    client.async_get_archived_notices.assert_not_called()
    # Undo remains possible without a healthy/loaded coordinator.
    hass.config_entries.async_get_entry(data["config_entry_id"]).mock_state(hass, ConfigEntryState.NOT_LOADED)
    removed = await hass.services.async_call("terralyra_ignis", "remove_official_report_link",
                                             {"config_entry_id": data["config_entry_id"], "link_id": response["link"]["link_id"]},
                                             blocking=True, return_response=True)
    assert removed["status"] == "removed"


@pytest.mark.parametrize("change", [{"incident_id": "not_a_candidate"}, {"review_token": "0" * 64}, {"latitude": 47.601}])
async def test_stale_or_non_candidate_save_is_rejected(hass, review_action, change):
    _, data = review_action
    save = await _candidate_call(hass, data)
    with pytest.raises(ServiceValidationError, match="changed"):
        await hass.services.async_call("terralyra_ignis", "save_official_report_link", save | change, blocking=True, return_response=True)
    assert await hass.data["test_report_links"].async_list(data["config_entry_id"]) == []


async def test_save_requires_separate_explicit_confirmation(hass, review_action):
    client, data = review_action
    save = await _candidate_call(hass, data)
    client.async_get_archived_notices.reset_mock()
    with pytest.raises(vol.Invalid):
        await hass.services.async_call("terralyra_ignis", "save_official_report_link", save | {"confirm_association": False}, blocking=True, return_response=True)
    client.async_get_archived_notices.assert_not_called()
