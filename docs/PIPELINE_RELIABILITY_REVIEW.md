# Processing-chain reliability follow-up

Local follow-up to the external review of 0.24.4 (5f91a3a).

- Product signatures compare all normalized observation fields and preserve
  multiplicity, ignoring input ordering and fetch timestamp. Same-size corrected
  products must be processed again.
- Discarding older scan samples triggers spatial clustering again. Removed
  pixels cannot remain connectivity bridges.
- Six-hour incident-family membership remains historical. Current position,
  power, source attribution and confirmation use members within thirty minutes
  of the newest acquisition. Historical peak values and source track IDs remain.
  This relative window is not a guarantee of wall-clock freshness.
- Published approaching events use location-specific, bounded trend samples
  (three acquisitions over at least twenty minutes). They carry location ID,
  name, distance and trend. Cooldown is per source track and location. The former
  primary-location approaching events are suppressed at publication. Other
  intensity/activity events retain their existing behavior.
- Map/family distance trend follows the same containing location as its distance.
  Legacy location samples are not inferred from primary-location history; new
  location trend windows need to accumulate. Changing reference coordinates
  resets the corresponding samples.

Regression coverage includes same-size corrections, obsolete bridging pixels,
historical versus current family evidence, JSON-restored location samples and
coordinator replays of opposite motion between two monitored locations, including
the final published event payload. Local tests do not replace a deployed HA
acceptance check. No Recorder history is removed.
