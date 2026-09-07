"""Provider-neutral geographic planning for fire-risk forecasts."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .monitoring import MonitoredLocation
from .products.fire_risk import EUROPE_BOUNDS, FORECAST_DAYS, PRODUCT_ID

FIRE_RISK_PROVIDER_LSA_SAF = "eumetsat_lsa_saf_frmv3"
FIRE_RISK_PROVIDER_GWIS = "jrc_gwis_fwi"

FIRE_RISK_SOURCE_NAMES = {
    FIRE_RISK_PROVIDER_LSA_SAF: "EUMETSAT LSA SAF FRMv3",
    FIRE_RISK_PROVIDER_GWIS: "JRC GWIS / ECMWF FWI",
}


@dataclass(frozen=True, slots=True)
class FireRiskSourceAssignment:
    """One operational fire-risk source assigned to a location."""

    provider: str
    product: str
    forecast_days: int
    coverage: str

    def attrs(self) -> dict[str, str | int]:
        """Return stable, coordinate-free Home Assistant attributes."""
        return {
            "provider": self.provider,
            "name": FIRE_RISK_SOURCE_NAMES.get(self.provider, self.provider),
            "product": self.product,
            "forecast_days": self.forecast_days,
            "coverage": self.coverage,
            "status": "active",
        }


@dataclass(frozen=True, slots=True)
class FireRiskCoverageOpportunity:
    """A possible source which is deliberately not active yet."""

    provider: str
    product: str
    reason: str

    def attrs(self) -> dict[str, str]:
        """Return stable, coordinate-free Home Assistant attributes."""
        return {
            "provider": self.provider,
            "name": FIRE_RISK_SOURCE_NAMES.get(self.provider, self.provider),
            "product": self.product,
            "status": "not_active",
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FireRiskLocationPlan:
    """Compatible equal fire-risk sources for one monitored location."""

    location_id: str
    location_name: str
    assignments: tuple[FireRiskSourceAssignment, ...]
    coverage_opportunities: tuple[FireRiskCoverageOpportunity, ...] = ()

    @property
    def covered(self) -> bool:
        """Return whether at least one validated provider covers the location."""
        return bool(self.assignments)

    def attrs(self) -> dict[str, object]:
        """Return a bounded provider plan without coordinates."""
        return {
            "location_id": self.location_id,
            "location_name": self.location_name,
            "covered": self.covered,
            "status": (
                "covered" if self.covered else "no_compatible_fire_risk_source"
            ),
            "relationship": "equal_peers",
            "providers": [item.provider for item in self.assignments],
            "source_names": [
                FIRE_RISK_SOURCE_NAMES.get(item.provider, item.provider)
                for item in self.assignments
            ],
            "assignments": [item.attrs() for item in self.assignments],
            "source_count": len(self.assignments),
            "inactive_coverage_opportunities": [
                item.attrs() for item in self.coverage_opportunities
            ],
        }


def plan_fire_risk_sources(location: MonitoredLocation) -> FireRiskLocationPlan:
    """Assign only validated fire-risk products that cover the location center."""
    assignments: list[FireRiskSourceAssignment] = []
    if _point_in_bounds(location.latitude, location.longitude, EUROPE_BOUNDS):
        assignments.append(
            FireRiskSourceAssignment(
                FIRE_RISK_PROVIDER_LSA_SAF,
                PRODUCT_ID,
                FORECAST_DAYS,
                _frmv3_coverage(location),
            )
        )

    # GWIS is deliberately visible only as an opportunity until its live WMS
    # contract passes every bounded go/no-go gate in the research record.
    opportunities = (
        FireRiskCoverageOpportunity(
            FIRE_RISK_PROVIDER_GWIS,
            "Canadian Fire Weather Index",
            "live_wms_validation_required",
        ),
    )
    return FireRiskLocationPlan(
        location.id,
        location.name,
        tuple(assignments),
        opportunities,
    )


def summarize_fire_risk_plans(
    plans: tuple[FireRiskLocationPlan, ...],
) -> str:
    """Summarize operational fire-risk coverage across enabled locations."""
    if not plans:
        return "unknown"
    covered = sum(plan.covered for plan in plans)
    if covered == len(plans):
        return "covered"
    if covered:
        return "partial"
    return "not_covered"


def _point_in_bounds(
    latitude: float,
    longitude: float,
    bounds: tuple[float, float, float, float],
) -> bool:
    """Return whether a finite WGS84 coordinate is inside inclusive bounds."""
    if not all(math.isfinite(value) for value in (latitude, longitude)):
        raise ValueError("Fire-risk coverage coordinates must be finite")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Fire-risk coverage coordinates are out of range")
    west, south, east, north = bounds
    return west <= longitude <= east and south <= latitude <= north


def _frmv3_coverage(location: MonitoredLocation) -> str:
    """Distinguish a complete radius from an edge-clipped FRMv3 area."""
    west, south, east, north = EUROPE_BOUNDS
    lat_delta = location.radius_km / 110.574
    lon_delta = location.radius_km / (
        111.320 * max(0.2, abs(math.cos(math.radians(location.latitude))))
    )
    if (
        location.longitude - lon_delta >= west
        and location.longitude + lon_delta <= east
        and location.latitude - lat_delta >= south
        and location.latitude + lat_delta <= north
    ):
        return "full_radius"
    return "radius_clipped_to_product_bounds"

