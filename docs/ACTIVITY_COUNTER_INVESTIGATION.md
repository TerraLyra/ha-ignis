# Activity counter investigation — 2026-09-11

Scope: diagnosis against the 0.24.3 code. No production logic or Recorder data
was changed during this investigation. The historical September 10 spike has
not been attributed conclusively; screenshots do not contain its raw inputs.

## Reproduced mechanisms

The replay used the real MultiProviderPool, update_activity_history and
summarize_activity functions with mocked providers (no network/HA writes).

1. Provider A repeatedly returns one unchanged detection acquired 12 hours ago.
2. Provider B returns empty products at minutes 0, 10, 20, 30, 40 and 50.
3. The pool's maximum product timestamp advances with B. Its merged detection
   tuple still contains A's unchanged detection.
4. Feeding the merged count into history, as the coordinator does after
   location/confidence/FRP filtering, produces hourly counts 1, 2, 3, 4, 5, 6.
   There is one distinct detection, zero acquired within the last hour.

The coordinator filters location, confidence and FRP before this count, but
does not filter detection acquisition age. Current clustering corrections do
not fix this separate len(filtered) aggregation path.

Additionally, summarizing those records with now two hours before the first
record still returns 6: window() checks only the lower bound. A pool timestamp
can regress when the freshest provider fails and an older peer still succeeds.
That transition requires an end-to-end regression test before implementing a fix.

## Required correction design

- Define the metric as distinct source observations by acquisition time,
  rather than the sum of snapshot sizes by product publication time.
- Deduplicate repeated source observations across refreshes and restarts using
  stable provider/satellite identities plus observation identity/time.
- Preserve separate observations of the same fire at different times; this is
  not the same as counting unique fire incidents.
- Bound windows on both sides and evaluate against a non-regressing clock.
- Keep FRP snapshot history and new-incident counts separate from observation
  counts; do not infer new incidents from backfilled observations.
- Version persisted activity data: old aggregate counts cannot be accurately
  converted into unique observations. Do not manufacture converted history or
  silently present a partly populated rolling window as complete.
- Bound memory/storage and expose incomplete retention if limits are reached.

Acceptance scenarios: repeated cache, independent refresh cadence, delayed
backfill outside/inside the window, partial outage/recovery, restart, future
timestamps and retention limits. Existing Recorder history remains untouched.

## Local implementation after diagnosis

The observation counter now uses a separate versioned ledger keyed by a hash
of provider, satellite, acquisition time and source detection ID (or coordinates
when no ID exists). Repeated polls and FRP revisions do not add observations;
different acquisition times and satellites remain separate observations.
The ledger retains at most 20,000 records from the last six hours and survives
restarts. Location/filter scope changes start a new collection window.

The existing count entity exposes `counting_method`, `collection_started_at`,
`window_collection_complete`, `retention_limited` and a coverage caveat.
Window completion describes elapsed collection time, not guaranteed provider
coverage. Eviction marks all windows conservatively incomplete for six hours.
Legacy aggregate history still supports FRP and incident aggregates but is not
used to manufacture unique acquisition counts. HA Recorder is not purged.

The observation summary uses current UTC rather than the pooled product clock;
unchanged successful polls still age the count without rerunning tracking.
These are source-observation counts, not distinct physical fires. The original
historical spike remains unproven and should not be marked resolved solely
because these reproducible mechanisms have been corrected.
