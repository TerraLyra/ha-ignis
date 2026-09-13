# FRMv3 date availability and safe failure notices

On 2026-09-13, the configured public ADAGUC WMS advertised Risk dates
2026-08-31 through 2026-09-11, at 12:00 UTC. The production date parser
was checked against the live response (12 dates, latest 2026-09-11).
This is a time-specific observation, not a permanent service limit.

The [official map-service description](https://lsa-saf.eumetsat.int/en/data/map-service/)
describes FRMv3 as a demonstration forecast covering today and the next nine
days. It does not guarantee that each date is currently retrievable.

## Failure contract

- A non-future point-query 404 triggers a bounded GetCapabilities request.
- Only an explicit Risk time catalogue excluding the requested date produces
  a date-unavailable failure, with requested and latest advertised dates.
- An advertised date, missing/invalid catalogue, or failed catalogue request
  keeps the original service failure classification. A 404 alone is not proof
  of a missing forecast date.
- Catalogue XML is parsed with defusedxml; external DTDs are not fetched and
  entities/external references are rejected. Standard ADAGUC DOCTYPEs work.
- No old forecast or map is substituted for today's data. Existing future-date
  handling is unchanged.
- User-facing failure reasons never include upstream XML or arbitrary error
  text. The existing four-failure issue threshold and recovery clearing remain.
- Automatic retry intervals remain bounded, including very large failure counts.
- Satellite active-fire monitoring is independent of forecast availability.

Tests cover missing/advertised dates, broken catalogues, safe XML parsing,
coordinator issue context, no map substitution, issue recovery, translations,
and saturated retry backoff. This change does not restore upstream data.
