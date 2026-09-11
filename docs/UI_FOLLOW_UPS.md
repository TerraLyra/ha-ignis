# UI follow-ups — 2026-09-11

## Location summary card

User-approved backlog item inspired by the review of
https://github.com/vwylaw/nsw_fire_danger at commit 926f7d4
(version 1.3.10). This records a product idea, not approval to copy or install it.

- One compact card per monitored location: active detections, nearest distance,
  forecast, official restrictions where supported, source attribution, freshness
  and coverage.
- Keep satellite observations, forecast danger and official restrictions
  separate; do not collapse them into a safety gauge.
- Missing/unavailable restrictions must never display as “no ban”.
- Use explicit entity associations, not entity-name suffix guessing.
- Use validity dates and the relevant location timezone; distinguish stale,
  preliminary and final data.

## Distance history after 0.24.2

User screenshot after restart shows Carmichael's current distance as 163.5 km
at 12:35:40 on 2026-09-11, while an older 11:48:03 entry is 9831.7 km.
The pre-update readings remain in Home Assistant history and inflate the graph
scale. This is distinct from browser cache and from the corrected current state.

- Do not automatically purge Recorder data during integration updates.
- Any targeted history deletion requires explicit authorization, exact entity
  identification, and a backup/recovery discussion before execution.
- Consider a future reference-aware distance history design so changes of
  monitoring reference do not silently mix incomparable distances.
- The screenshot alone does not independently validate the California center
  coordinates or the numerical 163.5 km distance.
