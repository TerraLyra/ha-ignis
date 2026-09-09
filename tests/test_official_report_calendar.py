"""Optional publication calendar must not masquerade as incident history."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terralyra_ignis.official_report_calendar import (
    OfficialReportCalendar,
)
from custom_components.terralyra_ignis.official_reports import ATTRIBUTION


def notice(number=1, published="2026-09-09T09:13:00+00:00"):
    return {
        "title": "Kigyulladt a nádas",
        "publisher": ATTRIBUTION,
        "url": f"https://www.katasztrofavedelem.hu/modules/vesz/esemeny/{number}",
        "published_at": published,
        "association": "not_matched",
    }


def calendar(hass, response):
    client = AsyncMock()
    client.async_get_archived_notices.return_value = response
    entry = MockConfigEntry(domain="terralyra_ignis")
    entry.add_to_hass(hass)
    return OfficialReportCalendar(hass, entry, client), client


async def test_disabled_by_default_and_no_initial_network(hass):
    entity, client = calendar(hass, {"status": "available", "notices": []})
    assert entity.entity_registry_enabled_default is False
    assert entity.event is None
    assert entity.coordinator.update_interval.total_seconds() == 900
    client.async_get_archived_notices.assert_not_called()


async def test_publications_have_attribution_stable_id_and_explicit_limitations(hass):
    hass.config.language = "hu"
    entity, client = calendar(hass, {"status": "available", "notices": [notice()]})
    events = await entity.async_get_events(
        hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC)
    )
    event, = events
    assert event.summary.startswith("BM OKF · ")
    assert event.uid == notice()["url"]
    assert ATTRIBUTION in event.description
    assert notice()["url"] in event.description
    assert "Közzétételi idő" in event.description
    assert "Nincs műholdas észleléshez párosítva" in event.description
    assert "nem teljes archívum" in event.description
    assert (event.end - event.start).total_seconds() == 60
    assert entity.event is None
    client.async_get_archived_notices.assert_awaited_once()
    await entity.coordinator.async_shutdown()


async def test_date_window_overlap_and_order(hass):
    entity, _ = calendar(hass, {"status": "available", "notices": [
        notice(3, "2026-09-10T00:00:00+00:00"),
        notice(2, "2026-09-09T11:00:00+00:00"),
        notice(1, "2026-09-08T23:59:30+00:00"),
        notice(4, "2026-09-08T23:59:00+00:00"),
    ]})
    events = await entity.async_get_events(
        hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC)
    )
    assert [event.uid.rsplit("/", 1)[-1] for event in events] == ["1", "2"]
    await entity.coordinator.async_shutdown()


async def test_failed_feed_is_not_an_empty_success_or_old_news(hass):
    entity, _ = calendar(hass, {"status": "unavailable", "notices": []})
    with pytest.raises(HomeAssistantError):
        await entity.async_get_events(
            hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC)
        )
    assert not entity.available
    await entity.coordinator.async_shutdown()


async def test_empty_feed_and_unsupported_language(hass):
    hass.config.language = "xx"
    entity, _ = calendar(hass, {"status": "available", "notices": []})
    assert await entity.async_get_events(
        hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC)
    ) == []
    await entity.coordinator.async_shutdown()


async def test_archived_calendar_during_feed_outage(hass):
    item = notice() | {"archive_origin": "manual_import", "description": "Saved text"}
    entity, _ = calendar(hass, {"status": "available", "feed_status": "unavailable", "notices": [item]})
    events = await entity.async_get_events(hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC))
    assert "manual_import" in events[0].description
    assert "Live RSS: unavailable" in events[0].description
    assert "Saved text" in events[0].description
    await entity.coordinator.async_shutdown()


async def test_calendar_filters_nonfire_without_deleting_archive(hass):
    from copy import deepcopy

    reports = [notice(1), notice(2) | {"title": "Elsőfokú riasztást adott ki zivatarok kialakulása miatt a HungaroMet"},
               notice(3) | {"title": "Karambol történt", "description": "A tűzoltók áramtalanítottak."},
               notice(4) | {"title": "Beavatkozás Egyeken"}]
    original = deepcopy(reports)
    entity, _ = calendar(hass, {"status": "available", "notices": reports})
    events = await entity.async_get_events(hass, datetime(2026, 9, 9, tzinfo=UTC), datetime(2026, 9, 10, tzinfo=UTC))
    assert [event.uid for event in events] == [reports[0]["url"]]
    assert "explicit_fire_language_in_title" in events[0].description
    assert reports == original
    assert entity.coordinator.data["notices"] == original
    await entity.coordinator.async_shutdown()
