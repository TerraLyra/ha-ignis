# Hungarian official report source review

Checked: 2026-09-09. This is a source-readiness assessment, not a legal opinion
or an enabled provider.

## Verified public interfaces

- The official [RSS directory](https://baz.katasztrofavedelem.hu/34244/rss-forrasok)
  explicitly links the emergency-notice RSS service.
- The [national RSS endpoint](https://www.katasztrofavedelem.hu/10466/RSS_VESZ)
  responds with RSS 2.0 without credentials.
- Its copyright field expressly permits free reuse of the notices with BM OKF
  attribution. This permission is specific to the feed; do not assume it covers
  unrelated website content or photographs.
- The channel declares Hungarian language and a five-minute TTL. TTL is a cache
  hint, not a published quota or availability guarantee.
- The observed response contained three notices from different counties, all
  traffic accidents. This is a snapshot, not evidence of a permanent three-item
  limit, a fire-only feed, or complete national incident coverage.

## Data contract and gaps

Observed item fields are title, link, description and RFC-style publication
date with a numeric timezone. No geographic coordinates, structured incident
category or separate incident start/end time appeared in the RSS sample.

An inspected linked event page (event 91793, a traffic accident) contains a
structured JavaScript object with event ID, category, location text, latitude
and longitude. That demonstrates technical availability, not a documented API
contract or guaranteed spatial precision. Do not execute page JavaScript to
extract it. Do not treat publication time as the fire's ignition time.

The [website legal notice](https://baz.katasztrofavedelem.hu/lablec/jogi_nyilatkozat)
places restrictions on reproducing content and storing website content in
databases. The RSS-specific reuse statement and these broader conditions need
to be distinguished. Before implementing ongoing event-page extraction and
persistence, clarify whether the RSS permission also covers event coordinates
and category metadata, or request a supported structured endpoint.

## Implementation decision

RSS discovery is technically feasible and has an explicit attribution-based
reuse statement. Fully automatic geographic association is **not ready** on
RSS alone. Version 0.18.0 provides on-demand RSS discovery. The next iteration
adds a disabled-by-default publication calendar, with 15-minute refreshes only
after the user enables it. It shares the manual action's client/cache. No
automatic geocoding, persistent report storage, map markers or evidence upgrades
are enabled. Calendar entries show publication time, not incident start/duration.

### Manual Home Assistant action

In Developer Tools → Actions, select **Get official BM OKF notices**, or invoke
`terralyra_ignis.get_official_reports` with no fields and request its response.
Every returned notice contains its title, original URL, BM OKF attribution,
publication time and `not_matched` association. These are emergency notices,
including traffic accidents, not a fire-only list. A successful empty list is
not evidence that no fires exist.

Requests use the fixed national RSS URL, reject redirects, enforce a 20-second
timeout and 256 KB decompressed body limit, and keep results in memory for five
minutes. Failures also impose a five-minute cooldown and return `unavailable`
without presenting old notices as current or creating Repair issues. No event
pages are downloaded. The action is shared across entries to avoid redundant
calls and adds no requests unless explicitly invoked.

Do not substitute a settlement centre for an event coordinate, or classify a
notice as a fire merely because it mentions firefighters. A small rolling
feed also cannot reconstruct the September 8 Egyek incident retrospectively.

## Next implementation gate

### Review-only event date hints (next release)

The manual action retains up to 4,000 plain-text characters from the RSS
description, always alongside attribution. This does not fetch the linked page.
`description_status` distinguishes complete and truncated text. A narrow
Hungarian rule recognizes expressions such as "tegnap kora este gyulladt meg"
and returns `reported_start_date_hint`, precision `day`, the original evidence
phrase and timezone `Europe/Budapest`. The date anchors to publication, never
retrieval. Unrecognized, negated, repeated or truncated input remains `unknown`.

Recognized hints have `event_time_status: requires_review`. The notice could
describe another fire or quote an earlier statement, so these hints are **not**
fed automatically into `match_reports`. They are neither exact ignition times
nor extinction times. The Egyek case demonstrated why publication time alone
misses older observations; it did not establish a safe universal extraction rule.
The publication calendar continues to use publication time unchanged.

### Geographic association

`terralyra_ignis.review_official_report` provides a manual, response-only trial.
Select a loaded configuration entry and a report URL still in the current RSS
snapshot. Confirm that the notice describes a fire; supply reviewed fire
latitude/longitude and an explicit assumed location uncertainty (0.1–25 km).
Do not supply a settlement centre as a precise fire position. Optional
`event_start` and `event_end` must be ISO timestamps with timezones; end requires
start. Without them, only publication time is used. Extracted date hints are
never applied automatically.

The action compares at most 500 local history entries, returns candidate IDs,
distances, relations, reasons and skipped-record counts, and applies no changes.
`probable` is a heuristic relation, not a calibrated probability or official
confirmation. No result does not prove there was no fire; history or RSS may be
incomplete. The existing RSS cache bounds requests; coordinates/history remain
local. An expired notice requires a future saved-report workflow, not automatic
scraping or manual insertion into the live integration.

Clarify with the provider:

1. Whether attributed local use of event coordinates/category is permitted.
2. Whether a supported JSON, GeoRSS or CAP interface exists, including history.
3. Expected polling limits, retention guidance and coordinate precision.

Once resolved, implement one opt-in adapter with a fixed HTTPS host, bounded
downloads and redirects, cache/backoff, and no requests in the satellite update
critical path. Preserve source URL and BM OKF attribution; expose incomplete
location/time as uncertainty. Tests must cover non-fire notices, stale and
empty feeds, malformed XML, duplicate updates and ambiguous incident matches.
Keep satellite counts, notification eligibility and evidence strength unchanged
by report association. Feed failures must not create a Repair requiring no
action from the user.
