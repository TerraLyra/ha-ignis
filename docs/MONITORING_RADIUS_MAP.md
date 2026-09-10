# Active-fire monitoring-radius map overlay

TerraLyra IGNIS exposes one native Home Assistant geolocation entity for every
enabled monitored location. These entities use the separate
`terralyra_ignis_monitoring_areas` source so the overlay is optional and existing
fire-map cards are not changed by an integration update.

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

`focus: false` prevents distant monitoring centers from forcing a global map
view. `cluster: false` prevents a center marker from being grouped with nearby
fire markers, keeping its radius decoration consistently visible.

The radius is stored in metres in the generic `gps_accuracy` compatibility
attribute because that is the circle decoration supported by the native Home
Assistant map. It is also exposed as `monitoring_radius_km`, together with
`map_circle_meaning: active_fire_monitoring_area`, to make its meaning explicit.

## Limits

- The circle is the user-configured active-fire monitoring boundary.
- It is not a measured fire perimeter, satellite footprint, uncertainty radius,
  evacuation area, or safety zone.
- It provides no guarantee that every fire inside it will be detected.
- The map does not automatically fit the full circle; zoom can be adjusted in
  the card or interactively.
- Changing a location, its enabled state, or its radius reloads the integration
  and recreates the corresponding overlay from the saved settings.
