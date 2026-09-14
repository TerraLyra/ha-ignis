# Minimal official-report contract — R1 preparation

Status: initial offline model, NSW conversion and Queensland parser now implemented.
See OFFICIAL_SOURCE_PARSERS.md for actual scope, validation and remaining gates.
No new source is enabled. The design discussion below is retained as context.
Based on existing NSW parser/calendar and a bounded Queensland live sample on
2026-09-14. The Queensland feed is mixed: incident information points and warning
polygons share one collection. A single OfficialFireIncident class would be too narrow.

## Minimal common record

| Field | Meaning / constraint |
| --- | --- |
| provider + source_id | Stable namespaced identity; no generated satellite IDs |
| record_kind | Incident or warning; classification uses verified source schema, not geometry alone |
| jurisdiction | Source jurisdiction, separate from user location assignments |
| title, source_url, attribution | Source text/links, sanitized and bounded by adapter |
| geometry_role | Incident point, warning area, fire perimeter or unknown; not interchangeable |
| geometry | Validated geometry with source accuracy/uncertainty; never infer a fire point from a warning centroid |
| raw_type, raw_status, raw_warning_level | Preserve original vocabulary, including unknown values |
| planned_burn | True / false / unknown; no automatic alert suppression |
| event_updated_at | Source event revision time only when offset/zone is known |
| published_at, expires_at | Distinct source timestamps; do not substitute publication time for event revision |
| source_date, raw_updated | Preserve NSW local calendar date and raw text without inventing UTC |
| retrieved_at | Transport receipt; does not establish record freshness |

A separate snapshot holds fetch health, request metadata, completeness and counters.
The archive's first_seen/last_seen are local lifecycle metadata. Missing from a later
snapshot is not official closure. Warnings can relate to several incidents, and an
incident can have several warnings. No relation is inferred merely from nearby points.

## NSW mapping and compatibility

Reuse `NswRfsClient` and `parse_feed`. Map current accepted dictionaries through a
pure conversion boundary first, retaining existing calendar dictionaries and UIDs.
No second client, network request, new sensor, config migration or persistence schema
change is needed for the first model step. `date`/`updated_raw` remain available;
`update_order` is not an aware timestamp. Status and category remain original values.
Existing planned-burn exclusion remains unchanged until an explicit display feature
exists for that separate record type.

## Queensland mapping hypotheses requiring tests

Official resource discovered through CKAN package_show:
https://www.data.qld.gov.au/api/3/action/package_show?id=queensland-fire-and-rescue-current-bushfire-incidents

Current sample endpoint:
https://publiccontent-gis-psba-qld-gov-au.s3.amazonaws.com/content/Feeds/BushfireCurrentIncidents/bushfireAlert.json

- `UniqueID` appears source-specific; do not use `OBJECTID` as stable identity without evidence.
- `QFDWarnings` collection includes Point/Information and Polygon/Advice records.
  Do not classify the entire collection as warnings or all records as incidents.
- Preserve `CurrentStatus`, `GroupedType`, `WarningLevel`, `EventType` separately.
  `Information` is not proof that there is no warning elsewhere for the same fire.
- `ItemDateTimeLocal_ISO`, `PublishDateLocal_ISO`, `ItemExpiryDateTimeLocal_ISO`
  are distinct, offset-aware fields. Avoid the undocumented `ItemDateTimeUTM` interpretation.
- The examined point was a permitted burn with an August event/expiry date and a
  September publication date. Fresh publication must not reactivate expired context.
- Polygon coordinates include a third ordinate. Validate geographic axes; do not
  treat an extra ordinate as an incident location or silently truncate bad structures.
- The adapter needs mixed-record, expired-point, warning-without-incident, unknown
  classification, duplicate/revised-ID and ambiguous-geometry fixtures before runtime use.

See `QUEENSLAND_SAMPLE_METADATA_2026_09_14.json` for bounded factual metadata.
No current news/advice text or user configuration is stored in that file.

## Next implementation package

Implement the immutable common record and NSW conversion with equivalence tests.
Then implement a standalone Queensland parser with synthetic fixtures informed by the
observed schema. Only after record semantics and provider conditions are settled add
fetch/cache and location filtering. Warning polygon intersection is a separate task;
point-in-radius code is not an acceptable substitute for warning-area relevance.
