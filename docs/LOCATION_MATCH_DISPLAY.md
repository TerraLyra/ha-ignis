# Map location match attribute contract

Local unreleased change, based on v0.25.0.

Previously a fire map entity's `location_matches` included evaluated locations outside
its radius (`inside_radius: false`). This was a misleading user-facing label.

On **fire geolocation entities only**:
- `location_matches` contains only evaluated locations with `inside_radius: true`.
- `location_comparisons` contains all evaluated locations, including outsiders.
- If locations were evaluated but none match, `location_matches` is an empty list.
- If no comparisons exist, both attributes remain absent as before for matches.
- Order and per-location distance/trend values are preserved.

Example: Home and Nearby are inside; Remote is outside. The map's matches list
contains Home and Nearby; comparisons contains all three. The scalar location and
distance continue to refer to the already selected nearest affected location.

Consumers of the map attribute that need all evaluated locations must use
`location_comparisons`. This is an intentional map attribute semantic change.
`FireCluster.attrs()`, bus events, internal matching and history serialization retain
their previous contract. No data migration, Recorder cleanup or reconfiguration is
required. Other entities using cluster serialization are outside this targeted fix.

Regression tests cover overlapping matches plus an outsider, all outsiders and no
comparisons; assert other fields and the underlying cluster serialization are unchanged.

## Local verification — 2026-09-14

- Targeted geolocation, location matching, notification and incident-family suite:
  64 passed.
- Full suite: 788 passed; config-flow coverage 100%; two NumPy-reload warnings
  emitted by the local h5py test environment.
- Python compilation, JSON validation and diff whitespace checks passed.
- Executed with Python 3.14.7 using the handover's test runtime after confirming
  it exists locally. The system Homebrew Python has an expat import failure.
- HACS/Hassfest workflows were not executed for these unpushed local changes.
  No release, HA installation or live UI verification has occurred.
