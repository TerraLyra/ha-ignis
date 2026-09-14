"""Offline source contracts using synthetic records, never live advice."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json

import pytest

from custom_components.terralyra_ignis.nsw_rfs import parse_feed as parse_nsw
from custom_components.terralyra_ignis.official_sources.models import GeometryRole, RecordKind
from custom_components.terralyra_ignis.official_sources.nsw import from_nsw_event
from custom_components.terralyra_ignis.official_sources.queensland import parse_feed, MAX_BYTES, MAX_ITEMS

NOW = datetime(2026, 9, 14, 20, tzinfo=UTC)


def feature(warning=False, **props):
    return {"type": "Feature", "geometry": (
        {"type": "Polygon", "coordinates": [[[150, -25, 0], [151, -25, 0], [150, -24, 0], [150, -25, 0]]]}
        if warning else {"type": "Point", "coordinates": [150, -25]}),
        "properties": {"UniqueID": "WARN-1" if warning else "QF-1", "EventType": "Fire",
            "GroupedType": "FIRE VEGETATION", "WarningTitle": "Synthetic fire",
            "WarningLevel": "Advice" if warning else "Information",
            "ItemDateTimeLocal_ISO": "2026-09-14T18:00:00+10:00",
            "PublishDateLocal_ISO": "2026-09-15T05:00:00+10:00",
            "ItemExpiryDateTimeLocal_ISO": "2026-09-15T18:00:00+10:00", **props}}


def payload(*records):
    return json.dumps({"type": "FeatureCollection", "features": records}).encode()


def parse(*records):
    return parse_feed(payload(*records), retrieved_at=NOW)


def test_nsw_conversion_preserves_existing_contract_without_inventing_time():
    body = payload({"type": "Feature", "geometry": {"type": "Point", "coordinates": [151, -30]},
        "properties": {"title": "Synthetic NSW", "category": "Advice",
            "guid": "https://incidents.rfs.nsw.gov.au/api/v1/incidents/123",
            "description": "TYPE: Bush Fire<br/>FIRE: Yes<br/>STATUS: Under control<br/>UPDATED: 14 Sep 2026 19:48"}})
    existing = parse_nsw(body)
    original = deepcopy(existing)
    event = existing["events"][0]
    report = from_nsw_event(event, retrieved_at=NOW)
    assert report.uid == event["uid"]
    assert report.title == event["title"]
    assert report.geometry.coordinates == (event["longitude"], event["latitude"])
    assert report.raw_status == event["status"]
    assert report.raw_warning_level == event["alert_level"]
    assert report.source_date.isoformat() == event["date"]
    assert report.raw_updated == event["updated_raw"]
    assert report.event_updated_at is report.published_at is report.expires_at is None
    assert report.expired_at(NOW) is None
    assert existing == original == parse_nsw(body)
    with pytest.raises(FrozenInstanceError):
        report.title = "Changed"
    with pytest.raises(ValueError):
        from_nsw_event(event, retrieved_at=NOW.replace(tzinfo=None))


def test_mixed_feed_distinguishes_incident_and_warning_without_centroid():
    point, warning = feature(), feature(True)
    before = deepcopy(warning)
    result = parse(point, warning)
    assert result.fetched_count == 2
    incident, alert = result.records
    assert incident.kind == RecordKind.INCIDENT
    assert incident.geometry.role == GeometryRole.INCIDENT_POINT
    assert alert.kind == RecordKind.WARNING
    assert alert.geometry.role == GeometryRole.WARNING_AREA
    assert alert.geometry.coordinates[0][0] == (150, -25, 0)
    assert warning == before
    assert alert.event_updated_at == datetime(2026, 9, 14, 8, tzinfo=UTC)
    assert alert.published_at == datetime(2026, 9, 14, 19, tzinfo=UTC)
    assert alert.expired_at(NOW) is False
    assert alert.expired_at(alert.expires_at) is True


def test_fresh_publication_does_not_reactivate_expired_planned_burn():
    result = parse(feature(GroupedType="FIRE PERMITTED BURN",
        ItemDateTimeLocal_ISO="2026-08-01T00:00:00+10:00",
        ItemExpiryDateTimeLocal_ISO="2026-08-02T00:00:00+10:00"))
    record = result.records[0]
    assert record.planned_burn is True
    assert record.expired_at(NOW) is True
    assert record.published_at > record.expires_at


@pytest.mark.parametrize("props", [{"EventType": "Flood"}, {"GroupedType": "NEW TYPE"},
    {"WarningLevel": "Unknown warning"}])
def test_unknown_or_non_fire_classification_is_counted(props):
    result = parse(feature(**props))
    assert result.filtered_count == 1
    assert result.records == ()


@pytest.mark.parametrize("bad", [None, {}, {"type": "Point", "coordinates": [True, -25]},
    {"type": "Point", "coordinates": [181, -25]},
    {"type": "Point", "coordinates": [150, float('nan')]},
    {"type": "Point", "coordinates": [150, -25, 0, 0]},
    {"type": "Polygon", "coordinates": [[[150,-25],[151,-25],[150,-24]]]},
    {"type": "Polygon", "coordinates": [[[150,-25],[150,-25],[150,-25],[150,-25]]]},
    {"type": "MultiPolygon", "coordinates": []}])
def test_bad_or_ambiguous_geometry_cannot_create_record(bad):
    item = feature(True)
    item['geometry'] = bad
    result = parse(feature(), item)
    assert result.invalid_count == 1
    assert len(result.records) == 1


@pytest.mark.parametrize("stamp", ["2026-09-14T20:00:00", "yesterday", 123, "x" * 65])
def test_invalid_offset_or_time_rejected(stamp):
    result = parse(feature(), feature(True, ItemDateTimeLocal_ISO=stamp))
    assert result.invalid_count == 1


def test_unknown_times_stay_unknown_and_text_is_bounded():
    result = parse(feature(WarningTitle="<b>Árvíztűrő</b> &amp; Synthetic",
                           ItemDateTimeLocal_ISO=None, ItemExpiryDateTimeLocal_ISO=None))
    report = result.records[0]
    assert report.title == "Árvíztűrő & Synthetic"
    assert report.event_updated_at is None
    assert report.expired_at(NOW) is None
    with pytest.raises(ValueError):
        parse(feature(WarningTitle="x" * 1001))


def test_duplicates_corrections_and_equal_revision_conflict_are_order_independent():
    old = feature()
    new = feature(WarningTitle="Revised", ItemDateTimeLocal_ISO="2026-09-14T19:00:00+10:00")
    assert parse(old, new).records == parse(new, old).records
    assert parse(old, new).records[0].title == "Revised"
    assert len(parse(new, new).records) == 1
    conflict = deepcopy(new)
    conflict['properties']['WarningTitle'] = "Contradiction"
    assert parse(new, conflict, old).records == ()
    assert parse(old, conflict, new).conflicted_ids == 1


@pytest.mark.parametrize("body", [b'null', b'[]', b'{', b'\xff', b'[' * 2000,
    b' ' * (MAX_BYTES + 1), payload(*([None] * (MAX_ITEMS + 1)))])
def test_invalid_or_oversized_document_fails(body):
    with pytest.raises(ValueError):
        parse_feed(body, retrieved_at=NOW)


def test_empty_success_and_all_invalid_are_distinct():
    assert parse().fetched_count == 0
    with pytest.raises(ValueError):
        parse({})
    with pytest.raises(ValueError):
        parse_feed(payload(), retrieved_at=NOW.replace(tzinfo=None))


def test_duplicate_json_keys_and_bad_optional_types_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        parse_feed(b'{"type":"FeatureCollection","features":[],"features":[]}', retrieved_at=NOW)
    with pytest.raises(ValueError):
        parse(feature(CurrentStatus=False))


def test_geometry_point_is_validated_and_vertex_budget_enforced():
    invalid = feature(UniqueID="other")
    invalid['geometry']['coordinates'] = [150, -91]
    assert parse(feature(), invalid).invalid_count == 1
    warning = feature(True)
    warning['geometry']['coordinates'] = [[[150, -25]] * 10001]
    assert parse(feature(), warning).invalid_count == 1
