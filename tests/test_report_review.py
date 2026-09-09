"""Non-mutating review against local satellite history."""

from copy import deepcopy

import pytest

from custom_components.terralyra_ignis.report_review import review_notice

NOTICE = {
    "url": "https://www.katasztrofavedelem.hu/modules/vesz/esemeny/123",
    "publisher": "BM OKF", "title": "Synthetic fire notice",
    "published_at": "2026-09-09T14:21:00+02:00",
    "reported_start_date_hint": "2026-09-08",
}
HISTORY = [{
    "track_id": "night", "latitude": 47.61, "longitude": 21.0,
    "first_seen": "2026-09-09T03:05:00+02:00", "last_seen": "2026-09-09T03:05:00+02:00",
}, {
    "track_id": "day", "latitude": 47.62, "longitude": 21.0,
    "first_seen": "2026-09-09T12:38:00+02:00", "last_seen": "2026-09-09T16:08:00+02:00",
}]
INPUT = {"latitude": 47.615, "longitude": 21.0, "location_uncertainty_km": 5}


def test_review_uses_publication_not_unreviewed_hint_and_preserves_input():
    original = deepcopy(HISTORY)
    result = review_notice(HISTORY, NOTICE, **INPUT)
    assert [item["incident_id"] for item in result["candidates"]] == ["day"]
    assert result["time_basis"] == "publication_only"
    assert result["publisher"] == "BM OKF"
    assert result["changes_applied"] is False
    assert HISTORY == original


def test_explicit_broad_window_returns_multiple_candidates_without_merging():
    result = review_notice(HISTORY, NOTICE, **INPUT,
        event_start="2026-09-08T00:00:00+02:00", event_end="2026-09-09T14:21:00+02:00")
    assert len(result["candidates"]) == 2
    assert all(item["relation"] == "possible" for item in result["candidates"])
    assert all("multiple_candidate_incidents" in item["reasons"] for item in result["candidates"])
    assert result["coordinate_basis"] == "user_supplied_not_rss"


@pytest.mark.parametrize("extra", [
    {"event_end": "2026-09-09T14:21:00+02:00"},
    {"event_start": "2026-09-09T01:00:00"},
    {"event_start": "invalid"},
    {"event_start": "2026-09-10T00:00:00+02:00", "event_end": "2026-09-09T00:00:00+02:00"},
])
def test_invalid_event_window_rejected(extra):
    with pytest.raises(ValueError):
        review_notice(HISTORY, NOTICE, **INPUT, **extra)


def test_incomplete_and_duplicate_history_is_reported():
    result = review_notice([{}, *HISTORY, HISTORY[0]], NOTICE, **INPUT)
    assert result["history_records_checked"] == 2
    assert result["history_records_skipped"] == 2


def test_limit_and_empty_history():
    with pytest.raises(ValueError):
        review_notice(HISTORY * 251, NOTICE, **INPUT)
    assert review_notice([], NOTICE, **INPUT)["candidates"] == []
