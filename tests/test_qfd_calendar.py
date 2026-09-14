"""Opt-in QFD reports: bounded scope, time labels and worker rendering."""
from datetime import UTC, datetime, timedelta
from dataclasses import replace
from unittest.mock import AsyncMock, patch
import threading
import asyncio
import logging
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform
from zoneinfo import ZoneInfo

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.qfd_calendar import QfdCalendar, _render
from custom_components.terralyra_ignis.monitoring import MonitoredLocation
from custom_components.terralyra_ignis.official_sources.models import OfficialReport, OfficialGeometry, GeometryRole, RecordKind, ParsedReports
from custom_components.terralyra_ignis.official_sources.qld_client import QfdSnapshot

NOW = datetime(2026,9,14,20,tzinfo=UTC)
START = datetime(2026,9,13,tzinfo=UTC)
END = datetime(2026,9,17,tzinfo=UTC)
LOC = MonitoredLocation('home','Home',-25,150,10,True,'manual')


def record(**changes):
    r=OfficialReport('qld_qfd','test',RecordKind.INCIDENT,'AU-QLD','Synthetic',
        'https://www.fire.qld.gov.au/Current-Incidents','Queensland Fire Department; CC BY 4.0',
        OfficialGeometry(GeometryRole.INCIDENT_POINT,(150,-25)),
        'FIRE VEGETATION','','Information',False,NOW,
        event_updated_at=NOW-timedelta(hours=1),published_at=NOW,
        expires_at=NOW+timedelta(hours=1))
    return replace(r,**changes)


def snapshot(*records,status='available'):
    return QfdSnapshot(ParsedReports(records,len(records),0,0,0),status,NOW,NOW)


async def test_default_disabled_no_fetch_until_requested_and_executor_used(hass,freezer):
    freezer.move_to(NOW)
    entry=MockConfigEntry(domain='terralyra_ignis');entry.add_to_hass(hass)
    client=AsyncMock();client.async_get_reports.return_value=snapshot(record())
    entity=QfdCalendar(hass,entry,client)
    assert entity.entity_registry_enabled_default is False and entity.event is None
    client.async_get_reports.assert_not_called()
    assert entity.extra_state_attributes["undated_reports_last_query"] is None
    thread_ids=[]
    def rendered(*args):
        thread_ids.append(threading.get_ident())
        return _render(*args)
    try:
        with patch('custom_components.terralyra_ignis.qfd_calendar.resolve_monitored_locations',return_value=(LOC,)),patch('custom_components.terralyra_ignis.qfd_calendar._render',side_effect=rendered),patch.object(hass,'async_add_executor_job',side_effect=asyncio.to_thread):
            events=await entity.async_get_events(hass,START,END)
            assert len(events)==1
            assert thread_ids[0] != threading.get_ident()
            assert 'not ignition time' in events[0].description
            assert events[0].uid == 'qld_qfd:test'
            assert entity.extra_state_attributes['undated_reports_last_query'] == 0
    finally:
        await entity.coordinator.async_shutdown()


def test_overlap_dates_hungarian_and_elapsed_context():
    data=snapshot(record(expires_at=NOW-timedelta(hours=1),planned_burn=True),status='stale')
    events,_=_render(data,(LOC,replace(LOC,id='near',name='Near',longitude=150.01),
        replace(LOC,id='far',name='Far',latitude=40),replace(LOC,id='off',enabled=False)),
        NOW,START,END,ZoneInfo('Europe/Budapest'),True)
    assert len(events)==1
    event=events[0]
    assert event.start.isoformat()=='2026-09-15' # Queensland date, not UTC date.
    assert 'Home' in event.description and 'Near' in event.description
    assert 'Far' not in event.description
    assert 'Elmúlt forrásoldali lejárat' in event.summary
    assert 'Tervezett égetés' in event.summary and 'stale' in event.summary
    assert 'Queensland Fire Department' in event.description
    assert _render(data,(LOC,),NOW,START,datetime(2026,9,14,22,tzinfo=UTC),ZoneInfo('Europe/Budapest'),True)[0]==[]


