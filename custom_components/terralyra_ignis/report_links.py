"""Bounded, reversible manual report links, separate from satellite evidence."""

import asyncio
import json
import re
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from .official_reports import NOTICE_URL
from .report_context import FireReport, IncidentContext

MAX_LINKS = 1000
RETENTION = timedelta(days=30)
REASONS = {
    "compatible_time", "nearby_location", "publication_time_only",
    "imprecise_event_time", "imprecise_location_match", "multiple_candidate_incidents",
}


def fingerprint(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def notice_fingerprint(notice: dict) -> str:
    """A revised publication requires a new review, even at the same URL."""
    return fingerprint({key: notice.get(key, "") for key in ("url", "title", "description", "published_at")})


def review_payload(notice: dict, inputs: dict, candidate: dict) -> dict:
    return {
        "report_url": notice["url"], "report_fingerprint": notice_fingerprint(notice),
        "input": {key: inputs.get(key) for key in (
            "latitude", "longitude", "location_uncertainty_km", "event_start", "event_end",
        )},
        "candidate": {key: value for key, value in candidate.items() if key != "review_token"},
    }


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timezone required")
    return parsed


def _identity(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Invalid identity")
    return value


def _clean(raw: dict, now: datetime) -> dict:
    """Revalidate disk records; discard unknown fields and invalid provenance."""
    entry_id = _identity(raw["config_entry_id"])
    reviewed = _time(raw["reviewed_at"])
    expires = _time(raw["expires_at"])
    if not now - RETENTION <= reviewed <= now < expires <= reviewed + RETENTION:
        raise ValueError("Expired or invalid review")
    payload = raw["review"]
    if not NOTICE_URL.fullmatch(payload["report_url"]):
        raise ValueError("Invalid source")
    if not re.fullmatch(r"[a-f0-9]{64}", payload["report_fingerprint"]):
        raise ValueError("Invalid publication fingerprint")
    inputs = payload["input"]
    report = FireReport(
        url=payload["report_url"], publisher="BM OKF", language="hu", published_at=reviewed,
        latitude=inputs["latitude"], longitude=inputs["longitude"],
        location_uncertainty_km=inputs["location_uncertainty_km"],
        event_start=_time(inputs["event_start"]) if inputs.get("event_start") else None,
        event_end=_time(inputs["event_end"]) if inputs.get("event_end") else None,
    )
    candidate = payload["candidate"]
    incident = IncidentContext(
        incident_id=_identity(candidate["incident_id"]), latitude=candidate["latitude"],
        longitude=candidate["longitude"], first_seen=_time(candidate["first_seen"]),
        last_seen=_time(candidate["last_seen"]),
    )
    reasons = candidate["reasons"]
    if (candidate["relation"] not in ("possible", "probable")
        or not isinstance(reasons, list) or not reasons or len(reasons) > len(REASONS)
        or any(not isinstance(reason, str) or reason not in REASONS for reason in reasons)
        or not 0 <= candidate["distance_km"] <= 8):
        raise ValueError("Invalid candidate")
    for key in ("providers", "satellites"):
        labels = candidate[key]
        if not isinstance(labels, list) or len(labels) > 32 or any(not isinstance(v, str) or len(v) > 100 for v in labels):
            raise ValueError("Invalid source metadata")
    clean_candidate = {key: candidate[key] for key in (
        "incident_id", "latitude", "longitude", "first_seen", "last_seen", "providers",
        "satellites", "relation", "reasons", "distance_km",
    )}
    clean_payload = {
        "report_url": report.url, "report_fingerprint": payload["report_fingerprint"],
        "input": {key: inputs.get(key) for key in (
            "latitude", "longitude", "location_uncertainty_km", "event_start", "event_end",
        )}, "candidate": clean_candidate,
    }
    # Also reject NaN/infinite values and excessively large serialized records.
    if len(json.dumps(clean_payload, allow_nan=False)) > 12000:
        raise ValueError("Review too large")
    return {
        "config_entry_id": entry_id,
        "link_id": fingerprint([entry_id, report.url, incident.incident_id]),
        "reviewed_at": reviewed.isoformat(), "expires_at": expires.isoformat(),
        "approval": "manual_review_not_official_confirmation", "review": clean_payload,
    }


class ReportLinks:
    """Atomic local persistence with entry isolation, lazy expiry and no polling."""

    def __init__(self, store):
        self._store = store
        self._lock = asyncio.Lock()
        self._records = None

    async def _load(self, now):
        if self._records is None:
            saved = await self._store.async_load()
            self._records = saved.get("links", []) if isinstance(saved, dict) else []
            if not isinstance(self._records, list):
                self._records = []
        records = {}
        for raw in self._records[:MAX_LINKS]:
            try:
                clean = _clean(raw, now)
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
            records[clean["link_id"]] = clean
        return list(records.values())

    async def _save(self, records):
        if records != self._records:
            await self._store.async_save({"links": records})
            self._records = records

    async def async_list(self, entry_id: str) -> list[dict]:
        async with self._lock:
            records = await self._load(datetime.now(UTC))
            await self._save(records)
            return deepcopy([r for r in records if r["config_entry_id"] == entry_id])

    async def async_add(self, entry_id: str, notice: dict, inputs: dict, candidate: dict) -> dict:
        async with self._lock:
            now = datetime.now(UTC)
            record = _clean({
                "config_entry_id": entry_id, "reviewed_at": now.isoformat(),
                "expires_at": min(now + RETENTION, _time(notice["published_at"]) + RETENTION).isoformat(),
                "review": review_payload(notice, inputs, candidate),
            }, now)
            records = await self._load(now)
            existing = next((r for r in records if r["link_id"] == record["link_id"]), None)
            if existing and existing["review"] == record["review"]:
                return deepcopy(existing)
            if existing is None and len(records) >= MAX_LINKS:
                raise ValueError("Manual link limit reached; remove an old link first")
            records = [r for r in records if r["link_id"] != record["link_id"]] + [record]
            await self._save(records)
            return deepcopy(record)

    async def async_remove(self, entry_id: str, link_id: str) -> bool:
        async with self._lock:
            records = await self._load(datetime.now(UTC))
            kept = [r for r in records if not (r["config_entry_id"] == entry_id and r["link_id"] == link_id)]
            removed = len(kept) != len(records)
            await self._save(kept)
            return removed


def resolve_links(links: list[dict], history: list[dict], notices: list[dict]) -> list[dict]:
    """Stale links stay inspectable but never decorate unrelated/reused IDs."""
    records = {r.get("track_id"): r for r in history}
    reports = {n["url"]: n for n in notices}
    result = []
    for link in links:
        payload = link["review"]
        candidate = payload["candidate"]
        record = records.get(candidate["incident_id"])
        notice = reports.get(payload["report_url"])
        if record is None:
            status = "incident_missing"
        else:
            try:
                same_identity = _time(record["first_seen"]) == _time(candidate["first_seen"])
            except (KeyError, TypeError, ValueError):
                same_identity = False
            if not same_identity:
                status = "incident_identity_changed"
            elif notice is None:
                status = "report_missing"
            elif notice_fingerprint(notice) != payload["report_fingerprint"]:
                status = "report_changed"
            else:
                status = "active"
        result.append({**deepcopy(link), "status": status})
    return result
