# Builder handoff: deliver the personal Aura CLI

Read AURA_ARCHITECTURE.md, AURA_PRD.md, AURA_PRODUCT_DIRECTION.md (this directory),
AGENTS.md, .agent/AGENT_RULES.md, current state and applicable packets. The owner's
September 25 direction preserves the agent lineup and makes memory, skills and safe
resume first-release requirements. The image is a target, not runtime evidence.

## Execute in this order

1. Fetch current main and every open PR. Map exact SHAs, dependencies, useful code,
   tests, unresolved review findings and unique changes. Do not trust stale PR bodies.
2. Reconcile any competing specification drafts with the 45-requirement canonical PRD.
   Keep the PRD at no more than 50 numbered requirements. Preserve useful detail elsewhere.
3. Start a clean integration branch from current main. Reuse corrected CLI, provider,
   memory/learning and isolation code where suitable. Preserve the brand assets and
   historical ledgers. Account for valid work before closing superseded drafts.
4. Implement the smallest complete `aura build` path: bounded work order, Sol planning,
   DeepSeek implementation, deterministic checks, Astra review, repair and final handoff.
5. Design persistent storage, project memory, on-demand SKILL.md loading and restart
   checkpoints into that path. Finish cross-session recall, correction and safe resume
   before describing the first usable release as complete.
6. Demonstrate a real task in a disposable repo; retain candidate identity, actual checks,
   independent review, tool/provider effects, budget and cost (or UNKNOWN). Exercise
   crash recovery without duplicate effects and relevant memory/skill use on a second task.
7. Add Luna's separate builder lane and MiniMax support. Sol schedules independent work;
   conflicts serialize. Test and review the final combined candidate.
8. Prove a bounded unattended multi-task build, forced stuck recovery and attributable
   reuse of reviewed lessons. Report owner interventions and the remaining blockers.

## Implementation choices

Use one application and the existing Python foundation. Add a clear terminal interface.
Use SQLite for searchable task/session/memory data, Markdown for guidance and skills,
and retain useful ledger integrity. Define one authority for each state value. Do not
introduce a service fleet, UI, new roles or generalized plugin marketplace as prerequisites.
Persist Nick's relevant preferences and project decisions with provenance; expose inspect,
correct, remove and export. Load skills only when relevant and review learned procedures.

Use exact verified provider IDs for the intended Sol, DeepSeek V4.1 Flash, Luna 6,
MiniMax and Astra roles. Resolve MiniMax variant, account access, billing and the inherited
audit-family conflict before activating affected paths. No silent model substitutions.
Run only within currently verified owner scope, budget and permissions. This documentation
push itself does not authorize provider spend, deployments or unrelated merges/deletions.

Keep isolation, independent review, bounded recovery and UNKNOWN handling effective.
Record intent before external effects. Two materially different repairs are the limit
before Sol replans. Separate code defects from access, environment and owner decisions.
Use existing scope/review gates; a design simplification requires an explicit reviewed
change, not bypassing checks. Preserve old failed evidence. Do not simulate live approval.

## Definition of each delivery

Provide a runnable command, actual observed outcome, exact commit, local validation,
independent review, remaining blockers and the next smallest task. Tests alone do not
prove provider dispatch, memory quality, parallelism or unattended operation. Compare
accepted task outcomes, time, cost and interventions on representative projects.

If owner-held trust attestation, credentials or budget are missing, prepare everything
independent of them and identify the exact external action required. Do not stall on
routine choices already covered by the approved requirements.
