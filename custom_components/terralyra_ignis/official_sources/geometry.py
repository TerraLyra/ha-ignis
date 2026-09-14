"""Validated GeoJSON-linear polygons versus spherical monitoring circles.

Ambiguous topology, unsupported geography and numerical/budget limits stay unknown.
"""
from dataclasses import dataclass
import math

from shapely.geometry import Point, Polygon
from shapely.errors import GEOSException

from ..clustering import EARTH_RADIUS_KM, haversine_km

MAX_VERTICES = 2000
MAX_EVALUATIONS = 20000
BOUNDARY_TOLERANCE_KM = 0.001


@dataclass(frozen=True, slots=True)
class CheckedArea:
    polygon: Polygon | None
    rings: tuple
    reason: str | None = None


def check_area(rings) -> CheckedArea:
    """Never repair invalid official geometry or infer a perimeter."""
    try:
        if not isinstance(rings, (tuple, list)) or not 1 <= len(rings) <= 100:
            raise ValueError
        if any(not isinstance(r, (tuple, list)) for r in rings):
            raise ValueError
        if sum(map(len, rings)) > MAX_VERTICES:
            return CheckedArea(None, (), "geometry_vertex_limit")
        normalized = []
        for ring in rings:
            points = []
            for p in ring:
                if not isinstance(p, (tuple, list)) or len(p) not in (2, 3):
                    raise ValueError
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in p):
                    raise ValueError
                if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
                    raise ValueError
                points.append(tuple(p[:2]))
            if len(points) < 4 or points[0] != points[-1]:
                raise ValueError
            normalized.append(tuple(points))
        points = [p for r in normalized for p in r]
        if not points:
            raise ValueError
        if max(p[0] for p in points) - min(p[0] for p in points) >= 180 or any(abs(p[1]) > 85 for p in points):
            return CheckedArea(None, (), "unsupported_geography")
        polygon = Polygon(normalized[0], normalized[1:])
        if polygon.is_empty or not polygon.is_valid or polygon.area == 0:
            raise ValueError
        return CheckedArea(polygon, tuple(normalized))
    except (ValueError, TypeError, GEOSException):
        return CheckedArea(None, (), "invalid_topology")


def circle_relation(area: CheckedArea, latitude: float, longitude: float, radius_km: float,
                    *, max_evaluations: int = MAX_EVALUATIONS) -> str:
    """Return intersects/outside/unknown using bounded spherical distance tests.

    GeoJSON edges interpolate longitude/latitude linearly. For any segment midpoint,
    R*(abs(delta latitude)+abs(delta longitude))/2 bounds spherical distance to every
    point on that segment. This Lipschitz bound permits safe outside rejection without
    treating degrees as kilometres or approximating a circle with an inscribed polygon.
    """
    if any(type(v) not in (int, float) or not math.isfinite(v)
           for v in (latitude, longitude, radius_km)):
        return "unknown"
    if not (-85 <= latitude <= 85 and -180 <= longitude <= 180 and 0 <= radius_km < 10000):
        return "unknown"
    if area.polygon is None:
        return "unknown"
    if area.polygon.covers(Point(longitude, latitude)):
        return "intersects"
    stack = [(a, b) for ring in area.rings for a, b in zip(ring, ring[1:])]
    uncertain = False
    evaluations = 0
    while stack:
        if evaluations >= max_evaluations:
            return "unknown"
        a, b = stack.pop()
        midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
        try:
            distance = haversine_km(latitude, longitude, midpoint[1], midpoint[0])
        except ValueError:
            return "unknown"  # Floating-point ambiguity near antipodal points.
        evaluations += 1
        bound = EARTH_RADIUS_KM * math.radians(abs(b[0]-a[0]) + abs(b[1]-a[1])) / 2
        if distance < radius_km - BOUNDARY_TOLERANCE_KM:
            return "intersects"
        if distance - bound > radius_km + BOUNDARY_TOLERANCE_KM:
            continue
        if bound <= BOUNDARY_TOLERANCE_KM:
            uncertain = True
            continue
        stack.extend(((a, midpoint), (midpoint, b)))
    return "unknown" if uncertain else "outside"
