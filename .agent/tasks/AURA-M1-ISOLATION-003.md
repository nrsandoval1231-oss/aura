# AURA-M1-ISOLATION-003 — Offline WSL sandbox runner proposal

Status: PROPOSED; dependency AURA-M1-ISOLATION-002 must receive independent
acceptance first. Freeze its exact accepted SHA as this packet's base before
dispatch. This packet grants no live provider or CLI authority.

## Allowed files

Planned scope, inactive until this packet becomes READY:

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

Accept one typed offline proposal in a disposable Git repo. Record durable
intent before any target Git or WSL effect. Launch a network-isolated Ubuntu
Bubblewrap process with read-only source and proposal binds, writable bounded
candidate output, no home/credentials/siblings, fixed Python 3.14.4 standard
library `unittest`, and no caller-supplied command. Create one isolated Git
worktree inside the sandbox. Run checks on an exact candidate commit. Verify
commit/tree, changed paths, content and check result in a fresh read-only
sandbox using trusted verifier code; report `REVIEW_REQUESTED`, never approval.
An interrupted or ambiguous effect stays UNKNOWN across restart and blocks
retry until explicit reconciliation.

## Finite budget and authority

- One invocation, one proposal, at most 2 exact-allowlisted text files,
  at most 16 KiB per file, at most 32 KiB total.
- One candidate commit, one fixed unittest discovery check. No provider/model
  calls; USD budget $0 for this packet. The separate $5 first DeepSeek ceiling
  is not spend authority here.
- Sandbox wall time at most 90 seconds; fixed Git subprocess timeout 10 seconds;
  test timeout 30 seconds; CPU 30 seconds; memory 512 MiB; at most 32 processes;
  captured output at most 1 MiB; candidate output at most 5 MiB. Missing
  enforceable resource limits fail closed.
- No network, host credential mount, host home, sibling worktree, controller
  receipt mount, user shell interpolation, or production CLI dispatch.
- Reject an unexpected WSL distro, Bubblewrap binary, Python/Git runtime
  version or digest, missing sandbox, source mutation, dirty/stale base,
  symlink/path escape, extra changed files, check mutation, or failed check.

## Acceptance and gates

Meaningful tests must reproduce the prior self-rewrite and pre-intent Git
fsmonitor failures, exercise local `include`, filter and hook attempts, deny
host file and network access, show a clean source and exact rerunnable
candidate, and kill a sandbox after intent to prove restart UNKNOWN without
duplicate effects. Run focused tests, Ruff, diff checks and final
`./scripts/validate.sh` once per frozen source candidate. Preserve a separate
independent Astra verdict and the detached audit gate's UNKNOWN if the
owner-held public key is still unpinned. Do not mark M1 complete or merge the
experimental branch from this offline proof.

## Rollback and checkpoint

The runner is a new unwired module. A failing or unsafe implementation is
rejected and left disconnected; revert only its source files in a new bounded
repair while retaining the append-only evidence and review. Stop after two
materially distinct repairs, return to this packet's sandbox invariants, and
replan. Checkpoint after the first denial regression and before any integration.
