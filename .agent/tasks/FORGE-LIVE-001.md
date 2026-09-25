# FORGE-LIVE-001 — First governed live Builder request

**Status:** AWAITING_AUDIT after one live request and a validated proposal; candidate and repository-level evidence still require independent review.
**Node:** FORGE-LIVE-001
**Authority:** The owner authorized V0 completion and, on 2026-09-22 in this task, up to **$15 total** for the first DeepSeek Builder API call. This grant covers one bounded request only, not retries or an external repository push.
**Risk:** HIGH (paid external model request)
**Retry budget:** Zero automatic retries. An ambiguous request outcome is UNKNOWN and stops this packet.

## Objective

Have the actual configured DeepSeek Builder propose one small, useful edit to Forge Agent's `README.md` Credentials section: clarify that `BUILDER_MODEL` takes a DeepSeek API model ID such as `deepseek-flash`, not its display name. Validate the structured response, apply only a bounded edit after deterministic checks, and durably record the real call and candidate. This proves the provider boundary and one real Builder output; it does not by itself complete the Sentinel or external repository trial.

## Base

- `0f48fb55324ddba7822bd76c572216b74b7a0086` (local planning base carrying the independently audited wire correction; record the exact execution base before any request)
- `d5fec8d27f89b4ca7f3b410c9045a2865fbdc223` (exact clean execution base of the one authorized request)

## Dependencies

- Independent PASS on the DeepSeek JSON transport correction, including refusal of incomplete `finish_reason` responses.
- Clean isolated worktree and exact candidate identity; run local tests and diff checks before any paid request.
- Preflight the ignored `.env` file without logging the credential. Require the configured model ID `deepseek-flash` and a plausible key.
- Record the owner-authorized $15 total ceiling and verify the one-request maximum output bound. If preflight cannot establish a conservative request cost below the ceiling, stop before effect.

## Allowed files

- `scripts/first_live_builder.py`
- `tests/test_first_live_builder.py` for no-network preflight, fake response, and interrupted outcome behavior.
- `README.md` Credentials section only, after the real Builder response passes schema and scope checks.
- `.agent/tasks/FORGE-LIVE-001.md`
- `.agent/artifacts/FORGE-LIVE-001/**`
- `.agent/ledger/FORGE-LIVE-001.jsonl`
- `.agent/ledger/FORGE-LIVE-001.checkpoint.json`
- `.agent/ledger/FORGE-LIVE-001.claim.json`
- `.agent/graph/work-graph.json` (Sol only, before execution)

## Exclusions

- No alteration of historical ledgers or receipts. The stale slice bindings and misleading `FORGE-VAL-WIN-001` slice receipt remain separate repair work and cannot be cited as certification of this call.
- No provider, Governor, trust-kernel, canonical architecture, PRD, or Finish Contract change under this packet.
- No remote push, merge, deployment, external repository effect, automated retry, secret logging, or simulated independent audit.

## Invariants

- Use the existing `ModelProvider` and core `LedgerStore`. Atomically claim this packet's sole request before intent or transport; an interrupted claim remains a refusal of reuse. Before effect, append and durably reload a `CALL_INTENT` receipt with packet, base, request identity, model, prompt digest, output bound, and spend authority reference. Never put the key or full prompt in the ledger.
- Refuse if this packet's claim or any ledger component already exists, even if an outcome is recorded; there is no second request under this authorization. Bound the actual outbound DeepSeek request size as well as output tokens before effect.
- Make exactly one model request. A transport timeout, non-200 response, schema failure, non-`stop` finish reason, or interrupted process leaves the request UNKNOWN until separately reconciled; no blind retry.
- After response, append a `CALL_OUTCOME` receipt with the actual provider receipt, a recoverable bounded nonsecret proposal and its digest, and usage. If usage or billing is unavailable, record UNKNOWN rather than inventing cost.
- The Builder may propose only the named README section. Refuse any path, anchor, or content that fails deterministic scope checks. A validated model response is a proposal, not an approval or independent audit.
- Bind the applied edit and deterministic gate results to an exact candidate. Request a separate Astra audit. Keep local, remote, and runtime states distinct.

## Acceptance

1. Fake-transport tests prove one-request maximum across concurrent invocations, JSON/schema handling, actual outbound request size bound, persisted intent reload before effect, recoverable outcome persistence on success, and fail-closed ambiguous outcome without retry.
2. With the owner credential loaded from the ignored file, one real `Capability.CODING` call produces either an actual structured Builder response plus receipt or an honest UNKNOWN/refusal. Report actual model, input/output tokens when provided, and observed cost or UNKNOWN without exposing the key.
3. Apply only a valid bounded README edit. Run the canonical repository validation and ledger verification; record exact commands, exit codes, candidate SHA/tree, and changed files.
4. An independent auditor evaluates the exact candidate. This packet is not marked COMPLETE solely because the call succeeded.

## Handoff

Luna may build the no-network runner and tests in isolation. Sol validates and controls the one authorized live request after independent wire audit. Astra reviews the exact resulting candidate and real evidence. No builder self-certification or implied authorization to merge or push.
