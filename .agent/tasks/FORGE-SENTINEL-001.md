# FORGE-SENTINEL-001 — Local Sentinal Windows gate repair proving run

**Node:** FORGE-SENTINEL-001
**Status:** BLOCKED after one UNKNOWN provider outcome under the owner's separate two-call, $15 maximum grant; no retry until reconciliation
**Authority:** A2 local engineering experiment; no remote write or product claim
**Risk:** MEDIUM (paid API effect and model-authored code in a local clone)
**Retry budget:** one initial Builder call plus at most one materially different recovery call, together no more than $15; no automatic retry

## Objective

Measure real Forge Builder output on a bounded, resettable copy of the owner's Sentinal repository. At `d43e2629f2c3db87fdb1437a16f5e94a37136c53`, the clean local clone's assessment tests pass 27/27 and Ruff passes. Its full Python suite on this Windows host gives **411 passed, 6 failed, 3 skipped**: all six failures are `tests/test_ci_local.py` cases where `shutil.which("bash")` selects the nonfunctional WindowsApps WSL launcher while Git Bash is available. This is a real baseline defect in the local validation path. The canonical Sentinal product is stopped pending field data; this packet may repair only the local clone's validation runner and may not expand the product.

## Base

- `15366f908e201debe4c6d6c443ca0e243208fd9b` — independently signed Forge FORGE-INTEGRATED-001 candidate.
- `d43e2629f2c3db87fdb1437a16f5e94a37136c53` — clean local Sentinal worktree at `C:/Users/nrsan/AppData/Local/ForgeAgent/proving-ground/sentinal-run`, branch `codex/forge-sentinel-run`. No remote branch is authorized.

## Allowed files

- `scripts/sentinel_builder.py`
- `tests/test_sentinel_builder.py`
- `.agent/artifacts/FORGE-SENTINEL-001/**`
- `.agent/ledger/FORGE-SENTINEL-001.*` (ledger only at effect time)
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/tasks/FORGE-SENTINEL-001.md` (Sol only)

The local Sentinal clone may change only `scripts/ci_local.py`, plus
`tests/test_ci_local.py` if a real regression test is needed, after the model
proposal is reviewed. The canonical checkout and remote remain unchanged.

## Exclusions

- No edits to canonical Sentinal main checkout, its remote, product/research code, PRD, architecture, held-out data, evidence, deployment, credentials, or field-data claims.
- No remote push, merge, deploy, outreach, user-facing prediction, or production effect.
- Do not use the prior one-call spend grant. The owner separately authorized **up to $15 total for at most two additional DeepSeek Builder calls** for this local proving-ground exercise. Use fewer calls if sufficient. No unmeasured retry.
- No simulated model response may stand in for the paid-call result or for an independent audit.

## Invariants and acceptance

1. Before any paid call, verify exact clean Forge and Sentinal SHAs, configured model ID, ignored credential presence without printing it, request bounds, claim absence, and conservative total spend bound. Persist a core ledger `CALL_INTENT` and reload it before the effect. An ambiguous outcome is `UNKNOWN` and blocks retry.
2. Send the actual failing `run_step` behavior, relevant tests, and the narrow requirement to the configured DeepSeek Builder. Require a structured replacement proposal limited to `scripts/ci_local.py`'s `run_step` function. Treat it as untrusted; review and validate scope before applying. Log only sanitized output and provider receipt, never the key.
3. Show the baseline six failures before application and the affected and full research tests afterward, with exact commands, exits, candidate SHA, changed files, and no hidden failures. A failed first proposal may consume the second call only under a documented materially different recovery strategy and remaining budget.
4. Preserve Sentinal evidence tiers, no-control authority, and pre-field product stop. The local clone stays on a temporary branch. Forge's append-only receipt and checkpoint reload after interruption; no duplicate paid call is possible from one claim.
5. Produce a reviewable proving packet with baseline repo/spec/architecture identities, prompt/response digests, model receipt, candidate and tests, audit and repair history, discovery/spec decision, restart result, outcome and lesson candidate. Mark unproved Finish Contract elements UNKNOWN. An independent auditor reviews the exact local candidate; Builder does not certify itself.

## Validation

- Forge focused tests for preflight, claim/reload, refusal/UNKNOWN, scope, and spend cap.
- Sentinal: `python -m pytest -q tests/test_ci_local.py`, `python -m pytest -q`, `python -m ruff check src tests scripts` in the isolated research venv.
- Forge: `scripts/validate.sh` with the signed integrated-audit env, classifying any new active-packet slice failure separately; `git diff --check` on both candidates.

## Handoff

Luna implements the Forge one-call runner and tests only. Sol controls the paid call, proposal review/application, graph transition, and evidence packet. Independent Astra audits the exact candidate before any local merge. The owner retains authority over any remote effect.
