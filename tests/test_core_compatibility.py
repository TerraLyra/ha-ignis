"""Cross-layer contracts to preserve during incremental Core extraction.

All observations and storage are synthetic. These tests run the real pipeline,
including its HA event payloads, without provider requests or production data.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.const import DOMAIN, BUS_EVENT_NEW_FIRE
from custom_components.terralyra_ignis.coordinator import IgnisCoordinator
from custom_components.terralyra_ignis.incident_families import consolidate_incident_families
from custom_components.terralyra_ignis.models import (
    FireCluster, FireDetection, FireLifecycle, ProviderSnapshot, ProviderStatus,
)
from custom_components.terralyra_ignis.monitoring import MonitoredLocation, MonitoringCenter

NOW = datetime(2026, 9, 15, 12, tzinfo=UTC)
LOCATIONS = (
    MonitoredLocation("home", "Home", 47, 19, 50, True, "manual"),
    MonitoredLocation("california", "California", 38, -122, 250, True, "manual"),
)


def snapshot(at=NOW, *, latitude=38.1, populated=True):
    detection = FireDetection(
        provider="nasa_firms", satellite="N21", product="FRP", timestamp=at,
        latitude=latitude, longitude=-122, frp_mw=20, confidence=1,
        source_detection_id=f"synthetic:{latitude}:{at.isoformat()}",
    )
    return ProviderSnapshot(
        "nasa_firms", "N21", "FRP", at, at, ProviderStatus.AVAILABLE,
        "https://example.invalid/fire", "synthetic", (detection,) if populated else (),
    )


@pytest.fixture
def runtime(hass, monkeypatch):
    # Keep repair UI out of this contract; the processing and bus remain real.
    for name in ("async_set_authentication_issue", "async_set_provider_outage_issue"):
        monkeypatch.setattr(
            f"custom_components.terralyra_ignis.coordinator.{name}",
            lambda *args, **kwargs: None,
        )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    stored = {}

    async def save(value):
        stored.clear()
        stored.update(json.loads(json.dumps(value)))

    def create():
        provider = AsyncMock()
        provider.health = ()
        instance = IgnisCoordinator(
            hass, entry, provider,
            monitoring_center=MonitoringCenter("Home", 47, 19, False),
            monitored_locations=LOCATIONS,
        )
        instance._store = AsyncMock()
        instance._store.async_load.side_effect = lambda: deepcopy(stored) or None
        instance._store.async_save.side_effect = save
        return instance

    return create, stored


async def publish(instance, product):
    instance.provider.async_fetch_latest.return_value = product
    instance.data = await instance._async_update_data()
    return instance.data


@pytest.mark.asyncio
async def test_json_restart_retains_identity_history_and_remote_distance(runtime):
    create, stored = runtime
    first = create()
    await first._async_setup()
    data = await publish(first, snapshot())
    initial = data.tracked_fires[0].attrs()
    history = deepcopy(stored["incident_history"])
    assert initial["incident_id"] == "4913b91b10c9"
    assert initial["location_id"] == "california"
    assert initial["distance_km"] == 11.12
    assert initial["minimum_distance_km"] == 11.12
    assert initial["first_seen"] == NOW.isoformat()
    assert initial["detections_total"] == 1
    assert history[0]["locations"] == [
        {"id": "california", "name": "California", "distance_km": 11.1}
    ]

    restarted = create()
    await restarted._async_setup()
    replay = await publish(restarted, snapshot())
    attrs = replay.tracked_fires[0].attrs()
    for key in ("track_id", "incident_id", "first_seen", "last_seen",
                "detections_total", "source_track_ids", "distance_km",
                "minimum_distance_km", "location_id"):
        assert attrs[key] == initial[key]
    assert replay.new_fires == []
    assert stored["incident_history"] == history
    assert len(stored["tracks"]) == 1


@pytest.mark.asyncio
async def test_new_fire_bus_contract_and_replay_after_restart(runtime, hass):
    create, stored = runtime
    events = []
    unsubscribe = hass.bus.async_listen(BUS_EVENT_NEW_FIRE, lambda event: events.append(dict(event.data)))
    try:
        instance = create()
        await instance._async_setup()
        await publish(instance, snapshot(populated=False))
        product = snapshot(NOW + timedelta(minutes=10))
        data = await publish(instance, product)
        await hass.async_block_till_done()
        assert len(events) == 1
        assert events == data.new_fires
        payload = events[0]
        assert payload["incident_id"] == payload["track_id"] == "b20835ddefeb"
        assert payload["source_track_ids"] == [payload["incident_id"]]
        assert payload["source_track_count"] == 1
        assert payload["location_id"] == "california"
        assert payload["affected_locations"] == ["California"]
        assert payload["distance_km"] == 11.12
        assert payload["providers"] == ["nasa_firms"]
        assert payload["first_seen"] == product.product_timestamp.isoformat()
        assert payload["source_url"] == "https://example.invalid/fire"
        assert "California" in payload["notification_message"]
        assert "Home" not in payload["notification_message"]
        identity = payload["incident_id"]

        restarted = create()
        await restarted._async_setup()
        await publish(restarted, product)
        # A delayed re-delivery beyond the matching window must retain identity.
        await publish(restarted, replace(product, product_timestamp=NOW + timedelta(hours=8)))
        await hass.async_block_till_done()
        assert len(events) == 1
        assert [track["track_id"] for track in stored["tracks"]] == [identity]
        assert stored["tracks"][0]["detections_total"] == 1
    finally:
        unsubscribe()


def test_family_merge_split_preserves_persisted_anchor_under_reordering():
    def cluster(track_id, latitude, provider):
        return FireCluster(latitude, 21, 170, .8, 12, NOW, 1,
                           track_id=track_id, first_seen=NOW, last_seen=NOW,
                           providers=(provider,), lifecycle=FireLifecycle.CONTINUING)

    members = [cluster("anchor", 47.70, "eumetsat_lsa_saf"),
               cluster("peer", 47.71, "nasa_firms")]
    def group(values):
        return consolidate_incident_families(values, home_latitude=47,
            home_longitude=19, matching_radius_km=3, matching_window=timedelta(hours=6))

    merged = group(members)
    assert len(merged) == 1
    assert merged[0].track_id == "anchor"
    assert merged[0].source_track_ids == ("anchor", "peer")
    persisted = json.loads(json.dumps({m.track_id: m.family_id for m in members}))
    restored = [replace(m, family_id=persisted[m.track_id]) for m in members]
    restored[1].latitude = 48
    for order in (restored, list(reversed(restored))):
        split = group(deepcopy(order))
        assert {m.source_track_ids: m.track_id for m in split} == {
            ("anchor",): "anchor", ("peer",): "peer",
        }
