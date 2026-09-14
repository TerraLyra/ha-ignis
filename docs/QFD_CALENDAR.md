# Queensland QFD report calendar — local unreleased integration

## Enablement and scope

The integration now registers **Reports — Queensland QFD** (Hungarian:
**Jelentések — Queensland QFD**), disabled by default. After a separately approved
release and HACS update/restart, enable the entity in the IGNIS entity list and add
its actual entity ID to your calendar card. Do not guess a generated entity ID.
No existing dashboard configuration is changed by this implementation.

The client is shared in `hass.data` across entries. Construction/disabled registration
makes no network request. Enabled entities request the fixed statewide feed using a
30-minute coordinator/cache; no enabled monitored locations means no request. Full
jurisdiction auto-assignment is not implemented: enabling this Queensland-specific
calendar is an explicit source choice. If enabled with only distant locations, it
still fetches the public feed and filters locally; no private coordinates are sent.

Geometric projection and event rendering run through the HA executor on immutable
snapshots. The source-point radius and validated warning-area intersections are
separate relations. One record lists each matched location with its own distance
for point records; warning areas receive no invented distance to a fire. Unknown
relations are separately named, and wholly unresolved records are omitted from local
calendar events with `unresolved_reports_last_query` diagnostic disclosure.

## Dates and presentation

All-day entries use the event-revision date in Australia/Brisbane. If only publication
time exists, that date is used with explicit publication-fallback and uncertain-time
labels. If neither is usable, no retrieval date is invented; the count is exposed in
`undated_reports_last_query`. Query boundaries are evaluated in the HA calendar zone.
The day is not an ignition date or duration. UID is the existing provider + source ID.

Incident reports and warnings have distinct title prefixes. Titles additionally show
elapsed expiry / uncertain source time / source time-window labels; stale/partial
feeds and planned burns are visible too. Descriptions retain source URL/attribution,
original type/status/warning level, source timestamps and matching location context.
An elapsed expiry remains context; it does not establish official closure. Source-time
windows do not certify active fires. Planned burns do not suppress satellite alerts.

The optional calendar is a **current-feed report view**, not an archive or emergency
boolean. `event` is None deliberately. Old records can still appear on their source
revision day while retained by the feed; records removed from the feed are not archived.
No Recorder or existing report history is deleted. No new warning/new-fire events or
automatic satellite links are emitted. Missing official reports are not an all-clear.

## Failure handling

No usable snapshot raises an unavailable error rather than returning a false empty
success. Retained snapshots are shown with stale labels. Empty successful data can
return an empty calendar. Diagnostics expose feed state and parser omission counters;
spatial/undated counters refer to the last calendar query, not a live incident count.
The exact upstream meaning of QFD expiry remains unresolved and is not guessed.

## Validation / deployment boundary

Tests cover default-disabled registry behavior, enablement, listener removal, no
request without enabled locations, actual worker execution via the test executor,
overlapping locations, Queensland source day versus HA range boundaries, Hungarian
labels, stale/planned context, warning-area relevance, missing dates and unavailability.
This is local implementation only. No release, GitHub publication, HACS installation,
HA restart, live entity enablement or dashboard edit has been performed.

Local result: full suite 867 passed, config-flow coverage 100%; the six QFD calendar
tests passed again after adding the undated-query diagnostic. Compilation/diff checks
passed. Two existing NumPy/h5py reload warnings remain. Linux CI/HACS/Hassfest and
live Home Assistant validation are still required before treating this as deployed.
