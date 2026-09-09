"""Date clues are review-only, publication-local and never exact timestamps."""

from datetime import datetime

import pytest

from custom_components.terralyra_ignis.report_time import hungarian_start_hint


def test_egyek_wording_preserves_day_precision_and_original_evidence():
    result = hungarian_start_hint(
        "A területen még tegnap kora este gyulladt meg a nádas.",
        datetime.fromisoformat("2026-09-09T14:21:00+02:00"),
    )
    assert result["reported_start_date_hint"] == "2026-09-08"
    assert result["reported_start_evidence"] == "tegnap kora este gyulladt meg"
    assert result["event_time_status"] == "requires_review"
    assert result["reported_start_precision"] == "day"
    assert "event_start" not in result and "event_end" not in result


@pytest.mark.parametrize("published,expected", [
    ("2026-09-08T23:30:00+00:00", "2026-09-08"),
    ("2026-01-01T00:30:00+01:00", "2025-12-31"),
    ("2026-03-29T03:30:00+02:00", "2026-03-28"),
    ("2026-10-25T03:30:00+01:00", "2026-10-24"),
])
def test_local_date_boundaries_and_dst(published, expected):
    result = hungarian_start_hint("Tegnap gyulladt ki a tűz.", datetime.fromisoformat(published))
    assert result["reported_start_date_hint"] == expected


@pytest.mark.parametrize("text", [
    "Tegnap vonultak ki a tűzoltók.",
    "Nem tegnap gyulladt ki a tűz.",
    "Tegnapelőtt gyulladt ki a tűz.",
    "Tegnap gyulladt ki az egyik, tegnap gyulladt ki a másik.",
    "A tűz ma kezdődött.",
    "",
])
def test_unsupported_or_ambiguous_text_is_unknown(text):
    assert hungarian_start_hint(text, datetime.fromisoformat("2026-09-09T14:21:00+02:00")) == {"event_time_status": "unknown"}


def test_naive_date_is_unknown():
    naive = datetime(2026, 9, 9)  # noqa: DTZ001 - intentional invalid-input test
    assert hungarian_start_hint("Tegnap gyulladt ki.", naive) == {"event_time_status": "unknown"}
