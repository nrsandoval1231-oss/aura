# FORGE-PB-001 — Product Brain and Living Specification

## Objective

Implement the smallest deterministic Product Brain required by Canonical Architecture Phase 2: ingest owner-controlled intent and requirements, track assumptions, decisions and invariants, version requirements with lineage, maintain a Finish Contract, produce a stable specification hash, detect simple contradictions, and reconstruct state from append-only specification receipts.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Branch: `codex/forge-pb-001`
- Stacked base branch: `codex/forge-tk-001`
- Base SHA: `e292c9e004fb5c18f5c81df261f63c66ad710b04`
- Base PR: `#1`

## Allowed files

- `src/forge/product_brain.py`
- `src/forge/__init__.py`
- `tests/test_product_brain.py`
- `.agent/tasks/FORGE-PB-001.md`
- `.agent/artifacts/FORGE-PB-001/**`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/DECISIONS.md`

## Exclusions

No model agents, Product Brain reasoning, discovery acceptance, specification evolution from unvalidated observations, Architect/Builder/Auditor loop, Git effects, merges, SQLite adapter, Learning Engine, deployment, or changes to canonical authority documents.

## Dependencies and invariants

- `FORGE-TK-001` is complete at the stacked base and PR #1 remains unmodified and unmerged.
- North Star and Finish Contract replacement require owner authority.
- Requirement mutation preserves immutable versions and explicit lineage.
- Missing references and malformed replay fail closed or remain explicit contradictions.
- Specification hashing is deterministic and insensitive to insertion order.
- Every Product Brain mutation emits an append-only receipt with before/after specification hashes.
- UNKNOWN and unresolved contradictions cannot be represented as success.
- Self-improvement evidence fields and the `FORGE-SI-001` V0 gate remain preserved.

## Acceptance checks

- Ingest North Star, Finish Contract, requirements, assumptions, decisions, and invariants.
- Enforce requirement lifecycle and reject invalid transitions.
- Version requirements with exact version increments and supersession lineage.
- Detect missing requirement dependencies, missing assumptions, and references to inactive requirements.
- Produce a stable specification hash across equivalent insertion orders.
- Replay receipts into the same Product Brain and detect corrupted or malformed records.
- Prevent owner-controlled intent or Finish Contract replacement without A3 authority.
- Retain explicit evidence contracts and UNKNOWN-compatible states.
- Existing trust-kernel tests and all repository gates pass repeatedly.

## Validation

```text
uv run --python 3.13 --with pytest --with ruff pytest
uv run --python 3.13 --with ruff ruff check .
uv run --python 3.13 python -m compileall -q src tests
git diff --check
```

## Risk and recovery

- Risk: silent specification drift or lineage loss.
- Repair budget: two materially different bounded repairs.
- Any conflict with canonical authority returns `ESCALATE`; missing evidence remains `UNKNOWN`.

## Required artifacts

- `.agent/artifacts/FORGE-PB-001/COMPLETION.json`
- `.agent/artifacts/FORGE-PB-001/REVIEW.json`
- exact candidate SHA/tree, validation evidence, changed files, remaining risks, and one next direction.
