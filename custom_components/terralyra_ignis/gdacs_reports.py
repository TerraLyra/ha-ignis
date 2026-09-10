"""Bounded GDACS context parsing; not satellite evidence or a live provider yet."""

import json
import math
from datetime import datetime
from html.parser import HTMLParser

ATTRIBUTION = "Global Disaster Alert and Coordination System, GDACS"
MAX_BYTES = 2_000_000
MAX_ITEMS = 100


class GdacsDataError(ValueError):
    """Reject invalid pages rather than silently claiming full coverage."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(value):
    if not isinstance(value, str) or len(value) > 10_000:
        raise GdacsDataError("Invalid text")
    parser = _Text()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())[:500]


def _identifier(value):
    if type(value) is not int or not 0 < value < 10**12:
        raise GdacsDataError("Invalid event identifier")
    return value


def _boolean(value):
    if type(value) is bool:
        return value
    if value in ("true", "false"):
        return value == "true"
    raise GdacsDataError("Invalid boolean")


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise GdacsDataError("Invalid timestamp")
    datetime.fromisoformat(value)
    return value  # Preserve upstream timezone ambiguity; never assume HA local time.


def parse_page(payload: bytes, status: int = 200) -> list[dict]:
    """Normalize one full page; retain duplicates for the archive to reconcile.

    No perimeter/radius or time matching is implied by these centroid records.
    Revisions must be keyed by uid, not by retrieval time or modified timestamp.
    """
    if status == 204:
        if payload:
            raise GdacsDataError("Unexpected body for empty response")
        return []
    if status != 200 or len(payload) > MAX_BYTES:
        raise GdacsDataError("Invalid response status or size")
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise GdacsDataError("Expected FeatureCollection")
        features = data.get("features")
        if not isinstance(features, list) or len(features) > MAX_ITEMS:
            raise GdacsDataError("Invalid page size")
        result = []
        for feature in features:
            if not isinstance(feature, dict) or feature.get("type") != "Feature":
                raise GdacsDataError("Invalid feature")
            props = feature["properties"]
            if props["eventtype"] != "WF":
                raise GdacsDataError("Unexpected hazard in wildfire page")
            event_id = _identifier(props["eventid"])
            episode_id = _identifier(props["episodeid"])
            geometry = feature["geometry"]
            if geometry["type"] != "Point":
                raise GdacsDataError("Expected event centroid")
            lon, lat = geometry["coordinates"]
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in (lon, lat)):
                raise GdacsDataError("Invalid coordinates")
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise GdacsDataError("Coordinates outside globe")
            start, end = _time(props["fromdate"]), _time(props["todate"])
            if datetime.fromisoformat(start) > datetime.fromisoformat(end):
                raise GdacsDataError("Reversed event interval")
            result.append({
                "provider": "gdacs", "uid": f"gdacs:WF:{event_id}",
                "event_id": event_id, "episode_id": episode_id,
                "title": _text(props.get("name") or props.get("description") or "Wildfire"),
                "publisher": ATTRIBUTION,
                "url": f"https://www.gdacs.org/report.aspx?eventid={event_id}&episodeid={episode_id}&eventtype=WF",
                "latitude": lat, "longitude": lon,
                "location_precision": "representative_point_not_ignition",
                "fromdate_raw": start, "todate_raw": end,
                "modified_raw": _time(props["datemodified"]),
                "time_semantics": "upstream_interval_not_verified_ignition_or_extinction",
                "is_current": _boolean(props["iscurrent"]),
                "is_temporary": _boolean(props["istemporary"]),
                "upstream_source": _text(props.get("source", "")),
                "country": _text(props.get("country", "")),
                "alert_level": _text(props.get("alertlevel", "")),
                "evidence_role": "context_only_not_independent_confirmation",
            })
        return result
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as err:
        raise GdacsDataError("Invalid GDACS wildfire page") from err
