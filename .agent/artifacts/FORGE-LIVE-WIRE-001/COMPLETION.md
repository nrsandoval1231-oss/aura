# FORGE-LIVE-WIRE-001 completion evidence

## Scope

Prepared the DeepSeek Builder transport for the first live call. DeepSeek now
uses its documented Chat Completions JSON Output mode (`json_object`) and receives
the target Pydantic JSON Schema as an explicit system instruction. Local Pydantic
validation remains the acceptance boundary for model output.

## Pre-fix reproduction

Before the repair, `PROVIDERS["deepseek"].wire` was `openai`, so a CODING call
sent `response_format.type=json_schema`, the OpenAI-specific structured-output
shape. The regression test `test_deepseek_uses_json_output_and_schema_instruction`
failed on that shape before the adapter selection was changed.

## Changes

- Added `DeepSeekAdapter` with `response_format: {"type": "json_object"}`.
- Added a deterministic schema instruction containing `schema.model_json_schema()`.
- Added `max_tokens=4096` to bound the first call's output.
- DeepSeek parsing now requires `finish_reason == "stop"`; `length`, missing,
  and other finish reasons fail closed before schema validation.
- Kept OpenAI, Google, Kimi, and Anthropic adapter behavior unchanged.
- Added tests for DeepSeek transport, schema instruction, token bound,
  truncated completion rejection, and the unchanged OpenAI JSON Schema request.

## Validation

- `PYTHONPATH=.../src python -m pytest tests/test_model_provider.py -q` — exit 0, 23 passed.
- Full pytest, Ruff, format, and repository gate remain to be rerun by Sol on
  the integrated candidate.

## Candidate and limits

This worktree contains uncommitted changes only; no commit, live request, key
read, push, merge, or deployment was performed. No live DeepSeek behavior is
claimed by this artifact. The first paid call must remain subject to the packet,
the exact integrated candidate, and independent audit.

Changed files: `src/forge/providers/model_provider.py`,
`tests/test_model_provider.py`, and this artifact.
