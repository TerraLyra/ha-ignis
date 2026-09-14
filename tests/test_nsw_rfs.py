"""Synthetic official-shaped records; no live network or private locations."""

import asyncio
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.monitoring import MonitoredLocation
from custom_components.terralyra_ignis.nsw_rfs import MAX_BYTES, MAX_ITEMS, NswRfsClient, parse_feed
from custom_components.terralyra_ignis.nsw_rfs_calendar import NswRfsCalendar


def feature(**props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [151, -30]},
            "properties": {"title": "Synthetic fire", "category": "Advice",
                "guid": "https://incidents.rfs.nsw.gov.au/api/v1/incidents/123",
                "description": "TYPE: Bush Fire <br />FIRE: Yes <br />STATUS: Under control <br />"
                               "UPDATED: 14 Sep 2026 19:48 <br />RESPONSIBLE AGENCY: Rural Fire Service",
                **props}}


def payload(*features):
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def test_official_shape_geometry_collection_and_identity():
    first = feature()
    first["geometry"] = {"type": "GeometryCollection", "geometries": [first["geometry"],
                          {"type": "GeometryCollection", "geometries": []}]}
    newer = deepcopy(first)
    newer["properties"]["description"] = newer["properties"]["description"].replace("19:48", "20:48")
    result = parse_feed(payload(newer, first))
    assert len(result["events"]) == 1
    event = result["events"][0]
    assert (event["latitude"], event["longitude"]) == (-30, 151)
    assert event["uid"] == "nsw_rfs:123"
    assert event["date"] == "2026-09-14"
    assert event["updated_raw"] == "14 Sep 2026 20:48"


@pytest.mark.parametrize("kind", ["Hazard Reduction", "Burn off", "Fire Alarm", "Other", "Assist Other Agency", "New unknown type"])
def test_non_fire_and_planned_types_excluded(kind):
    record = feature()
    record["properties"]["description"] = record["properties"]["description"].replace("Bush Fire", kind)
    result = parse_feed(payload(record))
    assert not result["events"]
    assert result["filtered_records"] == 1


@pytest.mark.parametrize("kind", ["Bush Fire", "Grass Fire", "Structure Fire", "Haystack Fire", "Car Fire", "Vehicle/Equipment Fire"])
def test_explicit_fire_types_included(kind):
    record = feature()
    record["properties"]["description"] = record["properties"]["description"].replace("Bush Fire", kind)
    assert len(parse_feed(payload(record))["events"]) == 1


def test_planned_category_and_fire_no_excluded():
    record = feature()
    record["properties"]["description"] = record["properties"]["description"].replace("FIRE: Yes", "FIRE: No")
    assert parse_feed(payload(record, feature(category="Planned Burn")))["filtered_records"] == 2


@pytest.mark.parametrize("geometry", [None, {"type": "Polygon", "coordinates": []},
    {"type": "Point", "coordinates": [151, 100]}, {"type": "Point", "coordinates": [True, -30]},
    {"type": "Point", "coordinates": [float("nan"), -30]}])
def test_invalid_geometry_never_becomes_location_match(geometry):
    record = feature()
    record["geometry"] = geometry
    result = parse_feed(payload(record))
    assert not result["events"] and result["unmapped_records"] == 1


def test_unmapped_lga_placeholder_is_omitted():
    result = parse_feed(payload(feature(title="Synthetic (Unmapped Incident)")))
    assert not result["events"] and result["unmapped_records"] == 1


@pytest.mark.parametrize("raw", [b"{}", b"null", b"broken", b"x" * (MAX_BYTES + 1),
    payload(*([None] * (MAX_ITEMS + 1))), payload(feature(description="changed schema"))])
def test_invalid_documents_fail_explicitly(raw):
    with pytest.raises(ValueError):
        parse_feed(raw)


def test_missing_or_invalid_dates_not_guessed_from_pubdate():
    bad = feature(description="TYPE: Bush Fire<br>FIRE: Yes<br>UPDATED: 31 Feb 2026 12:00",
                  pubDate="14/09/2026 9:46:00 AM")
    result = parse_feed(payload(feature(), bad))
    assert len(result["events"]) == 1 and result["invalid_records"] == 1


class Response:
    def __init__(self, body=b"", status=200):
        self.body, self.status, self.content = body, status, self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        for offset in range(0, len(self.body), size):
            yield self.body[offset:offset + size]


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


