# AURA-M0-CLI-002 — Correct and bind CLI candidate

Status: READY. Separate successor after independent CORRECT on 53fb0e3; preserve AURA-M0-CLI-001 evidence unchanged.

## Objective

Refuse partial ledger-pair loss, reconcile handoff claims, and bind the corrected six-command M0 CLI to deterministic gates and fresh independent review. Build remains blocked without an authorized builder and trust.

## Base

- `53fb0e325b45e03af53e3bb574e98a971b64a724` on `codex/aura-m0-cli-runner` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M0-CLI-001.md`
- `.agent/tasks/AURA-M0-CLI-002.md`
- `.agent/artifacts/AURA-M0-CLI-001/REVIEW-53fb0e3.json`
- `.agent/artifacts/AURA-M0-CLI-002/**`
- `.agent/ledger/AURA-M0-CLI-002.*`
- `docs/packets/AURA-M0-CLI-001.md`
- `docs/AURA_HANDOFF.md`
- `src/forge/aura_runtime.py`
- `tests/test_aura_runtime.py`

## Exclusions and invariants

No historical ledger or slice rewrite, provider call, protected trust or policy change, new executor, merged PR, deployment, or authority expansion. The append-only ledger stays authoritative; missing JSONL or checkpoint is UNKNOWN/BLOCKED and cannot reset history. Existing `forge` commands remain. PR #1 is draft and unreviewed. The simulated slice is not an external audit or merge authority.

## Acceptance and handoff

Both partial-ledger cases preserve surviving bytes and refuse all reads/mutations. Frozen candidate passes focused tests and `./scripts/validate.sh`, except for a clearly reported external-audit gate if owner-pinned trust is still absent. Fresh Astra review inspects exact commit. Record base/candidate, changed files, test output, spend, blocked M1 work, and next bounded packet. Retry budget: one repair within this successor.
