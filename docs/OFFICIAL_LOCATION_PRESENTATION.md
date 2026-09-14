# Official report location and time projection

Update: warning areas now use topology validation and bounded spherical intersection.
See `OFFICIAL_WARNING_GEOMETRY.md`, which supersedes the bounds-only section below.

Pure function `official_sources/presentation.py`, now called by the optional QFD
calendar in the HA executor. It performs no I/O or history mutation.

## Point incidents

Enabled monitored circles are compared with source incident points using spherical
haversine distance. Boundary points are included. A source report appears once with
all matching location IDs/names and each location's distance. Disabled locations are
excluded. Duplicate enabled IDs and invalid location coordinates fail explicitly.
This distance is to the publisher point, not necessarily the nearest actual fire edge.

## Warning areas

Shapely validates topology; bounded spherical subdivision tests monitoring circles
against the source area (including holes). Verified model intersections join relevant
records with `warning_area_intersects`. Unsupported/invalid/near-boundary cases stay
`geometry_unknown`; records with no verified relation remain unresolved. No warning
area is turned into a fire point or perimeter. See `OFFICIAL_WARNING_GEOMETRY.md` for
geographic limits, computational tolerance and dependency validation.

## Time and source state

The projection re-evaluates source time on every call, even without another fetch.
It retains relevant elapsed-expiry records and planned burns with explicit labels:
- `source_expiry_elapsed`;
- `uncertain_source_time` for missing event/expiry, future event/publication, or an
  expiry earlier than the event revision;
- `source_expiry_not_elapsed`, which is NOT an active-fire or current-warning claim.

Feed health remains independent. Stale/unavailable retained records carry
`feed_not_current`; partial feeds carry an omissions note. Parser filtered/invalid/
conflicting-ID counters survive projection. Empty success is distinct from unavailable.
No classifications suppress satellite alarms or imply official closure.

`outside_count` counts source records with no retained location relation (including
when no enabled circles exist); it is a filtering diagnostic, not an absence-of-fire
measurement. The original snapshot is untouched and no archive/Recorder data is erased.

## Next implementation gate

Implement topology-aware warning polygon checks and defensible circle intersection,
or keep those records explicitly unresolved. Then add an opt-in HA presentation that
shows temporal uncertainty, feed state and source attribution. No release/activation
has occurred in this package.

Verification: 846 local tests passed, including 13 new cases; config-flow coverage
100%. Coverage includes overlap, disabled locations, zero-radius boundary, date-line
points, warning holes, uncertain date-line bounds, expiry aging, future/missing times,
planned burns, retained stale context and parser omission metadata. Existing NumPy/h5py
reload warnings remain. Compilation/diff checks passed; HA/CI deployment checks pending.
