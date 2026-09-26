# AURA-RUN-001 — Governed two-builder execution loop

Status: READY under the current owner Aura mission. This packet builds the first
operational local runner on the imported adaptive controller.

## Objective

Accept bounded independent tasks, dispatch at most one task to each of the
DeepSeek and Luna lanes in isolated Git worktrees, enforce checks and recovery
before retries, require independent candidate review, preserve restart state,
and make reviewed lessons available at later compatible slice boundaries.

## Base

- `bd534f7c8b4aa7c93b2e1550ee3fbb953a4121ca` on Aura `main` at dispatch;
  development branch `codex/aura-governed-runner` contains AURA-MIG-001 work.

## Allowed files

- `src/forge/engineering_runner.py`
- `tests/test_engineering_runner.py`
- `docs/integration/aura-runner.md`
- `.agent/tasks/AURA-RUN-001.md`
- `.agent/artifacts/AURA-RUN-001/**`
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `docs/AURA_HANDOFF.md` (Sol only)

## Exclusions

Do not edit canonical architecture, PRD, Finish Contract, AGENTS.md, existing
Governor/policy/trust/ledger/controller modules, historical receipts, provider
identifiers, or validation authority. Do not call paid models, push, merge,
deploy, or execute arbitrary external effects.

## Dependencies and invariants

Use existing SliceLearning, StuckDetector, Governor, BuildPacket, path policy,
and audit verification as authority boundaries. Caller-supplied reviewer labels
or keys cannot become trust roots. Each task has fixed checks and allowed files;
builders cannot alter either. Worktrees, packets, contexts, candidate identity,
and execution state are separate. Conflicting paths and dependencies serialize.
Interrupted effects remain UNKNOWN and block replay. Any lesson is only applied
from an authenticated reviewed snapshot at a new compatible slice boundary.

## Acceptance and validation

- Tests drive one local real file change and two independent concurrent local
  changes using isolated worktrees; integration is serial and review-gated.
- Repeated failure or repeated patch requires a materially different strategy;
  exhausted retries replan/escalate. Missing credentials/environment failures do
  not consume implementation repair budget.
- Restart does not duplicate an ambiguous effect. Cancellation and budget
  exhaustion block further execution. Missing checks remain UNKNOWN.
- Reviewed lesson changes a later strategy, comparable outcome measures it,
  harmful lesson withdrawal blocks future retrieval while preserving history.
- Focused tests, Ruff, full `scripts/validate.sh`, candidate-bound evidence,
  and independent Astra review before any completion claim.

## Authority, risk, recovery, handoff

A3 runtime integration expressly requested by owner. Two materially different
repair attempts. Luna owns only its three code/test/doc files and completion
artifact; Sol owns graph, state, integration, and final validation. Builder
handoff must include exact files, command exits, candidate, UNKNOWNs, and limits.
