# Aura engineering handoff
Date: 2026-09-25
Owner: Nick Sandoval
Product repository: https://github.com/nrsandoval1231-oss/aura

## Objective and owner decisions
Build Nick's own autonomous engineering agent using Forge as the foundation, informed by Hermes. This is a separate product called Aura, not a Hermes fork. Aura is the destination for future product work.

The owner explicitly authorized copying everything into this repository. This import includes the complete 284-file source snapshot from Forge candidate 3fcbb2ee6e5f7fd1d6c0c8c19adc1a9f34b86508, including the additive learning/recovery work from Forge draft PR #16. The original Forge README is preserved in docs/source/forge-readme.md; Aura's initial README is preserved in docs/source/aura-initial-readme.md. Other source files and assets remain byte-identical. Git commit history, issues, PR discussions, repository settings, credentials, and runtime state outside tracked files are not migrated. Forge remains unchanged.

## Accepted agent architecture
| Role | Model / implementation | Responsibility |
| --- | --- | --- |
| Engineering lead | Sol | Decomposition, architecture, task allocation, integration, replanning |
| Builder A | DeepSeek V4.1 Flash, intended name | First isolated coding loop |
| Builder B | Luna 6 | Second isolated coding loop |
| Utility worker | MiniMax | Bounded supporting work |
| Independent auditor | Astra | Separate candidate review with independent context |
| Governor | Deterministic software | Scope, authority, budgets, state, scheduling, integration |

Exact provider model IDs and availability must be verified before activation. Do not invent API IDs or silently substitute models. The user's original “DeepSeek 4.1 flags” was interpreted as Flash; preserve that intent while resolving the exact provider ID.

Two builders run concurrently only on independent work with separate worktrees, packets, contexts, and candidate identities. Shared reviewed knowledge is project-scoped. The engineering lead owns dependencies and integration; builders cannot certify themselves. Existing Forge cross-family audit policy conflicts with a Luna/Astra same-family pairing and needs explicit reconciliation before that pairing runs.

## What is implemented
The new implementation is an additive controller library, not the live parallel runner.

- src/forge/slice_learning.py: two named lanes (deepseek, luna), one active learning slice per lane, shared durable ledger, replay, locking, idempotent commands, immutable slice snapshots, recovery advice, and lesson lifecycle.
- src/forge/athena_engineering.py: narrow attributed port of Athena's directional outcome comparison; explicit engineering metrics and quality guardrails.
- Existing Forge StuckDetector and LessonStore are reused.
- src/forge/policy.py protects the new controller modules.
- tests/test_slice_learning.py and tests/test_athena_engineering.py cover concurrency, restart, evidence integrity, recovery, comparisons, and learning.
- docs/integration/parallel-adaptive-engineering.md describes the design and boundaries.
- .agent/tasks/FORGE-ADAPT-001.md and its completion artifact preserve the bounded packet and evidence. Its graph node remains AWAITING_AUDIT because full repository gates remain outstanding.

### Stuck resolution
Detect repeated patches and lack of material progress. Permit bounded, materially different repair strategies, then escalate to engineering replanning or owner decision as appropriate. Missing checks remain UNKNOWN. Recovery plans are advisory until the Governor's execution path enforces them. Recording a violation as history is not permission to perform it.

### Learning during coding
At slice start, retrieve validated lessons and pin an immutable context/check/lesson snapshot. Record attempts and actual strategy changes. Capture outcomes, propose attributable lessons, require independently authenticated review, and compare only compatible contexts and metrics. Retain helpful lessons; withdraw harmful lessons from future retrieval without rewriting historical application evidence.

Both lanes share accepted learning. A lesson withdrawn by one lane does not erase the other lane's historical evidence or silently mutate its running snapshot. Repairs can attribute the same lesson to a new candidate. Missing quality evidence is UNKNOWN, not proof of harm or success.

This evolves working strategy and memory, not model weights. Thirty slices can accumulate learning; thirty unrelated tasks do not establish statistically significant improvement.

