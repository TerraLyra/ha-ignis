"""Conservative affected-area bounds prefilter, never an exact fire-distance test."""

import json
import math

from .gdacs_reports import GdacsDataError, MAX_BYTES

MAX_VERTICES = 20000


def area_bounds(payload, event_id, episode_id):
    """Only use affected-area polygons belonging to this exact event revision."""
    if len(payload) > MAX_BYTES:
        raise GdacsDataError("Geometry too large")
    try:
        data = json.loads(payload)
        if data["type"] != "FeatureCollection" or len(data["features"]) > 100:
            raise ValueError("Bad geometry collection")
        points = []
        for feature in data["features"]:
            props = feature["properties"]
            if props.get("Class") != "Poly_area":
                continue
            if (props.get("eventtype"), props.get("eventid"), props.get("episodeid")) != ("WF", event_id, episode_id):
                raise ValueError("Geometry identity mismatch")
            geometry = feature["geometry"]
            if geometry["type"] == "Polygon":
                polygons = [geometry["coordinates"]]
            elif geometry["type"] == "MultiPolygon":
                polygons = geometry["coordinates"]
            else:
                raise ValueError("Unsupported affected area")
            for polygon in polygons:
                if not polygon:
                    raise ValueError("Empty polygon")
                for ring in polygon:
                    if len(ring) < 4 or ring[0] != ring[-1]:
                        raise ValueError("Unclosed ring")
                    for point in ring:
                        lon, lat = point
                        if any(type(v) not in (int, float) or not math.isfinite(v) for v in point):
                            raise ValueError("Invalid point")
                        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                            raise ValueError("Invalid point range")
                        points.append(point)
                        if len(points) > MAX_VERTICES:
                            raise ValueError("Too many vertices")
        if not points:
            return None
        return [min(p[0] for p in points), min(p[1] for p in points),
                max(p[0] for p in points), max(p[1] for p in points)]
    except (KeyError, TypeError, ValueError, RecursionError) as err:
        raise GdacsDataError("Invalid affected-area geometry") from err


def validate_bounds(bounds):
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("Invalid bounds")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in bounds):
        raise ValueError("Invalid bounds coordinates")
    west, south, east, north = bounds
    if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
        raise ValueError("Invalid bounds range")
    return list(bounds)


def location_relation(bounds, latitude, longitude, radius_km):
    """Overlapping bounding boxes are candidates, not confirmed intersections.

    Holes/concavities may create false positives; antimeridian cases stay unknown.
    No centroid-only exclusion is performed when an affected area is missing.
    """
    if bounds is None:
        return "unknown"
    west, south, east, north = validate_bounds(bounds)
    if east - west > 180:
        return "unknown"
    angle = radius_km / 6371.0
    delta_lat = math.degrees(angle)
    if latitude + delta_lat >= 90 or latitude - delta_lat <= -90:
        return "unknown"
    delta_lon = math.degrees(math.asin(min(1, math.sin(angle) / math.cos(math.radians(latitude)))))
    if longitude - delta_lon < -180 or longitude + delta_lon > 180:
        return "unknown"
    if north < latitude - delta_lat or south > latitude + delta_lat:
        return "outside"
    if east < longitude - delta_lon or west > longitude + delta_lon:
        return "outside"
    return "possible"
