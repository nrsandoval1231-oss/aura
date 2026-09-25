# FORGE-EXT-002-CORRECTION-003 — Preserve duplicate JSON values during secret scanning

**Status:** COMPLETE
**Parent:** FORGE-EXT-002
**Base:** `b9d3aa0f6b88fe8358d9a0f1025d4b8d3c5f7f53`
**Role:** Terra senior specialist
**Authority:** local correction only; no provider call, Hallam mutation, push, merge, or deployment
**Retry budget:** one implementation attempt followed by exact-candidate independent audit

## Objective

Close the duplicate-key normalization gap independently reproduced by Astra.
Before any response-derived digest or field is retained, scan the raw response
and a lossless JSON representation that preserves every duplicate-key value.
Apply the same rule to nested JSON strings accepted downstream.

## Allowed files

- `scripts/external_trial_recovery.py`
- `tests/test_external_trial_recovery.py`
- `.agent/artifacts/FORGE-EXT-002/COMPLETION.json`
- `.agent/artifacts/FORGE-EXT-002-CORRECTION-003/COMPLETION.json`

## Required proof

- Actual `run_once` tests for secrets hidden in earlier duplicate keys in the provider envelope and nested proposal JSON.
- Exercise UTF-8, UTF-16, and UTF-32 encodings.
- Prove refusal happens before response digest or content persistence and retry remains blocked.
- Preserve success, 2,048-token binding, UTF-16/32 scanning, malformed response refusal, and transport UNKNOWN behavior.
- Run focused tests, full pytest, graph check, Ruff check, Ruff format check, and base-to-candidate diff check.

## Exclusions

Do not remove raw scanning, weaken nested scanning, persist raw content, change
authority or cost bounds, call a provider, touch Hallam, or create a live ledger.

## Handoff

Return exact evidence, changed files, and remaining unknowns. Do not self-certify.
