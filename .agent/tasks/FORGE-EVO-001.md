# FORGE-EVO-001 — Prove governed specification evolution and restart reconciliation

**Node:** FORGE-EVO-001
**Authority:** A3 (owner-authorized; scope reaches protected surfaces)
**Risk:** MEDIUM
**Retry budget:** 2

## Objective

Two Finish Contract clauses had implementations and no demonstration. Both were
exercised only by unit tests and appeared in no harness, so nothing showed the pieces
working together on real state: "discovery can validate or reject specification changes
with lineage", and "local, remote, and any runtime state are separately reconciled".

The contract is explicit that the first is not satisfied by having the states:
completion "requires demonstrated failure recovery, observation-to-discovery
processing, governed specification evolution, and subsequent execution that uses the
evolved specification; producing a packet alone is insufficient."

## Base

- `d5e3c9b`

## Authority note

Scope reaches `scripts/validate.sh` and `src/forge/policy.py`. Proceeds under direct
owner instruction to complete the V0 build out — authority layer 1 in `AGENTS.md`.

## Allowed files

- `scripts/prove_governed_evolution.py`
- `scripts/validate.sh`
- `src/forge/policy.py`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/FORGE-EVO-001.md`
- `.agent/artifacts/FORGE-EVO-001/**`
- `docs/audit/2026-09-22-repository-audit.md`
- `tests/**`

## Exclusions

- No live model call. No canonical intent changes.
- No change to the trust kernel or the Product Brain: this packet proves what they
  already do. If a proof needed them altered to pass, the proof would be wrong.

## Invariants

- UNKNOWN is preserved and never resolved in either direction.
- A specification change requires validated discovery, lineage, and sufficient
  authority.
- Evidence bound to the wrong effect is refused, not downgraded to UNKNOWN.

## Acceptance

1. The mission reaches SPEC_EVOLUTION only by the kernel's own legal path, asserted
   against `_TRANSITIONS` rather than against a copy.
2. Evolution is refused without a Discovery Record, with insufficient authority, and
   from an unvalidated discovery — the "or reject" half of the clause.
3. The specification hash changes, both versions are retained, and v1 becomes
   SUPERSEDED while v2 becomes ACTIVE.
4. **Subsequent execution uses the evolved specification**: a packet bound to the new
   hash registers and one bound to the superseded hash is refused with
   `SPECIFICATION_IDENTITY_MISMATCH`.
5. A mission persisted to disk, discarded from memory, and rebuilt replays to the same
   state with the same head hash.
6. A truncated ledger does not restore, and restoring without an independent checkpoint
   is refused.
7. Local worktree, remote push, and runtime process effects reconcile separately to
   EFFECT_COMPLETED, SAFE_TO_RETRY, and UNKNOWN.
8. Absent evidence is UNKNOWN; evidence bound to a different effect raises.
9. An UNKNOWN disposition writes no reconciliation receipt, so the ledger never records
   a resolution that did not happen.
10. The gate re-derives the proof rather than trusting the committed artifact.
11. `./scripts/validate.sh` green.

## Also in this packet

A precision defect in the FORGE-FIX-004 A3 registry, found by this packet's own work.
`pattern_reaches_protected_surface` escalated `docs/packets/**` and `tests/**` to A3,
because a basename of `**` fnmatches every protected basename, and it escalated
`tests/unit/*.py` because the basename rule was not scoped to `src/` the way
`requires_owner_authority` scopes it. Over-firing matters for the same reason
under-firing does: a gate that demands owner authority for editing tests is a gate
people learn to wave through, and F9 is what waving it through costs. Both directions
are now asserted.

## Evidence

- `.agent/artifacts/FORGE-EVO-001/PROOF.json`
- `tests/test_governed_evolution.py` — 22 cases
- `tests/test_policy.py` — 22 new precision cases, both directions

## Stated boundary

Every component is the shipped implementation: the kernel's transition table and
authority checks, the Product Brain's versioning and lineage, `LedgerStore`, and
`ExecutionLoop`'s specification binding. No model is called. This proves the governed
machinery holds on real state; it claims nothing about the quality of agent output.
