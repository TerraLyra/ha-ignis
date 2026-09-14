# Review: optional Queensland reports and location display reliability

Adds a disabled-by-default Queensland QFD calendar, distinguishing source incident
points from warning areas and showing source-time uncertainty. The shared client
bounds requests and preserves stale data during outages. Geometry and rendering run
outside the HA loop; no new satellite associations or warning events are emitted.

Also corrects map-only location match labels and refreshes published next-update
estimates at expiry without extra provider requests. Existing entity identities,
NSW dictionary/calendar contracts and Recorder/history are preserved.

## Validation

867 local tests passed; config-flow coverage 100%. Bandit, runtime dependency audit
and baseline-relative secret checks passed. Linux ARM64/x86-64 geometry tests added
to CI; those jobs and official HACS/Hassfest checks remain pending remote execution.

## Reviewer focus

- New Shapely 2.1.2 dependency and supported-platform validation.
- Warning geometry limits/unknown relations, independent of temporal validity.
- Upstream expiry semantics remain unconfirmed; elapsed means only the source time.
- Report calendar is a feed snapshot, not an archive or active-emergency boolean.
- `location_comparisons` replaces the old map attribute's all-comparisons use case;
  events and history keep their existing serialization contract.

No version bump, release, remote publication or live HA modification is included.
