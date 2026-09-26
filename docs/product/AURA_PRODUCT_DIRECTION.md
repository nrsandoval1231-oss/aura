# Aura: Nick's personal autonomous coding CLI

Owner-confirmed direction: September 25, 2026 (America/Chicago).
This is the target product, not a claim that the runtime is complete.

![Aura target agent structure](assets/aura-agent-structure.png)

## Product promise

Tell Aura what to build in a selected repository. It understands the project, plans the
work, runs Nick's chosen agent team, tests and reviews the result, repairs problems,
remembers useful outcomes, and continues within the authorized scope and budget.
Nick can inspect or intervene from a simple terminal interface. An unattended build
ends in a verified result or a precise blocker that explains what is needed next.

The goal is superior performance on Nick's real coding projects: high-quality accepted
builds, short completion time, predictable cost, and fewer owner interventions. Feature
count and test count alone do not establish superiority to Hermes or another agent.

## Agent team

| Role | Intended assignment | Responsibility |
| --- | --- | --- |
| Owner | Nick | Objectives, priorities, scope, budgets and consequential decisions |
| Engineering lead | Sol | Plan, decompose, allocate, integrate and replan |
| Builder A | DeepSeek V4.1 Flash | Implement and repair bounded tasks |
| Builder B | Luna 6 | Parallel independent implementation and repair |
| Utility worker | MiniMax | Bounded research, discovery and preparation |
| Independent reviewer | Astra | Check candidate code, tests and acceptance criteria |
| Governor | Deterministic code, not a model | Enforce scope, budgets, state, retries and integration eligibility |

Model names above are intended labels. Verify exact provider IDs, account access,
capabilities and billing before activation. No silent substitution. MiniMax's exact
variant is unresolved. Resolve the inherited Luna/Astra audit-policy conflict explicitly.

Sol schedules two independent builder loops when dependencies and write conflicts allow.
Each builder has its own worktree, packet, context and candidate identity. MiniMax does
not approve candidates or lessons. Astra reviews without builder reasoning. Validate
the combined integration candidate, not only each builder's separate result.

## Persistent foundation, included in the first usable release

Memory has three scopes: Nick's relevant preferences and working conventions; each
project's architecture, decisions and constraints; and searchable session/build history
with outcomes and lessons. Every durable fact has provenance and time context. Explicit
owner corrections supersede stale beliefs. Keep unrelated project context separate;
retrieve relevant records rather than injecting every conversation into every prompt.
Provide inspect, correct, remove and export operations. Never use memory as credential
storage or let remembered advice override current owner intent or executable permissions.

Skills are focused, versioned SKILL.md procedures with optional scripts and references.
Load descriptions first and full instructions on demand. Support user-authored and
agent-proposed skills. Review learned procedures before sharing them across future tasks;
retain rollback and attribution. Pin each active task's memory/skill snapshot. Compatible
existing skills may be imported with provenance and inspected dependencies; do not
blindly execute arbitrary imported scripts.

Durable task state preserves the objective, plan, role assignments, worktree/candidate
identity, checkpoints, tool outcomes, budget and next action. After interruption,
reconcile actual repository/process/provider state before continuing. UNKNOWN blocks
replay of an uncertain effect; confirmed independent work may still proceed.

## Simple runtime

Start with one application: terminal interface, coordinator, execution engine, persistent
storage and verification. Use SQLite for sessions, tasks, checkpoints and searchable
memory, and Markdown for readable guidance and skills. Reuse existing validated ledger
and learning components where they fit; map responsibilities explicitly so two stores
do not disagree about authoritative task state. Avoid an unnecessary storage migration.

The interactive entry point is `aura`. Also expose `aura init`, `aura build`, `aura status`,
`aura inspect`, `aura pause`, and `aura resume`. These are target commands, not evidence
that current main implements them. Retain `forge` imports and compatibility entry points
while adding Aura's user-facing interface.

The same execution engine supports an attached terminal and later unattended operation.
If Nick's computer is off, execution requires a running remote machine; reconnecting a
terminal should restore visibility without restarting the build or duplicating effects.
Hosting selection and deployment remain separate implementation decisions.

## Delivery sequence

| Increment | Demonstration required |
| --- | --- |
| 1. Complete coding path | Real request -> Sol plan -> DeepSeek code -> checks -> Astra review -> bounded repair -> verified candidate and handoff |
| 2. Personal continuity | A second session recalls correct project decisions and skills; an interrupted task resumes safely |
| 3. Full agent team | Sol assigns independent tasks to DeepSeek and Luna; MiniMax assists; integrated result passes checks and fresh review |
| 4. Unattended build | Multi-task feature completes within scope and budget, exercises stuck recovery and restart, and reports results or a precise blocker |

Increments 1 and 2 together form the first usable release. Memory, skills and restart
interfaces are designed from the start; they are not postponed to an unrelated future
product. The complete architecture requires increments 3 and 4 plus demonstrated learning.

## Recovery and learning

Detect recurring failed checks, repeated patches and lack of progress. Permit at most
two materially different repair strategies, then return to Sol for replanning. Separate
coding defects from environment, access, provider and owner-decision blocks.

Intent -> Plan -> Implement -> Verify -> Learn -> Update -> Continue.
Record strategy, outcome, checks, cost, latency and evidence. Share reviewed lessons at
future task boundaries. Demonstrate a lesson changing a later strategy and compare
compatible outcomes. Withdraw harmful lessons without deleting history. Improvement
means better decisions and procedures; model-weight training is not required.

## Repository consolidation

Re-fetch main and all draft branches before implementation. Inspect useful CLI, isolation,
provider, memory and learning code before writing replacements. Integrate corrected,
reviewed work in coherent order; close superseded PRs only after accounting for unique
useful changes. Preserve negative evidence and historical receipts. The PR stack is not
the product roadmap. Do not restart all code or merge defective checkpoints to clear it.

Keep safeguards practical and enforced by code. This direction does not waive existing
trust, scope, budget or review gates; simplify any conflicting governance design through
an explicit reviewed change. No new UI, daemon or extra roles are prerequisite to the
first complete coding path. Do not wait for broad feature parity with Hermes.

Success is measured by accepted builds, regressions, completion time, cost, owner
interventions, restart success and attributable reuse of reviewed lessons. Establish
baselines on Nick's representative tasks before claiming an improvement.
