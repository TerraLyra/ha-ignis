# GDACS wildfire context (0.22.0)

The optional **Reports — GDACS wildfire context** calendar is disabled by default.
Enabling it starts the shared client; disabled calendars do not poll GDACS.
No API key is required. Data attribution:
**Global Disaster Alert and Coordination System, GDACS**.

## Interpretation

- This is international wildfire context, not a local news feed, new satellite
  detector or independent confirmation. GWIS/FIRMS origins remain visible.
- Only possible overlaps between affected-area bounds and a monitored-location
  radius envelope are shown. This is conservative bounding-box filtering, **not
  exact polygon intersection**. Concavities and holes can yield false positives.
- Missing, unsupported, antimeridian or polar geometry may be omitted. The
  `spatially_uncertain_records_omitted` attribute reports records omitted for
  uncertain spatial relevance in the last calendar query. An empty calendar
  does not prove that no fire is present.
- At most ten geometry requests per refresh, with a combined 30-second budget.
  Larger result sets can remain spatially unresolved; this initial limit is not
  complete global perimeter coverage.
- Entries show the provider's calendar dates as all-day context, inclusive of
  its last date. They do not assert precise ignition or extinction times. Raw
  timestamps are archived without inventing timezone information.
- Original report URL, attribution, GDACS alert level and feed status appear in
  descriptions. GDACS alert levels are not IGNIS fire-risk levels. Old archived
  records may be displayed with a stale-feed label after a network failure.
- The calendar has no active-event state and does not trigger fire notifications.
  BM OKF links and satellite evidence/counts are unchanged.

## Storage and requests

One installation-wide client serves all config entries and locations. Search
uses a 30-day window, hourly cache, five-page/100-record page limits and bounded
failure backoff. The separate `terralyra_ignis.gdacs_context_archive` HA Store
retains at most 1000 events for 30 days after their last successful retrieval.
Source date-filter semantics do not guarantee complete interval coverage.

GDACS products do not replace competent authorities' alerts or validated
emergency decisions. Completeness, timeliness and accuracy are not guaranteed.

References:
- https://gdacs.org/Documents/2025/GDACS_API_quickstart_v1.pdf
- https://www.gdacs.org/documents/2025/GDACS_Terms_of_use_Mar_25.pdf
- https://data.gdacs.org/Knowledge/models_wf.aspx

The disabled/enabled/removal lifecycle is covered by a Home Assistant entity
platform test: the disabled registry entry does not fetch, enabling starts the
coordinator, and removal unsubscribes it. Missing feed data raises an availability
error instead of silently claiming there are no events.

Before release: hosted CI, regional coverage checks, and review of the bounded geometry workload. Precise
spatial matching and automatic report associations are not implemented.
