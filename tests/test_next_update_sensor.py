"""Published next-update timestamps expire without fetching provider data."""
from datetime import UTC, datetime, timedelta
import logging
from types import SimpleNamespace

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.terralyra_ignis.coverage import LocationSourcePlan
from custom_components.terralyra_ignis.models import ProviderStatus
from custom_components.terralyra_ignis.sensor import MonitoredLocationNextUpdateSensor

NOW = datetime(2026, 9, 14, 10, tzinfo=UTC)


async def _setup(hass, freezer, received=NOW, status=ProviderStatus.AVAILABLE):
    freezer.move_to(NOW)
    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="test", config_entry=None)
    health = SimpleNamespace(
        provider_id="noaa_goes:G19", satellite="G19", location_ids=("home",),
        status=status, received_timestamp=received, label="GOES",
    )
    coordinator.provider = SimpleNamespace(health=(health,))
    entry = SimpleNamespace(entry_id="test", runtime_data=SimpleNamespace(coordinator=coordinator))
    entity = MonitoredLocationNextUpdateSensor(
        entry, LocationSourcePlan("home", "Home", ("noaa_goes",), ("G19",)),
        SimpleNamespace(longitude=-75),
    )
    entity.entity_id = "sensor.next_update_test"
    component = EntityComponent(logging.getLogger(__name__), "sensor", hass)
    await component.async_add_entities([entity])
    return coordinator, health, entity


async def test_published_estimate_advances_at_boundary_without_provider_update(hass, freezer):
    coordinator, health, entity = await _setup(hass, freezer)
    assert hass.states.get(entity.entity_id).state == (NOW + timedelta(minutes=10)).isoformat()
    for minutes in (10, 20, 55):
        current = NOW + timedelta(minutes=minutes)
        freezer.move_to(current)
        async_fire_time_changed(hass, current)
        await hass.async_block_till_done()
        state = hass.states.get(entity.entity_id)
        assert datetime.fromisoformat(state.state) > current
        assert state.attributes["next_source"] == "noaa_goes"
        assert state.attributes["next_satellite"] == "G19"
        assert state.attributes["estimate_type"] == "product_refresh_cadence"
        assert state.attributes["estimate_note"] == "estimated_not_guaranteed"
        assert health.received_timestamp == NOW
    await entity.async_remove()
    assert entity._cancel_estimate_timer is None


async def test_coordinator_reschedules_and_outage_cancels_timer(hass, freezer):
    coordinator, health, entity = await _setup(hass, freezer)
    health.received_timestamp = NOW + timedelta(minutes=4)
    freezer.move_to(NOW + timedelta(minutes=4))
    coordinator.async_set_updated_data({"cycle": 1})
    assert hass.states.get(entity.entity_id).state == (NOW + timedelta(minutes=14)).isoformat()
    old_deadline = NOW + timedelta(minutes=10)
    freezer.move_to(old_deadline)
    async_fire_time_changed(hass, old_deadline)
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == (NOW + timedelta(minutes=14)).isoformat()
    health.status = ProviderStatus.OUTAGE
    coordinator.async_set_updated_data({"cycle": 2})
    assert hass.states.get(entity.entity_id).state == "unavailable"
    assert entity._cancel_estimate_timer is None
    health.status = ProviderStatus.AVAILABLE
    coordinator.async_set_updated_data({"cycle": 3})
    assert entity._cancel_estimate_timer is not None
    await entity.async_remove()
    assert entity._cancel_estimate_timer is None


async def test_restart_with_old_receipt_and_no_receipt(hass, freezer):
    coordinator, health, entity = await _setup(hass, freezer, received=NOW - timedelta(days=3))
    assert datetime.fromisoformat(hass.states.get(entity.entity_id).state) > NOW
    health.received_timestamp = None
    coordinator.async_set_updated_data({"cycle": 1})
    assert hass.states.get(entity.entity_id).state == "unavailable"
    assert entity._cancel_estimate_timer is None
    await entity.async_remove()
