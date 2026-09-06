# Sentinel-3 SLSTR active-fire technical spike

Status: **implemented through the public EUMETView WFS**

Access rechecked: **2026-09-07**

## Decision

Use the official public EUMETView Web Feature Service for the Sentinel-3 SLSTR
Level 2 near-real-time Fire Radiative Power product. This route needs no
consumer key, password or token, unlike the full EUMETSAT Data Store API.

Sentinel-3A and Sentinel-3B are represented as separate equal peers. Neither
is primary or fallback. Their detections enter the same validation,
deduplication, clustering, tracking and alert pipeline as MTG, MSG-IODC, GOES
and optional NASA FIRMS observations.

## Fixed machine interface

- WFS host: `https://view.eumetsat.int/geoserver/wfs`
- Sentinel-3A layer: `copernicus:sentinel3a_slstr_level2_frp`
- Sentinel-3B layer: `copernicus:sentinel3b_slstr_level2_frp`
- product collection: `EO:EUM:DAT:0417`
- request: WFS 2.0 `GetFeature`, GeoJSON output
- filter: bounded `BBOX` predicates plus a 24-hour `time DURING` range
- requested coordinate reference system: EPSG:4326

The parser accepts only the expected point geometry and layer identity. It
validates satellite name, feature-ID family, coordinates, product and
acquisition times, FRP, FRP uncertainty, confidence, used MWIR channel and
pixel dimensions. The response is rejected if it exceeds 8 MiB, contains more
than 10,000 features or declares a truncated/mismatched feature count.

## Runtime boundaries

- automatically assigned between 82°S and 82°N;
- no more than ten enabled monitoring areas;
- each area uses the existing 1–500 km monitoring-radius bounds;
- one request per satellite is cached for at least 15 minutes;
- redirects are refused and the destination host/layer cannot be configured;
- rate limits, timeouts, server errors and invalid responses are normalized
  independently for Sentinel-3A and Sentinel-3B;
- a current valid empty collection is `available` with zero detections;
- public-service outages stay visible in source health and diagnostics without
  creating two non-actionable Home Assistant Repairs.

The 82° latitude limit is a deliberately conservative engineering assignment
gate, not the published edge of every possible SLSTR swath. It can be widened
later only with validated orbit/swath coverage behavior.

The 15-minute request cadence is not a satellite revisit estimate. Sentinel-3
is polar-orbiting, observations arrive in swaths, and EUMETSAT describes the
near-real-time product as normally available within three hours. Daytime
quality and Collection 3.2 limitations must remain visible in product
documentation; IGNIS does not turn a satellite detection into an official
emergency-service confirmation. The product's 0–100 confidence field is
normalized for the common model, but it must not be described as a calibrated
probability of fire.

## Privacy and operations

The request sends bounded monitored-location coordinates to EUMETView. It does
not send location names or credentials. Exact upstream request URLs are not
exposed as entity attributes. The public EUMETView landing page is used as the
safe source link.

## Official references

- EUMETView API guide:
  <https://user.eumetsat.int/resources/user-guides/eumetview-api-guide>
- EUMETSAT Sentinel-3 SLSTR FRP product collection:
  <https://data.eumetsat.int/product/EO:EUM:DAT:0417>
- EUMETView WFS capabilities:
  <https://view.eumetsat.int/geoserver/wfs?service=WFS&request=GetCapabilities>
