"""Tests for bounded active-fire coordinator work."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.const import DOMAIN
from custom_components.terralyra_ignis.coordinator import (
    IgnisCoordinator,
    _snapshot_signature,
)
from custom_components.terralyra_ignis.models import FireDetection, ProviderSnapshot, ProviderStatus
from custom_components.terralyra_ignis.monitoring import MonitoringCenter

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("positions,expected", [((.80, .82, .84), "east"),
                                               ((.84, .82, .80), "west")])
async def test_location_movement_replay_through_published_events(hass, monkeypatch, positions, expected):
    from custom_components.terralyra_ignis.monitoring import MonitoredLocation
    for name in ("async_set_authentication_issue", "async_set_provider_outage_issue"):
        monkeypatch.setattr(f"custom_components.terralyra_ignis.coordinator.{name}", lambda *a, **k: None)
    provider = AsyncMock()
    provider.health = ()
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"dedup_radius_km": 5})
    entry.add_to_hass(hass)
    coordinator = IgnisCoordinator(hass, entry, provider,
        monitoring_center=MonitoringCenter("West", 0, 0, False),
        monitored_locations=(MonitoredLocation("west", "West", 0, 0, 200, True, "custom"),
                             MonitoredLocation("east", "East", 0, 1, 200, True, "custom")))
    coordinator._store_loaded = True
    coordinator._async_save_state = AsyncMock()
    coordinator._async_resolve_new_fire_place = AsyncMock()
    events = []
    for index, longitude in enumerate(positions):
        acquired = NOW + timedelta(minutes=index * 10)
        observation = FireDetection(provider="test", satellite="S3A", product="FRP",
            timestamp=acquired, latitude=0, longitude=longitude, frp_mw=20, confidence=1)
        provider.async_fetch_latest.return_value = replace(_snapshot(),
            product_timestamp=acquired, detections=(observation,))
        coordinator.data = await coordinator._async_update_data()
        events.extend(coordinator.data.trend_events)
    approaching = [event for event in events if event["event_type"] == "fire_approaching"]
    assert len(approaching) == 1
    assert approaching[0]["location_id"] == expected
    assert approaching[0]["distance_trend"] == "approaching"
    assert coordinator.data.tracked_fires[0].distance_km < 30


def _snapshot() -> ProviderSnapshot:
    return ProviderSnapshot(
        provider="test_provider",
        satellite="test_satellite",
        product="test_product",
        product_timestamp=NOW,
        received_timestamp=NOW,
        status=ProviderStatus.AVAILABLE,
        source_url="https://example.invalid",
        filename="test-product",
        detections=(),
    )


def test_snapshot_signature_identifies_product_not_fetch_time() -> None:
    """Refetching one immutable product does not create new processing work."""
    snapshot = _snapshot()

    assert _snapshot_signature(snapshot) == _snapshot_signature(
        replace(snapshot, received_timestamp=NOW + timedelta(minutes=5))
    )
    assert _snapshot_signature(snapshot) != _snapshot_signature(
        replace(snapshot, product_timestamp=NOW + timedelta(minutes=5))
    )


def test_snapshot_signature_detects_same_size_corrections() -> None:
    detection = FireDetection(provider="test", satellite="test", product="fire",
        timestamp=NOW, latitude=47.5, longitude=19, frp_mw=20)
    snapshot = replace(_snapshot(), detections=(detection,))
    for corrected in (replace(detection, latitude=47.6),
                      replace(detection, timestamp=NOW - timedelta(minutes=5)),
                      replace(detection, frp_mw=30)):
        assert _snapshot_signature(snapshot) != _snapshot_signature(
            replace(snapshot, detections=(corrected,)))


@pytest.mark.asyncio
async def test_unchanged_product_skips_processing_and_storage(
    hass, monkeypatch
) -> None:
    """A repeated provider product reuses published data without another write."""
    monkeypatch.setattr(
        "custom_components.terralyra_ignis.coordinator.async_set_authentication_issue",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "custom_components.terralyra_ignis.coordinator.async_set_provider_outage_issue",
        lambda *args, **kwargs: None,
    )
    provider = AsyncMock()
    provider.async_fetch_latest.return_value = _snapshot()
    provider.health = ()
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    coordinator = IgnisCoordinator(
        hass,
        entry,
        provider,
        monitoring_center=MonitoringCenter("Home", 47.5, 19.0, False),
    )
    coordinator._store_loaded = True
    coordinator._async_save_state = AsyncMock()

    first = await coordinator._async_update_data()
    coordinator.data = first
    second = await coordinator._async_update_data()

    assert second is first
    assert coordinator.unchanged_update_skips == 1
    coordinator._store = AsyncMock()
    await IgnisCoordinator._async_save_state(coordinator)
    saved = coordinator._store.async_save.call_args.args[0]
    restored = IgnisCoordinator(hass, entry, provider,
        monitoring_center=MonitoringCenter("Home", 47.5, 19.0, False))
    restored._store = AsyncMock()
    restored._store.async_load.return_value = saved
    await restored._async_setup()
    assert restored._observation_counts == coordinator._observation_counts
    restored._count_scope = "changed location or filters"
    restored._observation_counts = {}
    await restored._async_setup()
    assert restored._observation_counts == {}
    assert coordinator.last_processing_duration_ms == 0.0
    assert coordinator.last_input_detection_count == 0
    coordinator._async_save_state.assert_awaited_once()


@pytest.mark.asyncio
async def test_observation_counter_replay_through_coordinator(hass, monkeypatch):
    """Fresh peer products cannot recount a cached acquisition; idle polls age it."""
    instant = [NOW]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant[0]

    monkeypatch.setattr("custom_components.terralyra_ignis.coordinator.datetime", Clock)
    for name in ("async_set_authentication_issue", "async_set_provider_outage_issue"):
        monkeypatch.setattr(f"custom_components.terralyra_ignis.coordinator.{name}", lambda *a, **k: None)
    provider = AsyncMock()
    provider.health = ()
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    coordinator = IgnisCoordinator(hass, entry, provider,
        monitoring_center=MonitoringCenter("Home", 47.5, 19.0, False))
    coordinator._store_loaded = True
    coordinator._async_save_state = AsyncMock()
    observation = FireDetection(provider="test", satellite="S3A", product="FRP",
        timestamp=NOW, latitude=47.5, longitude=19.0, frp_mw=20, confidence=1,
        source_detection_id="same-pixel")
    for minute in (0, 10, 20, 30, 40, 50):
        instant[0] = NOW + timedelta(minutes=minute)
        provider.async_fetch_latest.return_value = replace(_snapshot(),
            product_timestamp=instant[0], detections=(observation,))
        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data.activity.detections_1h == 1
    instant[0] = NOW + timedelta(minutes=61)
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.data.activity.detections_1h == 0
    assert coordinator.data.activity.detections_3h == 1
    assert coordinator.unchanged_update_skips == 1
    coordinator._store = AsyncMock()
    await IgnisCoordinator._async_save_state(coordinator)
    saved = coordinator._store.async_save.call_args.args[0]
    restored = IgnisCoordinator(hass, entry, provider,
        monitoring_center=MonitoringCenter("Home", 47.5, 19.0, False))
    restored._store = AsyncMock()
    restored._store.async_load.return_value = saved
    await restored._async_setup()
    restored.data = await restored._async_update_data()
    assert restored.data.activity.detections_1h == 0
    assert restored.data.activity.detections_3h == 1
