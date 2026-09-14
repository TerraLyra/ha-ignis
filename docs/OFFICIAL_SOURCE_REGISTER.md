# Official-source register — 2026-09-14

Research status, not a statement of live feed health or authorization to redistribute
all listed products. New feeds have not been enabled. Documentation was checked on
this date; each adapter still needs a bounded direct sample/schema/freshness probe.

| Jurisdiction | Official documentation / product | Evidence and remaining gate | Order |
| --- | --- | --- | --- |
| NSW | [RFS feeds](https://www.rfs.nsw.gov.au/news-and-media/stay-up-to-date/feeds) | GeoJSON calendar already shipped. CAP, warnings, ratings/bans are separate extensions. Preserve RFS attribution; check each added product's terms. | 1 |
| Queensland | [QFD dataset](https://www.data.qld.gov.au/dataset/queensland-fire-and-rescue-current-bushfire-incidents) | JSON/XML/CAP-AU/KMZ listed, CC BY 4.0; documented 30-minute incidents cadence. Points describe general areas, not fire spread. Resolve current resource URL and inspect schema/timestamps; old catalogue metadata is not live freshness. | 2 |
| Victoria | [CFA feeds](https://www.cfa.vic.gov.au/rss-feeds) | RSS and developer XML/JSON listed; developer access managed by EMV. Resolve applicable redistribution conditions before implementation. | 3; may swap with QLD |
| Western Australia | [DFES FAQ](https://www.dfes.wa.gov.au/emergencywa/faq), [Emergency WA terms](https://www.emergency.wa.gov.au/about) | DFES documents SLIP access using ArcGIS/WMS/WFS and RSS/CAP. Identify specific official layer, geometry role, access and reuse terms. No guessed map-backend scraping. | 4–5 |
| South Australia | [CFS feeds](https://www.cfs.sa.gov.au/warnings-restrictions/warnings/rss-feeds/) | Separate incidents, warnings, ratings/bans and CAP. Inspect linked resources and reuse terms. Reader refresh advice is not proof of exact publisher cadence. | 4–5 |
| Tasmania | [TFS feeds](https://www.fire.tas.gov.au/Show?pageId=xmlFeedsHome) | CC BY 4.0 with mandatory received-update display and prescribed disclaimer. Select statewide incidents/alerts; preserve required text in implementation after full terms review. | 6–8 |
| ACT | [ESA warnings](https://esa.act.gov.au/be-emergency-ready/warnings-alerts) | Official page references current-incidents XML and CAP at data.esa.act.gov.au. Verify current HTTPS resource, schema, access and terms. | 6–8 |
| Northern Territory | [NT fire map](https://pfes.nt.gov.au/fire-and-rescue-service/fire-incident-map) | Documented approximate 10–15-minute updates. Map says points/polygons represent general areas, not fire spread. Machine endpoint and reuse terms remain unverified. | 6–8 |

NSW existing endpoint: https://www.rfs.nsw.gov.au/feeds/majorIncidents.json
ACT documented CAP candidate: https://data.esa.act.gov.au/feeds/esa-cap-incidents.xml
These links are research inputs; they have not all passed direct parser checks here.

## Second-adapter decision

Start with Queensland's JSON incident resource after checking the actual current payload.
It has an explicit dataset licence and contrasts with NSW in field semantics. Incident
and warning resources may have different timing: the [Queensland media guide](https://www.qld.gov.au/emergency/dealing-disasters/disaster-types/bushfires/bushfire-and-the-media/media-information-sources-for-bushfires)
mentions warning-feed delay up to five minutes; do not apply that promise to all feeds.
If the incident resource is unusable, evaluate Victoria access before changing order.
Do not automatically fall back between sources with different meanings.

## Gate record required per product

Record owner, jurisdiction, authoritative landing page, resolved endpoint, checked date,
licence URL/version, required attribution/disclaimer, reuse limits, authentication,
rate limits, format/schema, maximum observed/bounded payload, ID stability, time zone,
geometry role, update cadence, last successful bounded sample, source timestamp,
known exclusions and test fixture provenance. Unknown values remain explicit unknowns.
A publicly viewable map is not sufficient evidence of an integration-ready feed.

## Global coverage worklist and method

Priority means engineering order, not a claimed ranking of annual wildfire severity.
Australia is explicitly first. Next: USA/Canada; Mediterranean; Latin America; then
other recurrently affected regions. Global research must include every country, not
only countries for which an easy API is found.

Initial candidates:
- USA, Canada.
- Portugal, Spain, France, Italy, Greece, Turkey, Cyprus and Balkan countries.
- Chile, Brazil, Argentina, Bolivia, Paraguay; assess Peru, Ecuador, Colombia, Venezuela.
- Algeria, Morocco, Tunisia; South Africa and other affected African countries.
- Indonesia and Southeast Asia; Russia, Mongolia, Kazakhstan, China, India, Nepal.
- Existing user locations (Hungary, Bosnia and Herzegovina, Japan) remain supported
  according to current provider coverage; this list does not declare them equal risks.

Create one country row (and subnational rows where needed) with separate fields for:
1. Recurrent impact: affected years in the latest ten complete years; forest-specific
   burned area and fraction, extreme years, documented population/ecosystem impacts.
2. Data quality: coverage gaps, differences between forest, grassland, savanna,
   agriculture and prescribed burns; missing impact data is not zero impact.
3. Delivery readiness: official incidents/warnings/restrictions/forecast separately;
   access, licence, geometry, freshness and source independence.
4. Decision: candidate, research, access-blocked, ready, implemented, verified; rationale
   and dated evidence. High impact plus poor access stays a priority research item.

Use [GWIS land-cover time series](https://gwis.jrc.ec.europa.eu/apps/country.profile/downloads)
and [EFFIS annual reports](https://forest-fire.emergency.copernicus.eu/reports-and-publications/annual-fire-reports)
for evidence gathering, supplemented with national reports. The all-country quantitative
screen has NOT yet been executed. Refresh it before claiming comprehensive prioritization.
Do not rank countries solely by hotspot counts or total savanna burned area.

USA candidate: [NIFC official incident data](https://www.nifc.gov/nicc/incident-information/national-incident-map).
Canada candidate: [CWFIS/CWFIF service catalogue](https://cwfis.cfs.nrcan.gc.ca/downloads/docs/en/references/cwfif/cwfis-data-placemat.pdf).
Validate exact current layers and their origin. GWIS/EFFIS satellite-derived context
must not be described as independent field confirmation merely because it is official.

### Access observation in this session

A direct browser-tool open of the Queensland dataset landing page returned a
JavaScript/robot verification page on 2026-09-14. Search-indexed official documentation
was readable, but no current resource payload was validated. This is an access
observation, not evidence that the QFD incident feed itself is down. Resolve the
published resource through an allowed official route before writing its adapter.

### Follow-up: Queensland direct sample succeeded

The official CKAN API was accessible despite the landing-page robot check and
returned the S3 resource URL. On 2026-09-14 at 19:22 UTC a bounded JSON read returned
HTTP 200, 90,629 bytes, 37 records (33 Points, 4 Polygons); Last-Modified was 19:18:27 UTC.
These are sample-specific figures, not expected stable counts. See the adjacent sample
metadata JSON and `OFFICIAL_REPORT_MODEL_PROPOSAL.md` for the mixed schema and time
semantics. Direct access is no longer blocked; semantic validation remains pending.
