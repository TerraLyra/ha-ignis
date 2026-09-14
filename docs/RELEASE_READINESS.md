# Local review and release readiness — 2026-09-14

Baseline v0.25.0 at 18066e5f70f48595cbb1cd83e61848b1118257ef.
The manifest version remains 0.25.0; these changes are not a published release.

## Review scope

- Preserve map-only attribute change versus internal event/history contracts.
- Verify next-update timer lifecycle and absence of new provider fetches.
- Preserve NSW calendar IDs, dictionary shape and existing records.
- Inspect QFD parser limits, immutable snapshots, expiry uncertainty, conditional
  requests, partial/stale/unavailable states and cancellation.
- Verify warning topology and spherical-model limits; no invented fire perimeter.
- Verify QFD calendar default-disabled registration, enable/unload, per-location
  relations, source date handling and worker execution.
- Reconcile historical milestone notes with current local implementation.

The Unreleased changelog now describes the final combined implementation rather than
contradictory intermediate steps. Local coverage output is ignored, not deleted.

## Remaining external gates

No Docker executable is available in the current shell. Full official HACS/Hassfest
and Linux ARM64/x86-64 runs have not been reproduced locally. The existing GitHub
workflows cover them, including the newly added geometry cases on both architectures.
No remote branch/PR/workflow dispatch, tag or release was created by this review.

A draft PR / remote CI run is the next way to exercise those jobs. A passing local
suite or wheel availability must not be described as passing Linux or HACS/Hassfest.
Live HA installation and current private configuration remain unverified; no access
is assumed. Deployment testing will need the installed HA version and user-provided
redacted diagnostics if a failure occurs. Existing history must remain intact.

## Local review results

- Latest full suite: 867 passed; config-flow coverage 100%. Six QFD calendar tests
  passed after the last undated-diagnostic addition. Two known NumPy/h5py warnings.
- Bandit 1.9.4, CI thresholds `-ll -ii`: no reported findings.
- pip-audit 2.10.1: no known vulnerabilities in resolved defusedxml 0.7.1,
  h5py 3.16.0, Shapely 2.1.2 and NumPy 2.5.3. This dependency resolution is the audit's
  environment, not a claim about the user's installed Home Assistant packages.
- detect-secrets 1.5.0: 229 tracked/new source files scanned, no findings beyond
  the existing baseline. External secret verification was disabled.
- No source-code behavior change was made during this review; documentation and
  coverage-output ignore rules were updated. No new test run was necessary for those.

These checks reduce risk but do not replace the outstanding Linux/HA platform gates.
