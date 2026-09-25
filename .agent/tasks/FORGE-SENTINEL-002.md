# FORGE-SENTINEL-002 — one-call recovery of the local Sentinal proving run

**Node:** FORGE-SENTINEL-002
**Status:** COMPLETE for the bounded local recovery after independent PASS on exact Forge 8c6cbfd and Sentinal 61258ab; full Phase 9 remains open
**Authority:** A2 local-only engineering and paid DeepSeek Builder proposal
**Risk:** MEDIUM; possible paid ambiguous effect
**Retry budget:** exactly one new call, no automatic retry

## Objective

Obtain one structured Builder proposal for the unchanged, local Sentinal Windows validation defect after FORGE-SENTINEL-001 returned UNKNOWN without a provider receipt. Preserve the first claim and ledger unchanged. The owner reports that attempt used $0.03; this is owner-reported billing, not an independently matched provider receipt. Its output remains UNKNOWN.

DeepSeek's published Chat Completions documentation says thinking is enabled by default. The first request did not set thinking mode and capped output at 4,096 tokens. The lost ProviderError detail prevents attribution. Use a materially different second request with thinking explicitly disabled. Record diagnostic facts before parsing so a provider response with non-200 status, incomplete finish, missing fields, or invalid schema can be classified without exposing the API key. Sources: https://api-docs.deepseek.com/guides/thinking_mode/ and https://api-docs.deepseek.com/guides/json_mode/.

## Base

- Forge base: `f5f00fb861da89ca07ad0cf9a2151db2dd507390`, branch `codex/forge-sentinel-proof`.
- Sentinal target: clean `d43e2629f2c3db87fdb1437a16f5e94a37136c53` in `C:/Users/nrsan/AppData/Local/ForgeAgent/proving-ground/sentinal-run`.
- Historical FORGE-SENTINEL-001 claim and two-receipt checkpoint head `3bfd2bfedd1269b23892838224ee46737abf532f6a774ef72a7f2f226193f629` must remain intact.

## Allowed files

- `scripts/sentinel_builder.py`
- `tests/test_sentinel_builder.py`
- `.agent/artifacts/FORGE-SENTINEL-002/**`
- `.agent/ledger/FORGE-SENTINEL-002.*` (effect time only)
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/tasks/FORGE-SENTINEL-002.md` (Sol only)

Luna: `scripts/sentinel_builder.py`, `tests/test_sentinel_builder.py`, and a code completion artifact under `.agent/artifacts/FORGE-SENTINEL-002/`. Sol: this packet, graph, state, live effect/ledger, target proposal application, and final artifact. The target may change only `scripts/ci_local.py` and, if essential, `tests/test_ci_local.py` after an actual proposal is reviewed.

## Invariants

1. Use a distinct `FORGE-SENTINEL-002` claim and core ledger. Never delete, edit, or replay the FORGE-SENTINEL-001 claim/ledger as a new request. Preflight fails on a pre-existing recovery claim.
2. Before the effect, establish exact clean Forge/target SHAs, credential presence without printing it, configured model, exact serialized wire payload and digest, output bound, and conservative spend bound. Account for the owner-reported $0.03 conservatively under the $15 total ceiling. Append CALL_INTENT and reload its checkpoint before sending.
3. Send the complete relevant target function and tests, but only ask for a replacement of `scripts/ci_local.py::run_step`. Set `thinking: {type: disabled}` on the actual DeepSeek wire payload and prove preflight digest matches the sent bytes. Do not mutate the shared provider registry or make another route globally non-thinking.
4. Preserve a provider receipt with request ID, HTTP status, finish reason, and token usage when available before schema/scope validation. Persist sanitized error category/status/digest for refusals or parse errors; no API key or raw secret-bearing headers. An ambiguous transport or interrupted effect remains UNKNOWN and blocks another call. No automatic retry.
5. Never apply a malformed, incomplete, or out-of-scope proposal. A usable model proposal is untrusted until independent review and local target tests. No remote writes, merge, deploy, product change, or field-data claim.

## Acceptance and handoff

- Luna supplies deterministic tests for valid response, response with non-stop finish and usage, HTTP refusal, transport ambiguity, restart/duplicate-claim refusal, wire digest including disabled thinking, and no credential leakage. Luna makes no live call and does not change governance files.
- Sol reruns focused and full Forge validation on exact clean candidate before the single call. If a usable proposal returns, Sol reviews scope, applies only to the local target, runs affected/full Sentinal tests, records exact candidate/evidence, and requests independent audit. If no usable proposal returns, preserve UNKNOWN or REFUSED as observed; do not invent a repair.
- Independent Astra audit is required before treating any local outcome as an accepted proving-ground result. This packet does not authorize a remote trial or V0 completion.