def test_warning_area_and_missing_date_do_not_invent_point_or_date():
    geometry=OfficialGeometry(GeometryRole.WARNING_AREA,(((149,-26),(151,-26),(151,-24),(149,-24),(149,-26)),))
    warning=record(kind=RecordKind.WARNING,geometry=geometry,raw_warning_level='Advice')
    events,_=_render(snapshot(warning),(LOC,),NOW,START,END,ZoneInfo('UTC'),False)
    assert 'Warning' in events[0].summary and 'warning area' in events[0].description
    assert '0.0 km' not in events[0].description
    assert _render(snapshot(record(event_updated_at=None,published_at=None)),(LOC,),NOW,START,END,ZoneInfo('UTC'),False)[0]==[]
    fallback,_=_render(snapshot(record(event_updated_at=None)),(LOC,),NOW,START,END,ZoneInfo('UTC'),False)
    assert 'Uncertain source time' in fallback[0].summary and 'publication_fallback' in fallback[0].description


async def test_unavailable_and_no_enabled_location(hass):
    entry=MockConfigEntry(domain='terralyra_ignis');entry.add_to_hass(hass)
    client=AsyncMock();client.async_get_reports.return_value=QfdSnapshot()
    entity=QfdCalendar(hass,entry,client)
    try:
        with patch('custom_components.terralyra_ignis.qfd_calendar.resolve_monitored_locations',return_value=(LOC,)):
            with pytest.raises(HomeAssistantError):await entity.async_get_events(hass,START,END)
    finally:await entity.coordinator.async_shutdown()
    client.reset_mock()
    entity=QfdCalendar(hass,entry,client)
    try:
        with patch('custom_components.terralyra_ignis.qfd_calendar.resolve_monitored_locations',return_value=()):
            assert await entity.async_get_events(hass,START,END)==[]
            client.async_get_reports.assert_not_called()
    finally:await entity.coordinator.async_shutdown()


def test_unknown_geometry_is_not_presented_as_local_warning():
    geometry=OfficialGeometry(GeometryRole.WARNING_AREA,(((149,-26),(151,-24),(149,-24),(151,-26),(149,-26)),))
    events,projection=_render(snapshot(record(kind=RecordKind.WARNING,geometry=geometry)),(LOC,),NOW,START,END,ZoneInfo('UTC'),False)
    assert events==[] and len(projection.unresolved)==1


async def test_real_registration_default_disabled_enable_and_unload(hass):
    entry=MockConfigEntry(domain='terralyra_ignis');entry.add_to_hass(hass)
    client=AsyncMock();client.async_get_reports.return_value=snapshot()
    entity=QfdCalendar(hass,entry,client)
    platform=EntityPlatform(hass=hass,logger=logging.getLogger(__name__),domain='calendar',
        platform_name='terralyra_ignis',platform=None,scan_interval=timedelta(seconds=30),entity_namespace=None)
    platform.config_entry=entry
    with patch('custom_components.terralyra_ignis.qfd_calendar.resolve_monitored_locations',return_value=(LOC,)):
        await platform.async_add_entities([entity])
        client.async_get_reports.assert_not_called()
        registry=er.async_get(hass)
        entity_id=registry.async_get_entity_id('calendar','terralyra_ignis',entity.unique_id)
        assert registry.async_get(entity_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION
        registry.async_update_entity(entity_id,disabled_by=None)
        entity=QfdCalendar(hass,entry,client)
        await platform.async_add_entities([entity])
        client.async_get_reports.assert_awaited_once()
        assert list(entity.coordinator.async_contexts())
        await platform.async_remove_entity(entity.entity_id)
        assert not list(entity.coordinator.async_contexts())
        await entity.coordinator.async_shutdown()
