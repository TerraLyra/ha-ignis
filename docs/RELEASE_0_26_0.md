# 0.26.0 — Queensland reports (prerelease)

Adds an optional, disabled-by-default Queensland QFD report calendar. Incident
points and warning areas remain distinct, with explicit source-time uncertainty,
bounded geometry processing and stale-data handling. No automatic satellite
association or persistent Queensland archive is introduced.

Also fixes map location-match labels and refreshes next-update estimates without
additional provider requests. Existing entity identities and history are preserved.

## Validation

PR #21 passed all GitHub checks: pytest/config-flow coverage, HACS, Hassfest,
CodeQL, security/dependency checks and Linux ARM64/x86-64 geometry/decoder tests.
The local suite passed 867 tests. Live Home Assistant validation remains pending;
this release is intentionally marked as a prerelease.

## Installation

In HACS, enable prerelease versions for TerraLyra IGNIS and select v0.26.0.
Keep a current backup including history, download, then restart Home Assistant.
The integration version should read 0.26.0 after restart.

Enable the Queensland report calendar explicitly to use it; see
[QFD calendar](QFD_CALENDAR.md). Existing monitored locations are used for filtering.
Elapsed source expiry is not proof that a fire has ended. Warning polygons are
not fire perimeters. This change does not address upstream forecast-date outages.

For code rollback, redownload v0.25.0 and restart without removing the integration
or deleting its history. Optimization remains paused.
