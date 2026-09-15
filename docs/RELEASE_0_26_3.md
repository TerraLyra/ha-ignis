# 0.26.3 — Replayed track identities

Older observations replayed outside the matching window could create another
retained record with the same deterministic track ID. Reuse the stored identity
without emitting another new-incident event or incrementing its history.

Presentation now lists unique source track IDs. Duplicate records cannot multiply
corroborating-detection counts for the same track/provider/satellite combination.
Stored records and Recorder history are preserved; no deletion is required.

875 local tests passed, including old-observation replay and duplicated source
records. Install v0.26.3 through HACS and restart Home Assistant. Keep the existing
backup. After refresh, source track count should equal the unique displayed IDs;
this count is not the number of independent satellites. Optimization remains paused.
