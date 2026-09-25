# Aura architecture

Owner-confirmed scope, September 24, 2026 (America/Chicago).

Aura is Nick Sandoval's autonomous engineering agent. Its loop is:
Intent → Plan → Implement → Verify → Learn → Update → Continue.

## Roles

| Role | Assignment | Responsibility |
| --- | --- | --- |
| Engineering lead | Sol | Decompose intent, agree interfaces, allocate slices, integrate, replan |
| Builder A | DeepSeek V4.1 Flash (intended label) | Bounded implementation and repair |
| Builder B | Luna 6 | Second independent implementation and repair loop |
| Utility | MiniMax | Bounded supporting work; cannot validate lessons or candidates |
| Independent auditor | Astra | Fresh independent context; verify exact candidates and lesson evidence |
| Governor | Deterministic code | Authority, dependencies, scope, budgets, state, integration eligibility |

Provider model IDs are not verified. The inherited provider adapter is infrastructure,
not an activated role configuration. The inherited cross-family audit rule conflicts
with Luna/Astra and remains fail-closed until an explicit owner-approved reconciliation.
Do not silently substitute another role, model, or audit policy.

## Two loops

Sol assigns independently verifiable slices. Each builder receives a separate worktree,
packet, context, frozen base, and candidate identity. Dependencies and conflicting edits
determine concurrency; different filenames alone do not prove independence. Integration
is centrally serialized where needed. Validate the combined candidate after integration.
A changed candidate invalidates its previous audit. Builders cannot approve themselves.

## Stuck resolution

Detect repeated patches, recurring failing checks, and lack of material progress.
Allow at most two materially different bounded repairs, then return to Sol for replanning.
Classify coding failures separately from environment failures, missing access, and owner
intent or authority decisions. UNKNOWN blocks unsafe continuation and survives restart.
Recovery advice must be enforced by the Governor before another effect is dispatched.

## Reviewed learning

Record strategy, exact candidate, checks, outcome, cost/latency where known, and evidence.
Review lessons independently before sharing them. Both lanes share accepted lessons;
each active slice pins a stable snapshot. Compare only compatible task contexts, metrics,
and required checks. Attribute a later strategy change and measured outcome to its lesson.
Withdraw harmful lessons from future retrieval without deleting historical evidence.
Persist replayable knowledge across restarts; never repeat an uncertain external effect.

Athena's current adaptation is scoped outcome comparison and lesson handling. It is not
model-weight training, full Arena/Gauntlet, or permission for general policy mutation.
The slice-30 objective requires demonstrated improvement in strategy and memory.

## Supporting runtime and trust

Keep intent ingestion, specification lineage, context isolation, provider transports,
path/scope checks, budgets, candidate identities, detached review, and durable ledgers.
These support the architecture; they are not separate Aura products. Production signing
keys and review trust must be owner-pinned outside builder scope. Test keys and simulated
roles grant no production authority. Lessons cannot weaken checks or expand permissions.

## Boundaries

Renzo UI, Jev/TypeSafe decision services, external product trials, Forge's old product
roadmap and completion records are outside Aura's active scope. Existing Python module
and CLI names remain `forge` for compatibility; the distribution is `aura-agent`.
Historical source attribution remains in code and Git history, not as active authority.
