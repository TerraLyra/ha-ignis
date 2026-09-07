"""Tests for provider-neutral per-location fire-risk source planning."""

from __future__ import annotations

import pytest

from custom_components.terralyra_ignis.const import LOCATION_SOURCE_MANUAL
from custom_components.terralyra_ignis.fire_risk_coverage import (
    FIRE_RISK_PROVIDER_GWIS,
    FIRE_RISK_PROVIDER_LSA_SAF,
    _point_in_bounds,
    plan_fire_risk_sources,
    summarize_fire_risk_plans,
)
from custom_components.terralyra_ignis.monitoring import MonitoredLocation
from custom_components.terralyra_ignis.products.fire_risk import EUROPE_BOUNDS


def _location(
    location_id: str,
    name: str,
    latitude: float,
    longitude: float,
    radius_km: float = 100,
) -> MonitoredLocation:
    return MonitoredLocation(
        id=location_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        enabled=True,
        source=LOCATION_SOURCE_MANUAL,
    )


def test_frmv3_is_assigned_by_location_instead_of_home_identity() -> None:
    budapest = plan_fire_risk_sources(
        _location("manual-budapest", "Budapest", 47.4979, 19.0402)
    )

    assert budapest.covered is True
    assert [item.provider for item in budapest.assignments] == [
        FIRE_RISK_PROVIDER_LSA_SAF
    ]
    assert budapest.attrs()["status"] == "covered"
    assert budapest.attrs()["relationship"] == "equal_peers"


@pytest.mark.parametrize(
    ("location_id", "name", "latitude", "longitude"),
    [
        ("california", "California", 38.5618, -121.6263),
        ("tokyo", "Tokyo", 35.6762, 139.6503),
        ("kampala", "Kampala", 0.3476, 32.5825),
    ],
)
def test_uncovered_locations_do_not_receive_false_frmv3_assignment(
    location_id: str,
    name: str,
    latitude: float,
    longitude: float,
) -> None:
    plan = plan_fire_risk_sources(
        _location(location_id, name, latitude, longitude)
    )

    assert plan.covered is False
    assert plan.assignments == ()
    assert plan.attrs()["status"] == "no_compatible_fire_risk_source"
    assert plan.attrs()["inactive_coverage_opportunities"] == [
        {
            "provider": FIRE_RISK_PROVIDER_GWIS,
            "name": "JRC GWIS / ECMWF FWI",
            "product": "Canadian Fire Weather Index",
            "status": "not_active",
            "reason": "live_wms_validation_required",
        }
    ]


def test_frmv3_reports_radius_clipping_at_product_edge() -> None:
    central = plan_fire_risk_sources(
        _location("central", "Central", 47.0, 19.0, 100)
    )
    edge = plan_fire_risk_sources(
        _location("edge", "Edge", 35.0, -9.5, 100)
    )

    assert central.assignments[0].coverage == "full_radius"
    assert edge.assignments[0].coverage == "radius_clipped_to_product_bounds"


def test_fire_risk_plan_summary_is_explicit() -> None:
    covered = plan_fire_risk_sources(_location("eu", "Europe", 47.0, 19.0))
    uncovered = plan_fire_risk_sources(
        _location("jp", "Tokyo", 35.6762, 139.6503)
    )

    assert summarize_fire_risk_plans(()) == "unknown"
    assert summarize_fire_risk_plans((covered,)) == "covered"
    assert summarize_fire_risk_plans((covered, uncovered)) == "partial"
    assert summarize_fire_risk_plans((uncovered,)) == "not_covered"


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(float("nan"), 0), (91, 0), (0, 181)],
)
def test_fire_risk_coverage_rejects_invalid_coordinates(
    latitude: float, longitude: float
) -> None:
    with pytest.raises(ValueError):
        _point_in_bounds(latitude, longitude, EUROPE_BOUNDS)

