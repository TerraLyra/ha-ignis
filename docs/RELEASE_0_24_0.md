# v0.24.0 — Explain empty active-fire maps

## New per-location observation sensor

- Adds **Location: <name> — Active-fire observation** for every enabled
  monitored location.
- Distinguishes active detections, no active detections with full source
  availability, no detections under limited coverage, startup and complete
  data unavailability.
- Exposes stable reason codes and exact fresh, delayed, unavailable and
  initializing source counts for dashboards and automations.
- Aligns active incident counts with the markers actually visible on the map;
  inactive and ended tracks remain in history but no longer count as active.

## Safety meaning

`No active detections` means only that IGNIS has no currently map-visible
satellite detections for that monitored location. It is not an all-clear and
does not confirm that no fire exists. Clouds, heavy smoke, tree canopy,
satellite timing, fire size and temperature can prevent detection.

## Installation

Update through HACS and restart Home Assistant. The new location sensors are
enabled by default and require no integration reconfiguration.
