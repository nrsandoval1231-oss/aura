# FORGE-INT-001 — Wire the orphaned subsystems into the harness

**Node:** FORGE-INT-001
**Authority:** A3 (owner-authorized; scope reaches protected surfaces)
**Risk:** MEDIUM
**Retry budget:** 2

## Objective

Close F15 of the 2026-09-22 audit for the Context Engine and the Governor's budgets.
Both were built, tested, and imported by nothing: `forge/__init__.py` said so in a
comment — "They were previously unreferenced" — and the import existed only so a
missing dependency would fail at import time. A subsystem with no caller is inventory,
not infrastructure, and its guarantees are properties of a library rather than of any
run.

`scripts/run_slice.py` now assembles each role's context through `ContextAssembler`
under the real policy and budget, and drives the loop with a Governor-owned
`BudgetLedger`. The slice evidence records each role's context digest, size receipt,
included source types and — the point — the source types the policy refused, so the
two independence properties can be checked by a reader rather than trusted.

## Base

- `9a56a1e`

## Authority note

Scope reaches `scripts/run_slice.py`, which is a protected surface: it produces the
candidate-bound evidence every packet's audit rests on. Proceeds under direct owner
instruction to complete the V0 build out — authority layer 1 in `AGENTS.md`.

## Allowed files

- `scripts/run_slice.py`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/FORGE-INT-001.md`
- `.agent/artifacts/FORGE-INT-001/**`
- `docs/audit/2026-09-22-repository-audit.md`
- `tests/**`

## Exclusions

- No live model call. The `providers` and `ingestion` seams are **not** closed by this
  packet: stages one through three of the Intent Ingestion Protocol call a model, so
  wiring `Mission` end to end is blocked on the same live call F12 is blocked on.
  `decisions/jev_decisions.py` likewise stays unwired — it advises a Governor that has
  no model to advise about yet.
- No change to the Context Engine or the Governor themselves; this packet wires what
  exists.

## Invariants

- A Builder is never given the specification. A role's forbidden source types are
  recorded in evidence, not asserted in prose.
- An Auditor is never given Builder reasoning.
- Budgets are the Governor's, not the loop's.

## Acceptance

1. The slice assembles Architect, Builder and Auditor contexts through
   `ContextAssembler`, under the real `ROLE_POLICY` and per-role budgets.
2. Each role's context carries provenance, and canonical sources carry A3 rather than
   being flattened to the default.
3. The slice evidence records, per role, the context digest, the size receipt, the
   included source types, and the source types the policy forbade.
4. The evidence asserts both independence properties negatively:
   `builder_was_given_specification` and `auditor_was_given_builder_reasoning` are
   both false, computed from the assembled items rather than declared.
5. The loop runs under a Governor-owned budget ledger and the budget record appears in
   the evidence, naming its unbounded dimensions.
6. Item lists are written per role rather than filtered from one shared list, so the
   independence guarantee does not live in a filter.
7. `./scripts/validate.sh` green.

## Evidence

- `.agent/artifacts/FORGE-INT-001/SLICE.json` — `role_contexts`,
  `context_independence`, and `budget` sections
- `tests/test_slice_contexts.py`

## Stated boundary

This closes F15 for two of the four orphaned subsystems. `providers` and `ingestion`
remain unwired and the audit record is updated to say so rather than marking F15
closed: both need one live model call, which is not authorized here and is the same
thing holding F12 open.
