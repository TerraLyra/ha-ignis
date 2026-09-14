# QFD on-demand client and source-time assessment

Current local implementation: the shared client is now wired to the disabled-by-default
QFD calendar (see `QFD_CALENDAR.md`). No live deployment has occurred; warning events
and satellite matching are not implemented.

## Time semantics investigation — 2026-09-14

The [official dataset](https://www.data.qld.gov.au/dataset/queensland-fire-and-rescue-current-bushfire-incidents)
describes general-area incident points and a 30-minute update cadence. The
[official information page](https://www.qld.gov.au/emergency/dealing-disasters/disaster-types/bushfires/bushfire-and-the-media)
points users to QFD's current incidents and warnings map. Targeted official-source
searches did not identify a field-level definition of `ItemExpiryDateTimeLocal_ISO`
or an explanation of why elapsed values remain in the feed. This is unresolved;
absence of a search result does not establish absence of documentation.

A previous bounded sample contained fresh publication times alongside older incident
and expiry times. It is not justified to call those incidents officially closed or
silently present them as current solely because the feed was refreshed.

`assess_report_time` therefore exposes independent source facts:
- source expiry: unknown / elapsed / not elapsed;
- event and publication time: unknown / future / at or before assessment time;
- expiry preceding event revision: inconsistent interval.

No result means active, safe, officially closed or recently observed. No record is
deleted by this assessment. A future UI must label uncertainty rather than invent a
validity rule. This does not change previously stored history or the existing NSW UI.

## Client behavior

`official_sources/qld_client.py` contains `QfdClient`, explicitly invoked by a caller.
Integration setup creates one instance per installation, shared across enabled
QFD calendars. Disabled registration makes no request. It uses the official catalogue-linked fixed HTTPS endpoint.

- Serialized requests and a 30-minute monotonic cache.
- 25-second HTTP timeout, 30-second enclosing operation timeout.
- No redirects; streamed response capped at the parser's 2 MiB limit.
- Background-thread parsing; immutable snapshots and report tuples.
- Bounded ETag/Last-Modified validators; conditional requests where supplied.
- 304 accepted only after a prior valid snapshot and a conditional request.
- 304 refreshes transport success, not the original record receipt/event/expiry times.
- 5–30-minute saturated failure backoff; numeric Retry-After can extend to 60 minutes.
  HTTP-date Retry-After is not implemented; normal bounded backoff applies.
- Failure retains the previous snapshot as stale, or unavailable without one.
- Valid empty success replaces the in-memory snapshot. This is not archive deletion;
  no persistent archive exists in this client.
- Partial status discloses any parser omissions/conflicting IDs, including filtered
  types. It does not claim all omissions are corrupt input.
- Safe failure codes only, no raw server bodies or exception messages in snapshots.
- Cancellation propagates without marking source failure or poisoning cache/retry state.

`available` describes a successfully parsed transport snapshot; it does not guarantee
that every contained report is temporally current or relevant to a monitored location.

## Next gate

Location relevance and explicit presentation policy remain before HA activation.
Incident points can use radius checks; warning polygons require separate topology and
intersection validation. Keep elapsed/uncertain context separate from active warnings.
Resolve source semantics where possible without guessing or contacting anyone without
user authorization. Source-time uncertainty does not block offline development.

## Verification

833 tests passed locally, including 11 new transport/time cases; config-flow coverage
100%. Tests cover concurrent cache reuse, 304, partial data, retained stale data,
valid-empty recovery, first failure, redirect rejection, timeouts, size limits,
rate-limit cooldown, 50 consecutive failures, invalid validators and cancellation.
Compilation and whitespace checks passed. Two pre-existing NumPy/h5py reload warnings
remain. HACS/Hassfest and live HA validation were not run for these local changes.
