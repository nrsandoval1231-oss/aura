# FORGE-EXT-002-CORRECTION-002 — Match response decoding at the credential boundary

**Status:** REDIRECTED
**Parent:** FORGE-EXT-002
**Base:** `e164833a8c9ae5589e3514cfc6c9fe3ebebe1c13`
**Role:** Terra senior specialist
**Authority:** local correction only; no provider call, Hallam mutation, push, merge, or deployment
**Retry budget:** one implementation attempt followed by exact-candidate independent audit

## Objective

Close the credential-scan decoding mismatch independently reproduced by Astra.
The scanner must inspect the same JSON representation accepted downstream, or
reject that representation before any response-derived digest or field is
persisted. UTF-16 and UTF-32 must not bypass secret detection.

## Allowed files

- `scripts/external_trial_recovery.py`
- `tests/test_external_trial_recovery.py`
- `.agent/artifacts/FORGE-EXT-002/COMPLETION.json`
- `.agent/artifacts/FORGE-EXT-002-CORRECTION-002/COMPLETION.json`

## Required proof

- Actual mocked `run_once` regressions for credential-bearing UTF-16 and UTF-32 HTTP 200 JSON responses.
- Cover a schema-valid field, an ignored extra field, and a nested or encoded field where applicable.
- Prove the result is fail-closed, the response digest remains absent, no response content is persisted, and retry remains blocked.
- Preserve the already-proved success, output-bound, and transport-UNKNOWN behaviors.
- Run focused tests, full pytest, graph check, Ruff check, Ruff format check, and base-to-candidate diff check.

## Exclusions

Do not weaken the scanner, persist raw response content, change the lesson or
authority, alter cost bounds, touch Hallam, call a provider, or create a live
EXT-002 ledger.

## Handoff

Return exact evidence, changed files, and remaining unknowns. Do not self-certify.
