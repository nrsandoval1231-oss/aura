# FORGE-SENTINEL-001 builder handoff

## Scope

Implemented the proposal-only Sentinel Builder runner in
`scripts/sentinel_builder.py` and its deterministic transport tests in
`tests/test_sentinel_builder.py`. The runner validates exact clean Forge and
Sentinal commits, checks the configured DeepSeek model and credential presence,
enforces the conservative `$15` ceiling, creates an atomic one-run claim, and
persists/reloads a core ledger intent before the external call. It records a
sanitized provider receipt and classifies malformed output, refusal, and
interruption as refused or UNKNOWN. A successful response is only a structured
proposal for the `run_step` function in `scripts/ci_local.py`; the target is
never modified.

The request includes the complete AST-bounded `run_step` implementation, its
top-level imports, and complete affected test functions. Missing, ambiguous, or
overlong context fails closed. One exact system prompt and wire payload are
used for preflight and the provider call; the intent records the exact prompt
and serialized payload digests. Proposal validation requires one Python function
named `run_step` and rejects excluded paths or malformed replacements.

## Evidence

- Base: `98d235ca786efbdaf7b68c22034a2661da59e7c2`
- Focused tests: `python -m pytest -q tests/test_sentinel_builder.py` — exit 0,
  **10 passed**.
- Ruff: `python -m ruff check scripts/sentinel_builder.py tests/test_sentinel_builder.py`
  — exit 0.
- Format: `python -m ruff format --check scripts/sentinel_builder.py tests/test_sentinel_builder.py`
  — exit 0.
- Diff check: `git diff --check` — exit 0.
- Repair focused tests: `python -m pytest -q tests/test_sentinel_builder.py` —
  exit 0, **11 passed**.
- No paid call was made by this builder. No target files, remote branches, or
  deployment state were changed.

## Risks and limits

The provider response remains untrusted and requires Sol's review before any
target edit. Billing is recorded as UNKNOWN when the provider does not return a
charge. The runner enforces one claim per packet stream and does not retry an
ambiguous call. This handoff does not certify the candidate or the Sentinel
repair.
