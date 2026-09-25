# AURA-M1-EXEC-002 — Repair exact candidate binding

Status: READY. This is a repair-only successor to the independently rejected
AURA-M1-EXEC-001 candidate. The raw CORRECT and reproduction are retained in
`.agent/artifacts/AURA-M1-EXEC-001/REVIEW-84a3d01.json`.

## Base

- Repository: `nrsandoval1231-oss/aura`; branch: `codex/aura-m0-cli-runner`.
- `84a3d014c578cf28a0115238ffabbe86a19927a3` frozen source base.
- Builder owns only `src/forge/aura_executor.py` and `tests/test_aura_executor.py`.
- Sol owns graph, task, docs, evidence, and handoff records.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-EXEC-002.md`
- `.agent/artifacts/AURA-M1-EXEC-001/REVIEW-84a3d01.json`
- `.agent/artifacts/AURA-M1-EXEC-002/**`
- `.agent/ledger/AURA-M1-EXEC-002.*`
- `docs/AURA_HANDOFF.md`
- `src/forge/aura_executor.py`
- `tests/test_aura_executor.py`

## Objective

Refuse any candidate whose bytes or tree differ from those tested. Add a
regression reproducing an allowed test file rewriting itself while passing;
the executor must not return `REVIEW_REQUESTED` for those bytes. A passing
one-file disposable task must still produce a candidate whose exact committed
tree is independently rerunnable. Preserve fail-closed UNKNOWN and append-only
effect receipts.

Contain local Git effects as far as this offline fixture permits: disable
hooks with a non-directory device path, scrub Git subprocess environment and
config, apply finite Git timeouts, and test meaningful hostile inputs. Do not
claim OS sandboxing. Document that arbitrary repository checks run with the
host user's filesystem authority, so production provider proposals and CLI
dispatch remain blocked pending a separate trusted isolation and audit packet.

## Invariants and exclusions

No provider calls, credentials, CLI activation, protected Governor/policy/trust
edits, audit self-approval, merge, deployment, retry of UNKNOWN, or evidence
rewrites. Preserve original source worktree. Fixed checks, exact allowlist,
candidate identity, finite budgets, and code/review context separation remain.

## Validation and handoff

Run focused tests and Ruff. Sol reruns focused checks and `./scripts/validate.sh`
once on a frozen exact candidate, then obtains fresh independent Astra verdict.
Missing detached external audit is reported as failed. Retry budget: one more
materially different repair after this, then replan. Record changed files, SHA,
test evidence, failure evidence, provider calls, and spend.
