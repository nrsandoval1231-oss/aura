# FORGE-GOV-001 — Governor budget enforcement

**Node:** FORGE-GOV-001
**Authority:** A3 (owner-authorized; scope reaches protected surfaces)
**Risk:** MEDIUM
**Retry budget:** 2

## Objective

The Finish Contract requires that "the Governor enforces state, scope, authority,
budgets, and valid transitions". Four of the five had implementations: state and
transitions in the trust kernel, scope and authority in the execution loop and the
protected-surface registry. Budgets had none. `BuildPacket.retry_limit` was declared
by every packet and read by nothing, so a packet could declare two retries and take
twenty.

## Base

- `aeecc62`

## Authority note

Scope reaches `src/forge/execution_loop.py`, `src/forge/policy.py` and
`src/forge/__init__.py`. Proceeds under direct owner instruction to complete the V0
build out — authority layer 1 in `AGENTS.md`. `src/forge/governor.py` is registered in
the protected-surface registry in the same packet that creates it, per DEC-011.

## Allowed files

- `src/forge/governor.py`
- `src/forge/execution_loop.py`
- `src/forge/policy.py`
- `src/forge/__init__.py`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/FORGE-GOV-001.md`
- `.agent/artifacts/FORGE-GOV-001/**`
- `tests/**`

## Exclusions

- No canonical intent changes. No live model call.
- No invented cost ceilings: token and currency dimensions stay unset, because no
  live call has been made and there is no real figure to set them from.

## Invariants

- A budget that nothing consults is documentation; every consumption goes through
  `spend`, which refuses once a limit is reached.
- A refused spend consumes nothing, so the recorded figures never drift from reality.
- Exhaustion is a stop, never a grant, and never overspendable by asking twice.
- Unlimited is explicit: `None` means unbounded and the ledger reports which
  dimensions are actually bounded.

## Acceptance

1. Spending within budget is allowed; exhausting it refuses the spend.
2. A refused spend consumes nothing and is still recorded — a refusal is the moment a
   limit did something.
3. A zero or negative limit is refused, because `None` already means unlimited and
   zero would silently mean blocked.
4. A zero or negative spend is refused, because a free charge would let unbounded work
   through a bounded dimension.
5. `remaining` on an unlimited dimension is `None`, not zero and not infinity.
6. The ledger names its unbounded dimensions, so "is this packet budgeted?" does not
   require reading five fields.
7. `retry_limit` now has a reader: absent an explicit budget it becomes the attempts
   budget, counted as the first attempt plus the declared retries.
8. A handoff refused for a protocol error does not consume a retry; only an accepted
   candidate does.
9. A budget ledger may be owned by the Governor and span loop instances, because a
   retry is a new loop and a per-loop budget could never be exhausted.
10. One packet's attempts cannot be charged to another packet's budget.
11. `./scripts/validate.sh` green.

## Evidence

- `.agent/artifacts/FORGE-GOV-001/COMPLETION.json`
- `tests/test_governor.py` — 26 cases
- `tests/test_execution_loop.py` — 4 new budget-enforcement cases
