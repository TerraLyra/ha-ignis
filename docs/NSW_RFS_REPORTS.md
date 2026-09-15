# NSW RFS fire reports

The optional **Reports — NSW RFS fires** calendar adds regional reporting from
the official NSW Rural Fire Service current-incidents GeoJSON feed. It is separate
from the satellite incident history, BM OKF and GDACS calendars.

## Enable after installing the version containing this feature

1. Open the TerraLyra IGNIS integration's entity list.
2. Show disabled entities and enable **Reports — NSW RFS fires** (Hungarian:
   **Jelentések — NSW RFS tűzesetek**).
3. Add that calendar to your native calendar or Calendar Card Pro entity list.
   Use the actual entity ID assigned by your installation.
4. Have an enabled monitored location whose radius includes an NSW incident.
   An installation with only Hungarian locations will normally show no NSW events.

The calendar is disabled by default and makes no network requests while unused.
Its entity state remains `Off` because these are report entries, not an active
emergency boolean. Enabling it does not enable satellite matching or alerts.

## Meaning of an entry

- One entry per upstream incident ID, even if several monitored circles overlap.
  The description lists only matching locations, with distances from each location.
- The all-day date is the calendar date in the publisher's `UPDATED` field, not
  ignition time, extinction time, or duration. It is not converted from the
  timezone-less `pubDate`. A later update can move an entry to another day.
- Upstream incident type, alert level, response status, size, agency and update
  text are preserved. An `Under control` report can still appear in the feed;
  presence does not mean uncontrolled fire. Zero reported hectares is not proof
  of zero burned area.
- The first version is a **current-feed snapshot, not a persistent archive**.
  Successfully removed records disappear; that is not interpreted as extinction.
  The cached snapshot does not survive a Home Assistant restart.

## Filtering and limitations

Included types, when `FIRE: Yes`: Bush Fire, Grass Fire, Structure Fire, Haystack
Fire, Vehicle/Equipment Fire, Car Fire and Vehicle Fire. Unknown and non-fire types,
Fire Alarm, Burn off and Hazard Reduction are excluded, as are reports explicitly
marked `Planned Burn`. Classification follows the publisher, not title guessing;
this cannot guarantee that every planned activity has been correctly labelled.

Distance filtering uses the publisher's WGS84 **incident point**, including points
inside a GeoJSON GeometryCollection. It does not intersect the supplied fire
perimeter: an incident whose perimeter crosses a circle but whose point lies
outside can be omitted. Missing/invalid points and `(Unmapped Incident)` LGA-centre
placeholders are omitted rather than treated as precise locations.

No minimum area threshold is imposed by IGNIS. Nevertheless, this feed is not a
complete list of every fire and has no global coverage. Neither an empty calendar
nor a missing satellite match establishes that there is no fire.

## Fetching and diagnostics

One shared request per installation at most every 30 minutes during successful
operation, not one request per location. Responses are limited to 8 MiB / 2000
features; redirects are disabled; HTTP timeout is 25 seconds. Parsing runs in a
worker. Errors retry after 5 minutes, increasing to a bounded 30 minutes.

`feed_status` is `available`, `partial` (some invalid records), `stale` (fetch failed,
previous snapshot retained) or `unavailable` (no successful snapshot). A failure
without cached data raises an unavailable error rather than returning an empty
calendar. `last_success` is the fetch time, **not** the latest incident update.
Other attributes count fetched, filtered, unmapped and invalid records across the
feed, not just the user's circles. Filtered or unmapped omissions do not imply
network failure. Consult each report's update text and the official site.

## Sources, attribution and safety

- [Official feed information and reuse conditions](https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds)
- [Official current-incidents GeoJSON](https://www.rfs.nsw.gov.au/feeds/majorIncidents.json)
- [Fires Near Me and incident definitions](https://www.rfs.nsw.gov.au/fire-information/fires-near-me)

The feed information page specifies attribution and CC BY 4.0, subject to its
exceptions; the map page has a separate CC BY 3.0 Australia notice. Consult the
upstream terms for the particular material being reused. No NSW RFS branding or
logos are bundled. Each event includes the required credit:

© State of New South Wales (NSW Rural Fire Service). For current information go to www.rfs.nsw.gov.au.

This is an unofficial integration, not an endorsed warning service. Do not rely
on it for personal safety decisions; follow current official advice.
# Report update times (development)

Timed entries use JSON `pubDate` interpreted as UTC only when conversion to
`Australia/Sydney` exactly matches the separate `UPDATED` date and minute.
Otherwise the report retains its all-day date. Timed entries have a one-minute
display slot, not an incident duration. Existing report UIDs remain unchanged.

Evidence checked on 2026-09-15: official CAP incident 676231 reports
`sent=2026-09-15T12:14:00+10:00`, JSON `pubDate=15/09/2026 2:14:00 AM`
and `UPDATED=15 Sep 2026 12:14`. This supports the UTC/Sydney interpretation;
it is an inference from matching official feeds, not a published field contract.
Runtime agreement checking and all-day fallback protect against inconsistent data.
RSS item pubDate in this sample equals feed publication time and is not used.

Sources: https://www.rfs.nsw.gov.au/feeds/majorIncidents.json and
https://www.rfs.nsw.gov.au/feeds/majorIncidentsCAP.xml, linked from
https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds.
