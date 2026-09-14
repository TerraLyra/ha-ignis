"""Source-point matches, uncertain warning bounds and non-destructive time labels."""
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.terralyra_ignis.monitoring import MonitoredLocation
from custom_components.terralyra_ignis.official_sources.models import (
    GeometryRole, OfficialGeometry, OfficialReport, ParsedReports, RecordKind,
)
from custom_components.terralyra_ignis.official_sources.qld_client import QfdSnapshot
from custom_components.terralyra_ignis.official_sources.presentation import project_reports

NOW = datetime(2026, 9, 14, tzinfo=UTC)


def location(id="home", lat=-25, lon=150, radius=10, enabled=True):
    return MonitoredLocation(id, id, lat, lon, radius, enabled, "manual")


def report(**changes):
    values = dict(provider="test", source_id="1", kind=RecordKind.INCIDENT,
        jurisdiction="AU-QLD", title="Synthetic", source_url="https://example.org",
        attribution="Synthetic", geometry=OfficialGeometry(GeometryRole.INCIDENT_POINT,(150,-25)),
        raw_type="FIRE VEGETATION", raw_status="", raw_warning_level="Information",
        planned_burn=False, retrieved_at=NOW, event_updated_at=NOW-timedelta(hours=1),
        published_at=NOW, expires_at=NOW+timedelta(hours=1))
    return OfficialReport(**(values | changes))


def snapshot(*reports, status="available"):
    return QfdSnapshot(ParsedReports(reports,len(reports),0,0,0),status,NOW,NOW)


def test_overlap_is_one_report_with_distinct_distances_and_disabled_excluded():
    data = snapshot(report())
    result = project_reports(data,(location(),location("near",lat=-25.01),
        location("far",lat=40),location("disabled",enabled=False)),now=NOW)
    assert len(result.relevant) == 1
    matches = result.relevant[0].locations
    assert [m.location_id for m in matches] == ['home','near']
    assert matches[0].distance_km == 0 < matches[1].distance_km
    assert result.relevant[0].report is data.parsed.records[0]


def test_point_boundary_zero_radius_and_antimeridian():
    data = snapshot(report(geometry=OfficialGeometry(GeometryRole.INCIDENT_POINT,(179.99,0))))
    assert len(project_reports(data,(location(lat=0,lon=-179.99,radius=3),),now=NOW).relevant) == 1
    assert project_reports(data,(location(lat=0,lon=-179.99,radius=1),),now=NOW).outside_count == 1
    assert len(project_reports(snapshot(report()),(location(radius=0),),now=NOW).relevant) == 1


def test_warning_holes_exclude_circles_wholly_inside_hole():
    geometry = OfficialGeometry(GeometryRole.WARNING_AREA,(
        ((149,-26),(151,-26),(151,-24),(149,-24),(149,-26)),
        ((149.5,-25.5),(150.5,-25.5),(150.5,-24.5),(149.5,-24.5),(149.5,-25.5))))
    warning = report(kind=RecordKind.WARNING,geometry=geometry)
    result = project_reports(snapshot(warning),(location(radius=1),location("far",lat=40)),now=NOW)
    assert result.relevant == () and result.unresolved == ()
    assert result.outside_count == 1
    intersecting = project_reports(snapshot(warning),(location(lat=-25.75,radius=1),),now=NOW)
    assert intersecting.relevant[0].locations[0].relation == 'warning_area_intersects'
    assert intersecting.relevant[0].locations[0].distance_km is None


def test_warning_dateline_and_polar_cases_remain_unknown():
    warning = report(kind=RecordKind.WARNING,geometry=OfficialGeometry(GeometryRole.WARNING_AREA,
        (((179,-1),(-179,-1),(-179,1),(179,1),(179,-1)),)))
    result = project_reports(snapshot(warning),(location(lat=0,lon=180),),now=NOW)
    assert result.unresolved[0].locations[0].relation == 'geometry_unknown'
    assert not result.relevant


@pytest.mark.parametrize('changes,category',[
    ({'expires_at':NOW},'source_expiry_elapsed'),
    ({'expires_at':None},'uncertain_source_time'),
    ({'event_updated_at':None},'uncertain_source_time'),
    ({'event_updated_at':NOW+timedelta(hours=2)},'uncertain_source_time'),
    ({'published_at':NOW+timedelta(hours=2)},'uncertain_source_time'),
    ({},'source_expiry_not_elapsed'),
])
def test_time_labels_are_explicit_and_records_retained(changes,category):
    data = snapshot(report(**changes),status='stale')
    result = project_reports(data,(location(),),now=NOW)
    assert result.relevant[0].time_category == category
    assert 'feed_not_current' in result.relevant[0].notes
    assert result.relevant[0].report is data.parsed.records[0]


def test_time_ages_without_fetch_and_planned_burn_is_not_removed():
    data = snapshot(report(planned_burn=True))
    initial = project_reports(data,(location(),),now=NOW)
    later = project_reports(data,(location(),),now=NOW+timedelta(hours=2))
    assert initial.relevant[0].time_category == 'source_expiry_not_elapsed'
    assert later.relevant[0].time_category == 'source_expiry_elapsed'
    assert 'planned_burn_context_only' in later.relevant[0].notes
    assert len(data.parsed.records) == 1


def test_empty_unavailable_and_omissions_stay_distinct():
    missing = project_reports(QfdSnapshot(),(location(),),now=NOW)
    empty = project_reports(snapshot(),(location(),),now=NOW)
    assert missing.feed_status == 'unavailable' and empty.feed_status == 'available'
    partial = replace(snapshot(report()),status='partial',parsed=ParsedReports((report(),),4,1,1,1))
    result = project_reports(partial,(location(),),now=NOW)
    assert (result.filtered_count,result.invalid_count,result.conflicted_ids)==(1,1,1)
    assert 'feed_has_omissions' in result.relevant[0].notes


def test_disabled_all_and_invalid_locations():
    assert project_reports(snapshot(report()),(location(enabled=False),),now=NOW).relevant == ()
    for locs in [(location(),location()),(location(lat=float('nan')),),(location(radius=-1),)]:
        with pytest.raises(ValueError):
            project_reports(snapshot(report()),locs,now=NOW)
