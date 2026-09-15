"""Existing HA attribute projection; no domain decisions or state mutations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import FireCluster, IncidentLocationMatch

from ..const import (
    ATTR_ACQUIRED,
    ATTR_ACTIVITY_TREND,
    ATTR_CONFIDENCE,
    ATTR_CONFIRMATION_LEVEL,
    ATTR_CORROBORATING_DETECTIONS,
    ATTR_DETECTIONS_TOTAL,
    ATTR_DIRECTION,
    ATTR_DISTANCE_KM,
    ATTR_DISTANCE_TREND,
    ATTR_DURATION_MINUTES,
    ATTR_FIRST_SEEN,
    ATTR_FRP_MW,
    ATTR_FRP_TREND,
    ATTR_INCIDENT_EXTENT_KM,
    ATTR_INCIDENT_ID,
    ATTR_INSIDE_RADIUS,
    ATTR_LAST_SEEN,
    ATTR_LATITUDE,
    ATTR_LIFECYCLE,
    ATTR_LOCATION_DESCRIPTION,
    ATTR_LOCATION_ID,
    ATTR_LOCATION_MATCHES,
    ATTR_LOCATION_NAME,
    ATTR_LOCATION_RADIUS_KM,
    ATTR_LONGITUDE,
    ATTR_MAXIMUM_CONFIDENCE,
    ATTR_MAXIMUM_FRP_MW,
    ATTR_MAXIMUM_PIXEL_COUNT,
    ATTR_MINIMUM_DISTANCE_KM,
    ATTR_NEAREST_SETTLEMENT,
    ATTR_PEAK_FRP_MW,
    ATTR_PIXEL_COUNT,
    ATTR_PLACE_ATTRIBUTION,
    ATTR_PLACE_NAME,
    ATTR_PROVIDERS,
    ATTR_SATELLITES,
    ATTR_SOURCE_TRACK_COUNT,
    ATTR_SOURCE_TRACK_IDS,
    ATTR_SOURCE_URL,
    ATTR_TRACK_ID,
    ATTR_TREND_SAMPLES,
    ATTR_TREND_WINDOW_MINUTES,
)


def location_attributes(self: IncidentLocationMatch) -> dict[str, str | float | bool]:
    """Return a bounded, privacy-local representation for HA attributes."""
    return {
        ATTR_INCIDENT_ID: self.incident_id,
        ATTR_LOCATION_ID: self.location_id,
        ATTR_LOCATION_NAME: self.location_name,
        ATTR_DISTANCE_KM: round(self.distance_km, 2),
        ATTR_LOCATION_RADIUS_KM: round(self.radius_km, 2),
        ATTR_DIRECTION: self.direction,
        ATTR_INSIDE_RADIUS: self.inside_radius,
        ATTR_DISTANCE_TREND: self.distance_trend.value,
    }


def fire_attributes(self: FireCluster) -> dict[str, Any]:
    """Return bounded Home Assistant state attributes."""
    attrs = {
        ATTR_LATITUDE: round(self.latitude, 6),
        ATTR_LONGITUDE: round(self.longitude, 6),
        ATTR_DISTANCE_KM: round(self.distance_km, 2),
        ATTR_CONFIDENCE: round(self.confidence, 3),
        ATTR_FRP_MW: round(self.frp_mw, 2),
        ATTR_ACQUIRED: self.acquired.isoformat(),
        ATTR_PIXEL_COUNT: self.pixel_count,
    }
    if self.track_id is not None:
        attrs[ATTR_TRACK_ID] = self.track_id
        attrs[ATTR_INCIDENT_ID] = self.family_id or self.track_id
    if self.source_track_ids:
        attrs[ATTR_SOURCE_TRACK_IDS] = list(self.source_track_ids)
        attrs[ATTR_SOURCE_TRACK_COUNT] = len(self.source_track_ids)
    if self.incident_extent_km is not None:
        attrs[ATTR_INCIDENT_EXTENT_KM] = round(self.incident_extent_km, 2)
    if self.peak_frp_mw is not None:
        attrs[ATTR_PEAK_FRP_MW] = round(self.peak_frp_mw, 2)
    if self.place_name is not None:
        attrs[ATTR_PLACE_NAME] = self.place_name
    if self.nearest_settlement is not None:
        attrs[ATTR_NEAREST_SETTLEMENT] = self.nearest_settlement
    if self.location_description is not None:
        attrs[ATTR_LOCATION_DESCRIPTION] = self.location_description
    if self.place_attribution is not None:
        attrs[ATTR_PLACE_ATTRIBUTION] = self.place_attribution
    if self.lifecycle is not None:
        attrs[ATTR_LIFECYCLE] = self.lifecycle.value
    if self.first_seen is not None:
        attrs[ATTR_FIRST_SEEN] = self.first_seen.isoformat()
    if self.last_seen is not None:
        attrs[ATTR_LAST_SEEN] = self.last_seen.isoformat()
    if self.first_seen is not None and self.last_seen is not None:
        attrs[ATTR_DURATION_MINUTES] = round(
            max(0.0, (self.last_seen - self.first_seen).total_seconds() / 60), 1
        )
    if self.minimum_distance_km is not None:
        attrs[ATTR_MINIMUM_DISTANCE_KM] = round(self.minimum_distance_km, 2)
    if self.maximum_frp_mw is not None:
        attrs[ATTR_MAXIMUM_FRP_MW] = round(self.maximum_frp_mw, 2)
    if self.maximum_pixel_count is not None:
        attrs[ATTR_MAXIMUM_PIXEL_COUNT] = self.maximum_pixel_count
    if self.detections_total is not None:
        attrs[ATTR_DETECTIONS_TOTAL] = self.detections_total
    if self.maximum_confidence is not None:
        attrs[ATTR_MAXIMUM_CONFIDENCE] = round(self.maximum_confidence, 3)
    if self.frp_trend is not None:
        attrs[ATTR_FRP_TREND] = self.frp_trend.value
    if self.activity_trend is not None:
        attrs[ATTR_ACTIVITY_TREND] = self.activity_trend.value
    if self.distance_trend is not None:
        attrs[ATTR_DISTANCE_TREND] = self.distance_trend.value
    if self.trend_samples is not None:
        attrs[ATTR_TREND_SAMPLES] = self.trend_samples
    if self.trend_window_minutes is not None:
        attrs[ATTR_TREND_WINDOW_MINUTES] = round(self.trend_window_minutes, 1)
    attrs[ATTR_CONFIRMATION_LEVEL] = self.confirmation_level.value
    attrs[ATTR_PROVIDERS] = list(self.providers)
    attrs[ATTR_SATELLITES] = list(self.satellites)
    attrs[ATTR_CORROBORATING_DETECTIONS] = self.corroborating_detections
    if self.source_url is not None:
        attrs[ATTR_SOURCE_URL] = self.source_url
    if self.location_matches:
        attrs[ATTR_LOCATION_MATCHES] = [
            match.attrs() for match in self.location_matches
        ]
        nearest = next(
            (match for match in self.location_matches if match.inside_radius),
            None,
        )
        if nearest is not None:
            attrs.update(nearest.attrs())
    return attrs
