# AURA-INTEGRATED-002 — Aura reconciliation and corrected runner checkpoint

Status: READY. This corrected successor integrates FORGE-ADAPT-001,
AURA-MIG-001, and AURA-RUN-001 without granting their historical candidates
acceptance in Aura.

## Objective

Bind the actual Aura integration candidate to the local full gate, preserve
source history, and obtain an independent audit of what the first local
two-builder runner does and does not enforce. This is a checkpoint toward the
owner's full Aura mission, not a Finish Contract completion claim.

## Base

- `bd534f7c8b4aa7c93b2e1550ee3fbb953a4121ca`

## Allowed files

- `.agent/CURRENT_STATE.md`
- `.agent/graph/work-graph.json`
- `.agent/tasks/FORGE-ADAPT-001.md`
- `.agent/tasks/AURA-MIG-001.md`
- `.agent/tasks/AURA-RUN-001.md`
- `.agent/tasks/AURA-INTEGRATED-001.md`
- `.agent/tasks/AURA-INTEGRATED-002.md`
- `docs/packets/AURA-RECON-001.md`
- `.agent/artifacts/AURA-MIG-001/**`
- `.agent/artifacts/AURA-RUN-001/**`
- `.agent/artifacts/AURA-INTEGRATED-001/**`
- `.agent/artifacts/AURA-INTEGRATED-002/**`
- `.agent/ledger/AURA-INTEGRATED-001.jsonl`
- `.agent/ledger/AURA-INTEGRATED-001.checkpoint.json`
- `.agent/ledger/AURA-EVID-001.jsonl`
- `.agent/ledger/AURA-EVID-001.checkpoint.json`
- `docs/AURA_HANDOFF.md`
- `docs/product/AURA_PRODUCT_DIRECTION.md`
- `docs/source/forge-current-state-at-import.md`
- `docs/integration/aura-runner.md`
- `src/forge/engineering_runner.py`
- `tests/test_engineering_runner.py`
- `scripts/run_slice.py`
- `tests/test_slice_contexts.py`

## Exclusions

No rewriting historical Forge ledgers, signed receipts, completion artifacts,
or canonical product documents. No silent change to cross-family audit policy,
provider model fallback, validator, or protected trust roots. No paid call,
push, merge, deployment, or autonomous external effect.

## Dependencies and invariants

The imported controller is a source implementation, not Aura acceptance.
Builder callback tests are local evidence only. Actual current repository and
candidate identity must be derived from Git. Required checks stay fixed and
missing results stay UNKNOWN. Independent Astra audit must inspect the frozen
candidate; a changed candidate requires fresh validation and review. Keep
outstanding full-loop obligations open and explicit.

## Acceptance and validation

- `scripts/validate.sh` exits zero on the exact candidate, including the
  active-slice and all historical-ledger gates.
- The product direction, Aura state, handoff, packets, and graph agree.
- Local one-lane and two-lane runner tests prove isolated worktrees, scope,
  checks, review gating, replay refusal, and mutation rejection.
- Astra independently returns ACCEPT, CORRECT, REDIRECT, ESCALATE, or
  COMPLETE_CANDIDATE with evidence, and Sol records the next direction.
- Any incomplete production trust, provider, learning, integration, or live
  proof remains a named future node and does not count as this checkpoint's
  success or overall product completion.

## Authority, risk, recovery, handoff

A3 graph/evidence integration authorized by the current owner request. Two
materially distinct repairs maximum. Sol owns integration and exact-candidate
validation; Astra independently audits. Handoff retains base/candidate SHA,
tree, changed files, check exits, durations if measured, review, and UNKNOWNs.
