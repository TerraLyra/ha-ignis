# v0.22.0 — GDACS wildfire context and clearer report links

## New optional calendar

- Adds **Reports — GDACS wildfire context**, disabled by default. No GDACS API
  key is required; enabling the calendar starts the shared cached client.
- Shows original GDACS report links and attribution, provider calendar dates
  as all-day events, and explicit possible-area-match/stale-feed labels.
- Separate bounded local archive: at most 1000 records, retained for 30 days
  after their last successful retrieval. Incomplete downloads do not replace
  the archive. Requests have timeouts, payload/page limits and failure backoff.

## Clearer reviewed report links

- Archived report title and BM OKF source appear first in satellite-calendar
  annotations. Observation/review times use the Home Assistant timezone.
- Technical link IDs remain available through the list/review actions rather
  than cluttering calendar descriptions. Existing manually saved links survive
  without migration; satellite event identities and evidence are unchanged.

## Important limitations

- GDACS focuses on significant wildfires and partly derives from GWIS/FIRMS.
  It does not count as an independent detection source or official confirmation.
- Location filtering uses affected-area bounding boxes, not exact polygon
  intersection. Missing/unsupported geometry may be omitted; at most ten geometry
  requests are attempted per refresh. An empty calendar is not an all-clear.
- Dates are provider calendar dates, not verified ignition or extinction times.
  GDACS does not replace national/local authority alerts or emergency decisions.
- No automatic associations or fire notifications are added.

## Installation

Update through HACS and restart Home Assistant after the release is published.
Existing behavior remains unchanged unless the new calendar entity is enabled.
To try GDACS, enable **Reports — GDACS wildfire context** in the IGNIS entity
list, then select it in the calendar dashboard. No integration re-creation is
needed. Read [the coverage notes](GDACS_CONTEXT.md) before relying on the view.

## Validation

Local Home Assistant 2026.9.1 / Python 3.14.4: 654 tests passed; configuration-flow
coverage 100%. Python and JSON checks passed. Hosted CI is a separate release gate.
