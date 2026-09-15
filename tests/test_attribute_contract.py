"""Frozen public attribute outputs captured before serializer extraction."""
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from custom_components.terralyra_ignis.models import (
    ConfirmationLevel, DistanceTrend, FireCluster, FireLifecycle,
    IncidentLocationMatch, MetricTrend,
)


def cases():
    now = datetime(2026, 9, 15, 12, tzinfo=UTC)
    basic = FireCluster(38.12345678, -122.12345678, 11.126, .87654, 12.346, now, 2)
    full = replace(basic, track_id="track", family_id="family",
        source_track_ids=("track", "peer"), incident_extent_km=1.236,
        peak_frp_mw=22.346, place_name="Place", nearest_settlement="Town",
        location_description="Near Town", place_attribution="Synthetic",
        lifecycle=FireLifecycle.CONTINUING, first_seen=now-timedelta(seconds=91),
        last_seen=now, minimum_distance_km=0, maximum_frp_mw=33.456,
        maximum_pixel_count=3, detections_total=4, maximum_confidence=.98765,
        frp_trend=MetricTrend.INCREASING, activity_trend=MetricTrend.STABLE,
        distance_trend=DistanceTrend.APPROACHING, trend_samples=3,
        trend_window_minutes=1.234, confirmation_level=ConfirmationLevel.MULTI_SOURCE,
        providers=("one", "two"), satellites=("A", "B"), corroborating_detections=1,
        source_url="https://example.invalid/fire")
    outside = IncidentLocationMatch("family", "home", "Home", 9000.123, 50, "W", False)
    inside = IncidentLocationMatch("family", "remote", "Remote", 11.126, 250, "N", True,
                                   DistanceTrend.APPROACHING, 0)
    return {
        "minimal": basic, "full": full,
        "zero_and_empty": replace(full, track_id="", family_id="", source_track_ids=(),
            peak_frp_mw=0, maximum_frp_mw=0, maximum_pixel_count=0, detections_total=0,
            maximum_confidence=0, trend_samples=0, trend_window_minutes=0,
            incident_extent_km=0, place_name="", providers=(), satellites=(), source_url=""),
        "remote_location": replace(full, location_matches=(outside, inside)),
        "outside_only": replace(full, location_matches=(outside,)),
        "negative_duration": replace(full, first_seen=now+timedelta(minutes=1)),
        "first_seen_only": replace(basic, first_seen=now),
        "last_seen_only": replace(basic, last_seen=now),
        "location_match": inside,
    }


@pytest.mark.parametrize("name", cases())
def test_frozen_attribute_contract_and_no_mutation(name):
    expected = json.loads((Path(__file__).parent / "fixtures/attribute_contract.json").read_text())
    value = cases()[name]
    before = deepcopy(value)
    result = value.attrs()
    assert result == expected[name]
    assert value == before
    # Returned mutable lists/dicts must never become the model's state.
    if "location_matches" in result:
        result["location_matches"][0]["location_name"] = "changed"
    if "providers" in result:
        result["providers"].append("changed")
    assert value == before
    assert value.attrs() == expected[name]
