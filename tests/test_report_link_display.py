"""Readable annotations retain uncertainty without exposing audit identifiers."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.terralyra_ignis.report_link_display import DETAILS, active_links, link_lines, local_time
from custom_components.terralyra_ignis.report_links import notice_fingerprint


@pytest.mark.parametrize("language", DETAILS)
def test_readable_link_preserves_review(language):
    link = {
        "link_id": "private-link-id",
        "report_title": "Egyek test report",
        "reviewed_at": "2026-09-10T11:09:12.076291+00:00",
        "review": {
            "report_url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
            "candidate": {
                "incident_id": "private-incident-id", "relation": "possible",
                "distance_km": 0.661,
                "first_seen": "2026-09-08T15:08:48+00:00",
                "last_seen": "2026-09-08T19:42:17+00:00",
            },
        },
    }
    original = deepcopy(link)
    lines = link_lines(link, language, "Europe/Budapest")
    text = "\n".join(lines)
    assert "Egyek test report" in lines[0]
    assert link["review"]["report_url"] in lines[1]
    assert DETAILS[language][1] in text
    assert "2026-09-08 17:08 CEST (UTC+0200)" in text
    assert "2026-09-08 21:42" in text
    assert "2026-09-10 13:09" in text
    assert "0.66 km" in text
    assert "private-" not in text and "076291" not in text
    assert link == original
    assert link_lines(link, "unknown", "UTC") == link_lines(link, "en", "UTC")


def test_repeated_dst_hour_is_unambiguous():
    assert local_time("2026-10-25T00:30:00+00:00", "Europe/Budapest") == "2026-10-25 02:30 CEST (UTC+0200)"
    assert local_time("2026-10-25T01:30:00+00:00", "Europe/Budapest") == "2026-10-25 02:30 CET (UTC+0100)"


async def test_existing_link_gets_local_title_without_storage_or_network_changes():
    notice = {"url": "https://example.test/report", "title": "Archived title"}
    incident = {"track_id": "one", "first_seen": "2026-09-08T15:08:48+00:00"}
    saved = {"review": {
        "report_url": notice["url"], "report_fingerprint": notice_fingerprint(notice),
        "candidate": {"incident_id": "one", "first_seen": incident["first_seen"]},
    }}
    original = deepcopy(saved)
    store = SimpleNamespace(async_list=AsyncMock(return_value=[saved]))
    client = SimpleNamespace(archive=SimpleNamespace(async_merge=AsyncMock(return_value=[notice])))
    hass = SimpleNamespace(data={"terralyra_ignis": {
        "official_report_links": store, "official_report_client": client,
    }})
    result = await active_links(hass, "entry", [incident])
    assert result[0]["report_title"] == "Archived title"
    assert saved == original
    store.async_list.assert_awaited_once_with("entry")
    client.archive.async_merge.assert_awaited_once_with()
    assert not await active_links(hass, "entry", [incident], [{**notice, "title": "Revised"}])
    assert not await active_links(hass, "entry", [], [notice])