async def test_shared_cache_stale_backoff_recovery_and_successful_empty():
    ticks = [0]
    session = Session(Response(payload(feature())), Response(status=503), Response(payload()))
    client = NswRfsClient(session, timer=lambda: ticks[0])
    first, second = await asyncio.gather(client.async_get_events(), client.async_get_events())
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False
    first["events"].clear()
    assert len(second["events"]) == 1
    ticks[0] = 1800
    stale = await client.async_get_events()
    assert stale["status"] == "stale" and stale["last_success"] == second["last_success"]
    assert len(stale["events"]) == 1
    await client.async_get_events()
    assert len(session.calls) == 2
    ticks[0] = 2100
    fresh = await client.async_get_events()
    assert fresh["status"] == "available" and not fresh["events"]


@pytest.mark.parametrize("response", [Response(status=302), Response(b"{}"), Response(b"x" * (MAX_BYTES + 1))])
async def test_first_failure_is_unavailable(response):
    result = await NswRfsClient(Session(response)).async_get_events()
    assert result["status"] == "unavailable" and result["last_success"] is None


async def test_long_outage_backoff_is_bounded():
    ticks = [0]
    client = NswRfsClient(Session(*(Response(status=503) for _ in range(100))), timer=lambda: ticks[0])
    for _ in range(100):
        assert (await client.async_get_events())["status"] == "unavailable"
        assert 0 < client._next_attempt - ticks[0] <= 1800
        ticks[0] += 1800


def location(name, lat=-30, lon=151, radius=50, enabled=True):
    return MonitoredLocation(name.lower(), name, lat, lon, radius, enabled, "manual")


async def test_calendar_radius_overlap_disabled_and_date_bounds(hass):
    hass.config.time_zone = "Europe/Budapest"
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_events.return_value = {**parse_feed(payload(feature())), "status": "stale"}
    entity = NswRfsCalendar(hass, entry, client)
    assert entity.event is None and entity.entity_registry_enabled_default is False
    client.async_get_events.assert_not_called()
    locations = [location("Near"), location("Overlap", lon=151.01), location("Home", 47, 21),
                 location("Disabled", enabled=False)]
    try:
        with patch("custom_components.terralyra_ignis.nsw_rfs_calendar.resolve_monitored_locations", return_value=locations):
            events = await entity.async_get_events(hass, datetime(2026, 9, 13, 22, tzinfo=UTC), datetime(2026, 9, 14, 22, tzinfo=UTC))
            assert len(events) == 1
            assert events[0].start == date(2026, 9, 14) and events[0].end == date(2026, 9, 15)
            description = events[0].description
            assert "Near (0.0 km)" in description and "Overlap" in description
            assert "Home" not in description and "Disabled" not in description
            assert "Feed: stale" in description and "not ignition time" in description
            assert "© State of New South Wales" in description
            assert not await entity.async_get_events(hass, datetime(2026, 9, 14, 22, tzinfo=UTC), datetime(2026, 9, 15, 22, tzinfo=UTC))
        with patch("custom_components.terralyra_ignis.nsw_rfs_calendar.resolve_monitored_locations", return_value=[location("Far", 47, 21)]):
            assert not await entity.async_get_events(hass, datetime(2026, 9, 13, tzinfo=UTC), datetime(2026, 9, 16, tzinfo=UTC))
    finally:
        await entity.coordinator.async_shutdown()


async def test_calendar_unavailable_not_empty(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_events.return_value = {"status": "unavailable", "events": []}
    entity = NswRfsCalendar(hass, entry, client)
    try:
        with pytest.raises(HomeAssistantError):
            await entity.async_get_events(hass, datetime(2026, 9, 13, tzinfo=UTC), datetime(2026, 9, 16, tzinfo=UTC))
    finally:
        await entity.coordinator.async_shutdown()


async def test_entity_registration_opt_in_and_unsubscribe(hass):
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.async_get_events.return_value = {"status": "available", "events": []}
    entity = NswRfsCalendar(hass, entry, client)
    platform = EntityPlatform(hass=hass, logger=logging.getLogger(__name__), domain="calendar",
                              platform_name="terralyra_ignis", platform=None,
                              scan_interval=timedelta(seconds=30), entity_namespace=None)
    platform.config_entry = entry
    await platform.async_add_entities([entity])
    client.async_get_events.assert_not_called()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("calendar", "terralyra_ignis", entity.unique_id)
    assert registry.async_get(entity_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION
    registry.async_update_entity(entity_id, disabled_by=None)
    entity = NswRfsCalendar(hass, entry, client)
    await platform.async_add_entities([entity])
    client.async_get_events.assert_awaited_once()
    assert list(entity.coordinator.async_contexts())
    await platform.async_remove_entity(entity.entity_id)
    assert not list(entity.coordinator.async_contexts())
    await entity.coordinator.async_shutdown()
