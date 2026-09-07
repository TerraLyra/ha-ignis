# Fire-risk provider research

Status: September 2026 technical decision record for the location-aware
fire-risk work planned for IGNIS 0.16.

## Decision

Build the 0.16 runtime around a provider-neutral, per-location fire-risk
interface. Keep LSA SAF FRMv3 as the first production provider and run a
bounded technical spike against the European Commission Joint Research
Centre's Global Wildfire Information System (GWIS) before enabling it.

GWIS is the preferred route to worldwide fire-danger coverage. It publishes
Canadian Fire Weather Index (FWI) forecasts for up to ten days through Web Map
Services and documents anonymous access to the related dataset. EU-owned
website content is normally reusable under CC BY 4.0 with attribution. The
production adapter still needs to verify the live WMS capabilities, layer and
time naming, point-query behaviour, response limits, cache semantics and
operational stability; no candidate source is counted as active until those
checks pass.

Do not label active-fire observations from GOES, Himawari, Sentinel-3 or NASA
FIRMS as fire-risk forecasts. Those sources detect thermal anomalies; they do
not replace a meteorological fire-danger model.

## Candidate comparison

| Candidate | Coverage and forecast | Access and licence | Integration effort | Decision |
|---|---|---|---|---|
| JRC GWIS / ECMWF FWI | Global viewer; daily FWI family, up to 10 days | Public WMS/data service; dataset catalogue says anonymous access; EU reuse normally CC BY 4.0 with attribution | Medium: WMS discovery, point sampling, map parsing and defensive caching | Preferred worldwide provider, pending live technical spike |
| LSA SAF FRMv3 | Europe; daily, day 0–9 | Public demonstration WMS; CC BY 4.0 attribution already implemented | Low: production adapter exists | Keep as an equal provider wherever its safe coverage applies |
| Open-Meteo weather forecasts | Global weather inputs, generally 9–15 km or better regionally, up to 15/16 days | No key for the non-commercial free endpoint; CC BY 4.0 data; free use is limited to 10,000 calls/day and has no uptime guarantee | High scientifically: the API does not expose a documented ready-made FWI field, so IGNIS would need a validated stateful FWI implementation | Fallback research path, not a fire-risk provider yet |
| USGS operational fire-danger WMS | United States; WFPI forecast layers for days 1–7 | Public OGC WMS | Medium | Valuable regional corroboration for California after global support |
| Canadian Wildland Fire Information System | Canada; current and forecast FWI/fire-danger layers | Public WMS/WFS/WCS documented without an application key | Medium | Valuable regional provider for Canada, not a global solution |
| National warning feeds | Country-specific and often authoritative | Terms, formats and machine access vary | Medium to high per country | Add only after a stable global baseline; never silently mix incompatible scales |

## Why not calculate a global FWI immediately?

The Canadian FWI system is stateful. FFMC, DMC and DC depend on prior values,
precipitation and local-noon meteorology; a plausible-looking formula based
only on today's temperature, humidity and wind would not be equivalent to an
operational FWI product. A self-calculated provider therefore requires:

- a cited reference implementation and regression vectors;
- persisted moisture-code state for every location;
- robust initialization and missing-day recovery;
- precipitation, temperature, humidity and wind normalization;
- hemisphere-aware season handling and documented model provenance;
- a distinct label such as "IGNIS calculated FWI" rather than an official
  national warning level.

This is feasible, and Open-Meteo makes the weather input easy to obtain, but it
is more scientific and maintenance risk than consuming GWIS's operational FWI.

## 0.16 provider contract

Every fire-risk provider must expose, without assuming Home:

- stable provider and product identifiers;
- an explicit geographic coverage test;
- forecast horizon and valid dates;
- normalized numeric value plus the provider's original value/class;
- sampled coordinate and per-location radius;
- generation, retrieval and expiry timestamps;
- attribution, source URL and licence note;
- bounded point, area and map requests;
- independent health, backoff and cache state.

The planner assigns every compatible provider to each enabled monitored
location as an equal source. Entities are created only for covered locations.
An uncovered location reports `no_compatible_fire_risk_source`; it must not be
shown as a false low-risk result or as a permanently broken provider.

## GWIS go/no-go gates

The GWIS adapter may be enabled only after an automated spike proves all of the
following against the live service:

1. capabilities and forecast layers are reachable without authentication;
2. global bounding boxes genuinely include test points in Europe, California,
   Tokyo, southern Africa and Australia;
3. today and future dates can be selected deterministically;
4. point values or pixel colours map unambiguously to documented FWI values or
   classes;
5. error documents, redirects and oversized responses are rejected safely;
6. requests can be cached so one installation makes at most a small bounded
   number of calls per forecast cycle;
7. attribution and modification notices satisfy the applicable reuse terms;
8. at least a short soak test shows acceptable availability and update age.

If any gate fails, GWIS remains a documented inactive opportunity and IGNIS
continues with FRMv3 plus a later evaluated provider.

## Sources

- GWIS applications and WMS description:
  https://gwis.jrc.ec.europa.eu/applications
- GWIS data and services:
  https://gwis.jrc.ec.europa.eu/applications/data-and-services
- JRC fire-danger dataset catalogue:
  https://data.jrc.ec.europa.eu/dataset/4b4f1ea6-da7b-4870-9be4-aa5b9a2a4b70
- GWIS data licence:
  https://gwis.jrc.ec.europa.eu/about-gwis/data-license
- Open-Meteo forecast documentation and terms:
  https://open-meteo.com/en/docs
  https://open-meteo.com/en/terms
- USGS operational fire-danger services:
  https://firedanger.cr.usgs.gov/apps/data-services-page
- CWFIS public data services:
  https://cwfis.cfs.nrcan.gc.ca/downloads/CWFIS_DataServices_HowtoAccessDailyMaps%26DataLayers.pdf

