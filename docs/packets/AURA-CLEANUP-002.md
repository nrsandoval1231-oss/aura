# AURA-CLEANUP-002 — consolidate approved direction and restore source validation

## Objective
Save the owner's approved product direction on main, repair inherited source checks,
and remove obsolete task packets from the active queue while preserving their bytes.
Authority: Nick requested entire-repository cleanup, appropriate closures and merges
on September 25, 2026, 23:40 America/Chicago. No provider calls or deployment.

## Base
Main 0dd62aae4959227a5c5a2d7cb618bbd7616bfef4; direction PR #9 at
5096cda24c36f1cd7247888b3de2855e7f8929c8 is the immediate parent.
Clean worktree verified; branch codex/aura-repo-cleanup.

## Allowed files
- `scripts/run_slice.py`
- `tests/test_slice_contexts.py`
- `.agent/tasks/AURA-INTEGRATED-001.md`
- `.agent/tasks/AURA-INTEGRATED-002.md`
- `.agent/tasks/AURA-MIG-001.md`
- `.agent/tasks/AURA-RUN-001.md`
- `docs/archive/packets/**`
- `docs/archive/packet-manifest.json`
- `docs/archive/README.md`
- `docs/REPOSITORY_CLEANUP.md`
- `docs/packets/AURA-CLEANUP-002.md`
- `.agent/CURRENT_STATE.md`
- `docs/AURA_HANDOFF.md`

## Dependencies and invariants
PRs #1–#8 were already closed unmerged as superseded before this cleanup. Do not
reactivate them or infer their code is accepted. Preserve unique branch commits,
all existing runtime receipts, artifacts and ledger bytes. Do not change graph
milestone status, policy, trust, validation gates, roles, model routing or budgets.
Archived packets retain old claims as history only; current runner/trust/proof
milestones remain open. No imported runtime is approved by this task.

## Acceptance and validation
Full scripts/validate.sh on the exact candidate, meaningful regression assertions,
archive hash parity, clean diff and independent exact-candidate review. Missing-ledger
failure remains fail-closed. Malformed-record tests must reach the intended check
through a valid preceding fixture. Check local links and PRD <=50 requirements.

## Risk, recovery and handoff
Protected validation source and test repairs require independent review. At most two
materially different repairs before replanning. Record full gate output and exact SHA
in the PR. Publish with GitHub connector; normal terminal push is unauthenticated.
Merge only reviewed passing work. Do not close or delete unrelated active work.
