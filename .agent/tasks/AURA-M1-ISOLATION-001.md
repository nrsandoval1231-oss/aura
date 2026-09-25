# AURA-M1-ISOLATION-001 — Isolated check and Git effect design

Status: READY. Replan after independent CORRECT on exact 84a3d01 and 0acb95d.
This is a design and feasibility packet, not another local executor repair.

## Base

- `0acb95d59436f73bfbc326f6a69b23689549fa63` rejected source basis.
- Repository: `nrsandoval1231-oss/aura`; experimental branch
  `codex/aura-m1-executor-spike`.

## Allowed files

- `.agent/tasks/AURA-M1-ISOLATION-001.md`
- `.agent/artifacts/AURA-M1-ISOLATION-001/**`
- `.agent/artifacts/AURA-M1-EXEC-002/REVIEW-0acb95d.json`
- `docs/packets/AURA-M1-ISOLATION-001.md`
- `.agent/CURRENT_STATE.md`
- `.agent/graph/work-graph.json`
- `docs/AURA_HANDOFF.md`

## Objective

Specify and test the smallest real isolation boundary for one disposable Git
task. Separate the trusted controller and append-only receipt writer from all
effectful Git commands, repository-local config, filters, hooks, test code,
network access, host credentials, source checkout, and sibling worktrees.
Durable intent must precede every external effect. An interrupted effect stays
UNKNOWN until reconciled; no blind retry. Fixed tests must run on exact candidate
bytes with a finite time and resource budget.

## Feasibility and acceptance

Ubuntu WSL has Bubblewrap and a read-only primitive worked in a shell probe;
Docker Desktop's daemon was unavailable and Linux pytest is not installed.
The packet must demonstrate a disposable denied-host-file read, denied network,
blocked repository-local Git fsmonitor/filter/include effect, tested exact
candidate, process restart/UNKNOWN, and clean source before implementation is
allowed to call itself trusted. Identify the necessary Linux runtime dependencies
and installation path without spending provider budget. Propose a separate
reviewable implementation packet with exact files, budgets, gates, and rollback.

## Exclusions and authority

No provider call, CLI dispatch, production activation, protected trust/policy
change, credential copy, audit self-approval, merge, deployment, or rewrite of
the two rejected candidates' evidence. Owner-approved auditor key and Aura
verifier migration are separate protected work. Two-builder scheduling is later.

## Handoff

Record exact environment/probe commands, denial results, unresolved OS and Git
risks, deterministic acceptance tests, and the next implementation packet.
