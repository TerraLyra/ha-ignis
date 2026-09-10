from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock
import pytest
import logging
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.gdacs_calendar import GdacsCalendar


async def test_opt_in_calendar_is_context_and_keeps_stable_identity(hass):
    hass.config.latitude, hass.config.longitude = 47, 21
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    record = {"uid": "gdacs:WF:1", "title": "Synthetic wildfire", "publisher": "GDACS",
              "url": "https://www.gdacs.org/report.aspx?eventid=1&eventtype=WF", "area_bounds": [20, 46, 22, 48],
              "fromdate_raw": "2026-09-01T00:00:00", "todate_raw": "2026-09-02T00:00:00",
              "upstream_source": "GWIS", "alert_level": "Orange"}
    client = AsyncMock()
    client.async_get_events.return_value = {"status": "stale", "events": [record]}
    calendar = GdacsCalendar(hass, entry, client)
    assert calendar.entity_registry_enabled_default is False
    assert calendar.event is None
    client.async_get_events.assert_not_called()
    events = await calendar.async_get_events(hass, datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 4, tzinfo=UTC))
    assert len(events) == 1
    assert events[0].start == date(2026, 9, 1) and events[0].end == date(2026, 9, 3)
    assert events[0].uid == "gdacs:WF:1"
    assert "Feed: stale" in events[0].description
    assert "Not independent confirmation" in events[0].description
    client.async_get_events.return_value = {"status": "available", "events": [{**record, "area_bounds": None}]}
    await calendar.coordinator.async_refresh()
    assert not await calendar.async_get_events(hass, datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 4, tzinfo=UTC))
    assert calendar.extra_state_attributes["spatially_uncertain_records_omitted"] == 1
    await calendar.coordinator.async_shutdown()


async def test_enabled_entity_subscribes_and_removal_unsubscribes(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_events.return_value = {"status": "available", "events": []}
    entity = GdacsCalendar(hass, entry, client)
    component = EntityPlatform(hass=hass, logger=logging.getLogger(__name__), domain="calendar",
                               platform_name="terralyra_ignis", platform=None,
                               scan_interval=timedelta(seconds=30), entity_namespace=None)
    component.config_entry = entry
    assert not list(entity.coordinator.async_contexts())
    client.async_get_events.assert_not_called()
    await component.async_add_entities([entity])
    client.async_get_events.assert_not_called()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("calendar", "terralyra_ignis", entity.unique_id)
    assert registry.async_get(entity_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION
    registry.async_update_entity(entity_id, disabled_by=None)
    entity = GdacsCalendar(hass, entry, client)
    await component.async_add_entities([entity])
    client.async_get_events.assert_awaited_once()
    assert list(entity.coordinator.async_contexts())
    await component.async_remove_entity(entity.entity_id)
    assert not list(entity.coordinator.async_contexts())
    await entity.coordinator.async_shutdown()


async def test_unavailable_calendar_does_not_claim_no_events(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_events.return_value = {"status": "unavailable", "events": []}
    entity = GdacsCalendar(hass, entry, client)
    try:
        with pytest.raises(HomeAssistantError):
            await entity.async_get_events(hass, datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 4, tzinfo=UTC))
    finally:
        await entity.coordinator.async_shutdown()
