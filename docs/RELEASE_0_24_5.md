# 0.24.5 — Processing-chain reliability

Update through HACS and restart Home Assistant. Existing entity IDs and Recorder
history remain unchanged.

Approaching events now identify the monitored location, with its own distance
and trend. Location-specific trend samples are persisted across restarts. After
this upgrade, allow at least three distinct acquisitions spanning twenty minutes
for a location trend; a repeated download does not provide another sample.

Historical members and peak FRP remain attached to an incident, but current
power, position and source confirmation use the newest thirty-minute acquisition
window. A historical peak is not current power. This relative window does not
guarantee fresh satellite coverage.

Corrected observations are reprocessed even if product metadata and detection
counts are unchanged. Older scan pixels cannot keep disconnected fresh groups
joined after those pixels are discarded.

Validation: 704 local tests passed, with 100% config-flow coverage. Tests include
published approaching-event payloads for opposite movements between two monitored
locations. Deployed Home Assistant acceptance testing remains necessary.
