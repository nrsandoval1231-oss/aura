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

1. Wire an isolated single-builder executor to the Governor, with verified provider
   adapter, explicit budget, exact candidate checks, and trusted independent review.
2. Confirm account-level provider access and configure Sol, DeepSeek, Luna, MiniMax,
   and Astra explicitly.
3. Reconcile the inherited cross-family audit rule with the requested Luna/Astra pairing.
4. Provision owner-pinned production review identities and signing material outside builder scope.
5. Connect SliceLearning to the Governor and real runner; enforce recovery before dispatch.
6. Add a second worktree and dependency-aware queue only after one task succeeds.
7. Validate combined candidates centrally and require fresh independent candidate review.
8. Demonstrate real execution, parallelism, forced stuck recovery, restart, and reviewed learning.

The `aura` CLI now records bounded requests in an external append-only ledger and
supports status, inspect, pause and resume on persisted state. `build` records a
stable ID and returns BLOCKED; it invokes no model or builder and creates no
candidate. The `forge` CLI and imports remain for compatibility. `run_slice.py` is an offline proving
harness with test keys and simulated roles; it is not the production runner. Production
trust is deliberately unprovisioned. No paid call, live activation, or deployment is part
of this packet. The local source gate and the live finish contract are separate.

The owner set a $5 maximum for the first live DeepSeek builder task on 2026-09-25;
no call has occurred under that ceiling. This is a per-task ceiling, not standing
permission for later calls. The owner requested help selecting audit trust. The
existing detached verifier is still hard-coded to a Forge audit domain and
validation artifact; an Aura-specific protected trust packet and owner approval
of the independent auditor's public-key fingerprint are prerequisites.

## Owner-selected audit trust bootstrap (key and fingerprint pending)

The owner selected an owner-held, passphrase-protected signing key outside all
Aura and Codex workspaces. The owner generates and retains the private key;
builder and controller processes must never receive it or its passphrase.
Astra supplies the independent exact-candidate verdict, and the owner signs
only after checking that report and the receipt. The signed receipt must keep
reviewer identity distinct from owner attestation. The owner must separately
approve the exact SHA-256 fingerprint of the public key for a protected trust
record. The Aura-specific verifier must bind a new Aura domain, repository,
packet, exact commit/tree, complete manifest, and local validation artifact.
Its migration and key pin require a dedicated governance packet and independent
review; the existing Forge verifier cannot be relabeled by filling empty fields.
Until the public key, fingerprint, and reviewed migration exist, detached audit
and merge eligibility stay UNKNOWN.
