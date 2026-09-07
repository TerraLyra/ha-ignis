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
from custom_components.terralyra_ignis.models import ProviderSnapshot, ProviderStatus
from custom_components.terralyra_ignis.monitoring import MonitoringCenter

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


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
    assert coordinator.last_processing_duration_ms == 0.0
    assert coordinator.last_input_detection_count == 0
    coordinator._async_save_state.assert_awaited_once()
