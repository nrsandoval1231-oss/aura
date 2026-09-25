# FORGE-LOOP-001 — Architect → Builder → Auditor proving loop

## Objective

Implement one deterministic Build Packet lifecycle from validated architecture output through bounded builder handoff, exact candidate identity, independent audit, and Governor-only merge eligibility. This proves Canonical Phase 3 without model integration or autonomous continuation.

## Authority

- Classification: `A3` protected governance implementation.
- Owner authorization: `PRESENT` — the repository owner directed this governed implementation to proceed and subsequently directed all three dependent pull requests to be merged in this Codex task on 2026-09-18.
- Scope: the files and acceptance contract in this packet only; no deployment, external effects, secrets, destructive operations, or autonomous modification of protected governance.
- The authorization does not replace exact-candidate validation or independent audit.

## Base identity

- Branch: `codex/forge-loop-001`
- Stacked base: `codex/forge-pb-001`
- Base SHA: `c044a14ea8974676a6274cd9d95ed8280a00fd3c`
- Dependency PRs: `#1`, `#2`

## Allowed files

- `src/forge/execution_loop.py`
- `src/forge/__init__.py`
- `tests/test_execution_loop.py`
- `.agent/tasks/FORGE-LOOP-001.md`
- `.agent/artifacts/FORGE-LOOP-001/**`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/DECISIONS.md`

## Exclusions

No model providers, actual code generation, shell/Git effects, merge execution, discovery validation, specification mutation, parallel builds, stuck resolution, persistence adapter, autonomous continuation, deployment, or Learning Engine.

## Invariants

- Build Packets are typed, bounded, candidate-base-bound, and refer only to known active requirements.
- Builder outputs are claims and cannot contain a valid PASS verdict.
- Changed paths must remain inside allowed patterns and outside forbidden patterns.
- Required evidence must be present before audit eligibility.
- Auditor role and context are independent from Builder role and context.
- Audits bind to exact immutable candidate identity; mutation invalidates the audit.
- Only deterministic Governor logic can mark a candidate merge eligible.
- UNKNOWN never becomes PASS or merge eligibility.
- Every lifecycle mutation emits an append-only receipt.

## Acceptance

- Demonstrate one valid packet through candidate, tests/evidence, independent audit PASS, and merge eligibility.
- Reject unknown requirements, contradictory Product Brain state, wrong repositories, candidate/base mismatch, forbidden or out-of-scope paths, missing evidence, Builder-authored audit, shared Builder/Auditor context, malformed verdicts, and changed candidates.
- Preserve unexpected observations as observations only; do not mutate specification.
- Existing trust-kernel and Product Brain suites remain green.
- Repeated tests, Ruff, compilation, and diff checks pass.

## Validation

```text
uv run --python 3.13 --with pytest --with ruff pytest
uv run --python 3.13 --with ruff ruff check .
uv run --python 3.13 python -m compileall -q src tests
git diff --check
```

## Risk and recovery

- Risk: role self-certification, context leakage, or candidate identity drift.
- Repair budget: two materially different bounded repairs.
- Ambiguous evidence or identity remains UNKNOWN and blocks continuation.

## Artifacts

- `.agent/artifacts/FORGE-LOOP-001/COMPLETION.json`
- `.agent/artifacts/FORGE-LOOP-001/REVIEW.json`
