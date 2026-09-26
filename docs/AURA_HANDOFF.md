# Aura engineering handoff

The owner-confirmed scope is AURA_ARCHITECTURE.md. Requirements are in AURA_PRD.md.
Source foundation: Forge snapshot 3fcbb2ee6e5f7fd1d6c0c8c19adc1a9f34b86508, imported
at Aura bd534f7c8b4aa7c93b2e1550ee3fbb953a4121ca. Historical records are in Git history.
They are not Aura execution authority or completion evidence.

## Retained implementation

- Intent ingestion, specification lineage, context isolation, scope and authority checks.
- Governor budgets, candidate-bound loop contracts, detached audits, durable ledgers.
- StuckDetector and LessonStore; two-lane SliceLearning controller and Athena comparison.
- Generic provider transports, still requiring reconciliation with the target role lineup.
- Offline adversarial tests and clearly labeled synthetic proof fixtures.

## Remaining integration

1. Confirm provider IDs and configure Sol, DeepSeek, Luna, MiniMax, and Astra explicitly.
2. Reconcile the inherited cross-family audit rule with the requested Luna/Astra pairing.
3. Provision owner-pinned production review identities and signing material outside builder scope.
4. Connect SliceLearning to the Governor and real runner; enforce recovery before dispatch.
5. Give each builder a worktree, dependency-aware queue, packet, context, and frozen base.
6. Validate combined candidates centrally and require fresh independent candidate review.
7. Demonstrate real execution, parallelism, forced stuck recovery, restart, and reviewed learning.

The existing CLI/module name is forge. Add the user-facing aura entry point while
retaining forge compatibility. run_slice.py is an offline proving
harness with test keys and simulated roles; it is not the production runner. Production
trust is deliberately unprovisioned. No paid call, live activation, or deployment is part
of the scope cleanup. The local source gate and the live finish contract are separate.

## September 25 delivery direction

Start with [the builder handoff](product/AURA_BUILDER_HANDOFF.md) and
[the approved product direction](product/AURA_PRODUCT_DIRECTION.md).
Persistent memory, skills and restart are first-release requirements. Deliver a complete
single-builder task plus continuity, then the full two-builder team and unattended builds.
The architecture image describes intent; no implementation completion is implied.
