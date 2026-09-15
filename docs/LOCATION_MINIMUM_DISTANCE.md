# Location-scoped historical minimum distance

Tracking preserves the legacy Home-based `minimum_distance_km` in persisted source
records. It is not reused as a location-specific minimum or deleted during upgrade.
New minima are accumulated per monitored-location ID inside the persisted
`location_trend_samples` state, with the reference coordinates. Moving a reference
point starts a new minimum; renaming it or changing its radius does not.

The published cluster minimum uses the same nearest in-radius location as its
current distance. Incident-family aggregation considers only minima for that same
location ID, including zero. If no scoped observations exist, the published minimum
is absent rather than reconstructed from a Home value. The minimum covers observed
samples since scoped tracking began; it is not a complete lifetime minimum for
pre-upgrade incidents. Existing Recorder and archived data are not rewritten.

Validation covers separate Home/California distances, persistence round-trip,
reference relocation, no invented legacy migration and multi-source aggregation.
