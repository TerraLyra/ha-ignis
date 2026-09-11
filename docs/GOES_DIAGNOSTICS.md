# Safe GOES failure diagnostics

The existing per-location active-fire source/observation attributes and downloaded
integration diagnostics expose `diagnostic_code` beside `failure_type`. No new
entity, endpoint, request, logging setting or credential is required.

| Code | Boundary to investigate |
| --- | --- |
| `goes_catalogue_failed` | Public catalogue request or validation |
| `goes_download_failed` | Product identity/download/size validation |
| `goes_temporary_file_failed` | Temporary file creation |
| `goes_dependency_unavailable` | Import failure while loading/running the decoder |
| `goes_decode_failed` | Product decoding |
| `goes_decoder_result_invalid` | Decoder did not return a normalized snapshot |
| `goes_identity_mismatch` | Snapshot identity differs from the selected product |

Codes locate a failing boundary; they do not establish the underlying cause.
They are allowlisted at the provider-error and health-model boundaries. Raw
exception text, URLs, local paths and credentials are not included. Existing
failure categories, retry delays and data handling remain unchanged. A deferred
retry retains the code and a successful source fetch clears it.

After deployment/restart, inspect `source_health` on California's active-fire
sources entity. For the `noaa_goes` entry, collect only `diagnostic_code`,
`failure_type`, `consecutive_failures` and `retry_at`. Do not publish full Home
Assistant diagnostics containing location or unrelated integration data.

Local validation: 711 tests passed, including safe decoder-error wrapping,
temporary-file cleanup, adapter propagation, retry retention, recovery and
rejection of arbitrary diagnostic strings. The deployed HA failure still needs
to be observed with this diagnostic build before choosing a corrective change.
