# FORGE-LIVE-WIRE-001 — DeepSeek JSON transport correction

**Node:** FORGE-LIVE-WIRE-001 (bounded repair; graph registration by Sol)
**Authority:** Owner's V0 completion instruction; no live request in the builder handoff
**Risk:** MEDIUM
**Retry budget:** 2 materially different local repairs

## Objective

Prepare Forge's configured DeepSeek Builder route for a first live call. The current shared OpenAI adapter sends `response_format.type=json_schema` to DeepSeek Chat Completions. DeepSeek's documented Chat Completions format accepts `text` and `json_object`; local Pydantic validation must still enforce the target schema. See https://api-docs.deepseek.com/api/create-chat-completion/ and https://api-docs.deepseek.com/guides/json_mode/.

## Base

- `7d786156df403adc20b41b751546364522be28bb`

## Allowed files

- `src/forge/providers/model_provider.py`
- `tests/test_model_provider.py`
- `.agent/tasks/FORGE-LIVE-WIRE-001.md`
- `.agent/artifacts/FORGE-LIVE-WIRE-001/**`

## Exclusions

- No live request, secret read, ledger rewrite, Governor or trust-kernel change, graph status change, push, merge, or deployment.
- Do not change the OpenAI, Google, Kimi, or Anthropic wire behavior merely to accommodate DeepSeek.
- Do not weaken local Pydantic validation or misreport schema-invalid output as success.

## Invariants

- The DeepSeek Chat Completions request uses documented JSON Output and explicitly instructs the model to emit JSON matching the schema.
- Output tokens are bounded for the first call; the request has a stable, short prompt and no secret in logged fields.
- A malformed or schema-invalid response fails closed and cannot be treated as a Builder candidate.
- DeepSeek `finish_reason` must be `stop`; a cut-off, aborted, filtered, or missing finish reason fails closed even if the returned text parses as schema-valid JSON.
- Other provider families retain their existing adapters.

## Acceptance

1. Reproduce the unsupported DeepSeek request shape in a pre-fix test or test observation.
2. Assert the DeepSeek request uses `json_object`, carries the schema instruction, and bounds output tokens; assert other provider request shapes are unchanged.
3. Assert valid structured output passes and invalid structured output fails closed.
   Include a `finish_reason=length` response whose body is otherwise schema-valid.
4. Run targeted provider tests, full pytest, Ruff check and format, and diff check. Report exact commands, exit codes, changed files, candidate identity, and unknowns.

## Handoff

Luna implements only the owned provider and test files plus completion artifact. Sol reruns gates and requests independent audit of the exact candidate before a paid call.
