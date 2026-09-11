"""Privacy-safe diagnostics for the TerraLyra IGNIS integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import IgnisConfigEntry
from .const import (
    CONF_FIRMS_MAP_KEY,
    CONF_MONITORED_LOCATIONS,
    CONF_MONITORING_CENTER_NAME,
    CONF_MONITORING_LATITUDE,
    CONF_MONITORING_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from .coverage import plan_location_sources, summarize_source_plans
from .fire_risk_coverage import (
    plan_fire_risk_sources,
    summarize_fire_risk_plans,
)

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_FIRMS_MAP_KEY,
    CONF_MONITORED_LOCATIONS,
    CONF_MONITORING_CENTER_NAME,
    CONF_MONITORING_LATITUDE,
    CONF_MONITORING_LONGITUDE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IgnisConfigEntry
) -> dict[str, Any]:
    """Return a bounded diagnostic summary without location or credentials."""
    active = entry.runtime_data.coordinator
    risk = entry.runtime_data.fire_risk_coordinator
    active_data = active.data
    risk_data = risk.data
    source_plans = tuple(
        plan_location_sources(
            location,
            lsa_saf_available=bool(entry.data.get(CONF_USERNAME)),
            firms_available=bool(entry.data.get(CONF_FIRMS_MAP_KEY)),
        )
        for location in getattr(active, "monitored_locations", ())
        if location.enabled
    )
    fire_risk_plans = tuple(
        plan_fire_risk_sources(location)
        for location in getattr(active, "monitored_locations", ())
        if location.enabled
    )
    provider_health = tuple(getattr(active.provider, "health", ()))

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "active_fire": {
            "last_update_success": active.last_update_success,
            "provider_status": active.provider_status.value,
            "provider": active.provider_name,
            "source_selection": "automatic_equal_peers",
            "assigned_sources": [
                {
                    "provider": item.provider_id,
                    "name": item.label,
                    "satellite": item.satellite,
                    "assigned_location_count": len(item.location_ids),
                    "status": item.status.value,
                    "failure_type": item.failure_type,
                    "diagnostic_code": getattr(item, "diagnostic_code", None),
                    "consecutive_failures": item.consecutive_failures,
                    "retry_at": (
                        item.retry_at.isoformat() if item.retry_at else None
                    ),
                    "product_timestamp": (
                        item.product_timestamp.isoformat()
                        if item.product_timestamp
                        else None
                    ),
                    "received_timestamp": (
                        item.received_timestamp.isoformat()
                        if item.received_timestamp
                        else None
                    ),
                }
                for item in provider_health
            ],
            "geographic_coverage": {
                "status": summarize_source_plans(source_plans),
                "enabled_location_count": len(source_plans),
                "covered_location_count": sum(item.covered for item in source_plans),
                "uncovered_location_count": sum(
                    not item.covered for item in source_plans
                ),
                "provider_assignment_counts": {
                    provider: sum(
                        provider in item.providers for item in source_plans
                    )
                    for provider in (
                        "eumetsat_lsa_saf",
                        "eumetsat_lsa_saf_iodc",
                        "noaa_goes",
                        "nasa_firms",
                    )
                },
            },
            "satellite": active.satellite,
            "product": active.provider_product,
            "product_time": (
                active.product_timestamp.isoformat()
                if active.product_timestamp
                else None
            ),
            "received_time": (
                active.received_timestamp.isoformat()
                if active.received_timestamp
                else None
            ),
            "performance": {
                "last_update_duration_ms": getattr(
                    active, "last_update_duration_ms", None
                ),
                "last_fetch_duration_ms": getattr(
                    active, "last_fetch_duration_ms", None
                ),
                "last_processing_duration_ms": getattr(
                    active, "last_processing_duration_ms", None
                ),
                "last_input_detection_count": getattr(
                    active, "last_input_detection_count", None
                ),
                "unchanged_update_skips": getattr(
                    active, "unchanged_update_skips", None
                ),
                "state_write_count": getattr(active, "state_write_count", None),
            },
            "active_cluster_count": (
                len(active_data.active_clusters) if active_data else None
            ),
            "tracked_fire_count": (
                len(active_data.tracked_fires) if active_data else None
            ),
            "incident_lifecycle_counts": (
                {
                    state: sum(
                        getattr(cluster, "lifecycle", None) is not None
                        and cluster.lifecycle.value == state
                        for cluster in active_data.tracked_fires
                    )
                    for state in ("new", "continuing", "inactive")
                }
                if active_data
                else None
            ),
            "incident_trend_counts": (
                {
                    metric: {
                        state: sum(
                            getattr(cluster, metric, None) is not None
                            and getattr(cluster, metric).value == state
                            for cluster in active_data.tracked_fires
                        )
                        for state in (
                            ("approaching", "stable", "receding", "unknown")
                            if metric == "distance_trend"
                            else ("increasing", "stable", "decreasing", "unknown")
                        )
                    }
                    for metric in ("frp_trend", "activity_trend", "distance_trend")
                }
                if active_data
                else None
            ),
            "raw_pixels_in_radius": (
                active_data.raw_pixels_in_radius if active_data else None
            ),
            "activity_summary": (
                {
                    "detections_1h": active_data.activity.detections_1h,
                    "detections_3h": active_data.activity.detections_3h,
                    "detections_6h": active_data.activity.detections_6h,
                    "new_incidents_24h": active_data.activity.new_incidents_24h,
                    "history_samples_24h": active_data.activity.samples_24h,
                }
                if active_data and getattr(active_data, "activity", None)
                else None
            ),
            "situation": (
                {
                    "level": active_data.situation.level.value,
                    "score": active_data.situation.score,
                    "reasons": list(active_data.situation.reasons),
                    "active_incidents": active_data.situation.active_incidents,
                }
                if active_data and getattr(active_data, "situation", None)
                else None
            ),
        },
        "fire_risk": {
            "source_selection": "automatic_equal_peers_by_location_coverage",
            "coverage": {
                "status": summarize_fire_risk_plans(fire_risk_plans),
                "enabled_location_count": len(fire_risk_plans),
                "covered_location_count": sum(
                    plan.covered for plan in fire_risk_plans
                ),
                "uncovered_location_count": sum(
                    not plan.covered for plan in fire_risk_plans
                ),
                "provider_assignment_counts": {
                    provider: sum(
                        any(
                            assignment.provider == provider
                            for assignment in plan.assignments
                        )
                        for plan in fire_risk_plans
                    )
                    for provider in {
                        assignment.provider
                        for plan in fire_risk_plans
                        for assignment in plan.assignments
                    }
                },
                "inactive_opportunity_counts": {
                    provider: sum(
                        any(
                            opportunity.provider == provider
                            for opportunity in plan.coverage_opportunities
                        )
                        for plan in fire_risk_plans
                    )
                    for provider in {
                        opportunity.provider
                        for plan in fire_risk_plans
                        for opportunity in plan.coverage_opportunities
                    }
                },
            },
            "last_update_success": risk.last_update_success,
            "generated_at": (
                risk_data.generated_at.isoformat() if risk_data else None
            ),
            "forecast_days": len(risk_data.days) if risk_data else None,
            "near_home_risk": (
                risk_data.days[0].risk if risk_data and risk_data.days else None
            ),
            "area_risk": risk_data.area_risk if risk_data else None,
        },
        "place_names_enabled": entry.runtime_data.place_name_resolver is not None,
    }
