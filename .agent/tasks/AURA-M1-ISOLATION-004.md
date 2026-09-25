# AURA-M1-ISOLATION-004 — Bind corrected offline runner evidence

Status: READY. Evidence-only successor to AURA-M1-ISOLATION-003, whose retained
slice binds the earlier ecd2cef candidate and must remain unchanged.

## Base

- Repository: `nrsandoval1231-oss/aura`
- Branch/worktree: `codex/aura-m1-isolated-runner` in `C:\Users\nrsan\.codex\worktrees\aura-m1-isolated-runner\Aura`
- Base SHA: `825dba817461a54ccbe0b76d6603635e172075b6`
- Dependencies: AURA-M1-ISOLATION-002 independent bounded ACCEPT at `a30c7fca8f6b300cd33012c4eb618897f76794a6`; AURA-M1-ISOLATION-003 implementation and real restart proof retained at base.

## Objective

Bind the existing offline WSL runner and fresh-process restart proof to one new
exact source candidate. Retain both AURA-M1-ISOLATION-003 candidate commits and
its append-only ledger/slice unchanged. Obtain independent security review of
the complete source at the new exact candidate. This is an offline review
request, not production or CLI authority.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-ISOLATION-004.md`
- `.agent/artifacts/AURA-M1-ISOLATION-004/**`
- `.agent/ledger/AURA-M1-ISOLATION-004.*`
- `docs/packets/AURA-M1-ISOLATION-004.md`

No source, test, provider, CLI, Governor, protected verifier, trust record,
prior packet artifact, prior ledger, PRD, architecture, finish contract, or
AGENTS edits. Any functional repair requires another bounded packet.

## Acceptance and validation

- Confirm base and clean worktree; inspect prior raw fresh-process kill and WSL
  denial outputs, one durable intent, no retry effect, fixed check, exact Git
  candidate and read-only verifier.
- Run focused `tests/test_aura_sandbox.py`, Ruff, diff checks, and
  `./scripts/validate.sh` against the frozen candidate. Record every failed
  gate. The external detached audit remains UNKNOWN until owner trust is pinned.
- Produce new append-only slice and ledger evidence for this packet without
  `--rebind` or editing prior streams. Preserve raw independent verdict bound to
  the exact commit. Never turn local simulated `MERGE_ELIGIBLE` into approval.
- Independent review must inspect scope, authority, credential isolation,
  resource limits, hostile Git config, exact candidate/test binding, effect
  replay, restart UNKNOWN, and evidence before a reviewable PR is claimed.

## Budget and checkpoint

No provider calls or spend; USD budget $0. One evidence candidate and one
material repair at most. Checkpoint before freeze. If a gate or independent
review finds a source defect, stop this packet and create a new repair packet.
Do not push, merge, deploy, or activate the runner from this packet.
