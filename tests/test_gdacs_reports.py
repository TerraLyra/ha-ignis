"""GDACS page parsing without network or Home Assistant state changes."""

from copy import deepcopy
import json

import pytest

from custom_components.terralyra_ignis.gdacs_reports import GdacsDataError, MAX_BYTES, parse_page


def page():
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [21.1671, 44.8678]},
        "properties": {
            "eventtype": "WF", "eventid": 1030252, "episodeid": 40,
            "name": "Forest fires in Serbia", "country": "Serbia", "source": "GWIS",
            "fromdate": "2026-08-05T00:00:00", "todate": "2026-08-25T00:00:00",
            "datemodified": "2026-09-10T12:35:20", "iscurrent": "false",
            "istemporary": "false", "alertlevel": "Orange",
        },
    }]}


def encode(value):
    return json.dumps(value).encode()


def test_public_sample_fields_and_stable_revision_identity():
    data = page()
    before = deepcopy(data)
    first, = parse_page(encode(data))
    assert data == before
    assert first["latitude"] == 44.8678 and first["longitude"] == 21.1671
    assert first["is_current"] is False
    assert first["fromdate_raw"] == "2026-08-05T00:00:00"
    assert first["evidence_role"] == "context_only_not_independent_confirmation"
    props = data["features"][0]["properties"]
    props.update(episodeid=41, datemodified="2026-09-10T14:00:00")
    updated, = parse_page(encode(data))
    assert updated["uid"] == first["uid"] and updated["episode_id"] == 41


def test_empty_is_not_failure():
    assert parse_page(b"", 204) == []
    assert parse_page(encode({"type": "FeatureCollection", "features": []})) == []


@pytest.mark.parametrize("body,status", [(b"", 200), (b"<html>Error</html>", 200),
    (b"", 500), (b"x", 204), (b"x" * (MAX_BYTES + 1), 200)])
def test_bad_responses_fail(body, status):
    with pytest.raises(GdacsDataError):
        parse_page(body, status)


@pytest.mark.parametrize("field,value", [("eventtype", "EQ"), ("eventid", True),
    ("episodeid", -1), ("iscurrent", "unknown"), ("fromdate", "bad"),
    ("fromdate", "2027-01-01T00:00:00")])
def test_invalid_record_rejects_page(field, value):
    data = page()
    data["features"][0]["properties"][field] = value
    with pytest.raises(GdacsDataError):
        parse_page(encode(data))


@pytest.mark.parametrize("coordinates", [[181, 0], [0, -91], [float("nan"), 0], [True, 0], [1]])
def test_invalid_geometry(coordinates):
    data = page()
    data["features"][0]["geometry"]["coordinates"] = coordinates
    with pytest.raises(GdacsDataError):
        parse_page(encode(data))


def test_safe_text_and_constructed_url():
    data = page()
    data["features"][0]["properties"].update(name="<b>Test</b>", url={"report": "http://localhost/private"})
    result, = parse_page(encode(data))
    assert result["title"] == "Test"
    assert result["url"].startswith("https://www.gdacs.org/report.aspx?")


def test_oversized_page_is_not_silently_truncated():
    data = page()
    data["features"] *= 101
    with pytest.raises(GdacsDataError):
        parse_page(encode(data))
