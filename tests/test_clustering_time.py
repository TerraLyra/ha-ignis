"""Regression cases for temporal and overlapping-view FRP aggregation."""
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.terralyra_ignis.clustering import cluster_detections
from custom_components.terralyra_ignis.models import FireDetection

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)


def detection(minutes=0, satellite="MTG", frp=20, latitude=46.0, family=None):
    return FireDetection(
        provider=satellite, satellite=satellite, product="FRP",
        timestamp=NOW + timedelta(minutes=minutes), latitude=latitude,
        longitude=20.0, frp_mw=frp, source_family=family,
    )


def clusters(*items):
    return cluster_detections([(item, 0) for item in items], 46, 20, 1)


@pytest.mark.parametrize("satellite,minutes", [("MTG", 720), ("S3A", 1380)])
def test_remote_observations_do_not_sum_or_confirm(satellite, minutes):
    result = clusters(detection(), detection(minutes, satellite))
    assert len(result) == 1
    assert result[0].acquired == NOW + timedelta(minutes=minutes)
    assert all(item.frp_mw == 20 for item in result)
    assert all(item.confirmation_level.value == "single_source" for item in result)


def test_temporal_chain_cannot_extend_window():
    result = clusters(*(detection(minutes) for minutes in (0, 20, 40, 60)))
    assert len(result) == 1
    assert all(item.pixel_count == 1 for item in result)
    assert all(item.frp_mw == 20 for item in result)


def test_latest_scan_replaces_old_intensity():
    assert clusters(detection(frp=90), detection(15, frp=20))[0].frp_mw == 20


def test_same_scan_pixels_sum_but_overlapping_views_do_not():
    result = clusters(
        detection(family="lsa"),
        detection(latitude=46.001, family="lsa"),
        detection(satellite="IODC", frp=40, family="lsa"),
    )
    assert len(result) == 1
    assert result[0].frp_mw == 40
    assert result[0].confirmation_level.value == "single_source"


def test_independent_contemporary_views_still_confirm():
    result = clusters(detection(), detection(5, satellite="S3A"))
    assert len(result) == 1
    assert result[0].frp_mw == 20
    assert result[0].confirmation_level.value == "multi_source"


def test_adjacent_scan_lines_keep_their_combined_power():
    result = clusters(detection(), detection(0.5, latitude=46.001))
    assert result[0].frp_mw == 40
    assert result[0].pixel_count == 2


def test_remote_old_fire_is_not_removed_by_newer_elsewhere():
    result = clusters(detection(), detection(720, latitude=47))
    assert len(result) == 2


def test_replaying_history_does_not_duplicate_live_incident():
    from custom_components.terralyra_ignis.tracking import update_incidents

    observations = (detection(), detection(720))
    result = update_incidents(
        [], clusters(*observations), now=NOW + timedelta(hours=12),
        matching_radius_km=2, memory_hours=24,
    )
    replay = update_incidents(
        result.incidents, clusters(*reversed(observations)),
        now=NOW + timedelta(hours=12), matching_radius_km=2, memory_hours=24,
    )
    assert len(replay.incidents) == 1
    assert not replay.new_incidents
    assert not replay.trend_events
