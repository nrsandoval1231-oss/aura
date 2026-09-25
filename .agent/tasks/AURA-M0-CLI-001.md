# AURA-M0-CLI-001 — Single-builder CLI foundation

Status: READY. Owner request of 2026-09-25 authorizes a reviewable branch and PR, not paid calls, merge, or deployment.

## Objective

Expose the six Aura CLI commands and a durable, bounded request path toward M0/M1. PR #1's expanded PRD is proposed until reviewed.

## Base

- `a581d1485ceb9317dc15ad80f8fd4144be82c875` on `codex/aura-m0-cli-runner` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/tasks/AURA-M0-CLI-001.md`
- `pyproject.toml`
- `src/forge/aura_cli.py`
- `src/forge/aura_runtime.py`
- `tests/test_aura_cli.py`
- `tests/test_aura_runtime.py`
- `tests/test_aura_routing_policy.py`
- `docs/packets/AURA-M0-CLI-001.md`
- `docs/AURA_HANDOFF.md`

Existing `forge` imports and commands remain functional.

## Exclusions and invariants

No provider call, credential change, policy/trust relaxation, protected kernel edit, two-builder scheduler, deployment, merge, or historical evidence rewrite. The Governor controls budgets and scope; ledger receipts remain authoritative. Frozen base, isolated worktree, exact candidate, context separation, independent review, and UNKNOWN effect reconciliation fail closed. A locally configured command must be identified as a local adapter, never as an owner-selected provider.

## Acceptance

Six CLI commands have stable JSON outputs and persistent IDs, with explicit BLOCKED or UNKNOWN where activation lacks authority. A disposable repository test shows a durable bounded build request, inspection, pause/resume, restart persistence and refusal of unconfigured dispatch. No builder, candidate, or review is claimed by this packet. Existing `forge` tests and `./scripts/validate.sh` pass on the frozen candidate. Independent Astra audit inspects that candidate. Retry limit two materially different repairs.

## Handoff

Record base/candidate SHAs, changed files, test output, an offline disposable request transcript, measured spend or UNKNOWN, failed gates, review verdict, and next packet. No M1 live completion claim from offline tests.
