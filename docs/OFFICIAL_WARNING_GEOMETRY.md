# Warning-area validation and circle intersection

Implemented locally, not enabled in Home Assistant. Supersedes the previous
bounds-only warning relation described in `OFFICIAL_LOCATION_PRESENTATION.md`.

## Model and decisions

Use Shapely 2.1.2 / GEOS for polygon topology and centre-in-area (including boundary),
with explicit holes. Invalid rings, self-intersections, holes outside the shell and
nested holes are not repaired; they remain unknown. The first ring is the shell;
ring winding reversal does not change relevance. The optional third ordinate is
validated but omitted from horizontal geometry.

Edges use linear longitude/latitude interpolation, consistent with
[RFC 7946 section 3.1.1](https://www.rfc-editor.org/rfc/rfc7946#section-3.1.1).
Distance uses the integration's existing spherical Earth model (R=6371.0088 km),
not degree-based planar distance or an inscribed polygon approximation to a circle.
This is not an ellipsoidal WGS84 geodesic accuracy claim.

For a centre outside the polygon, each boundary segment's midpoint distance is
compared with a conservative bound on distance to any point along the segment:
R * (absolute delta latitude + absolute delta longitude), in radians, divided by 2.
The bound follows from the spherical path length being no greater than that coordinate
L1 path length and the triangle inequality. Clearly disjoint segments are discarded;
a sampled boundary point strictly inside the radius establishes an intersection.
Remaining segments are subdivided. Hole edges participate too.

A 1-metre computational uncertainty margin keeps near-tangent cases unknown; it is
not a guarantee that source coordinates or a spherical Earth model are accurate to
one metre. A centre on a valid boundary is included. No distance to a fire perimeter
is published, because the area is a warning area, not a burn scar or active fire edge.

## Limits

- At most 2000 vertices and 100 rings for topology validation.
- At most 20000 boundary evaluations per area/circle relation.
- Pole-adjacent latitude beyond +/-85 degrees, longitude span >=180 degrees,
  monitoring radius >=10000 km, numerical ambiguity or work-limit exhaustion: unknown.
- MultiPolygon is not added to the QFD parser in this package.
- Invalid/unsupported areas remain in unresolved results, not excluded as safe.
- A report matching one location can still contain explicitly unknown relations for
  others. Consumers must inspect each relation, not apply a report-level match to all.

Future HA integration must call this CPU-bound projection in its executor; no new
main-loop processing, polling, alert or automatic satellite link is enabled here.
The existing parser can retain up to 10000 vertices, but larger-than-2000 areas stay
unknown at this spatial stage. Geometry rejection never deletes the input snapshot.

## Dependency and validation

Pinned `shapely==2.1.2` added to manifest and test requirements; version stays 0.25.0.
[Shapely validity documentation](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.is_valid.html).
[PyPI release files](https://pypi.org/project/shapely/2.1.2/#files) confirm CPython 3.14
macOS ARM64 and Linux manylinux ARM64/x86-64 wheels. Only macOS ARM64 was executed
locally; Linux geometry tests were added to the existing two-architecture workflow,
which has not been dispatched/pushed. Wheel availability is not a CI pass.

Tests cover centres/boundaries, edge-only crossings, near tangency, holes, reversed
winding, concavity, self-crossings, invalid holes, collinear rings, geographic limits,
vertex/work budgets and numerical failure. No live HA configuration was accessed.

Final local verification: 861 tests passed; config-flow coverage 100%. Compilation,
JSON and diff checks passed. Two pre-existing NumPy/h5py reload warnings remain.
Test runtime uses `/private/tmp/ignis-geometry-deps` for the isolated Shapely install
alongside the previously verified Python 3.14.7 test environment.
