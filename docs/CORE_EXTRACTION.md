# Incremental Core extraction

## First boundary: geographic distance

The spherical distance function and Earth radius now live in `core/geo.py`.
`clustering.py` re-exports both existing names, so consumers keep their current
imports. The function body, constants, units and numeric behaviour are unchanged.
Clustering rules, storage schemas, retention, IDs, provider requests and HA
entity/event representations are unchanged. This is not a performance change.

The internal `core/` folder is not a standalone package yet. Importing through
the integration's parent still initializes HA-specific code. A separate isolated
Python test runs the geographic leaf without site packages; it proves only the
leaf's independence, not independence of the complete integration package.

## Compatibility baseline

`test_core_compatibility.py` uses synthetic observations and JSON-round-tripped
in-memory storage with the real coordinator pipeline and HA event bus. It locks:

- persisted incident IDs, observation counts and history across restart;
- California-relative distance/minimum rather than the unrelated Home point;
- new-fire event payload and no second alert after restart or delayed replay;
- inherited family anchor identity after a split and input reordering.

`test_geo_contract.py` locks kilometre distances at the date line, poles,
antipodes and an ordinary monitored location, plus the legacy import path.
Existing detailed tracking, family, location and event tests remain in place.

No production histories or HA configuration are used. Tests do not certify the
separate, still-open policy for location removal or retention. This change does
not address that policy or alter the legacy Home wording in situation reasons.

Next: separate the location model and validation from HA configuration access,
keeping existing serialized keys, IDs and public imports. An independently
installable Core and any new incident-ID scheme remain later work.

## Second boundary: location models

`core/locations.py` owns the location/center value objects, validators and
existing JSON field names/radius bounds. `monitoring.py` re-exports the public
classes/functions and retains HA configuration resolution, Home coordinate
refresh, legacy center adaptation, manual ID creation and option updates.
`const.py` re-exports the moved schema constants with unchanged values.

Location matching, incident history, coverage and official-report presentation
now import the value object directly without importing HA configuration helpers.
The model/validation bodies are unchanged. JSON serialization, source labels,
center storage keys and ID generation semantics are preserved. No migration,
retention change or new validation policy is introduced.

An isolated no-site-packages test covers stored Home/manual records, radius
bounds, invalid records and duplicate IDs. Existing HA config tests and the
cross-layer restart/history/event contracts continue exercising the adapters.
