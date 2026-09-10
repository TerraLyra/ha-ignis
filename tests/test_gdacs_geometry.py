import json
import pytest

from custom_components.terralyra_ignis.gdacs_geometry import area_bounds, location_relation
from custom_components.terralyra_ignis.gdacs_reports import GdacsDataError


def geometry(event=1, episode=2):
    return json.dumps({"type": "FeatureCollection", "features": [{
        "properties": {"eventtype": "WF", "eventid": event, "episodeid": episode, "Class": "Poly_area"},
        "geometry": {"type": "Polygon", "coordinates": [[[20, 46], [22, 46], [22, 48], [20, 46]]]},
    }]}).encode()


def test_bounds_candidate_not_exact_intersection():
    bounds = area_bounds(geometry(), 1, 2)
    assert bounds == [20, 46, 22, 48]
    assert location_relation(bounds, 47, 21, 1) == "possible"
    assert location_relation(bounds, 40, 10, 1) == "outside"
    # A wide area overlaps the location even when its center is far outside.
    assert location_relation([10, 46, 21, 48], 47, 21, 1) == "possible"


@pytest.mark.parametrize("bounds,lat,lon", [(None, 47, 21), ([-179, 0, 179, 2], 1, 180), ([0, 80, 1, 89], 89.99, 0)])
def test_uncertain_areas_are_not_outside(bounds, lat, lon):
    assert location_relation(bounds, lat, lon, 10) == "unknown"


def test_wrong_revision_rejected():
    with pytest.raises(GdacsDataError):
        area_bounds(geometry(episode=3), 1, 2)


def test_empty_geometry_is_unknown():
    assert area_bounds(b'{"type":"FeatureCollection","features":[]}', 1, 2) is None


def test_invalid_ring_rejected():
    data = json.loads(geometry())
    data["features"][0]["geometry"]["coordinates"][0][-1] = [23, 49]
    with pytest.raises(GdacsDataError):
        area_bounds(json.dumps(data).encode(), 1, 2)
