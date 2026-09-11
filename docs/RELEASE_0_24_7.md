# 0.24.7 — Provider fallback diagnostics

Unexpected provider exceptions now expose a safe diagnostic category instead of
an empty code. Existing GOES stage codes, retry policy and data handling remain
unchanged. Raw exception messages and arbitrary class names are not exported.

After updating through HACS and restarting Home Assistant, inspect
`source_health` on California's active-fire sources entity. For `noaa_goes`, read
`diagnostic_code`, `failure_type`, `consecutive_failures` and `retry_at`.

This is a diagnostic extension, not a confirmed fix for GOES data availability.
The forecast service's missing future dates are a separate investigation.

Validation: 718 tests passed locally; configuration-flow coverage 100%.