### Athena scope
Source: nrsandoval1231-oss/Athena at f630acec86f1ff4aa03c0307fc77bd66a3f6bdc5, especially athena_arena/evaluation.py and the domain/constraint documents.
Only the narrow comparison logic was adapted. Full Arena/Gauntlet, general policy mutation/promotion, and statistically supported self-improvement are not implemented here. Comparisons grant no execution authority.

## Validation and review evidence
The imported implementation passed 116 focused tests in a selected-file API snapshot: 96 existing stuck/learning tests and 20 new tests. Changed Python files passed Ruff checks and formatting; git diff --check passed.

Independent Astra review returned PASS for the bounded library at local snapshot commit f7398829541a222647f0486e6926e55ccdc556d5. It independently reran the 116 tests and checked repairs for four findings:
1. Incomplete checks incorrectly treated as harmful evidence.
2. Reusing a comparison context with a weaker required-check set.
3. Concurrent rollback blocking historical lesson attribution.
4. Lesson attribution lost across repair candidates.

Published Forge candidate content was checked against reviewed local content. The offline 30-slice fixture tests accumulation and persistence; it is not a live 30-slice model experiment.

Full scripts/validate.sh was NOT run for this candidate. Active-slice binding was NOT generated. Importing the files into Aura does not certify the new repository or transfer source-repository execution authority. Aura's full validation remains UNKNOWN until performed.

## Next build milestone: real governed two-lane execution
1. Establish Aura's actual checkout, remote, branch, frozen base, and clean worktree. Read AGENTS.md, .agent/AGENT_RULES.md, canonical architecture, finish contract, and this handoff.
2. Reconcile inherited repository identity and historical state in a bounded migration packet. Source governance/state/evidence documents still describe Forge and its past work; preserve historical receipts and signatures. Do not mass-replace identities inside evidence. Make Aura's current state explicit without treating Forge completion records as Aura certification.
3. Install declared development dependencies and run ./scripts/validate.sh from a full checkout. Repair actual integration issues, retain exact-candidate evidence, and complete required binding/audit gates.
4. Connect SliceLearning to the real Governor and runner: start slice, retrieve/pin lessons, run builder attempts and deterministic checks, enforce recovery decisions, review candidates, record outcomes, and measure attributed lessons.
5. Implement separate worktrees and a dependency-aware queue for the two builders. Integration must serialize overlapping changes and preserve independent review.
6. Wire a production review verifier to trusted identities/keys. The library deliberately has no permissive default verifier. Verify repository/candidate/lesson/baseline/context binding; do not use caller-provided keys as trust roots.
7. Configure real model adapters and bounded budgets. Resolve provider IDs and the Luna/Astra audit-policy conflict before live calls.
8. Exercise one small end-to-end task, then two independent tasks in parallel, including one forced stuck case and restart. Verify that an accepted lesson changes a later strategy and that harmful lessons are withdrawn.
9. Obtain independent review of the exact integrated Aura candidate. Keep paid execution, merge, and deployment authority separate from test success.

Build this milestone before expanding UI, adding many roles, or enabling broad autonomous policy mutation.

## Operational boundaries
- No credentials were added by this migration. Provision credentials and trusted signing material through the intended runtime mechanisms.
- No live paid model calls or deployment were performed by the adaptive-controller work or this import.
- Preserve UNKNOWN when checks, billing, effects, or verification are absent.
- Learning cannot weaken tests, expand authority, bypass auditing, or grant itself new permissions.
- Existing package/CLI/module names remain forge to avoid coupling a move with a breaking rename.
- Forge PR #16 is source provenance; continuing Aura work does not require merging it into Forge.

## Start instruction for the next engineer
Work in nrsandoval1231-oss/aura. Read this handoff and the governing files. Inspect the actual repository before editing. First reconcile Aura identity and run the full repository gate; then implement the smallest real two-builder integration with enforced stuck recovery and reviewed shared learning. Keep source historical evidence intact, use bounded packets and independent review, and report exactly what is operational versus still simulated.
