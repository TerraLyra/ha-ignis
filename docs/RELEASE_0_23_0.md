# v0.23.0 — Active-fire monitoring-radius map overlay

## New optional map overlay

- Adds one native map entity for every enabled monitored location.
- Draws the configured active-fire monitoring radius as a circle around the
  location center.
- Publishes the circles through the separate
  `terralyra_ignis_monitoring_areas` geolocation source, leaving existing fire
  map cards unchanged until the source is selected.
- Removes obsolete map entities when a location is deleted or disabled.

## Recommended map card

```yaml
type: map
geo_location_sources:
  - source: terralyra_ignis
    label_mode: icon
  - source: terralyra_ignis_monitoring_areas
    label_mode: icon
    focus: false
cluster: false
hours_to_show: 24
```

The overlay can also be added through the map-card editor by selecting the
TerraLyra IGNIS monitoring-area geolocation source. Disabling marker grouping
keeps centers from being grouped with nearby fire markers.

## Important limits

- A circle represents the configured active-fire search and alert boundary.
- It is not a fire perimeter, satellite footprint, positioning uncertainty,
  evacuation area, safety zone, or detection guarantee.
- Home Assistant's native map consumes the generic `gps_accuracy` decoration
  to draw the circle. IGNIS also exposes the explicit `monitoring_radius_km` and
  `map_circle_meaning` attributes so its actual meaning remains clear.
- Area centers are excluded from automatic map fitting in the recommended YAML;
  zoom remains under the user's control.

## Validation

Local Home Assistant 2026.9.1 / Python 3.14.4: 657 tests passed;
configuration-flow coverage 100%. Python lint and JSON validation passed.
