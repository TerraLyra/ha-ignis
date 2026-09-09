"""Bounded local publication archive; never a source of fire detections."""

import asyncio
from datetime import UTC, datetime, timedelta

from .official_reports import ATTRIBUTION, NOTICE_URL, _text
from .report_time import hungarian_start_hint

RETENTION_DAYS = 30
MAX_RECORDS = 1000


def clean_record(record: dict, now: datetime) -> dict:
    """Revalidate persisted/imported text; discard untrusted extra fields."""
    if not isinstance(record, dict) or not all(isinstance(record.get(k, ""), str) for k in ("url", "published_at", "title", "description")):
        raise ValueError("Invalid report fields")
    url = record["url"]
    published = datetime.fromisoformat(record["published_at"])
    if (not isinstance(url, str) or not NOTICE_URL.fullmatch(url)
        or published.tzinfo is None
        or not now - timedelta(days=RETENTION_DAYS) <= published <= now):
        raise ValueError("Invalid URL or publication date outside the 30-day archive window")
    title = _text(record["title"])
    if not title:
        raise ValueError("A title is required")
    description = _text(record.get("description", ""), 4001)
    truncated = len(description) > 4000 or record.get("description_status") == "truncated"
    return {
        "url": url, "title": title, "published_at": published.astimezone(UTC).isoformat(),
        "publisher": ATTRIBUTION, "language": "hu", "association": "not_matched",
        "description": description[:4000],
        "description_status": "truncated" if truncated else "complete",
        **({"event_time_status": "unknown"} if truncated else hungarian_start_hint(description, published)),
        "archive_origin": "rss" if record.get("archive_origin") == "rss" else "manual_import",
    }


class ReportArchive:
    """Serialize load/merge/save, deduplicate by source URL and survive restarts."""

    def __init__(self, store) -> None:
        self._store = store
        self._lock = asyncio.Lock()
        self._records = None

    async def async_merge(self, notices=(), *, origin="rss") -> list[dict]:
        async with self._lock:
            now = datetime.now(UTC)
            if self._records is None:
                saved = await self._store.async_load()
                self._records = saved.get("notices", []) if isinstance(saved, dict) else []
                if not isinstance(self._records, list):
                    self._records = []
            records = {}
            for raw in self._records[:MAX_RECORDS]:
                try:
                    record = clean_record(raw, now)
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                records[record["url"]] = record
            for raw in list(notices)[:100]:
                try:
                    record = clean_record(dict(raw, archive_origin=origin), now)
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                # A manual import must not overwrite an actual RSS observation.
                if origin == "manual_import" and records.get(record["url"], {}).get("archive_origin") == "rss":
                    continue
                records[record["url"]] = record
            result = sorted(records.values(), key=lambda n: (n["published_at"], n["url"]), reverse=True)[:MAX_RECORDS]
            if result != self._records:
                await self._store.async_save({"notices": result})
                self._records = result
            return [dict(n) for n in result]

    async def async_import(self, record: dict) -> dict:
        record = clean_record(record, datetime.now(UTC))
        await self.async_merge([record], origin="manual_import")
        return {"status": "archived", "url": record["url"], "changes_to_incidents": False}
