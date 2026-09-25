# FORGE-VAL-001 — Local-only deterministic validation

## Objective

Make `scripts/validate.sh` the single validation authority and remove the GitHub
Actions workflow. Validation runs locally, on a machine the owner controls, and
its result is recorded as evidence rather than inferred from a green badge.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Branch: `claude/local-validation`
- Base SHA: `cbb63f16febe0b189694b1664db66d2065affb25`
- Python: `>=3.12`

## Authority

- **Owner authorization:** explicit owner instruction, 2026-09-21: "we need to fix
  the github validation. all validation will be done locally. update docs to
  reflect."
- **Authority class:** A3. `AGENTS.md` and `.agent/DECISIONS.md` are protected
  surfaces and are changed here under that authorization.

## Allowed files

- the hosted workflow file, which this packet deletes
- `scripts/validate.sh`
- `scripts/run_slice.py`
- `src/forge/decisions/jev_decisions.py`
- `src/forge/config.py`
- `src/forge/cli.py`
- `src/forge/__init__.py`
- `tests/**`
- `pyproject.toml`
- `.env.example`
- `README.md`
- `AGENTS.md`
- `.agent/DECISIONS.md`
- `.agent/CURRENT_STATE.md`
- `.agent/graph/work-graph.json`
- `.agent/tasks/FORGE-VAL-001.md`
- `.agent/artifacts/FORGE-VAL-001/**`
- `.agent/ledger/**`
- `docs/audit/**`

## Scope notes

`scripts/run_slice.py` and `src/forge/decisions/jev_decisions.py` are in scope
because both referenced the surface being removed: the harness listed the
workflow directory in a packet's allowed paths, and the decision layer's
`__main__` block loaded credentials through `python-dotenv`, which
`src/forge/config.py` now replaces. Removing a surface is not finished while
things still point at it.

## Explicit exclusions

The trust kernel, execution loop, Product Brain, context engine, provider and
decision layers; the canonical architecture and PRD; the Finish Contract; any
live model provider call; any secret value committed to the repository.

## Dependencies and invariants

- Every gate that ran in CI still runs, in the same order, in `validate.sh`.
  Removing the runner must not remove a check.
- No secret is ever committed. `.env` stays ignored; `.env.example` carries
  names and never values.
- A validation claim without a recorded local run is UNKNOWN, not a pass.

## Acceptance checks

1. The hosted workflow is gone and nothing references it.
2. `scripts/validate.sh` runs every gate the workflow ran.
3. A test asserts the local runner covers the required gate set, so a gate cannot
   be dropped silently now that no second copy exists to compare against.
4. `.env.example` names every credential and model variable the code reads, and
   carries no values.
5. `.env` is ignored by git and is loaded when present.
6. README, AGENTS.md, CURRENT_STATE, DECISIONS and the audit record all state that
   validation is local.

## Retry budget

Two materially different bounded repairs per failing acceptance check.

## Required handoff artifacts

- `.agent/artifacts/FORGE-VAL-001/COMPLETION.json`
- `.agent/artifacts/FORGE-VAL-001/REVIEW.json`
- `.agent/artifacts/FORGE-VAL-001/SLICE.json`
- `.agent/ledger/FORGE-VAL-001.jsonl` and its checkpoint
