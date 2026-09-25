# FORGE-FIX-004 — Close the 2026-09-22 reaudit findings

**Node:** FORGE-FIX-004
**Authority:** A3 (owner-authorized; scope reaches protected surfaces)
**Risk:** HIGH
**Retry budget:** 2
**Kind:** Repair under DEC-006 — restores merged code to intent its own nodes
already approved. Adds no capability.

## Objective

Close F9-F11, F13, F14, and F16 of `docs/audit/2026-09-22-repository-audit.md`.
F12 cannot be closed without a live model call and is recorded as UNKNOWN.

## Base

- `df51dfa`

`AGENT_RULES` requires a packet to record its base identity. This one records it
because it has to: the branch carries a second packet, and diffing against
`origin/main` would hand this packet the other one's changed paths and fail its own
scope check. The candidate a packet certifies is what that packet changed.

## Authority note

This packet's scope reaches protected surfaces — `.agent/DECISIONS.md`,
`src/forge/execution_loop.py`, the evidence ledger, `scripts/validate.sh`, and the
work graph. It proceeds under direct owner instruction to complete the V0 build
out, which is authority layer 1 in `AGENTS.md`. That authorization is recorded here
rather than assumed, because F9 is a finding about authority checks being weaker
than they looked, and repairing it under an unrecorded grant would reproduce the
category of problem.

## Allowed files

- `src/forge/policy.py`
- `src/forge/execution_loop.py`
- `src/forge/ledger_store.py`
- `src/forge/cli.py`
- `src/forge/providers/model_provider.py`
- `scripts/validate.sh`
- `.env.example`
- `README.md`
- `.agent/DECISIONS.md`
- `.agent/CURRENT_STATE.md`
- `.agent/graph/work-graph.json`
- `.agent/tasks/FORGE-FIX-004.md`
- `.agent/artifacts/FORGE-FIX-004/**`
- `docs/audit/2026-09-22-repository-audit.md`
- `tests/**`

## Exclusions

- `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md`, `FORGE_AGENT_V0_PRD.md`, `AGENTS.md`,
  `docs/finish-contract.md` — no canonical intent changes in a repair.
- No live model call. No new capability.

## Invariants

- Fail closed on absent or ambiguous evidence.
- No in-code default model ids.
- Evidence is never destroyed to recover from a fault.
- One implementation of each security-relevant rule.

## Acceptance

1. Every surface F9 measured as unprotected requires A3, asserted by name.
2. A declared protected path that stops existing fails the build.
3. A crash between the two ledger writes is recoverable without discarding
   evidence, and the recovery is a deliberate call rather than a side effect of
   reading.
4. Two capabilities routing to one provider resolve different model ids, and every
   documented capability model variable is reachable.
5. A cross-family audit reroute cannot silently resolve the final-gate model, and
   the variable it did resolve appears in the receipt.
6. `.env.example` carries no values at all, asserted for every variable.
7. `forge graph check` fails on the README contradiction it previously passed, and
   on an unbackticked status contradiction.
8. The Python floor is gate zero and is asserted by `test_gate_parity.py`.
9. `./scripts/validate.sh` green.

## Evidence

- `.agent/artifacts/FORGE-FIX-004/COMPLETION.json`
- `tests/test_policy.py` — 47 cases, including the existence assertion
- `tests/test_ledger_store.py` — 6 new crash-window cases
- `tests/test_model_provider.py` — 5 new capability-routing cases
- `tests/test_cli.py` — 6 new consistency-gate cases
