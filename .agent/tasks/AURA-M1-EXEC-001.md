# AURA-M1-EXEC-001 — Isolated candidate executor

Status: READY. This is a local mechanism slice toward M1, authorized by the owner's continued Aura implementation direction. The previous CLI candidate's mandatory detached-audit gate remains blocked.

## Objective

For one typed, explicitly supplied builder proposal in a disposable Git repository, freeze a clean base, create an isolated worktree, apply only bounded file edits, run fixed required checks, and return exact reviewable candidate identity and evidence. Production `aura build` remains blocked; a test fixture is not a DeepSeek or Luna call.

## Base

- `581c4506819f8b7e2e393857193cd5f1295ec42a` on `codex/aura-m0-cli-runner` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-EXEC-001.md`
- `.agent/artifacts/AURA-M1-EXEC-001/**`
- `.agent/ledger/AURA-M1-EXEC-001.*`
- `docs/packets/AURA-M1-EXEC-001.md`
- `docs/AURA_HANDOFF.md`
- `src/forge/aura_executor.py`
- `tests/test_aura_executor.py`

## Exclusions and invariants

No CLI activation, provider call, credentials, owner-pinned trust change, Governor/policy/ledger-kernel edit, automated review, merge, deployment, or rewrite of retained evidence. The supplied proposal is untrusted data. Refuse dirty/changed bases, paths outside exact allowlist, symlinks and protected paths, duplicate/case-colliding paths, check changes, and any non-allowlisted changed file in the isolated worktree. Tests run without shell interpolation, with explicit timeout and finite budget. Keep builder reasoning and credentials out of review evidence. A failure or interruption is recorded as failure/UNKNOWN, not permission to retry.

## Acceptance

Disposable repository proof: one allowed one-file change passes a real deterministic test and yields a detached worktree plus exact Git commit/tree; rejection tests cover path escape, symlink, dirty base, stale base, extra changed path, failed/timeout check, and no original-worktree mutation. The executor returns evidence but never marks an unreviewed candidate COMPLETE or merge eligible. Focused checks, full `./scripts/validate.sh`, and independent Astra review inspect a frozen exact candidate. Missing external audit gate is reported, not weakened. Retry budget two materially different repairs.

## Handoff

Record exact base and source candidate SHA, changed files, check outputs, test repository base/candidate SHA, worktree path, effect/restart behavior actually observed, provider calls and spend, independent audit, and next packet for durable Governor/CLI dispatch.
