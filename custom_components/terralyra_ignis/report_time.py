"""Review-only date hints from a narrow set of Hungarian RSS expressions."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_YESTERDAY_IGNITION = re.compile(
    r"\btegnap(?:\s+(?:kora|késő|reggel|délelőtt|délután|este|éjjel|hajnalban)){0,3}"
    r"\s+gyulladt\s+(?:meg|ki)\b",
    re.IGNORECASE,
)


def hungarian_start_hint(description: str, published: datetime) -> dict[str, str]:
    """Return a candidate date, never a precise ignition or extinction time.

    Relative words anchor to publication in Hungary, not retrieval or UTC date.
    Hints require review: a notice may describe another fire or quote old text.
    Unrecognized, negated or multiple mentions deliberately remain unknown.
    """
    unknown = {"event_time_status": "unknown"}
    if published.tzinfo is None or published.utcoffset() is None:
        return unknown
    matches = list(_YESTERDAY_IGNITION.finditer(description))
    if len(matches) != 1 or re.search(r"\b(?:nem|sem)\b", description, re.IGNORECASE):
        return unknown
    try:
        day = published.astimezone(ZoneInfo("Europe/Budapest")).date() - timedelta(days=1)
    except (ValueError, OverflowError):
        return unknown
    return {
        "event_time_status": "requires_review",
        "reported_start_date_hint": day.isoformat(),
        "reported_start_precision": "day",
        "reported_start_evidence": matches[0].group(),
        "reported_start_timezone": "Europe/Budapest",
    }
