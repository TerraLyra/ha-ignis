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


def test_legacy_import_path_reexports_core_primitives():
    from custom_components.terralyra_ignis import clustering
    from custom_components.terralyra_ignis.core import geo

    assert clustering.haversine_km is geo.haversine_km
    assert clustering.EARTH_RADIUS_KM == geo.EARTH_RADIUS_KM == 6371.0088


def test_geo_leaf_runs_without_site_packages():
    """Only the leaf is standalone; do not pretend the HA parent package is."""
    from pathlib import Path
    import subprocess
    import sys

    path = Path(__file__).parents[1] / "custom_components/terralyra_ignis/core/geo.py"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c",
         "import runpy, sys; geo = runpy.run_path(sys.argv[1]); "
         "assert geo['haversine_km'](0, 0, 0, 0) == 0; "
         "assert not any(n.startswith(('homeassistant', 'custom_components')) for n in sys.modules)",
         str(path)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
