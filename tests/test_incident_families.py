"""Tests for presentation-level physical fire incident grouping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.terralyra_ignis.incident_families import (
    consolidate_incident_families,
)
from custom_components.terralyra_ignis.models import (
    ConfirmationLevel,
    FireCluster,
    FireLifecycle,
)

NOW = datetime(2026, 9, 8, 19, 0, tzinfo=UTC)


def _cluster(
    track_id: str,
    *,
    latitude: float = 47.7,
    provider: str = "eumetsat_lsa_saf_iodc",
    minutes: int = 0,
    family_id: str | None = None,
    confirmation: ConfirmationLevel = ConfirmationLevel.SINGLE_SOURCE,
) -> FireCluster:
    acquired = NOW + timedelta(minutes=minutes)
    return FireCluster(
        latitude=latitude,
        longitude=21.0,
        distance_km=170.0,
        confidence=0.8,
        frp_mw=12.0,
        acquired=acquired,
        pixel_count=1,
        track_id=track_id,
        family_id=family_id,
        lifecycle=FireLifecycle.CONTINUING,
        first_seen=acquired - timedelta(hours=1),
        last_seen=acquired,
        providers=(provider,),
        confirmation_level=confirmation,
    )


def _consolidate(clusters: list[FireCluster]) -> list[FireCluster]:
    return consolidate_incident_families(
        clusters,
        home_latitude=46.25,
        home_longitude=20.15,
        matching_radius_km=3.0,
        matching_window=timedelta(hours=6),
    )


def test_duplicate_nearby_tracks_become_one_presentation_incident() -> None:
    incidents = _consolidate([_cluster("iodc-a"), _cluster("iodc-b", latitude=47.71)])

    assert len(incidents) == 1
    assert incidents[0].track_id == "iodc-a"
    assert incidents[0].source_track_ids == ("iodc-a", "iodc-b")
    assert incidents[0].attrs()["source_track_count"] == 2


def test_independent_sources_allow_bounded_geolocation_offset() -> None:
    incidents = _consolidate(
        [
            _cluster("iodc"),
            _cluster("firms", latitude=47.76, provider="nasa_firms"),
        ]
    )

    assert len(incidents) == 1
    assert incidents[0].confirmation_level is ConfirmationLevel.MULTI_SOURCE
    assert set(incidents[0].providers) == {
        "eumetsat_lsa_saf_iodc",
        "nasa_firms",
    }


def test_lsa_saf_feeds_do_not_claim_independent_confirmation() -> None:
    incidents = _consolidate(
        [
            _cluster("iodc", provider="eumetsat_lsa_saf_iodc"),
            _cluster("mtg", latitude=47.71, provider="eumetsat_lsa_saf"),
        ]
    )

    assert len(incidents) == 1
    assert incidents[0].confirmation_level is ConfirmationLevel.SINGLE_SOURCE


def test_same_source_hotspots_outside_tracking_radius_remain_separate() -> None:
    incidents = _consolidate([_cluster("iodc-a"), _cluster("iodc-b", latitude=47.75)])

    assert len(incidents) == 2


def test_family_diameter_cap_prevents_chain_bridge() -> None:
    incidents = _consolidate(
        [
            _cluster("firms-a", latitude=47.70, provider="nasa_firms"),
            _cluster("iodc", latitude=47.76),
            _cluster("firms-b", latitude=47.86, provider="nasa_firms"),
        ]
    )

    assert len(incidents) == 2


def test_existing_family_id_survives_new_source_track() -> None:
    original = _cluster("original", family_id="original")
    firms = _cluster("firms", latitude=47.75, provider="nasa_firms")
    incidents = _consolidate([original, firms])

    assert incidents[0].track_id == "original"
    assert original.family_id == "original"
    assert firms.family_id == "original"
    assert incidents[0].source_track_ids == ("firms", "original")


def test_stale_and_current_tracks_can_remain_one_known_family() -> None:
    original = _cluster("original", family_id="original")
    later = _cluster(
        "firms",
        latitude=47.79,
        provider="nasa_firms",
        minutes=300,
        family_id="original",
    )

    incidents = _consolidate([original, later])

    assert len(incidents) == 1
    assert incidents[0].track_id == "original"


def test_anchor_keeps_family_id_when_an_inherited_family_splits() -> None:
    detached = _cluster("detached", family_id="original")
    anchor = _cluster("original", latitude=48.0, family_id="original")

    incidents = _consolidate([detached, anchor])

    assert len(incidents) == 2
    by_member = {incident.source_track_ids[0]: incident for incident in incidents}
    assert by_member["original"].track_id == "original"
    assert by_member["detached"].track_id == "detached"


def test_family_metadata_is_exposed_without_double_counting_intensity() -> None:
    incidents = _consolidate(
        [
            _cluster("iodc"),
            _cluster("firms", latitude=47.75, provider="nasa_firms"),
        ]
    )

    attrs = incidents[0].attrs()
    assert attrs["incident_id"] == incidents[0].track_id
    assert attrs["source_track_count"] == 2
    assert attrs["source_track_ids"] == ["firms", "iodc"]
    assert attrs["incident_extent_km"] > 0
    assert incidents[0].frp_mw == 12.0
