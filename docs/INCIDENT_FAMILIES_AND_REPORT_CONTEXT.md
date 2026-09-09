# Incident families and report context

## Purpose

Satellite products do not share one incident identifier. The same physical fire
can arrive as several nearby source tracks because of different pixels,
satellites, products, geolocation accuracy, or observation times. IGNIS must
preserve those observations for traceability while presenting one stable fire
to Home Assistant.

This document separates two concerns:

1. **incident-family consolidation**, which is local processing of satellite
   observations and controls Home Assistant entities, counts and events;
2. **report context**, which may later associate official notices or news with
   an incident but never creates or proves a satellite detection by itself.

## Incident-family contract

Every provider keeps its own persistent source tracks. Before IGNIS publishes
data to Home Assistant, a second conservative layer groups related tracks into
one presentation-level incident family.

The family identifier is stable across updates. It is inherited when a new
provider starts observing an existing incident. If a family later splits, the
original identifier stays with the group containing the original source-track
anchor; the other group receives its own source-track identifier.

Grouping requires temporal compatibility and bounded spatial distance:

- observations from the same evidence family use the configured same-fire
  radius (3 km by default);
- independent provider families may compensate for geolocation and resolution
  differences up to 8 km;
- LSA SAF MTG and LSA SAF IODC are one evidence family and therefore do not
  count as independent confirmation;
- a 16 km maximum family diameter prevents chains of nearby detections from
  joining two distinct fires.

The limits are deliberately conservative defaults, not a claim about fire
perimeters. They should only change with replay fixtures and measured
false-merge/false-split results.

## Published behavior

One incident family produces:

- one map entity and one Home Assistant history identity;
- one active-fire count contribution;
- at most one new-fire event for its initial appearance;
- at most one event of each trend type per update;
- combined provider and satellite attribution;
- `source_track_ids`, `source_track_count`, and `incident_extent_km` diagnostic
  attributes.

FRP, confidence, pixel count and detection totals are aggregated
conservatively. Values from overlapping feeds are not summed, because that
would imply physical additivity that the source products do not establish.

Historical duplicate entities created by older versions remain in Home
Assistant's recorder, but new updates no longer create one entity per grouped
source track.

## Validation before tuning

Build anonymized replay fixtures from real cases such as the Ároktő–Egyek–
Tiszacsege observations. Each fixture should retain source, satellite,
timestamp, coordinates, confidence/classification, FRP and the expected
incident-family membership.

Track at least these outcomes:

- obvious duplicate source tracks become one family;
- nearby but distinct fires remain separate;
- a late independent observation joins the existing stable identity;
- a family split does not swap Home Assistant entity identities;
- restart/replay produces the same result;
- counts, map markers, new-fire events and trend events agree.

## Future official-report and news context

Report enrichment should be a separate, optional adapter layer. Candidate
sources should be assessed per country for structured access, location and time
precision, update cadence, licensing, rate limits, language and long-term
reliability. Prefer, in order:

1. fire-service, civil-protection and emergency-management feeds;
2. public incident APIs and CAP/RSS/Atom feeds;
3. reputable local or national news feeds with permitted machine access;
4. broad aggregators only as discovery aids.

Reports are matched to an existing incident family using bounded time,
coordinates, settlement names and incident terms. A match must retain the
publisher, canonical URL, publication/update time, language, match reasons and
uncertainty. Duplicate or syndicated articles collapse to one report family.

User-facing evidence should remain explicit:

- **satellite detected** — thermal evidence exists;
- **multi-source satellite detection** — independent satellite evidence agrees;
- **officially reported** — an official source was matched;
- **reported in news** — a media report was matched;
- **unverified report** — context exists but the match is weak or incomplete.

An article must never silently upgrade a thermal anomaly to an official fire,
and missing news must never downgrade a satellite detection. URLs, downloads,
content size, redirects, caching and logging require the same bounded security
controls as satellite provider adapters. The first implementation should be
opt-in and should not scrape sites whose terms or controls prohibit it.

## Release sequence

### Matching foundation

`report_context.py` provides a local, immutable association API for adapter-
supplied fire reports and existing satellite incidents. It performs no network
requests and is not yet connected to Home Assistant entities or feed polling.
It retains publisher, URL, language, publication and event dates, spatial
uncertainty, and explicit match reasons. Results are `possible` or `probable`,
never confirmation of a fire. Publication-only dates, broad time intervals,
imprecise locations and multiple candidate incidents remain `possible`.

Matching is capped at 100 reports and 500 incidents, with an 8 km distance
and 6 hour temporal tolerance. These are initial candidate-search bounds,
not calibrated probabilities. A shared adapter-supplied original notice URL
groups syndicated reports; unrelated URLs are not inferred to be independent
evidence. HTTPS link validation is not a download/SSRF policy: a future feed
adapter still needs its own permitted-host, redirect and response-size controls.

The September 8 Egyek news example remains an unverified real-world candidate;
the unit tests use synthetic coordinates and do not claim to validate that fire.
Next: select and review one structured official feed, then add opt-in polling,
persistence and entity/calendar presentation around this API.

1. Ship incident-family consolidation with replay and persistence tests.
2. Collect diagnostics on family sizes and extents without sending telemetry.
3. Validate thresholds against user-supplied cases and adjust only with tests.
4. Add one structured official-report adapter as an opt-in experiment.
5. Add broader report discovery only after licensing, security and matching
   precision are demonstrated.
