# FORGE-TK-001 — Deterministic trust kernel

## Objective

Implement the smallest local-first deterministic trust kernel that enforces mission state transitions, authority, exact repository and candidate identity, append-only receipts, replay, integrity verification, UNKNOWN handling, and restart reconciliation. Preserve the evidence foundations required by the governed self-improvement loop without implementing the Learning Engine.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Remote: `https://github.com/nrsandoval1231-oss/forge-agent.git`
- Branch: `codex/forge-tk-001`
- Base SHA: `f54c84e8c1f234dcf042d85d81f5fd8d93b9f1e1`
- Python: `>=3.12`

## Allowed files

- `src/forge/**`
- `tests/**`
- `pyproject.toml`
- `.agent/tasks/FORGE-TK-001.md`
- `.agent/artifacts/FORGE-TK-001/**`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/DECISIONS.md`
- `docs/finish-contract.md`
- `docs/self-improvement-acceptance.md`

## Explicit exclusions

Product Brain, living-specification reasoning, model/provider integrations, agent roles, autonomous merges, discovery/spec evolution, full Learning Engine, cloud/deployment, browser automation, production writes, Sentinel, and changes to canonical architecture, PRD, AGENT_RULES, or AGENTS.md.

## Dependencies and invariants

- FORGE-REPO-001 is complete and canonical documents remain unchanged.
- Owner authorization is the pasted continuation request for this packet.
- Owner intent, authority, audit independence, security, event integrity, Finish Contract protections, and protected policy remain outside autonomous self-modification.
- Missing or ambiguous evidence is `UNKNOWN`, never success.
- Candidate identity is immutable and candidate-bound validation becomes invalid after mutation.
- Every meaningful transition produces a durable receipt; receipts are append-only and replayable.
- Restart reconciliation never blindly replays an ambiguous effect.
- V0 global automatic lesson promotion remains disabled.

## Acceptance checks

- All allowed transitions succeed and invalid transitions fail closed.
- Protected actions require the required authority; ordinary actions remain bounded.
- Repository and candidate identity mismatch fails closed.
- Receipts preserve provenance, reject mutation, detect ledger corruption, and replay deterministically.
- Missing evidence and ambiguous interrupted effects remain `UNKNOWN`.
- Malformed persisted records fail closed.
- Candidate mutation invalidates candidate-bound validation.
- Self-improvement acceptance contract traces Sections 216–222, 233, 238, 263, and 268; records attributable outcomes and candidate lessons, validates/rejects and scopes promotion, retains negative knowledge, retrieves lessons for planning, proves a later decision changed, measures a named outcome, supports demotion/rollback, and keeps automatic global promotion disabled.
- Repeated deterministic test runs, formatting, lint, type checks, affected tests, and diff checks pass.
- No secrets or unrelated changes are present.

## Validation commands

```text
python -m pytest
python -m ruff check .
python -m compileall -q src tests
git diff --check
```

## Authority, risk, and retry budget

- Authority: A1 implementation within this packet; protected governance changes are excluded.
- Risk: trust-kernel integrity and audit-boundary risk; fail closed on uncertainty.
- Repair budget: two materially different bounded repairs.

## Required handoff artifacts

- `.agent/artifacts/FORGE-TK-001/COMPLETION.json`
- `.agent/artifacts/FORGE-TK-001/REVIEW.json`
- exact candidate SHA, tree SHA, changed files, command results, and remaining UNKNOWNs.
