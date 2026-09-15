"""Contracts for the location model's HA-independent extraction boundary."""
import json
from pathlib import Path
import subprocess
import sys

from custom_components.terralyra_ignis import const, monitoring
from custom_components.terralyra_ignis.core import locations


def test_existing_imports_retain_type_and_validator_identity():
    for name in (
        "MonitoredLocation", "MonitoringCenter", "validate_monitored_location",
        "validate_monitored_locations", "validate_monitoring_center",
        "monitored_location_from_dict",
    ):
        assert getattr(monitoring, name) is getattr(locations, name)
    for name in (
        "LOCATION_ID", "LOCATION_NAME", "LOCATION_LATITUDE", "LOCATION_LONGITUDE",
        "LOCATION_RADIUS_KM", "LOCATION_ENABLED", "LOCATION_SOURCE",
        "LOCATION_SOURCE_HOME_ASSISTANT", "LOCATION_SOURCE_MANUAL",
        "MIN_RADIUS_KM", "MAX_RADIUS_KM",
    ):
        assert getattr(const, name) == getattr(locations, name)


def test_stored_location_roundtrip_without_home_assistant_or_site_packages():
    # Run the leaf independently; this does not claim the parent HA package
    # can already be imported without Home Assistant.
    path = Path(__file__).parents[1] / "custom_components/terralyra_ignis/core/locations.py"
    script = '''
import json, runpy, sys
m = runpy.run_path(sys.argv[1], run_name="location_contract")
records = [
    {"id":"home", "name":"Home", "latitude":47.0, "longitude":19.0,
     "radius_km":1.0, "enabled":True, "source":"home_assistant"},
    {"id":"manual-california", "name":"California", "latitude":38.0, "longitude":-122.0,
     "radius_km":500.0, "enabled":False, "source":"manual"},
]
values = tuple(m["monitored_location_from_dict"](r) for r in records)
m["validate_monitored_locations"](values)
assert [v.as_dict() for v in values] == records
assert m["MonitoringCenter"]("California", 38, -122, True).storage_key == "38.000000:-122.000000"
for change in ({"radius_km":0.9}, {"radius_km":500.1}, {"enabled":1},
               {"latitude":float("nan")}, {"source":"unknown"}, {"id":"bad id"}):
    try:
        m["monitored_location_from_dict"](records[0] | change)
    except ValueError:
        pass
    else:
        raise AssertionError(change)
try:
    m["validate_monitored_locations"]((values[0], values[0]))
except ValueError:
    pass
else:
    raise AssertionError("duplicate location ID accepted")
assert not any(n.startswith(("homeassistant", "custom_components")) for n in sys.modules)
print(json.dumps([v.as_dict() for v in values]))
'''
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script, str(path)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert [r["id"] for r in json.loads(result.stdout)] == ["home", "manual-california"]
