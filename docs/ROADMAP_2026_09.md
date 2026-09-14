# IGNIS — Australia-first roadmap

Baseline checked 2026-09-14: main and v0.25.0 at
`18066e5f70f48595cbb1cd83e61848b1118257ef`.
Local development only; no new release or HA deployment. This document consolidates
user-provided handover/planning material and source inspection, not a live HA audit.

## Delivery order

| Package | Scope | Completion gate | Status |
| --- | --- | --- | --- |
| R0a | Reconcile backlog; source register; map location labels | Targeted regression tests, documented attribute contract | Local implementation |
| R0b | Expired next-update estimates (#5) | Boundary/restart tests, no polling changes | Next reliability task |
| R1 | Minimal shared official-report contract using existing NSW client | Preserve NSW IDs/calendar; no duplicate fetch; source-specific times and geometry roles | Planned |
| R2 | Queensland (or Victoria if access is ready) plus bounded separate report history | Two adapters; restart/outage/correction/disappearance replay | Planned |
| R3 | Remaining Australian jurisdictions; NSW warnings/bans; location card | Validity and jurisdiction tests; independent observations/reports/warnings/forecast | Planned |
| R4 | Manual NSW/satellite review, then explainable candidates | Ambiguous and multi-front replays; reversible links; unchanged satellite evidence | Planned |
| R5 | USA/Canada, Mediterranean, Latin America, wider global coverage | Per-source access, attribution, schema and replay gates | Planned; does not depend on R4 |
| R6 | Opt-in warning-change events and validated automatic links | No duplicate alerts after restart, late updates or withdrawal | Deferred |

No dates or versions are promised before each package's evidence is available.
Optimization and coordinator decomposition remain paused. History is not purged.

## Reconciled backlog

- NSW GeoJSON calendar already exists (`nsw_rfs.py`, `nsw_rfs_calendar.py`,
  `tests/test_nsw_rfs.py`): reuse it, do not rebuild the older plan's MVP.
- Location-source detail requested by #6 exists in `sensor.py` and
  `LOCATION_OBSERVATION_DETAILS.md`; check acceptance criteria before closing.
  No GitHub issue has been changed in this work.
- Location matches: local map-only fix; see `LOCATION_MATCH_DISPLAY.md`.
- #5 next-update timestamp remains open. Inspect `MonitoredLocationNextUpdateSensor`
  and schedule calculation before choosing an overdue-state contract.
- #7 historical discontinuity is unresolved. The fixed observation ledger does
  not prove the cause of a specific historical graph transition.
- GDACS stale report and connection-loss reports need contemporary HA evidence;
  neither can be diagnosed from the source tree alone.
- FRMv3 missing-date handling is implemented; upstream data availability is separate.
- Location summary card, readability, official restrictions and forecast-source
  research remain planned. Satellite/provider health must remain visible.

## Design decisions before R1

Keep observations, official incidents, warnings, restrictions and forecasts distinct.
Preserve source IDs and original status strings. Model incident point, perimeter,
warning area and administrative area separately. Unknown warning is not no warning.
Use provider + source ID identity, version/update timestamps and explicit provenance.
A feed disappearance is not official closure. Store first/last seen separately from
publisher event times. Never invent ignition dates or convert local naive time to UTC
without a documented source rule.

The minimal common report contract should expose source ID, jurisdiction, name/type,
source URL/attribution, reported/updated/retrieved times, geometry role/uncertainty and
original status. Keep country-specific warning scales outside global enums. Validate
this with NSW and the second adapter before migrating BM OKF or GDACS.

The 10 km matching threshold and 0–100 score from the original proposal are hypotheses,
not validated confidence. Warning polygons do not establish fire identity. Planned
burn context must not silence satellite alerts. Manual links precede automatic links;
new official reports can be displayed without any satellite match.

## Tests and acceptance

For each adapter: bounded parsing, invalid schema/geometry/time, empty success versus
outage, stale snapshots, conditional requests where supported, rate limits, overlap,
borders, disabled providers, restart and revised upstream records. Provider failure
must not affect satellite counts or events. Preserve existing entity IDs and stores.
Require a dated live sample check before enabling each new adapter; documentation
availability alone is not proof of feed freshness.

## Needed later

No HA access is needed for repository development. For deployment-specific investigation:
redacted diagnostics, timestamped logs and exact installed version. For the location
card: current dashboard configuration and redacted entity attributes. The historical
uncommitted UI backlog is optional extra context, not assumed present on this machine.

## R0a result

Local source register and map display fix completed. Full suite: 788 passed,
config-flow coverage 100%. CI HACS/Hassfest and live HA verification pending;
no version changed, no GitHub write, no deployment. The independent temporary
runtime download was stopped once the existing verified test runtime was usable.

## R0b / R1 preparation follow-up

Local deadline-driven HA state refresh for #5 is implemented; see
`NEXT_UPDATE_EXPIRY.md`. Queensland direct sample access succeeded through the official
catalogue API. Its mixed point/warning-area schema requires distinct record kinds;
see `OFFICIAL_REPORT_MODEL_PROPOSAL.md`. R1 runtime model and Queensland adapter are
not yet implemented. No provider, polling, release or HA configuration was changed.

## Offline R1 and second-adapter parser completed

Implemented immutable reports, pure NSW conversion and standalone Queensland parsing;
822 tests pass, config-flow coverage 100%. Existing NSW runtime stays unchanged.
The live QFD parser check found 29 explicitly expired records in a fresh 37-record feed.
Fetching, display validity, archive and location filtering remain future work;
see `OFFICIAL_SOURCE_PARSERS.md`. Accepted record counts must not be active-fire counts.

## QFD transport foundation

On-demand QFD client and independent time assessment implemented; see
`QFD_CLIENT_AND_TIME_POLICY.md`. No field-level expiry semantics were found in the
reviewed official sources, so labels describe source times without asserting closure.
No HA wiring, automatic fetching, spatial matching or data retention changes.

## Location/time projection

Point filtering and explicit presentation data are implemented; see
`OFFICIAL_LOCATION_PRESENTATION.md`. Warning-area bounds are only candidates in an
unresolved group, not confirmed local warnings. Polygon topology/intersection and
opt-in HA presentation remain pending. No release or live configuration change.

## Warning geometry milestone

Topology and bounded spherical circle intersection implemented with Shapely 2.1.2.
The previous bounding-box candidates are replaced by verified model intersections,
clear exclusions or explicit unknowns; see `OFFICIAL_WARNING_GEOMETRY.md` for limits.
Opt-in HA presentation and execution outside the HA loop remain next. No version bump.

## Queensland optional calendar implemented locally

Shared client wired into integration setup and disabled-by-default calendar registered.
Source dates, uncertainty, feed status and geometry relations are explicit; processing
runs in the executor. See `QFD_CALENDAR.md`. Archive and automatic jurisdiction selection
remain separate work. Release and live HA validation remain unperformed.
