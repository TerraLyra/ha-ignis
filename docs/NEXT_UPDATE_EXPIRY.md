# Next-update timestamp expiry — local fix for #5

The cadence calculation already advances expired estimates. However a coordinator
entity's published HA state is not recalculated just because time passes. Between
provider updates its timestamp could therefore become a past "next" estimate.

Each loaded next-update sensor now maintains one local deadline callback at its
selected estimate. It recalculates and republishes at expiry, without fetching data.
Coordinator updates cancel/replace the callback; no usable estimate cancels it;
entity removal cancels it. Source selection, cadence, IDs and estimate qualification
are unchanged. This remains a cadence estimate, not proof of a new observation.

Tests exercise actual HA state publication at exact expiry, repeated expiry, a delayed
callback, source receipt changes, outage/recovery, old receipt at startup, no receipt,
and entity removal. As with all HA timers, a blocked/stopped event loop may delay the
callback; this is not a guarantee of real-time updates during HA unavailability.

No deployment or live HA verification has occurred. This change does not diagnose
or optimize the separate connection-loss reports.

Verification: 791 tests passed locally (Python 3.14.7), config-flow coverage 100%.
Two existing NumPy-reload warnings from h5py remained. Compilation and diff checks
passed. New tests exercise loaded HA entities and actual timer-driven state updates;
HACS/Hassfest and live HA validation remain pending for unpushed changes.
