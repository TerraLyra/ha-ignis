"""Geographic behaviour locked before moving the implementation."""
import pytest

from custom_components.terralyra_ignis.clustering import haversine_km


@pytest.mark.parametrize("points,expected", [
    ((0, 0, 0, 0), 0),
    ((0, 0, 0, 1), 111.1950802335329),
    ((0, 179.9, 0, -179.9), 22.23901604670658),
    ((89.9, 0, 89.9, 180), 22.23901604670658),
    ((-89.9, 0, -89.9, 180), 22.23901604670658),
    ((0, 0, 0, 180), 20015.114442035923),
    ((38, -122, 38.1, -122), 11.11950802335329),
])
def test_distance_contract(points, expected):
    assert haversine_km(*points) == pytest.approx(expected, abs=1e-8)
    lat1, lon1, lat2, lon2 = points
    assert haversine_km(lat2, lon2, lat1, lon1) == pytest.approx(expected, abs=1e-8)
