# 0.24.6 — Safe GOES diagnostics

Update through HACS and restart Home Assistant. No new entity or debug logging
configuration is required. Existing entity IDs, retry behavior and history remain.

In the California active-fire sources entity attributes, find `source_health`
and its `noaa_goes` entry. The new `diagnostic_code` identifies the failure stage:
catalogue, download, temporary storage, dependency import, decoding or normalized
result validation. See [GOES diagnostics](GOES_DIAGNOSTICS.md) for the code table.
The code persists during retry backoff and becomes null after success.

Only allowlisted codes are published, never raw exception text or native paths.
If reporting the result, share only diagnostic_code, failure_type,
consecutive_failures and retry_at, not the full attributes containing location data.

This release gathers evidence; it does not claim to fix the deployed GOES error.
Local validation: 711 tests passed, including code propagation, retry/recovery,
safe error wrapping, temporary-file cleanup and rejection of arbitrary strings.
