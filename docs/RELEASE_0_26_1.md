# 0.26.1 — NSW report update times (prerelease)

NSW RFS reports with corroborated update timestamps now appear as timed calendar
entries instead of all-day entries, allowing chronological display alongside
satellite observations. The timestamp means report update, not ignition or a
satellite association. A one-minute slot is used only for display.

JSON pubDate is interpreted as UTC only when its Sydney-local date and minute
match UPDATED. Missing or inconsistent timestamps retain the all-day fallback.
Report identities and stored history are preserved. No extra feed is fetched.

Validation: 70 affected tests passed locally, including standard/daylight-saving
offsets, inconsistent timestamps and calendar query boundaries.

In HACS, allow prereleases, select v0.26.1, download and restart Home Assistant.
Keep the existing backup. Queensland remains opt-in. This release does not fix
upstream fire-risk forecast availability. Optimization remains paused.
