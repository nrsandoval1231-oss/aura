# AURA-MIG-001 — Reconcile Aura import and baseline

Status: READY. Owner direction in the current Aura implementation request.

## Objective

Record Aura's current product direction and repository identity, preserve Forge
lineage, repair the imported adaptive packet's parser defect, and establish the
full validation baseline without weakening any gate.

## Base

- `bd534f7c8b4aa7c93b2e1550ee3fbb953a4121ca` on Aura `main` and `origin/main`.

## Allowed files

- `docs/product/AURA_PRODUCT_DIRECTION.md`
- `docs/AURA_HANDOFF.md`
- `docs/source/forge-current-state-at-import.md`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/FORGE-ADAPT-001.md`
- `.agent/tasks/AURA-MIG-001.md`
- `.agent/graph/work-graph.json`
- `.agent/artifacts/AURA-MIG-001/**`

## Exclusions

Historical Forge receipts, signatures, ledgers, completion artifacts, canonical
architecture, PRD, Finish Contract, validation authority, and provider routing.
No paid calls, push, merge, or deployment.

## Dependencies and invariants

Aura imports Forge content but does not inherit Forge certification. Preserve
historical file hashes as history. Use the actual Aura remote, branch, base and
candidate. UNKNOWN stays UNKNOWN. Current product decisions are owner supplied;
unverified provider IDs and credentials remain unverified.

## Acceptance and validation

- Product direction separates decisions, implementation, assumptions,
  integration, and future ideas; handoff links it.
- Aura current state and historical Forge lineage are unambiguous.
- Imported packet parses without relaxing the parser or rewriting its original
  completion evidence.
- Run `scripts/validate.sh` with declared development dependencies and record
  each actual failure and candidate identity. Run focused parser/graph checks.
- Independent Astra audit binds the exact frozen candidate before graph
  promotion. Any subsequent edit invalidates that audit.

## Authority, risk, recovery, handoff

A3 documentation/graph reconciliation expressly requested by owner; no runtime
activation. Two materially different repairs maximum. Handoff records changed
files, commands, exit codes, SHA/tree, UNKNOWNs, and review status in
`.agent/artifacts/AURA-MIG-001/`.
