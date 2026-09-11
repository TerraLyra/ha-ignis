# Safe GOES failure diagnostics

## Reproduced executor compatibility defect

The deployed `provider_unexpected_type_error` led to a local reproduction in
`_async_cleanup`: Home Assistant's `async_add_executor_job` returns a Future,
whereas `asyncio.create_task` requires a coroutine. Previous product test doubles
returned coroutines, so they did not exercise this contract. The cleanup error
could replace either a successful decode result or the original product failure.

The pending fix uses `asyncio.ensure_future`, accepting either kind of awaitable
while retaining shielded cleanup. Both executor contracts now cover successful
downloads, download validation, decoder errors and cancellation. An additional
test cancels the caller during pending Future cleanup and checks completion.
Local validation: 725 tests passed, configuration-flow coverage 100%. Restoration
of GOES availability in the deployed Home Assistant still requires verification.

## Diagnostic codes

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
| `provider_unexpected_import_error` | Unnormalized import/dependency exception |
| `provider_unexpected_runtime_error` | Unnormalized runtime exception |
| `provider_unexpected_type_error` | Unnormalized type exception |
| `provider_unexpected_value_error` | Unnormalized value exception |
| `provider_unexpected_os_error` | Unnormalized OS/I/O exception |
| `provider_unexpected_error` | Other unnormalized exception |

The `provider_unexpected_*` fallback applies to all providers. It identifies a
broad exception category, not a GOES processing stage or a root cause. Runtime
errors, for example, must not automatically be interpreted as blocking-I/O errors.
No arbitrary exception class names or messages are exported. This fallback does
not catch task cancellation or record it as a failed fetch.

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
