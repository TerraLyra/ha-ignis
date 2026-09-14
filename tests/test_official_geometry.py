"""Topology and conservative spherical circle/polygon intersection regressions."""
import pytest
from custom_components.terralyra_ignis.clustering import haversine_km
from custom_components.terralyra_ignis.official_sources.geometry import check_area, circle_relation

SQUARE = (((0,0),(1,0),(1,1),(0,1),(0,0)),)


def test_center_inside_and_on_boundary_including_zero_radius():
    area = check_area(SQUARE)
    assert area.reason is None
    assert circle_relation(area,.5,.5,0) == 'intersects'
    assert circle_relation(area,0,.5,0) == 'intersects'
    assert circle_relation(area,2,2,1) == 'outside'


def test_edge_crossing_when_no_vertex_is_inside_circle():
    area = check_area(SQUARE)
    assert circle_relation(area,-.01,.5,2) == 'intersects'
    assert circle_relation(area,-.01,.5,.5) == 'outside'


def test_tangency_is_uncertain_but_clear_sides_are_decided():
    area = check_area(SQUARE)
    radius = haversine_km(-.01,.5,0,.5)
    assert circle_relation(area,-.01,.5,radius) == 'unknown'
    assert circle_relation(area,-.01,.5,radius+.01) == 'intersects'
    assert circle_relation(area,-.01,.5,radius-.01) == 'outside'


def test_holes_and_reversed_ring_orientation():
    rings = (((0,0),(3,0),(3,3),(0,3),(0,0)),((1,1),(2,1),(2,2),(1,2),(1,1)))
    for shape in (rings, tuple(tuple(reversed(r)) for r in rings)):
        area = check_area(shape)
        assert circle_relation(area,1.5,1.5,1) == 'outside'
        assert circle_relation(area,1.5,1.5,60) == 'intersects'
        assert circle_relation(area,.5,.5,1) == 'intersects'


def test_concave_bounds_overlap_does_not_imply_intersection():
    area=check_area((((0,0),(3,0),(3,1),(1,1),(1,3),(0,3),(0,0)),))
    assert circle_relation(area,2,2,1) == 'outside'


@pytest.mark.parametrize('rings',[
    (((0,0),(1,1),(0,1),(1,0),(0,0)),),
    (((0,0),(1,0),(2,0),(0,0)),),
    (((0,0),(1,0),(1,1),(0,1)),),
    SQUARE+(((2,2),(3,2),(3,3),(2,3),(2,2)),),
    SQUARE+(((.2,.2),(.8,.2),(.8,.8),(.2,.8),(.2,.2)),
            ((.3,.3),(.7,.3),(.7,.7),(.3,.7),(.3,.3))),
    (((float('nan'),0),(1,0),(1,1),(float('nan'),0)),),
    (((True,0),(1,0),(1,1),(True,0)),),
])
def test_invalid_topology_is_unknown_never_repaired(rings):
    area=check_area(rings)
    assert area.reason == 'invalid_topology'
    assert circle_relation(area,.5,.5,1) == 'unknown'


def test_unsupported_geography_and_budget_are_explicit():
    for rings in [(((179,0),(-179,0),(-179,1),(179,1),(179,0)),),
                  (((0,86),(1,86),(1,87),(0,87),(0,86)),)]:
        assert check_area(rings).reason == 'unsupported_geography'
    assert circle_relation(check_area(SQUARE),2,2,1,max_evaluations=0) == 'unknown'
    assert check_area((tuple([(0,0)]*2001),)).reason == 'geometry_vertex_limit'
    assert circle_relation(check_area(SQUARE),90,0,1) == 'unknown'


def test_third_ordinate_does_not_change_surface_geometry():
    area=check_area((tuple((x,y,123) for x,y in SQUARE[0]),))
    assert circle_relation(area,.5,.5,1) == 'intersects'


def test_distance_numerical_failure_remains_unknown(monkeypatch):
    from custom_components.terralyra_ignis.official_sources import geometry
    def ambiguous(*args):
        raise ValueError('rounding')
    monkeypatch.setattr(geometry,'haversine_km',ambiguous)
    assert circle_relation(check_area(SQUARE),2,2,1) == 'unknown'
