# 0.24.4 — acquisition-time observation counters

Update through HACS and restart Home Assistant. No dashboard migration is
required. The recent-detections entity keeps its identity, but its 1/3/6-hour
values now count distinct source observations acquired within each interval.
These values are not unique physical fire counts: a later scan or another
satellite can legitimately provide another observation of the same incident.

Repeated downloads and fresh empty peer products no longer recount cached
observations. Acquisitions older than a window or in the future are excluded.
Successful unchanged-product polls age the counters without rerunning tracking.
Distinct observation identities survive restart in a bounded six-hour ledger.

Old aggregate counts cannot be converted accurately and are not used to seed
the new ledger. Currently returned observations can populate it on first fetch.
Counts may therefore drop at upgrade. `window_collection_complete` exposes
whether 1/3/6 hours of collection time have elapsed; `retention_limited` warns
when the 20,000-record limit has caused eviction. Neither flag guarantees
complete satellite coverage. Provider outages remain independently reported.

Existing Home Assistant Recorder graphs retain the old values; there is no
automatic history deletion. FRP and new-incident aggregates remain separate.
The specific September 10 historical spike is not conclusively attributed.

See [investigation](ACTIVITY_COUNTER_INVESTIGATION.md) for the reproduced
mechanisms and regression scenarios.
