# AURA-M1-ISOLATION-003 — Offline WSL sandbox runner

Status: READY; independent feasibility ACCEPT is recorded for AURA-M1-ISOLATION-002
at exact candidate `a30c7fca8f6b300cd33012c4eb618897f76794a6`. This candidate is a
new implementation packet frozen at that base.

## Base and review

- Repository: `nrsandoval1231-oss/aura`
- Branch: `codex/aura-m1-isolated-runner`
- Base SHA: `a30c7fca8f6b300cd33012c4eb618897f76794a6`
- Prerequisite review: `.agent/artifacts/AURA-M1-ISOLATION-003/PREREQUISITE-REVIEW.json`
- This ACCEPT covers reproducible feasibility probes only; it grants no production
  authority and does not satisfy the owner-pinned detached audit gate.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-ISOLATION-003.md`
- `.agent/artifacts/AURA-M1-ISOLATION-003/**`
- `.agent/ledger/AURA-M1-ISOLATION-003.*`
- `docs/packets/AURA-M1-ISOLATION-003.md`
- `src/forge/aura_sandbox.py`
- `src/forge/aura_sandbox_verifier.py`
- `tests/test_aura_sandbox.py`

No edits to `aura_cli.py`, `aura_runtime.py`, the rejected `aura_executor.py`,
provider adapters, Governor/policy, protected audit verifier, AGENTS, PRD,
architecture, or finish contract.

## Objective

Accept one typed offline proposal in a disposable Git repo. Record durable intent
before any target Git or WSL invocation. Launch an explicitly pinned Ubuntu WSL
Bubblewrap process with read-only target/proposal/code binds, writable 5 MiB
candidate tmpfs, no home/credentials/siblings/network, fixed Python 3.14.4 standard
library `unittest`, and no caller-supplied command. Create one isolated Git
worktree inside the sandbox. Run checks on an exact candidate commit. Transfer a
bounded Git bundle and verify it in a fresh sandbox using separate trusted verifier
code; rerun the fixed check with the candidate mounted read-only. Report
`REVIEW_REQUESTED`, never approval. An interrupted or ambiguous effect stays
UNKNOWN across restart and blocks retry.

## Finite budget and authority

- One invocation, one proposal, at most 2 exact-allowlisted text files, at most
  16 KiB per file, at most 32 KiB total.
- One candidate commit and one fixed unittest discovery check. No provider/model
  calls; USD budget $0 for this packet. The separate $5 first DeepSeek ceiling is
  not spend authority here.
- Sandbox wall time at most 90 seconds; fixed Git subprocess timeout 10 seconds;
  test timeout 30 seconds; CPU 30 seconds; address space 512 MiB; at most 32
  processes; captured output at most 1 MiB; candidate tmpfs at most 5 MiB.
  Missing enforceable limits fail closed.
- No network, host credential mount, host home, sibling worktree, caller shell
  interpolation, or production CLI dispatch.
- Reject unexpected WSL distro, Bubblewrap/Python/Git binary digest or runtime
  version, missing namespaces, source mutation, dirty/stale base, symlink/path
  escape, extra changed files, check mutation, or failed check.

## Acceptance and gates

Meaningful tests reproduce the prior self-rewrite and pre-intent Git fsmonitor
failures, exercise local include/filter/hook attempts, deny host-file and network
access, show a clean source and exact rerunnable candidate, and kill a sandbox
after durable intent to prove restart UNKNOWN without duplicate effects. Run
focused tests, Ruff, diff checks and final `./scripts/validate.sh` on the frozen
source candidate. Preserve a separate independent review and the detached audit
gate's UNKNOWN while owner-held trust is unpinned. Do not mark M1 complete or
merge this experimental branch.

## Rollback and checkpoint

The runner remains unwired. A failing or unsafe implementation is rejected and
left disconnected; repair only its source files in a new bounded packet while
retaining append-only evidence and review. Stop after two materially distinct
repairs, return to this packet's sandbox invariants, and replan. Checkpoint after
the first denial regression and before the full runner test. No live provider
spend or CLI activation.
