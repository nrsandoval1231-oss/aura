# FORGE-EXT-002-CORRECTION-001 — Pre-call runtime correction

**Status:** COMPLETE
**Parent:** FORGE-EXT-002
**Base:** `2b56ef1686f7ee76690bb7355cc122362ddc402b`
**Role:** Terra senior specialist after Luna exhausted the packet's two local repair attempts
**Authority:** local correction only; no provider call, Hallam mutation, push, merge, or deployment
**Retry budget:** one implementation attempt followed by exact-candidate independent audit

## Objective

Correct the two candidate-blocking defects independently reproduced by Astra before any external effect:

1. construct `CallReceipt` with the model's required keyword arguments so a valid HTTP 200 selection can succeed;
2. force both preflight and transmitted provider payloads to use `MAX_OUTPUT_TOKENS`, and bind the recorded intent and conservative estimate to that transmitted value.

## Allowed files

- `scripts/external_trial_recovery.py`
- `tests/test_external_trial_recovery.py`
- `.agent/artifacts/FORGE-EXT-002/COMPLETION.json`
- `.agent/artifacts/FORGE-EXT-002-CORRECTION-001/COMPLETION.json`

## Required proof

- Add an integration-level mocked `run_once` success test proving one request, durable intent before dispatch, a valid provider receipt, `SUCCEEDED` outcome, and blocked retry.
- Replace or strengthen the transport interruption test so it invokes `run_once`, produces `UNKNOWN`, retains a durable claim/outcome, and blocks retry.
- Assert the transmitted `max_tokens` equals the intent's `output_token_bound` and that the cumulative conservative estimate is recomputed from the transmitted bound.
- Run the focused suite, full pytest, graph check, Ruff check, Ruff format check, and base-to-candidate diff check.

## Exclusions

Do not change the lesson, packet authority, spend ceiling, Hallam files, provider count, governance surfaces, or retained EXT-001 evidence. Do not call a provider or create an EXT-002 ledger.

## Handoff

Return changed files, exact commands and exit codes, remaining unknowns, and confirmation that both Forge and Hallam remain externally untouched. Do not self-certify.
