"""Conservative report matching with synthetic, non-confirmatory examples."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.terralyra_ignis.report_context import (
    FireReport,
    IncidentContext,
    match_reports,
)

NOW = datetime(2026, 9, 8, 19, tzinfo=UTC)
INCIDENT = IncidentContext("incident", 47.6, 21.0, NOW, NOW)
REPORT = FireReport(
    "https://example.org/fire", "Example publisher", NOW, "hu",
    47.6, 21.0, 0.5, event_start=NOW,
)


def test_precise_report_is_probable_but_never_confirmed() -> None:
    result, = match_reports((INCIDENT,), (REPORT,))
    assert result.relation == "probable"
    assert result.reports == (REPORT,)
    assert result.incident_id == INCIDENT.incident_id


def test_publication_time_is_not_an_event_timestamp() -> None:
    result, = match_reports((INCIDENT,), (replace(REPORT, event_start=None),))
    assert result.relation == "possible"
    assert "publication_time_only" in result.reasons


def test_nearby_distinct_incidents_are_not_silently_resolved() -> None:
    other = replace(INCIDENT, incident_id="other", latitude=47.61)
    results = match_reports((INCIDENT, other), (REPORT,))
    assert len(results) == 2
    assert all(result.relation == "possible" for result in results)
    assert all("multiple_candidate_incidents" in result.reasons for result in results)


def test_syndicated_news_and_original_notice_share_one_family() -> None:
    official = replace(REPORT, source_kind="official", publisher="Fire service")
    news = replace(REPORT, url="https://example.org/article", origin_url=REPORT.url)
    result, = match_reports((INCIDENT,), (news, official))
    assert result.origin_url == REPORT.url
    assert len(result.reports) == 2
    assert match_reports((INCIDENT,), (official, news)) == (result,)


def test_different_day_or_distant_place_is_rejected() -> None:
    assert not match_reports((INCIDENT,), (replace(REPORT, event_start=NOW - timedelta(days=3)),))
    assert not match_reports((INCIDENT,), (replace(REPORT, latitude=48.6),))
    assert not match_reports((), (REPORT,))
    assert not match_reports((INCIDENT,), ())


def test_precise_event_can_be_reported_days_later() -> None:
    result, = match_reports((INCIDENT,), (replace(REPORT, published_at=NOW + timedelta(days=3)),))
    assert result.relation == "probable"


def test_uncertain_position_or_day_wide_time_stays_possible() -> None:
    for report in (
        replace(REPORT, location_uncertainty_km=10),
        replace(REPORT, event_end=NOW + timedelta(days=1)),
    ):
        result, = match_reports((INCIDENT,), (report,))
        assert result.relation == "possible"


@pytest.mark.parametrize("changes", [
    {"url": "javascript:alert(1)"},
    {"url": "https://user:password@example.org/fire"},  # pragma: allowlist secret - synthetic rejection test
    {"latitude": float("nan")},
    {"location_uncertainty_km": -1},
    {"published_at": NOW.replace(tzinfo=None)},
    {"event_end": NOW - timedelta(hours=1)},
])
def test_invalid_report_metadata_is_rejected(changes) -> None:
    with pytest.raises(ValueError):
        replace(REPORT, **changes)


def test_input_work_is_bounded() -> None:
    with pytest.raises(ValueError):
        match_reports((INCIDENT,), (REPORT,) * 101)
    with pytest.raises(ValueError):
        match_reports((INCIDENT, INCIDENT), (REPORT,))
