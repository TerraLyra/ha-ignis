# 0.24.8 — GOES executor cleanup fix

Fix temporary-product cleanup to accept the Future returned by Home Assistant's
executor, as well as coroutine-based executors. Previously, cleanup could raise
TypeError after a successful decode, discarding the result or masking the original
product error. Shielded cleanup still finishes when its caller is cancelled.

Validation: 725 local tests passed, configuration-flow coverage 100%. Tests cover
both executor contracts, valid downloads, invalid downloads, decoder failures,
download cancellation and cancellation while cleanup is pending.

Update through HACS and restart Home Assistant. Then verify NOAA GOES source
health and its latest successful product. This fixes a reproduced compatibility
defect; live recovery still needs confirmation and other source failures may
remain. Missing future fire-risk forecast dates are a separate investigation.
