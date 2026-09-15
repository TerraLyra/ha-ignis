# 0.26.2 — Location-specific minimum distance

A California incident now uses California for both its current distance and its
minimum observed distance. Previously the historical minimum could still refer
to Home even though the current map distance referred to another location.

Minima are stored per location and survive restart. Changing reference coordinates
starts a new minimum. Merged incidents combine only values for the same location.
Legacy Home-based records and existing history are preserved, not relabelled.
If no location-specific observations exist yet, the minimum is omitted. New minima
cover observations since this tracking began, not the full pre-upgrade lifetime.

Validation: 873 local tests passed; all PR #23 GitHub checks passed, including
HACS, Hassfest, full pytest/coverage, security and Linux ARM64/x86-64 tests.

In HACS, download v0.26.2 and restart Home Assistant. Keep the
existing backup and integration configuration. No history deletion is required.
After a fresh observation, inspect an incident belonging to a non-Home location.
Optimization remains paused.
