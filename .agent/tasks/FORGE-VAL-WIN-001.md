# FORGE-VAL-WIN-001 — Preserve executable validation on Windows

**Node:** FORGE-VAL-WIN-001
**Authority:** A3 owner-authorized validation repair, separate from FORGE-ING-001
**Risk:** MEDIUM
**Retry budget:** 2

## Objective

The local validation authority cannot generate a new integrated candidate receipt on this Windows checkout because `test_runner_is_executable` checks `stat.S_IXUSR` on NTFS, where the mode bit is absent even though Git records `scripts/validate.sh` as `100755`. Retain the actual executable invariant on POSIX and verify Git's executable mode on Windows. This is a separate repair of the known Windows gate failure, not a weakening of ingestion evidence.

## Base

- `7d786156df403adc20b41b751546364522be28bb`

## Allowed files

- `tests/test_gate_parity.py`
- `.agent/tasks/FORGE-VAL-WIN-001.md`
- `.agent/artifacts/FORGE-VAL-WIN-001/**`
- `.agent/graph/work-graph.json` (Sol only)

## Read if needed

- `scripts/validate.sh`
- `docs/adr/0001-local-first-evidence-governed-v0.md`
- `.agent/AGENT_RULES.md`

## Exclusions

- No change to `scripts/validate.sh`, its Git mode, the required gate set, the evidence ledger, trust kernel, ingestion code, protected canonical documents, or old packet receipts.

## Invariants

- A checkout on a POSIX filesystem must have the actual owner execute bit.
- The Git index must record the runner as executable (`100755`) on every platform, including Windows; missing or `100644` fails.
- The test must not skip Windows or silently pass when Git cannot identify the tracked path.

## Acceptance

1. Reproduce the current Windows failure on the base with Git mode `100755` and absent `stat.S_IXUSR`.
2. Validate both modes: `100755` passes and `100644` or untracked runner fails in a focused isolated fixture or subprocess, without changing the real repository mode.
3. On POSIX, also assert `SCRIPT.stat().st_mode & stat.S_IXUSR`.
4. Focused test and full pytest pass on this Windows checkout; Ruff and diff checks pass.
5. Record exact candidate SHA, commands, exit codes, and remaining unknowns; preserve all old evidence.

## Handoff

Builder implements only the owned test and completion artifact. Sol reruns gates and requests independent audit. No builder self-certification, commit, push, merge, deployment, spend, or graph status change.
