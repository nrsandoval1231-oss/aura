# Forge Agent — Canonical Architecture v1

**System:** Forge Agent
**Type:** Autonomous engineering runtime
**Architecture status:** Canonical v1

> **Stable Intent → Living Specification → Adaptive Execution → Evidence → Discovery → Better Specification**

# 1. North Star

Forge Agent is not an autonomous coding assistant.

It is an **autonomous engineering system** that accepts an owner's imperfect description of a desired product, builds toward that intent, discovers missing or incorrect assumptions through real implementation evidence, improves its specification, redirects its own work, recovers from failures, and accumulates validated engineering knowledge.

Its job is not:

> Finish every item in the PRD.

Its job is:

> **Produce the best evidence-supported implementation of the owner's intent that it is authorized to produce.**

That distinction governs everything below.

---

# 2. System architecture

```text
                         ┌───────────────────────┐
                         │         OWNER         │
                         │                       │
                         │ Intent / Decisions    │
                         │ Authority / Approval  │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │      NORTH STAR       │
                         │   Owner-controlled    │
                         └───────────┬───────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         FORGE GOVERNOR                               │
│                                                                      │
│ State Machine │ Authority │ Scope │ Budgets │ Policy │ Escalation   │
└───────────────┬──────────────────────────────────────┬───────────────┘
                │                                      │
                ▼                                      ▼
      ┌───────────────────┐                  ┌──────────────────┐
      │   PRODUCT BRAIN   │                  │ EXECUTION ENGINE │
      │                   │                  │                  │
      │ Living Spec       │◄────────────────►│ Architect        │
      │ Finish Contract   │                  │ Builder          │
      │ Architecture      │                  │ Tool Runtime     │
      │ Decisions         │                  │ Stuck Resolver   │
      │ Assumptions       │                  └────────┬─────────┘
      │ Discoveries       │                           │
      └─────────▲─────────┘                           ▼
                │                             CANDIDATE REVISION
                │                                    │
                │                                    ▼
                │                           ┌──────────────────┐
                │                           │     AUDITOR      │
                │                           │                  │
                │                           │ Independent      │
                │                           │ Verification     │
                │                           │ Discovery        │
                │                           └────────┬─────────┘
                │                                    │
                │                  ┌─────────────────┼──────────────┐
                │                  │                 │              │
                │                  ▼                 ▼              ▼
                │                PASS             REPAIR        DISCOVERY
                │                  │                 │              │
                │                  ▼                 │              ▼
                │               MERGE               │      DISCOVERY ENGINE
                │                  │                 │              │
                │                  └──────────┬──────┘              │
                │                             │                     │
                │                             ▼                     │
                │                       OUTCOME ENGINE ◄────────────┘
                │                             │
                │                             ▼
                │                       LESSON ENGINE
                │                             │
                └─────────────────────────────┘

                             NEXT ITERATION
```

---

# 3. The Governor

This should be **normal deterministic software**, not another agent.

The Governor owns execution.

An LLM may recommend:

> BUILD-017 should be attempted next.

The Governor determines whether BUILD-017 **may actually execute**.

It owns:

- current state;
- permitted transitions;
- authority levels;
- write scopes;
- repository identity;
- model/tool permissions;
- budgets;
- retry limits;
- stuck detection;
- owner escalation;
- candidate revisions;
- audit requirements;
- completion eligibility.

This prevents Forge from becoming agents prompting agents until something happens.

---

# 4. Canonical state machine

```text
INITIALIZING
     ↓
UNDERSTANDING
     ↓
PLANNING
     ↓
TASK_READY
     ↓
IMPLEMENTING
     ↓
TESTING
     │
     ├── FAIL ─────→ REPAIRING
     │                  │
     │            progress?
     │              /       \
     │            yes        no
     │             │          │
     │             ▼          ▼
     │          TESTING   STUCK_RESOLUTION
     │                         │
     │                    new strategy
     │                         │
     │                         ▼
     │                    IMPLEMENTING
     │
     ▼
AUDITING
  │     │      │
PASS   FAIL  DISCOVERY
  │     │      │
  │     ▼      ▼
  │  REPAIR  DISCOVERY_REVIEW
  │              │
  │        ┌─────┴──────┐
  │        ▼            ▼
  │    ACCEPTED      REJECTED
  │        │
  │        ▼
  │   SPEC_EVOLUTION
  │        │
  │        ▼
  │    REPLANNING
  │
  ▼
MERGING
  ↓
OUTCOME_EVALUATION
  ↓
LEARNING
  ↓
RECONCILING
  ↓
FINISH_EVALUATION
  │
  ├── INCOMPLETE → PLANNING
  │
  ├── OWNER_REQUIRED → PAUSED
  │
  └── SATISFIED → COMPLETE
```

Every transition generates a receipt.

That gives us complete replayability.

---

# 5. Authority hierarchy

Forge needs an explicit hierarchy of truth.

```text
L0   OWNER INTENT / NORTH STAR
              ↓
L1   PRODUCT CONSTRAINTS
              ↓
L2   LIVING SPECIFICATION
              ↓
L3   ARCHITECTURE / ADRs
              ↓
L4   EXECUTION GRAPH
              ↓
L5   BUILD PACKET
              ↓
L6   IMPLEMENTATION
              ↓
L7   EVIDENCE
```

Lower layers can expose problems in higher layers.

They cannot silently redefine them.

That gives us a critical concept:

### Upward challenge without unauthorized mutation

Evidence can say:

> "Requirement R-17 appears wrong."

Forge can investigate that.

But evidence cannot simply rewrite the North Star.

---

# 6. Three authority levels

### A1 — Autonomous

Forge acts without asking.

Examples:

- code implementation;
- tests;
- refactoring;
- bug fixes;
- internal interfaces;
- documentation;
- reversible dependency changes;
- build sequencing;
- implementation strategy.

### A2 — Governed evolution

Forge may modify the living specification when evidence supports the change **and the change remains inside the North Star**.

Examples:

- discovering another required entity;
- replacing a bad technical approach;
- splitting a requirement;
- adding missing validation;
- changing architecture;
- superseding a requirement;
- reordering the execution graph.

Every A2 mutation requires a **Discovery Record + evidence + rationale**.

### A3 — Owner

Forge stops and asks.

Examples:

- changing product purpose;
- changing target customer;
- weakening security/governance;
- destructive external actions;
- fundamental scope expansion;
- contradictory owner decisions;
- unresolved product tradeoffs requiring preference rather than engineering evidence.

---

# 7. The Living Specification

This is one of Forge's defining innovations.

The PRD is no longer just a Markdown checklist.

Internally, Forge represents requirements as objects:

```yaml
requirement:
  id: R-017
  version: 3

  statement:
    "Represent power demand at the building level."

  origin:
    type: discovery
    discovery: DISC-009

  status: active

  confidence: 0.94

  authority: A2

  assumptions:
    - A-041
    - A-052

  dependencies:
    - R-006
    - R-012

  evidence_required:
    - integration_test
    - schema_validation

  supersedes:
    - R-017:v2
```

Therefore the specification has history.

Forge can answer:

**Why does this requirement exist?**

That's enormously important.

---

# 8. Assumption Registry

This deserves first-class status.

Most PRDs fail because of assumptions nobody realized were assumptions.

Forge explicitly tracks them.

```text
A-031

ASSUMPTION
One campus has one energization date.

SOURCE
Initial PRD

CONFIDENCE
0.62

DEPENDENTS
R-14
R-17
R-22

STATUS
CHALLENGED

CONTRADICTORY EVIDENCE
PR-008
TEST-114
PROJECT-OBSERVATION-19
```

Now when implementation invalidates A-031, Forge immediately knows **which requirements may also be wrong**.

This is how we attack:

> We don't know what we don't know.

---

# 9. Architect

The Architect doesn't code.

It answers:

> Given current intent, specification, repository reality, evidence and learned knowledge, what is the highest-value valid next engineering action?

Output is a **Build Packet**.

```yaml
build_packet:
  id: BUILD-027

  objective:
    "Introduce building-level energization."

  requirements:
    - R-017
    - R-018

  allowed_paths:
    - src/domain/**
    - tests/domain/**

  forbidden_paths:
    - governor/**
    - north-star/**

  acceptance:
    - schema test passes
    - migration test passes
    - existing project tests remain green

  evidence_required:
    - test_receipt
    - diff_receipt
    - verifier_receipt
```

Builder receives bounded work, not "go improve the repo."

---

# 10. Builder

The Builder has substantial autonomy **inside the packet**.

It can:

```text
Inspect
→ Implement
→ Run
→ Fail
→ Diagnose
→ Modify
→ Test
→ Repeat
```

But it cannot:

- grade itself;
- expand its own authority;
- weaken the Finish Contract;
- alter Governor rules;
- silently modify the North Star;
- declare completion.

---

# 11. Independent Auditor

I'm intentionally calling this **Auditor**, not merely Verifier.

It has two responsibilities.

### Verification

> Did the Builder actually accomplish what it claims?

### Discovery

> What did implementing this teach us about the product?

Every candidate therefore receives two judgments:

```text
IMPLEMENTATION VERDICT
PASS / FAIL / UNKNOWN

DISCOVERY VERDICT
NONE / OBSERVATION / MATERIAL DISCOVERY
```

A PR can therefore simultaneously be:

```text
Implementation: PASS

Discovery:
Current architecture assumes exactly one telemetry
source per asset. Integration evidence demonstrates
multiple simultaneous sources.

Recommendation:
Create DISC-014.
```

**That is exactly the behavior we wanted.**

---

# 12. Discovery Engine

This becomes a major subsystem.

A valid Discovery must contain:

```yaml
discovery:
  id: DISC-014

  observation:
    "Assets can expose multiple telemetry streams."

  evidence:
    - TEST-221
    - BUILD-027
    - REPO-OBS-71

  affected_assumptions:
    - A-019

  affected_requirements:
    - R-012
    - R-014

  hypothesis:
    "Telemetry should be modeled one-to-many."

  proposed_change:
    "Introduce TelemetrySource entity."

  confidence: 0.91

  authority: A2

  validation:
    required: true
```

Crucially:

**Discovery ≠ truth.**

It is a hypothesis supported by evidence.

---

# 13. Discovery validation

Before rewriting large portions of the product, Forge asks:

> Can this hypothesis be tested cheaply?

Potentially:

```text
DISCOVERY
    ↓
CHEAP EXPERIMENT
    ↓
RESULT
 ┌──┴──┐
supports contradicts
   │       │
   ▼       ▼
PROMOTE   REJECT
```

This prevents one Auditor hallucination from sending the entire project sideways.

---

# 14. Spec evolution

Validated discoveries can generate **Spec Patches**.

Example:

```text
SPEC-PATCH-012

R-014 v2 → SUPERSEDED

CREATE R-014 v3
Assets support one or more telemetry sources.

CREATE R-014A
Telemetry sources preserve independent provenance.

CREATE R-014B
Source conflicts remain observable.

ADD A-041
Telemetry timestamps may not be synchronized.

REPLAN REQUIRED
YES
```

Then the execution graph gets rebuilt.

---

# 15. The feature you specifically wanted

Suppose the current plan is:

```text
BUILD-20
BUILD-21
BUILD-22
BUILD-23
BUILD-24
```

After BUILD-21, Auditor discovers BUILD-23 rests on a false assumption.

Forge can autonomously produce:

```text
BUILD-20 ✓
BUILD-21 ✓

DISC-07 VALIDATED

BUILD-22 → modified
BUILD-23 → superseded
BUILD-23A → created
BUILD-23B → created
BUILD-24 → dependency changed

NEW EXECUTION ORDER:

BUILD-23A
   ↓
BUILD-22
   ↓
BUILD-23B
   ↓
BUILD-24
```

The Builder is now building something **we never explicitly told it to build**.

But Forge can explain exactly **why**.

That's the magic.

---

# 16. Stuck Resolver

"Retry three times" is insufficient.

Forge should track attempts semantically.

```text
Attempt 1
strategy = modify parser

Attempt 2
strategy = modify parser differently

Attempt 3
strategy = modify parser again
```

Those aren't three meaningful strategies.

They're effectively one.

Forge detects:

```text
NO MATERIAL STRATEGY CHANGE
+
NO EVIDENCE IMPROVEMENT
=
STUCK
```

Then Stuck Resolver performs a **context reset**.

It reloads:

```text
North Star
↓
Relevant requirements
↓
Architecture
↓
Assumptions
↓
Repository reality
↓
Attempts
↓
Failures
```

And must propose a materially different approach.

---

# 17. Escalation isn't failure

Eventually Forge will encounter:

```text
Missing credential
Unknown business decision
External dependency
Irreversible operation
Conflicting owner intent
```

Correct behavior:

```text
OWNER-DECISION-004

Question:
Should historical telemetry remain immutable
after reconciliation?

Why Forge cannot decide:
Both options satisfy current North Star but have
different product consequences.

Affected work:
BUILD-031
BUILD-034

Work that can continue:
BUILD-032
BUILD-033
BUILD-037
```

And then **Forge keeps working on everything else**.

One blocked decision shouldn't stop the machine.

---

# 18. Evidence Ledger

Every meaningful event becomes append-only evidence.

```text
RUN
BUILD
COMMIT
DIFF
TEST
FAILURE
REPAIR
AUDIT
DISCOVERY
SPEC_CHANGE
DECISION
MERGE
OUTCOME
LESSON
```

Each record contains provenance.

This gives us:

- replayability;
- debugging;
- accountability;
- learning data;
- causality;
- product history.

SQLite is sufficient initially.

---

# 19. Outcome Engine

This is where Forge goes beyond most coding agents.

A discovery being accepted does not mean it was **correct**.

Forge follows what happened.

```text
DISC-014
   ↓
SPEC-PATCH-012
   ↓
BUILD-031
   ↓
TESTS
   ↓
SUBSEQUENT BUILDS
   ↓
Did architecture improve?
```

Possible outcomes:

```text
CONFIRMED
PARTIALLY_CONFIRMED
DISPROVED
INCONCLUSIVE
```

Now Forge learns from **results**, not merely reasoning.

---

# 20. Lesson Engine

Experiences can generate Candidate Lessons.

Example:

```text
LESSON-CANDIDATE-019

Pattern:
External-provider IDs should not serve as
canonical domain identity.

Observed:
4 times

Successful correction:
Introduce internal canonical identity and
preserve provider IDs as aliases.

Confidence:
0.93
```

Only validated lessons get promoted.

Then future Architects receive:

```text
Relevant validated lessons:
LESSON-019
LESSON-031
LESSON-044
```

That's how Forge becomes better over time **without retraining the model**.

---

# 21. Negative knowledge

Failures matter too.

Forge should remember:

> We tried X under conditions Y. It failed because Z.

Otherwise autonomous agents repeatedly rediscover the same bad ideas.

So:

```text
knowledge/
    validated_patterns
    validated_antipatterns
    unresolved_hypotheses
```

---

# 22. Contradiction Engine

Forge continuously looks for conflicts between:

```text
North Star
↕
Specification
↕
Architecture
↕
Repository
↕
Tests
↕
Evidence
↕
Learned Knowledge
```

Example:

```text
CONTRADICTION-008

PRD:
One organization owns one campus.

Repository:
OrganizationCampus is many-to-many.

Tests:
Explicitly test multiple organizations.

History:
DISC-004 previously invalidated one-to-one ownership.

Severity:
HIGH

Recommended:
Reconcile PRD.
```

This prevents documentation and implementation from slowly becoming different products.

---

# 23. Finish Contract

Forge does not finish because:

```text
all tasks = checked
```

It finishes when:

```text
North Star
        ↓
Active Requirements
        ↓
Evidence Requirements
        ↓
Verification
        ↓
Critical Contradictions = 0
        ↓
Critical Discoveries unresolved = 0
        ↓
Finish Contract
        ↓
SATISFIED
```

Tasks are implementation details.

**Evidence defines completion.**

---

# 24. Model architecture

Don't bind Forge to one model.

Use a model interface:

```text
ModelProvider
    ├── reason()
    ├── generate()
    ├── review()
    ├── summarize()
    └── structured_output()
```

Then policies decide routing.

For example:

```text
Architect → strongest reasoning model
Builder → strong coding model
Auditor → independent strong model/context
Cheap classification → fast model
Lesson extraction → strong reasoning model
```

This also lets Forge improve model routing later.

---

# 25. Tools

Tools should be capabilities with explicit permissions:

```text
read_file
write_file
search_repo
shell
run_tests
git_diff
git_commit
git_worktree
github_pr
github_merge
web_search
browser
python
```

Each tool call gets:

```text
agent
run
authority
```

### 25. Tool Runtime — continued

Every tool invocation needs an execution envelope:

```yaml
tool_call:
  id: TOOL-000194
  run: RUN-0031
  actor: builder
  build_packet: BUILD-027

  tool: write_file

  authority: A1

  scope:
    repository: sentinel
    allowed_paths:
      - src/domain/**
      - tests/domain/**

  request_hash: "..."

  started_at: "..."
  completed_at: "..."

  result: success

  evidence:
    - EVENT-001928
```

The important principle is:

> **Models request capabilities. The runtime grants and executes them.**

The model never owns its permissions.

A Builder saying:

> "I need to modify `/governor/policy.py`."

does not give it permission to do so.

The Governor evaluates that request against the active Build Packet and policy.

---

# 26. Repository Adapter

Forge should not embed Git behavior throughout the agents.

Create a deterministic `RepositoryAdapter`.

Conceptually:

```python
RepositoryAdapter
    identify()
    inspect()
    status()
    diff()
    create_worktree()
    create_branch()
    commit()
    get_revision()
    compare_revisions()
    prepare_candidate()
    merge()
    cleanup()
```

This establishes one authoritative definition of repository reality.

Agents should not reason about:

> "I think we're probably on main."

Forge knows:

```yaml
repository:
  canonical_remote: ...
  canonical_branch: main
  base_revision: a831f...
  candidate_revision: f293a...
  worktree_clean: true
```

Repository identity becomes evidence.

---

# 27. Worktree isolation

Every significant Build Packet gets an isolated workspace.

```text
CANONICAL MAIN
      │
      │ freeze revision
      ▼
 BASE SHA
      │
      ├──────────────┐
      ▼              ▼
WORKTREE A       WORKTREE B
BUILD-027        BUILD-028
      │              │
      ▼              ▼
 CANDIDATE A      CANDIDATE B
```

The Builder works on a candidate.

The Auditor receives:

- frozen base;
- candidate revision;
- exact diff;
- test receipts;
- relevant requirements;
- acceptance criteria.

It does **not** simply trust the Builder's narrative.

---

# 28. Independent verification

Independence needs to be architectural, not prompt-based.

The Auditor should receive a **fresh context**.

It should not inherit:

```text
Builder reasoning
Builder confidence
Builder's "everything looks good" summary
```

Instead:

```text
AUDITOR CONTEXT

North Star slice
Relevant specification
Build Packet
Base revision
Candidate revision
Diff
Deterministic evidence
Repository state
```

Then independently determine:

```text
PASS
FAIL
UNKNOWN
```

`UNKNOWN` is important.

Forge must never convert insufficient evidence into PASS merely because continuing is convenient.

---

# 29. Merge authority

Passing an audit makes a candidate **merge eligible**.

It does not necessarily mean the Auditor itself performs the merge.

```text
BUILDER
   ↓
candidate
   ↓
AUDITOR
   ↓
PASS
   ↓
GOVERNOR
   ↓
merge eligibility checks
   ↓
MERGE
```

Before merge, Governor confirms:

```text
candidate unchanged since audit
base compatibility valid
required tests valid
required receipts present
authority valid
no blocking contradiction
no superseding discovery
```

This closes the classic:

> "Auditor reviewed SHA A, but SHA B got merged."

failure.

---

# 30. Parallel execution

Forge should eventually support multiple simultaneous Build Packets.

But **not immediately**.

The execution graph determines which work can safely parallelize:

```text
               BUILD-10
                  │
          ┌───────┴────────┐
          ▼                ▼
      BUILD-11          BUILD-12
          │                │
          └───────┬────────┘
                  ▼
              BUILD-13
```

Forge can execute `11` and `12` concurrently only when:

- dependency graph permits it;
- write scopes don't conflict;
- architecture doesn't require sequencing;
- resource budgets permit it.

The Governor owns scheduling.

---

# 31. Conflict-aware concurrency

Path overlap alone isn't sufficient.

Two builds could touch different files while changing the same domain assumption.

Therefore Forge needs **semantic conflict metadata**.

Example:

```yaml
build_packet:
  id: BUILD-011

  domains:
    - telemetry.identity

  invariants_touched:
    - INV-009

  assumptions_touched:
    - A-031
```

Another Build Packet touching `A-031` should probably not execute concurrently.

This can start conservatively in V0.

---

# 32. Context Engine

Forge should **not dump the entire repository and entire PRD into every prompt**.

Context becomes a governed resource.

The Context Engine assembles:

```text
ROLE
+
CURRENT OBJECTIVE
+
RELEVANT NORTH STAR
+
RELEVANT REQUIREMENTS
+
RELEVANT ARCHITECTURE
+
RELEVANT ASSUMPTIONS
+
RELEVANT LESSONS
+
REPOSITORY SLICE
+
CURRENT EVIDENCE
```

Different roles receive different contexts.

That's both cheaper and better.

---

# 33. Context provenance

Every important context item needs provenance.

Forge should know:

```yaml
context_item:
  id: CTX-491

  content:
    "TelemetrySource is one-to-many with Asset."

  source:
    type: requirement
    id: R-014
    version: 3

  authority: L2

  confidence: 1.0
```

This prevents retrieved text from becoming indistinguishable from canonical truth.

---

# 34. Four-memory architecture

Forge maintains four fundamentally different memory classes.

### Truth Memory

Owner-controlled or strongly governed:

```text
North Star
Owner decisions
Product constraints
Architectural invariants
```

### Working Memory

Temporary execution state:

```text
Current mission
Active Build Packets
Current hypotheses
Temporary observations
Stuck state
```

### Evidence Memory

Append-only history:

```text
Tests
Diffs
Failures
Audits
Discoveries
Outcomes
Receipts
```

### Learned Memory

Validated reusable knowledge:

```text
Patterns
Antipatterns
Engineering lessons
Tool strategies
Domain lessons
```

They must **not be one generic vector store**.

---

# 35. Epistemic states

Forge should explicitly represent what it knows.

Useful states:

```text
KNOWN
SUPPORTED
HYPOTHESIZED
UNKNOWN
CONTRADICTED
SUPERSEDED
```

This matters enormously for discovery.

Example:

```yaml
assumption:
  statement: "Every Asset has one telemetry source."
  epistemic_state: contradicted
```

Rather than silently replacing the old statement.

---

# 36. Uncertainty budget

Not every unknown needs resolution.

Forge should distinguish:

```text
BLOCKING UNKNOWN
MATERIAL UNKNOWN
TOLERABLE UNKNOWN
IRRELEVANT UNKNOWN
```

Otherwise autonomous engineering systems waste huge amounts of time investigating things that don't affect the objective.

The Architect decides whether uncertainty deserves work.

---

# 37. Investigation Packets

Sometimes the correct next action isn't coding.

Forge therefore needs another execution primitive:

```text
BUILD PACKET
```

and:

```text
INVESTIGATION PACKET
```

Example:

```yaml
investigation:
  id: INVEST-012

  question:
    "Can telemetry timestamps arrive out of order?"

  reason:
    "Architecture choice depends on ordering guarantees."

  allowed_actions:
    - inspect_repo
    - inspect_tests
    - inspect_docs

  expected_output:
    evidence
    conclusion
    confidence
```

That allows Forge to **reduce uncertainty before committing to implementation**.

---

# 38. Experiments

Discoveries sometimes require actual experiments.

Forge should support:

```text
EXPERIMENT-001
```

Example:

> Can the existing persistence layer handle concurrent event ingestion without violating ordering?

Forge can build a temporary test harness, run it, capture results, and discard the experiment afterward.

This makes product discovery empirical rather than purely linguistic.

---

# 39. Planning horizon

The Architect should not generate a 100-task detailed plan upfront.

Unknowns make that brittle.

Instead:

```text
LONG HORIZON
Direction

MEDIUM HORIZON
Execution graph

SHORT HORIZON
Detailed Build Packet
```

The farther into the future Forge looks, the less detailed its commitments should be.

This makes replanning cheap.

---

# 40. Adaptive execution graph

The execution graph is mutable.

```text
GRAPH v1
    ↓
BUILD
    ↓
DISCOVERY
    ↓
GRAPH v2
    ↓
BUILD
    ↓
FAILURE
    ↓
REPLAN
    ↓
GRAPH v3
```

Forge preserves every graph version.

That gives us a history of **how its understanding evolved**.

---

# 41. Product Brain

The Product Brain isn't another LLM.

It's the structured state describing the product.

Conceptually:

```text
ProductBrain
├── NorthStar
├── Requirements
├── Assumptions
├── Decisions
├── Architecture
├── Invariants
├── Discoveries
├── Contradictions
├── FinishContract
└── ExecutionGraph
```

Agents reason over this state.

They don't own it.

---

# 42. Decision records

Forge must distinguish discoveries from decisions.

A discovery says:

> Evidence suggests X.

A decision says:

> Forge/Owner has selected X.

Example:

```yaml
decision:
  id: DEC-031

  question:
    "Canonical telemetry relationship"

  choice:
    "Asset 1:N TelemetrySource"

  basis:
    - DISC-014
    - EXPERIMENT-008

  authority: A2

  reversible: true
```

This prevents old alternatives from continually resurfacing.

---

# 43. Architecture Decision Records

Material architectural changes create ADRs automatically.

Not every code choice deserves one.

Forge should create an ADR when a decision affects:

- major component boundaries;
- persistence model;
- public interfaces;
- security;
- identity;
- event semantics;
- major dependencies;
- future implementation constraints.

The Architect and Auditor can both propose them.

Governor records the accepted result.

---

# 44. Invariant Registry

Requirements describe behavior.

Invariants describe things that **must remain true across implementations**.

Example:

```yaml
invariant:
  id: INV-008

  statement:
    "A Builder may never verify its own candidate."

  authority: L1

  verification:
    - governor_test
```

Or product-level:

```text
Every commercial signal retains source provenance.
```

Forge checks impacted invariants during planning and audit.

---

# 45. Self-correction

Within a Build Packet:

```text
IMPLEMENT
   ↓
TEST
   ↓
FAIL
   ↓
DIAGNOSE
   ↓
REPAIR
   ↓
TEST
```

This is **self-correction**.

It is temporary and local.

No durable lesson is created merely because a repair worked once.

---

# 46. Self-improvement

Self-improvement is different.

```text
EXPERIENCE
    ↓
PATTERN DETECTED
    ↓
LESSON CANDIDATE
    ↓
VALIDATION
    ↓
PROMOTION
    ↓
FUTURE EXECUTION POLICY CHANGES
```

Examples of what Forge may improve:

- planning strategies;
- context selection;
- tool selection;
- known failure patterns;
- build decomposition;
- testing strategies;
- repository inspection strategies;
- domain-specific engineering skills.

---

# 47. Protected self-improvement boundary

This is a **hard invariant**.

Forge may improve:

```text
skills
strategies
prompts
routing
context policies
learned patterns
```

Forge may **not autonomously weaken**:

```text
Governor
authority boundaries
independent verification
audit requirements
owner-controlled North Star
security policy
evidence requirements
```

In shorthand:

> **The learner cannot rewrite the constitution that governs the learner.**

Changes there require owner-controlled evolution.

---

# 48. Skill system

Skills should be structured capabilities rather than giant prompts.

Example:

```text
skills/
  engineering/
    skill.yaml
    architect.md
    builder.md
    auditor.md
    tests/
```

A skill defines:

```yaml
skill:
  name: engineering

  roles:
    - architect
    - builder
    - auditor

  allowed_tools: ...

  workflow: ...

  evidence_contract: ...

  learning_scope: ...
```

Eventually:

```text
engineering
research
product-design
data-engineering
security-review
gridlens
sentinel
trailforge
```

All share the same runtime.

---

# 49. Skill evolution

Forge may propose improvements to skills based on validated lessons.

Example:

```text
LESSON-031

Repeated failure:
Builders modify generated migrations directly.

Validated strategy:
Inspect migration ownership before editing schema artifacts.

Affected skill:
engineering.builder.repository-inspection
```

Forge creates a candidate skill patch.

That patch itself gets tested and independently audited before promotion.

Thus even self-improvement follows:

**Build → Verify → Learn.**

---

# 50. Model routing

Model selection should be policy-driven.

Example:

```yaml
routing:
  architecture:
    capability: high_reasoning

  implementation:
    capability: coding

  audit:
    capability: high_reasoning
    independent_context: true

  classification:
    capability: fast

  lesson_validation:
    capability: high_reasoning
```

Forge asks for a capability rather than hard-coding a specific model throughout the application.

---

# 51. Model independence

A useful later capability is cross-model verification.

For example:

```text
Architect → Model A
Builder   → Model B
Auditor   → Model A/C
```

But **different model names are not the definition of independence**.

The essential requirement is independent context and evidence-based review.

We shouldn't unnecessarily complicate V0 with mandatory multi-provider support.

---

# 52. Structured agent contracts

Agents should return schema-valid output.

Not:

```text
"Looks good! I think we should probably..."
```

Instead:

```json
{
  "verdict": "FAIL",
  "findings": [],
  "discoveries": [],
  "confidence": 0.96
}
```

Invalid outputs are runtime errors, not something downstream code guesses how to interpret.

---

# 53. Event-sourced execution

Forge's execution history should be event-oriented.

Current state can be derived from:

```text
RUN_STARTED
MISSION_ACCEPTED
BUILD_CREATED
BUILD_STARTED
TOOL_CALLED
TEST_FAILED
REPAIR_STARTED
CANDIDATE_CREATED
AUDIT_FAILED
DISCOVERY_CREATED
SPEC_PATCH_ACCEPTED
BUILD_SUPERSEDED
AUDIT_PASSED
MERGE_COMPLETED
LESSON_PROMOTED
RUN_COMPLETED
```

This gives us restartability and debugging.

---

# 54. Restartability

Forge must survive interruption.

After restart:

```text
Load event ledger
      ↓
Reduce current state
      ↓
Inspect repository reality
      ↓
Compare expected vs actual
      ↓
Reconcile
      ↓
Continue safely
```

Never assume the previous process exited cleanly.

This is essential for overnight autonomous operation.

---

# 55. Reconciliation

The event ledger says what Forge **believes** happened.

Repository reality says what actually exists.

On startup and critical transitions:

```text
EXPECTED STATE
      ↕
ACTUAL STATE
```

If they differ, Forge enters:

```text
RECONCILIATION_REQUIRED
```

before doing more work.

---

# 56. Failure taxonomy

Forge should classify failures.

```text
IMPLEMENTATION_FAILURE
TEST_FAILURE
TOOL_FAILURE
MODEL_FAILURE
CONTEXT_FAILURE
SPEC_FAILURE
ARCHITECTURE_FAILURE
DEPENDENCY_FAILURE
ENVIRONMENT_FAILURE
AUTHORITY_BLOCK
EXTERNAL_BLOCK
UNKNOWN_FAILURE
```

Different failures require different recovery strategies.

This is much better than one generic `retry()`.

---

# 57. Progress detection

Forge needs an objective concept of progress.

Signals include:

```text
fewer failing tests
new evidence obtained
uncertainty reduced
candidate diff materially changed
blocking contradiction resolved
requirement state advanced
new strategy attempted
```

Repeated execution without evidence improvement triggers stuck detection.

---

# 58. Retry budgets

Retries need budgets at multiple levels:

```text
tool retry
implementation retry
strategy retry
build retry
mission budget
```

Example:

```text
Tool timeout:
retry cheaply

Same test failure:
diagnose

Repeated same strategy:
STUCK_RESOLUTION

Repeated materially different strategies:
Architectural reconsideration

No valid solution:
Owner escalation
```

---

# 59. Cost and resource governor

Autonomy without budgets can become absurdly expensive.

Governor tracks:

```text
tokens
model calls
wall time
tool calls
compute
build attempts
research depth
```

A mission can specify:

```yaml
budget:
  wall_time: 8h
  max_model_cost: ...
  max_build_attempts: 100
```

V0 doesn't need sophisticated economic optimization, but the primitive should exist.

---

# 60. Human interruption

Owner can always:

```text
PAUSE
RESUME
STOP
REPLAN
OVERRIDE
APPROVE
REJECT
```

These become events.

The system should never require killing random processes to regain control.

---

# 61. Owner inbox

Forge should consolidate owner-required decisions.

Not interrupt Nick every six minutes.

Example:

```text
OWNER INBOX

3 decisions pending

DEC-41  High priority
Blocks telemetry persistence.

DEC-42  Low priority
Does not block current work.

DEC-43  Medium priority
Forge recommends A based on DISC-19.
```

Forge continues everything it can while waiting.

---

# 62. Explainability

Every major action should answer:

```text
What are you doing?
Why?
What evidence caused this?
What authority permits it?
What changed?
What happens next?
```

Not by exposing hidden chain-of-thought.

By exposing **structured engineering rationale and evidence**.

---

# 63. Mission report

At any point Forge should be able to produce:

```text id="dl7q4j"
FORGE STATUS

Mission:
Build Sentinel telemetry ingestion.

North Star:
unchanged

Specification:
v1.0 → v1.4

Requirements:
32 active
18 satisfied
9 pending
3 discovered
2 superseded

Builds:
21 attempted
16 passed
3 repaired
1 superseded
1 active

Audits:
16 PASS
4 FAIL
1 pending

Discoveries:
7 total
4 validated
1 rejected
1 under investigation
1 owner-required

Stuck recoveries:
2

Contradictions:
1 non-blocking

Lessons:
3 candidates
1 validated
2 awaiting additional evidence

Current work:
BUILD-022

Owner blockers:
None

Finish Contract:
18 / 32 requirements satisfied
NOT YET SATISFIED
```

The point isn't a fancy dashboard.

The point is that **Forge itself knows this state deterministically**.

A UI can come later.

---

# 64. Mission

A Mission is the top-level execution object.

Example:

```yaml id="md8yk3"
mission:
  id: MISSION-001

  objective:
    "Implement production-ready telemetry ingestion."

  repository:
    id: sentinel

  north_star:
    ref: NS-001

  specification:
    ref: SPEC-001

  finish_contract:
    ref: FC-001

  authority_policy:
    ref: POLICY-001

  budget:
    wall_time: 8h

  status:
    active
```

A Mission can span dozens or hundreds of Build Packets.

---

# 65. Mission acceptance

Forge should not immediately start coding after receiving a prompt.

First:

```text id="oipugf"
OWNER REQUEST
     ↓
UNDERSTAND
     ↓
IDENTIFY REPOSITORY
     ↓
LOAD NORTH STAR
     ↓
LOAD SPECIFICATION
     ↓
INSPECT REPOSITORY REALITY
     ↓
IDENTIFY CONTRADICTIONS
     ↓
ESTABLISH FINISH CONTRACT
     ↓
MISSION ACCEPTED
```

This startup protocol prevents a lot of autonomous-agent stupidity.

---

# 66. Bootstrap when documentation is weak

Real repositories won't always contain clean architecture documents.

Forge must tolerate:

```text id="d02v79"
PRD missing
architecture stale
tests incomplete
README wrong
owner intent informal
```

It should reconstruct a **provisional product model** from available evidence.

But provisional knowledge is labeled accordingly.

```text id="sc8f0e"
PROVISIONAL SPECIFICATION

Confidence: 0.64

Derived from:
repository
tests
README
owner prompt

Unresolved contradictions: 4
```

Forge can then investigate before building.

---

# 67. Source hierarchy

When sources disagree, Forge needs deterministic precedence.

Default:

```text id="xmy9hy"
OWNER DECISION
      ↓
NORTH STAR
      ↓
CURRENT CANONICAL SPEC
      ↓
ACCEPTED ADR / INVARIANT
      ↓
CURRENT REPOSITORY REALITY
      ↓
TESTS
      ↓
DOCUMENTATION
      ↓
HISTORICAL RECORD
      ↓
MODEL INFERENCE
```

But repository reality doesn't automatically outrank product intent.

If code contradicts the PRD, that may mean **the code is wrong**.

Forge surfaces the contradiction rather than choosing whichever source is convenient.

---

# 68. Canonical vs descriptive truth

This distinction is critical.

**Canonical truth**:

> What the product is supposed to be.

**Descriptive truth**:

> What currently exists.

Example:

```text id="40vvhj"
CANONICAL:
Asset supports multiple telemetry sources.

DESCRIPTIVE:
Current database schema allows only one.
```

That's not ambiguity.

That's work.

Forge should understand the difference.

---

# 69. Requirement lifecycle

Requirements have explicit states:

```text id="cokd7w"
PROPOSED
   ↓
ACTIVE
   ↓
IMPLEMENTING
   ↓
EVIDENCED
   ↓
VERIFIED
   ↓
SATISFIED
```

Alternative exits:

```text id="11o2np"
SUPERSEDED
REJECTED
BLOCKED
OWNER_REQUIRED
```

A requirement isn't satisfied because code exists.

It becomes satisfied only when its evidence contract is met.

---

# 70. Discovery lifecycle

Likewise:

```text id="t30n7f"
OBSERVATION
     ↓
DISCOVERY_CANDIDATE
     ↓
INVESTIGATING
     ↓
SUPPORTED
     ↓
VALIDATED
     ↓
ACCEPTED
     ↓
SPEC_CHANGE
     ↓
OUTCOME_PENDING
     ↓
CONFIRMED / DISPROVED / INCONCLUSIVE
```

This is how we prevent "agent idea" from becoming "product truth."

---

# 71. Lesson lifecycle

```text id="02u7z6"
EXPERIENCE
    ↓
LESSON_CANDIDATE
    ↓
EVIDENCE_ACCUMULATION
    ↓
VALIDATION
   / \
  /   \
 ▼     ▼
PROMOTE REJECT
   │
   ▼
ACTIVE LESSON
   │
   ▼
FUTURE EVALUATION
   │
   ├── reinforced
   ├── narrowed
   └── retired
```

Even learned knowledge remains falsifiable.

---

# 72. Temporal validity

Some lessons are context-dependent.

Forge should support:

```yaml id="kkhr3d"
lesson:
  scope:
    language: python
    framework: sqlalchemy
    architecture: event-sourced

  valid_since: ...
  last_confirmed: ...
```

Otherwise a lesson learned from one technology stack becomes a universal rule forever.

---

# 73. Scope-aware learning

Lessons should have scopes such as:

```text id="bajbyq"
GLOBAL ENGINEERING
REPOSITORY
PROJECT
DOMAIN
FRAMEWORK
TOOL
MODEL
```

Example:

> "Never use provider IDs as canonical identity"

may eventually become a broad architecture lesson.

Whereas:

> "Sentinel's telemetry adapter returns naive UTC timestamps"

belongs to Sentinel.

This prevents memory pollution.

---

# 74. Causal lineage

Forge should be able to trace:

```text id="igx7kf"
Why does this code exist?
```

Example:

```text id="rmgytz"
src/telemetry/source.py
        ↑
BUILD-031
        ↑
R-014 v3
        ↑
SPEC-PATCH-012
        ↑
DISC-014
        ↑
TEST-221 + repository evidence
```

And backwards:

```text id="fq5o9p"
If we change R-014, what might break?
```

Forge can traverse its dependents.

This is much more valuable than generic "memory."

---

# 75. Evidence graph

SQLite can remain the storage layer, but conceptually the records form a graph:

```text id="w12w5p"
Requirement
   ↓
Build
   ↓
Commit
   ↓
Test
   ↓
Audit
   ↓
Discovery
   ↓
Spec Patch
   ↓
Requirement
```

We do **not** need a graph database in V0.

Relationships in relational tables are enough.

Don't overengineer storage.

---

# 76. Evidence quality

Not all evidence has equal weight.

Forge should classify evidence roughly as:

```text id="5tut91"
E0 — assertion
E1 — static observation
E2 — deterministic test
E3 — integration evidence
E4 — independent reproduction
E5 — real-world outcome
```

This doesn't need a fake mathematical scoring system.

It simply gives the Architect/Auditor a shared vocabulary for evidence strength.

---

# 77. Evidence freshness

Evidence can become stale after relevant code changes.

Example:

```text id="n7ueub"
TEST-211 passed against SHA abc123

Candidate now:
SHA def456
```

Forge must determine whether TEST-211 remains applicable.

A stale test receipt cannot satisfy a Finish Contract merely because it once passed.

---

# 78. Verification impact analysis

Forge should avoid rerunning the entire universe after every tiny change.

Given a diff:

```text id="3w9vqb"
changed files
    ↓
affected components
    ↓
affected requirements
    ↓
affected invariants
    ↓
required verification
```

Then run the smallest sufficient evidence set.

Before final completion, broader verification can occur.

This is both faster and cheaper.

---

# 79. Auditor adversarial posture

The Auditor's job isn't to be helpful to the Builder.

Its job is to find reasons the candidate **doesn't deserve to merge**.

It should actively look for:

```text id="55tk9v"
requirement gaps
unhandled edge cases
false assumptions
test gaming
scope violations
regressions
stale evidence
architecture drift
security problems
undocumented behavior changes
```

But it should not invent arbitrary preferences.

Every finding needs a basis.

---

# 80. Auditor discovery posture

At the same time, Auditor asks:

```text id="k4kwnh"
What surprised us?

What became observable only because we built this?

Which assumptions changed?

What new dependency appeared?

Did implementation reveal a better abstraction?

Does the specification still describe the best product?

Did we discover work with higher value than
something currently planned?
```

This is where Forge transitions from **autonomous coding** to **autonomous product engineering**.

---

# 81. Discovery priority

Not every discovery should redirect the roadmap.

Forge considers:

```text id="jltu3a"
impact
confidence
urgency
dependency effects
cost of delay
cost of change
reversibility
North Star relevance
```

A minor cleanup discovery can wait.

A discovery that invalidates the data model should replan immediately.

---

# 82. Opportunity discovery

Forge should also be allowed to discover **positive opportunities**, not only defects.

Example:

> While implementing telemetry reconciliation, Forge discovers the event model already supports deterministic replay with little additional work.

That could unlock a major product capability.

Forge may create:

```text id="1h8hzj"
OPPORTUNITY-004
```

But opportunity discovery faces a higher bar than fixing a requirement because it can cause scope creep.

If it materially expands product purpose, it becomes A3 owner territory.

---

# 83. Scope-creep defense

Autonomous discovery creates a serious danger:

**Forge could endlessly improve the product and never finish.**

We need a hard countermeasure.

Every proposed discovery-driven change gets classified:

```text id="jpturw"
REQUIRED FOR NORTH STAR
MATERIAL PRODUCT IMPROVEMENT
OPTIONAL IMPROVEMENT
OUT OF SCOPE
```

During an active mission:

- required → incorporate;
- material → incorporate if authority/budget permits;
- optional → backlog;
- out of scope → record or discard.

This is critical.

---

# 84. Value-of-information

Forge should sometimes investigate before coding when the cost of being wrong is high.

Conceptually:

```text id="h1d2mu"
Cost of investigation
        vs
Cost of implementing wrong assumption
```

If a 10-minute investigation can prevent a 6-hour architectural mistake, investigate.

We don't need sophisticated equations in V0.

The Architect just needs this decision principle.

---

# 85. Reversibility

Forge should strongly prefer reversible decisions when uncertainty is high.

```text id="oxcnrm"
HIGH UNCERTAINTY
      +
REVERSIBLE OPTION AVAILABLE
      =
PREFER REVERSIBLE PATH
```

Irreversible decisions demand stronger evidence or owner authority.

That's good engineering regardless of AI.

---

# 86. Technical debt

Forge should explicitly distinguish:

```text id="u8qygf"
intentional debt
accidental debt
temporary scaffolding
defect
```

If it knowingly chooses a temporary solution, it creates a debt record with:

```text id="jjsul9"
reason
impact
exit condition
affected requirements
recommended timing
```

No invisible TODO graveyard.

---

# 87. Cleanup behavior

Forge should clean up:

```text id="n1c0vp"
temporary files
experimental branches
stale worktrees
generated debugging artifacts
abandoned candidate changes
```

but only when deterministic policy confirms they are Forge-owned and safe to remove.

It should never "clean up" arbitrary user files.

---

# 88. Security model

V0 should be local-first and conservative.

Default posture:

```text id="rh3fg5"
repository read        ALLOW
candidate write        ALLOW within scope
tests                  ALLOW
local shell            governed
network                explicit capability
secrets                deny by default
production writes      deny
destructive actions    deny
canonical branch write Governor only
```

The Builder should never receive raw credentials merely because a tool requires authentication.

Credential handling belongs below the model layer.

---

# 89. Secret boundary

Tools can use credentials without putting those credentials into model context.

Conceptually:

```text id="n5gm4i"
MODEL
  │
  │ "call GitHub PR API"
  ▼
TOOL RUNTIME
  │
  ├── retrieves credential securely
  │
  ├── executes
  │
  └── returns sanitized result
```

Forge logs that a credential-backed action occurred.

Not the credential itself.

---

# 90. External side effects

Operations such as:

```text id="5rm2mj"
deploy production
send email
delete cloud resources
purchase service
modify production DB
publish content
```

are **not ordinary engineering writes**.

They need explicit policies and often owner approval.

Forge Agent V0 should mostly avoid these.

---

# 91. Sandbox philosophy

The ideal long-term execution hierarchy:

```text id="2v25us"
MODEL
 ↓
FORGE TOOL API
 ↓
PERMISSION LAYER
 ↓
SANDBOX / WORKTREE
 ↓
HOST SYSTEM
```

The model should not conceptually have unrestricted machine access.

Even if V0 initially uses local subprocesses, the API boundary should anticipate stronger sandboxing later.

---

# 92. Observability

Forge needs machine-readable telemetry for itself.

Track:

```text id="sxdmsu"
mission duration
build duration
model usage
tool usage
failure types
repair attempts
audit failure rate
discovery rate
discovery validation rate
stuck events
owner interruptions
lesson promotion
spec churn
```

Not because dashboards are cool.

Because these measurements tell us whether Forge is actually improving.

---

# 93. Self-improvement metrics

We should be able to answer over time:

```text id="3ph8bc"
Are builds completing faster?

Are fewer candidates failing audit?

Are stuck recoveries becoming more successful?

Are previously learned lessons preventing repeat failures?

Are discovery hypotheses becoming more accurate?

Is owner intervention decreasing?

Is cost per verified requirement decreasing?
```

That's the empirical definition of Forge "getting better."

Not vibes.

---

# 94. Learning effectiveness

Every promoted lesson should eventually be evaluated.

Example:

```text id="gmk2hn"
LESSON-019 applied in:
BUILD-044
BUILD-071
BUILD-103

Outcomes:
3 successful
0 contradicted

Effect:
Prevented known identity-pattern failure twice.

Status:
REINFORCED
```

Or:

```text id="c4j3jz"
Lesson caused unnecessary complexity twice.

Status:
CHALLENGED
```

Forge's memory should be corrigible.

---

# 95. Prompt evolution

Prompts can improve, but prompts are **versioned artifacts**.

```text id="3d5i8c"
architect_prompt v4
builder_prompt v7
auditor_prompt v5
```

A proposed change gets:

```text id="2u1gzr"
hypothesis
expected benefit
evaluation
candidate version
```

Then compare outcomes.

We should avoid Forge casually rewriting its own prompts after every run.

---

# 96. Policy evolution

Policy is more sensitive than prompts.

Forge may **recommend** Governor policy changes.

It does not autonomously activate changes that alter:

```text id="d7lz63"
authority
security
verification independence
owner boundaries
evidence requirements
```

Those remain protected.

---

# 97. Model-generated code is untrusted

This should be explicit:

> **All Builder output is an untrusted candidate until verified.**

It doesn't matter how capable the model is.

The architecture assumes Builder mistakes are normal.

That assumption makes the whole system stronger.

---

# 98. Model-generated discoveries are also untrusted

Same principle:

> **A Discovery is an untrusted hypothesis until supported and validated.**

This protects the living PRD from agent enthusiasm.

---

# 99. Model failure containment

If an agent produces nonsense:

```text id="y3m4m4"
schema invalid
contradicts context
requests forbidden action
hallucinates repository state
```

the runtime rejects it.

It does not let one malformed response corrupt system state.

---

# 100. Determinism boundary

We should deliberately separate:

### Deterministic

```text id="iqwxst"
state transitions
permissions
event storage
repository identity
schema validation
hashing
merge eligibility
budgets
protected boundaries
```

### Probabilistic

```text id="aqb0jy"
planning
coding
diagnosis
discovery
architectural reasoning
lesson extraction
```

Forge becomes reliable by surrounding probabilistic intelligence with deterministic control.

---

# 101. Database

For V0:

**SQLite.**

Tables roughly:

```text id="4ejp7w"
missions
events
requirements
requirement_versions
assumptions
decisions
invariants
build_packets
investigations
experiments
candidates
audits
discoveries
spec_patches
contradictions
outcomes
lesson_candidates
lessons
tool_calls
model_calls
owner_requests
```

That's plenty.

No PostgreSQL initially.

No vector database initially.

No graph database initially.

---

# 102. Filesystem artifacts

Human-readable canonical artifacts still matter.

Suggested:

```text id="33xwzw"
.forge/
├── north-star.md
├── specification.md
├── finish-contract.yaml
├── architecture/
│   └── ADR-*.md
├── decisions/
├── discoveries/
├── reports/
└── forge.yaml
```

SQLite holds operational truth.

These artifacts make Forge understandable without proprietary tooling.

---

# 103. Repository-local vs global state

```text id="cnc3cb"
~/.forge/
├── config/
├── models/
├── skills/
├── lessons/
│   ├── global/
│   ├── frameworks/
│   └── tools/
└── runtime/

repo/.forge/
├── forge.yaml
├── north-star.md
├── specification.md
├── finish-contract.yaml
├── architecture/
├── decisions/
├── discoveries/
├── lessons/
├── reports/
└── state/
```

The distinction is important:

> **Product knowledge belongs with the product. General engineering knowledge belongs with Forge.**

Sentinel knowledge shouldn't accidentally influence GridLens unless it has been deliberately promoted into a broader validated lesson.

---

# 104. Knowledge promotion

Lessons move upward only through explicit promotion.

```text id="snt0c6"
SENTINEL EXPERIENCE
       ↓
Sentinel lesson
       ↓
Repeated elsewhere?
       ↓
Domain lesson
       ↓
Repeated across domains?
       ↓
Global engineering lesson
```

For example:

```text id="gv93rb"
"Sentinel provider X sends duplicate events"
```

stays Sentinel-specific.

But:

```text id="wktq2i"
"External provider identity should not be used
as canonical internal identity"
```

might eventually become a global architectural lesson.

Forge should earn generalization.

---

# 105. Cross-project learning

Eventually this becomes extremely powerful.

```text id="sk6q5c"
GridLens ─────┐
Sentinel ─────┼──→ FORGE EXPERIENCE STORE
Trailforge ───┤
Athena ───────┘
                    ↓
              validated patterns
                    ↓
             future projects
```

But cross-project retrieval must respect scope.

Forge should retrieve a lesson because it is **structurally relevant**, not because two repositories happen to use Python.

---

# 106. Retrieval

V0 does not need sophisticated semantic infrastructure.

Start with:

```text id="f7xusg"
structured metadata
+
keyword search
+
explicit relationships
+
recency
+
scope
```

If lesson volume becomes large enough that retrieval quality suffers, then introduce embeddings.

Don't build a vector database because "AI agents need vector databases."

They often don't.

---

# 107. Context compression

Long missions will accumulate enormous histories.

Agents do not need every historical event.

Forge should maintain derived state such as:

```text id="1f50b5"
CURRENT PRODUCT STATE
CURRENT EXECUTION STATE
OPEN CONTRADICTIONS
ACTIVE DISCOVERIES
RELEVANT DECISIONS
RELEVANT LESSONS
```

Raw events remain available for audit.

This is **state reduction**, not lossy replacement of evidence.

---

# 108. Reducers

Event reducers deterministically construct current state.

Conceptually:

```python id="5i2irh"
state = reduce(events)
```

Examples:

```text id="1au1hr"
RequirementReducer
MissionReducer
BuildReducer
DiscoveryReducer
OwnerDecisionReducer
LessonReducer
```

This makes restart and replay far safer.

---

# 109. Reducer invariants

Reducers need tests proving things like:

```text id="p1zpdw"
replaying events twice produces same state

event order is preserved

invalid transition fails closed

unknown event version does not silently disappear

state can be reconstructed from ledger
```

This is part of Forge's trust kernel.

---

# 110. Trust kernel

The smallest protected core of Forge is:

```text id="qofupg"
Governor
State machine
Authority evaluator
Event ledger
Reducers
Repository identity
Permission system
Merge eligibility
Audit independence
Protected policy
```

This is essentially Forge's **trust kernel**.

Everything else can evolve much more aggressively.

This idea maps very cleanly to what we learned from Anvil/Nucleus.

---

# 111. Trust-kernel change policy

Forge may build changes to its own trust kernel eventually.

But:

```text id="3x66p5"
FORGE
  ↓
proposes trust-kernel change
  ↓
isolated candidate
  ↓
expanded deterministic tests
  ↓
independent audit
  ↓
OWNER APPROVAL
  ↓
merge
```

Forge cannot autonomously approve changes to the machinery that controls Forge.

That remains a constitutional boundary.

---

# 112. Forge building Forge

Eventually Forge should be capable of developing itself.

That is a major milestone.

```text id="y1fl9c"
Forge v1
   ↓
builds candidate Forge v1.1
   ↓
Forge v1 independently audits candidate
   ↓
owner approves protected changes
   ↓
Forge v1.1
```

But self-hosting is **not a V0 requirement**.

First Forge needs to prove itself on another repository.

---

# 113. Self-hosting maturity levels

I would define:

```text id="l48x95"
F0  Forge cannot modify Forge

F1  Forge can modify non-protected Forge components

F2  Forge can propose protected-core changes

F3  Forge can run regression experiments against
    candidate versions of itself

F4  Forge can demonstrate measurable improvement
    across versions while governance remains intact
```

We should not rush this.

---

# 114. Execution profiles

Different missions need different operating postures.

Examples:

```text id="i6d3o2"
conservative
balanced
exploratory
```

**Conservative**

Stronger evidence, fewer autonomous spec changes.

**Balanced**

Default engineering behavior.

**Exploratory**

More investigations and experiments; still cannot violate authority boundaries.

The profile affects thresholds, not constitutional rules.

---

# 115. Engineering modes

Separate from profiles, a mission may be:

```text id="08yxom"
GREENFIELD
FEATURE
BUGFIX
REFACTOR
MIGRATION
HARDENING
AUDIT
RECOVERY
```

Architect behavior changes accordingly.

A bugfix mission shouldn't spontaneously redesign the entire product unless evidence shows the existing architecture makes the bug unavoidable.

---

# 116. Brownfield awareness

Most useful Forge work will happen in existing repositories.

Forge must respect:

```text id="lyptgx"
existing architecture
existing conventions
tests
migration history
public APIs
compatibility requirements
historical decisions
```

It should not treat every repository as a greenfield rewrite opportunity.

---

# 117. Legacy contradictions

Sometimes code exists for historical reasons that are no longer valid.

Forge can discover:

```text id="sv5p6h"
LEGACY-CONSTRAINT-007

Original reason:
Provider API lacked stable IDs.

Current reality:
Provider added stable IDs in v3.

Affected architecture:
Custom identity translation layer.

Recommendation:
Investigate retirement.
```

But it should not delete legacy machinery merely because it looks ugly.

Evidence first.

---

# 118. Test strategy

Forge should think in layers:

```text id="wz5o4d"
STATIC
  ↓
UNIT
  ↓
INTEGRATION
  ↓
SYSTEM
  ↓
ACCEPTANCE
```

Not every Build Packet needs every layer.

The Finish Contract determines what ultimately matters.

---

# 119. Test generation

Builders may generate tests.

But tests written by the Builder are **not automatically independent proof**.

The Auditor can:

- inspect Builder tests;
- run them;
- create adversarial verification;
- use existing independent tests;
- request stronger evidence.

This prevents:

> "I wrote a test that proves my implementation works."

from being sufficient by itself.

---

# 120. Test gaming defense

Auditor specifically checks for:

```text id="h5ox2k"
weakened assertions
deleted tests
excessive mocking
hard-coded fixtures
test-only branches
disabled validation
narrowed input domains
snapshot acceptance without inspection
```

A green suite is evidence.

It isn't automatically proof.

---

# 121. Regression ownership

If a Build Packet breaks an unrelated requirement, Builder owns the regression unless evidence shows the requirement itself should evolve.

Forge doesn't allow:

> "Those tests aren't relevant to my feature."

without proving that claim.

---

# 122. Unknown failures

Sometimes Forge won't understand a failure.

Correct state:

```text id="xbnnv6"
UNKNOWN
```

Then it can:

```text id="1nlk62"
collect evidence
reduce problem
reproduce
investigate
change model
change strategy
escalate
```

It must never invent an explanation merely to keep the loop moving.

---

# 123. Minimal reproducibility

Stuck Resolver should attempt to reduce difficult failures.

```text id="32fjw2"
large failing system
      ↓
smallest reproduction
      ↓
identify violated assumption
      ↓
repair
```

This should become a reusable engineering skill.

Over time, Forge can learn which reduction strategies work best.

---

# 124. Counterfactual reasoning

For major discoveries, Architect/Auditor should sometimes ask:

> What happens if we **don't** make this change?

This guards against overreacting to interesting observations.

Example:

```text id="svh4qg"
DISC-019 proposes event sourcing.

Counterfactual:
Current CRUD persistence still satisfies every active
requirement and Finish Contract.

Conclusion:
Interesting architecture opportunity, but not required.

Disposition:
BACKLOG
```

This is one of our best defenses against autonomous overengineering.

---

# 125. Simplicity preference

Forge should have a canonical engineering principle:

> **Prefer the simplest architecture that satisfies the current evidence-supported product model while preserving reasonable evolution paths.**

Discovery should improve the product.

It should not become an excuse to build clever infrastructure.

---

# 126. Complexity budget

Architect can explicitly recognize complexity cost.

A proposal that introduces:

```text id="4c2ozb"
new service
new database
new queue
new framework
new runtime
new deployment dependency
```

needs stronger justification than a local change.

This isn't a numeric score initially.

It's an engineering constraint.

---

# 127. Dependency policy

New dependencies require:

```text id="x3x7b8"
need
fit
maintenance status
license compatibility
security implications
replacement cost
```

Forge should not install a package merely because the Builder remembers its name.

For consequential dependencies, verify current package reality.

---

# 128. External knowledge

When repository evidence isn't enough, Forge can research external sources.

Example:

```text id="ag6prg"
INVEST-019

Question:
Does PostgreSQL guarantee X under isolation level Y?

Source requirement:
Primary documentation preferred.
```

External information enters Forge as **evidence with provenance**, not canonical truth by default.

---

# 129. Freshness

External technical facts can change.

Forge records:

```text id="6unycx"
source
retrieved_at
version
applicable environment
```

A lesson based on an old API version should not blindly govern a new implementation.

---

# 130. Research boundary

Research can inform:

```text id="9ptj1b"
architecture
dependency choice
API usage
security
performance
domain behavior
```

But external "best practices" do not automatically override the project's North Star or validated local evidence.

Forge engineers the actual product, not a generic tutorial.

---

# 131. Architecture drift detection

Forge continuously compares:

```text id="mvb62v"
accepted architecture
        ↕
repository reality
```

Drift may mean:

```text id="veec29"
implementation defect
documentation stale
intentional evolution
undocumented discovery
```

Forge investigates before reconciling.

---

# 132. Specification drift detection

Same for:

```text id="6jjh7i"
Living Specification
        ↕
Repository behavior
```

If the implementation consistently does something valuable not represented in the spec, that can itself become a discovery.

---

# 133. Dead requirement detection

Forge may discover a requirement that no longer contributes to the North Star.

It can propose:

```text id="b81qnf"
R-029 → SUPERSEDED
```

But it must show:

```text id="93vx07"
why it existed
what changed
what evidence invalidated it
what depends on it
what happens if removed
```

Deleting work from the PRD deserves the same rigor as adding work.

---

# 134. Requirement splitting

A vague requirement can become more precise through implementation.

```text id="7sb8ow"
R-014

"Support telemetry ingestion."
```

may evolve into:

```text id="u0sl62"
R-014A  Accept multiple telemetry sources
R-014B  Preserve source provenance
R-014C  Detect duplicate observations
R-014D  Handle out-of-order timestamps
```

That's not scope creep if implementation evidence shows these are necessary to satisfy the original intent.

It's **specification resolution**.

---

# 135. Requirement merging

The opposite also happens.

Forge may discover:

```text id="8b6fdu"
R-21
R-22
R-27
```

are actually manifestations of one domain concept.

It can consolidate them while preserving historical lineage.

Living specification means evolution in both directions.

---

# 136. Finish Contract evolution

This is more sensitive than normal PRD evolution.

A discovery can reveal that the existing Finish Contract is insufficient.

Forge may **propose** strengthening it.

Example:

```text id="gox4g7"
Discovery:
Restart behavior is critical to telemetry correctness.

Proposed Finish Contract addition:
System must recover ingestion state after process restart.
```

If clearly implied by the North Star, this may be A2.

Weakening the Finish Contract should face a much higher authority threshold.

Forge should never make completion easier simply because it's struggling.

---

# 137. Monotonic evidence principle

Forge may learn that old evidence is invalid.

But it should never erase history.

```text id="xkz6dg"
TEST-014
PASS at SHA abc
```

remains true historically.

Later:

```text id="gh2am5"
TEST-014
STALE for current candidate
```

History is preserved while applicability changes.

---

# 138. Immutable audit history

Events, decisions, discoveries and audits should be append-only at the logical level.

Corrections happen through new events:

```text id="t16h1v"
DISC-014 CREATED
DISC-014 VALIDATED
DISC-014 LATER_DISPROVED
```

not by rewriting history to pretend Forge was always right.

That's necessary for meaningful learning.

---

# 139. Product evolution report

Forge should be able to show:

```text id="6j3zv7"
ORIGINAL UNDERSTANDING
         ↓
WHAT WE DISCOVERED
         ↓
WHAT CHANGED
         ↓
WHY IT CHANGED
         ↓
WHAT THE PRODUCT IS NOW
```

This will be incredibly useful for you because autonomous execution shouldn't leave you wondering:

> "What did the agent actually turn my product into?"

---

# 140. Owner digest

Instead of raw logs, Forge should summarize meaningful changes:

```text id="7a58rq"
FORGE OVERNIGHT DIGEST

Built:
Telemetry source model
Ingestion reconciliation
Restart recovery

Discovered:
Assets require multiple telemetry sources.

Changed:
R-014 split into four requirements.

Rejected:
Event sourcing was investigated but did not provide
enough value for current requirements.

Recovered:
BUILD-019 became stuck after three migration strategies.
Forge replaced the migration approach with additive
schema evolution and passed independent audit.

Learned:
One candidate engineering lesson awaiting validation.

Needs you:
No decisions.

Finish Contract:
74% evidenced.
```

**That** is the interface I think you'll actually want day-to-day.

---

# 141. Completion audit

Before mission completion, Forge runs a broader audit than ordinary PR verification.

It asks:

```text id="vfmj9j"
Does implementation satisfy all active requirements?

Is every required evidence item current?

Are all critical invariants satisfied?

Are any material contradictions unresolved?

Are validated discoveries reconciled?

Are owner decisions resolved or explicitly excluded?

Are temporary artifacts cleaned?

Is repository state canonical and reproducible?

Does the Finish Contract actually pass?
```

Only then can:

```text id="pj9r11"
MISSION_COMPLETE
```

be emitted.

---

# 142. Partial completion

Sometimes a mission legitimately cannot finish.

Forge should report:

```text id="fw9y1i"
MISSION_PARTIALLY_COMPLETE
```

with exact reasons.

Example:

```text id="qk7v85"
41 / 43 requirements satisfied.

Blocked:
R-041 requires production API credentials.
R-043 depends on owner decision DEC-012.

Everything else independently verified.
```

This is much better than either pretending completion or saying "I'm stuck."

---

# 143. Stop conditions

Canonical stop conditions:

```text id="h29oc8"
A — Finish Contract satisfied

B — Budget exhausted

C — No valid authorized work remains

D — Owner decision required and all independent
    work exhausted

E — Environment prevents safe continuation

F — Governor detects integrity violation
```

Stop conditions are deterministic.

The model does not decide that it's tired.

---

# 144. Integrity violation

Examples:

```text id="f58xkv"
canonical repository changed unexpectedly

candidate changed after audit

event ledger corruption

protected policy modified

repository identity mismatch

worktree cannot be reconciled
```

Forge fails closed.

It should not "probably be fine" its way through trust failures.

---

# 145. Recovery from crash

On restart:

```text id="cl6yyi"
BOOT
 ↓
VERIFY LEDGER
 ↓
IDENTIFY ACTIVE MISSION
 ↓
INSPECT REPOSITORY
 ↓
INSPECT WORKTREES
 ↓
RECONCILE
 ↓
DETERMINE LAST SAFE STATE
 ↓
CONTINUE
```

This is a first-class feature, not an afterthought.

---

# 146. Idempotency

Where practical, deterministic actions should be idempotent.

For example:

```text id="w6bxmp"
create candidate
record audit
apply spec patch
reduce state
```

should detect prior completion rather than accidentally duplicating state after restart.

---

# 147. Long-running autonomy

With the above machinery, Forge can safely execute:

```text id="bq12ok"
MISSION
  ↓
hours
  ↓
dozens of builds
  ↓
multiple discoveries
  ↓
several replans
  ↓
stuck recoveries
  ↓
owner decisions when necessary
  ↓
completion
```

without needing the user to provide a new prompt after every task.

That is the autonomous-building capability we're after.

---

# 148. What "autonomous" means — continued

For Forge:

> **Autonomous means the ability to select and execute valid next work toward an authorized objective without requiring human prompting between steps, while remaining inside deterministic authority, evidence, and safety boundaries.**

Autonomy does **not** mean:

```text id="6z6wgd"
unrestricted shell access
unbounded spending
changing product purpose
self-approving work
ignoring failed tests
rewriting governance
making irreversible decisions
```

The goal is **high agency inside explicit authority**.

---

# 149. Autonomous continuation

After every completed unit of work, Forge asks:

```text id="b1gbhg"
Finish Contract satisfied?
        │
       NO
        ↓
Authorized work available?
        │
       YES
        ↓
Highest-value valid next action?
        ↓
PLAN
        ↓
EXECUTE
```

There is no:

> "Would you like me to continue?"

inside normal autonomous execution.

If the mission authorizes continuation, **Forge continues**.

---

# 150. Autonomous replanning

Forge is not bound to its original task sequence.

It may replan when:

```text id="rzuh1k"
new evidence appears
discovery invalidates assumption
build exposes hidden dependency
architecture changes
requirement becomes unnecessary
higher-value blocking work emerges
stuck resolution changes strategy
owner decision changes constraints
```

The execution graph is therefore a **current hypothesis about how to reach the Finish Contract**.

It is not sacred.

---

# 151. Autonomous product discovery

Forge may discover necessary product behavior that wasn't explicitly written.

This is central.

```text id="g2t02s"
PRD
 ↓
BUILD
 ↓
REALITY
 ↓
SURPRISE
 ↓
EVIDENCE
 ↓
DISCOVERY
 ↓
VALIDATION
 ↓
SPEC EVOLUTION
```

The initial PRD is intentionally allowed to be incomplete.

Forge's responsibility includes reducing that incompleteness through engineering evidence.

---

# 152. Autonomous redirection

A validated discovery may cause Forge to tell the Builder:

```text id="0aj3me"
STOP BUILD-031.

R-019 is based on assumption A-044.

A-044 has been contradicted by TEST-219 and
integration evidence from BUILD-030.

BUILD-031 is therefore superseded.

Execute INVEST-012 followed by BUILD-031A instead.
```

This is not failure to follow the plan.

**This is the system working correctly.**

---

# 153. Autonomous stuck recovery

Forge does not merely retry.

Canonical stuck loop:

```text id="2syf06"
FAILURE
   ↓
DIAGNOSIS
   ↓
REPAIR
   ↓
FAILURE
   ↓
PROGRESS CHECK
   ↓
NO MATERIAL PROGRESS
   ↓
STUCK
   ↓
REDUCE PROBLEM
   ↓
RELOAD HIGHER-ORDER INTENT
   ↓
GENERATE DIFFERENT STRATEGY
   ↓
TEST STRATEGY
```

If that repeatedly fails:

```text id="3s9u7w"
architecture reconsideration
        ↓
specification reconsideration
        ↓
external blocker?
        ↓
owner escalation
```

Forge climbs the abstraction ladder rather than smashing harder into the same implementation.

---

# 154. Autonomous self-correction

Self-correction occurs within the active engineering loop.

```text id="98lg3c"
Builder makes mistake
       ↓
Tests expose mistake
       ↓
Builder repairs
       ↓
Auditor finds deeper issue
       ↓
Builder repairs
       ↓
Audit passes
```

No owner involvement is necessary unless authority boundaries are crossed.

---

# 155. Autonomous self-improvement

Self-improvement happens **across** engineering loops.

```text id="wt9uzl"
Run 1
  ↓
Experience
  ↓
Candidate lesson

Run 2
  ↓
Similar evidence
  ↓
Lesson strengthened

Run 3
  ↓
Lesson predicts successful strategy
  ↓
Outcome confirms it

        ↓

PROMOTED KNOWLEDGE

        ↓

Run 4 starts with better engineering guidance
```

That's what we mean when we say:

> **Forge gets better while building.**

Not model retraining.

**Validated harness improvement.**

---

# 156. Three nested loops

This is the canonical heart of Forge Agent.

## Loop A — Engineering

```text id="5bfazq"
PLAN
 ↓
BUILD
 ↓
TEST
 ↓
AUDIT
 ↓
MERGE
 ↓
CONTINUE
```

Purpose:

**Produce correct implementation.**

---

## Loop B — Discovery

```text id="5yvr9a"
OBSERVE
 ↓
QUESTION
 ↓
HYPOTHESIZE
 ↓
INVESTIGATE / EXPERIMENT
 ↓
VALIDATE
 ↓
EVOLVE SPECIFICATION
 ↓
REPLAN
```

Purpose:

**Produce a better understanding of the product.**

---

## Loop C — Learning

```text id="d6md1f"
EXPERIENCE
 ↓
PATTERN
 ↓
LESSON CANDIDATE
 ↓
VALIDATE
 ↓
PROMOTE
 ↓
APPLY
 ↓
MEASURE OUTCOME
 ↓
REINFORCE / REVISE / RETIRE
```

Purpose:

**Produce a better engineering system.**

Together:

```text id="c00gnm"
                 ┌───────────────────────────┐
                 │      LEARNING LOOP        │
                 │                           │
                 │   ┌───────────────────┐   │
                 │   │  DISCOVERY LOOP   │   │
                 │   │                   │   │
                 │   │  ┌─────────────┐  │   │
                 │   │  │ ENGINEERING │  │   │
                 │   │  │    LOOP     │  │   │
                 │   │  └─────────────┘  │   │
                 │   └───────────────────┘   │
                 └───────────────────────────┘
```

That diagram should probably become one of Forge's canonical visuals.

---

# 157. Fourth loop: governance

There is actually a fourth surrounding loop, but it serves a different purpose.

```text id="gopjve"
INTENT
 ↓
AUTHORITY
 ↓
ACTION
 ↓
EVIDENCE
 ↓
POLICY CHECK
 ↓
CONTINUE / ESCALATE
```

Governance surrounds all three intelligence loops.

So the complete model is:

```text id="jy00k3"
┌─────────────────────────────────────────────┐
│                 GOVERNANCE                  │
│                                             │
│   ┌─────────────────────────────────────┐   │
│   │              LEARNING               │   │
│   │                                     │   │
│   │   ┌─────────────────────────────┐   │   │
│   │   │          DISCOVERY          │   │   │
│   │   │                             │   │   │
│   │   │   ┌─────────────────────┐   │   │   │
│   │   │   │     ENGINEERING     │   │   │   │
│   │   │   └─────────────────────┘   │   │   │
│   │   └─────────────────────────────┘   │   │
│   └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

---

# 158. Stable Intent / Living Specification

This remains the foundational relationship.

```text id="49um3i"
           STABLE INTENT
                │
                │ constrains
                ▼
       LIVING SPECIFICATION
                │
                │ directs
                ▼
       ADAPTIVE EXECUTION
                │
                │ produces
                ▼
             EVIDENCE
                │
                │ reveals
                ▼
            DISCOVERY
                │
                │ improves
                ▼
       LIVING SPECIFICATION
```

And the loop repeats.

---

# 159. Why North Star remains stable

Without a stable reference, self-improvement can become drift.

Imagine:

```text id="9zqgxe"
PRD changes architecture
        ↓
architecture changes requirements
        ↓
requirements change product
        ↓
product changes North Star
```

Eventually Forge could efficiently build something completely different from what Nick wanted.

Therefore:

> **Evidence may challenge our understanding of how to achieve the North Star. It does not autonomously redefine why the product exists.**

That is constitutional.

---

# 160. North Star format

Keep it short.

Something like:

```yaml id="xw2nj8"
north_star:
  product: Sentinel

  purpose:
    "Detect developing generator problems early enough
    for operators to act before failure."

  primary_user:
    "Generator fleet operators and technical operations teams."

  core_outcome:
    "Turn telemetry into trustworthy evidence of developing
    equipment problems."

  non_goals:
    - "Generic IoT dashboard"
    - "Unexplained AI predictions"

  invariants:
    - "Evidence must remain traceable."
    - "Unknown must remain distinguishable from healthy."
```

The North Star should **not become a 100-page specification**.

If everything is sacred, nothing is adaptable.

---

# 161. Owner intent updates

The owner can change the North Star.

That's allowed.

But it's explicit:

```text id="u1s9d7"
NS-001 v1
     ↓
OWNER DECISION
     ↓
NS-001 v2
```

Then Forge performs impact analysis:

```text id="5tgflw"
requirements affected
architecture affected
builds invalidated
lessons potentially invalid
Finish Contract changes
```

Intent evolution is therefore controlled rather than silently absorbed.

---

# 162. Forge constitution

I would give Forge a short machine-readable constitution.

Core laws:

```text id="q8glr0"
1. Owner-controlled intent outranks agent preference.

2. Evidence outranks unsupported assertion.

3. Implementation claims require independent verification.

4. Unknown remains unknown until supported.

5. Discoveries are hypotheses until validated.

6. Living specifications may evolve inside authorized intent.

7. The execution plan is expendable.

8. Failed strategies are evidence.

9. Learning must be validated before becoming durable policy.

10. The learner may not weaken its own governance.

11. Irreversible actions require stronger authority.

12. Completion is determined by the Finish Contract,
    not by agent confidence.
```

These twelve laws are enough.

Don't turn the constitution into another giant prompt.

---

# 163. System roles

Canonical V1 roles:

```text id="u30gjj"
GOVERNOR
ARCHITECT
BUILDER
AUDITOR
STUCK RESOLVER
LESSON EVALUATOR
```

But these do **not necessarily require six simultaneous agents**.

Important distinction.

They are **roles/contracts**.

The same underlying model can perform different roles in isolated invocations.

---

# 164. No agent swarm

I explicitly recommend **against**:

```text id="m1yjea"
20 permanent agents
agents chatting continuously
agents voting on everything
recursive debate
unbounded delegation
```

That adds cost and nondeterminism without necessarily adding intelligence.

Forge uses specialized roles only where role separation produces meaningful engineering value.

---

# 165. Architect contract

Input:

```text id="e5g7bf"
North Star
current specification
architecture
execution graph
repository state
open discoveries
open contradictions
relevant lessons
budget
```

Output:

```text id="mrfw5q"
next action
reason
dependencies
authority
Build/Investigation Packet
expected evidence
```

Architect does not implement.

---

# 166. Builder contract

Input:

```text id="6k2d2n"
Build Packet
bounded repository context
relevant architecture
acceptance criteria
tool permissions
```

Output:

```text id="yt8n08"
candidate revision
implementation summary
tests attempted
evidence produced
unexpected observations
blockers
```

Builder does not declare PASS.

---

# 167. Auditor contract

Input:

```text id="f47j56"
North Star slice
specification slice
Build Packet
base revision
candidate revision
diff
evidence
```

Output:

```text id="hh3f0j"
implementation verdict
findings
evidence gaps
invariant findings
discovery candidates
confidence
```

Auditor does not modify the candidate it is reviewing.

---

# 168. Stuck Resolver contract

Input:

```text id="q6ccmf"
objective
relevant intent
current architecture
attempt history
failure evidence
strategies already attempted
```

Output:

```text id="oxl6bh"
failure model
materially different strategy
why previous strategies failed
new investigation if necessary
recommended authority
```

It cannot simply return:

> "Try again more carefully."

---

# 169. Lesson Evaluator contract

Input:

```text id="y15do7"
candidate lesson
supporting experiences
contradictory experiences
scope
outcomes
```

Output:

```text id="mgldmp"
PROMOTE
REJECT
NEEDS_MORE_EVIDENCE
NARROW_SCOPE
```

This role protects long-term memory quality.

---

# 170. Discovery responsibility

Discovery should not belong only to Auditor.

Any role can emit an **Observation**.

```text id="xjj0n6"
Builder → observation
Architect → observation
Auditor → observation
Stuck Resolver → observation
Tool runtime → deterministic anomaly
```

But observations flow through the same Discovery Engine.

Nobody gets a shortcut into canonical product truth.

---

# 171. Builder observations

This is important because the Builder sees implementation reality most directly.

Example:

```text id="n1c3bu"
OBS-118

While implementing BUILD-041, the existing domain model
requires one Organization per Site, but fixtures contain
shared Sites.

No spec change requested by Builder.
```

The Builder reports the observation.

Discovery Engine decides what happens next.

This prevents Builder from silently redesigning scope while still capturing what it learns.

---

# 172. Auditor after merge

You specifically described the **Auditor approving PRs and doing merges while noticing patterns**.

I agree, with one refinement.

The Auditor should analyze both:

### Pre-merge

```text id="sk2e09"
Is this candidate correct?
What did this candidate reveal?
```

### Post-merge / cumulative

```text id="r35c57"
What patterns are emerging across the last N merges?
```

That second function is essential for discoveries that are invisible within one PR.

---

# 173. Cumulative audit

Periodically:

```text id="cqtrph"
MERGE-21
MERGE-22
MERGE-23
MERGE-24
MERGE-25
    ↓
CUMULATIVE AUDIT
```

Ask:

```text id="0a1kpx"
Are we repeatedly working around the same abstraction?

Are multiple requirements symptoms of one missing concept?

Is complexity increasing unexpectedly?

Are tests repeatedly failing in the same subsystem?

Are new domain patterns emerging?

Has repository reality diverged from architecture?

Is a planned future build now obviously wrong?
```

This is **exactly** where Forge can see something we didn't know when writing the PRD.

---

# 174. Pattern discovery

Example:

```text id="pf0nt9"
BUILD-031:
special handling for source ownership

BUILD-037:
special handling for source permissions

BUILD-041:
special handling for source credentials

BUILD-044:
special handling for source health
```

Individually they may all pass.

Cumulative Auditor recognizes:

> "Source" is probably a missing first-class domain entity.

That generates:

```text id="b49nbi"
DISC-021

Pattern:
Four independently successful builds introduce
source-specific state.

Hypothesis:
Source should be modeled explicitly rather than
remaining adapter metadata.

Evidence:
BUILD-031
BUILD-037
BUILD-041
BUILD-044

Potential impact:
R-12
R-19
R-22
Architecture telemetry layer
```

**This is one of the most important capabilities in Forge.**

---

# 175. Scheduled reflection

Cumulative auditing should occur based on events, not just arbitrary time.

Triggers:

```text id="ud70f7"
after N successful merges
after major architecture change
after repeated stuck events
after high spec churn
before major milestone
before Finish Contract completion
```

V0 could simply run it every **5 merges** plus before completion.

---

# 176. Reflection cannot block endlessly

Reflection itself can become agent procrastination.

So Governor budgets it.

```text id="cyhvjl"
REFLECTION
  ↓
material discovery?
 / \
no  yes
│    │
▼    ▼
continue  investigate
```

If nothing meaningful is found, Forge gets back to work.

---

# 177. Product-quality optimization

Forge should optimize for:

```text id="z91jd0"
North Star satisfaction
correctness
simplicity
maintainability
evidence quality
future adaptability
```

Not:

```text id="oeb1nc"
lines of code
number of commits
number of requirements
number of agents
number of discoveries
```

More activity does not mean better engineering.

---

# 178. Discovery-quality optimization

Likewise, we do not want Forge maximizing discovery count.

The best run may discover nothing because the PRD was excellent.

Forge should be rewarded conceptually for **useful validated discoveries**, not novelty.

---

# 179. Self-improvement-quality optimization

Same principle.

A stable skill that works should not constantly rewrite itself.

Forge should prefer:

```text id="0ppb9l"
stable proven behavior
```

over:

```text id="z5ubwq"
continuous mutation for its own sake
```

Improvement requires evidence of an actual problem or opportunity.

---

# 180. V0 thesis

Now we can finally define V0 cleanly.

Forge V0 must prove:

> **Given an imperfect PRD and an existing repository, Forge can autonomously implement meaningful functionality, independently verify its work, recover from implementation failures, discover at least one material specification issue when real evidence supports it, evolve the living specification within owner intent, redirect subsequent work accordingly, and complete against an evidence-based Finish Contract.**

That's the experiment.

---

# 181. V0 does not need

Explicitly exclude:

```text id="yefrfh"
web dashboard
multi-machine execution
distributed workers
Kubernetes
PostgreSQL
graph database

vector database
complex embeddings pipeline
agent swarm
multi-provider orchestration
automatic cloud deployment
production environment writes
full browser automation
voice interface
mobile app
visual workflow builder
marketplace
plugin ecosystem
automatic model training
distributed memory
complex reinforcement learning
self-modification of protected governance
```

If any of those become necessary to prove the V0 thesis, we add the minimum required piece.

Otherwise they wait.

---

# 182. V0 technology stack

My recommended V0:

```text id="s0zmqx"
Language             Python 3.12+
CLI                  Typer
Validation           Pydantic
Database             SQLite
ORM / persistence    SQLAlchemy or thin sqlite layer
Git                  subprocess + deterministic adapter
Model API            provider abstraction
Tests                pytest
Configuration        YAML
Structured output    JSON / Pydantic
Logging              stdlib structured logging
```

No framework should become Forge's architecture.

The architecture belongs to us.

---

# 183. V0 process architecture

One local Forge process is enough.

```text id="cn3i0v"
┌─────────────────────────────┐
│        FORGE PROCESS        │
│                             │
│ Governor                    │
│ State Machine               │
│ Event Ledger                │
│ Product Brain               │
│ Context Engine              │
│ Model Router                │
│ Tool Runtime                │
│ Repository Adapter          │
│                             │
└─────────────┬───────────────┘
              │
              ├──── LLM API
              │
              ├──── Git
              │
              ├──── Filesystem
              │
              └──── Test/Shell processes
```

We don't need microservices.

---

# 184. V0 repository architecture

I would start Forge itself approximately like this:

```text id="lue6c1"
forge-agent/
│
├── pyproject.toml
├── README.md
├── AGENTS.md
│
├── forge/
│   │
│   ├── cli/
│   │   ├── main.py
│   │   ├── run.py
│   │   ├── status.py
│   │   └── inspect.py
│   │
│   ├── core/
│   │   ├── governor.py
│   │   ├── state_machine.py
│   │   ├── authority.py
│   │   ├── policies.py
│   │   └── errors.py
│   │
│   ├── product/
│   │   ├── north_star.py
│   │   ├── specification.py
│   │   ├── requirements.py
│   │   ├── assumptions.py
│   │   ├── decisions.py
│   │   ├── invariants.py
│   │   ├── contradictions.py
│   │   └── finish_contract.py
│   │
│   ├── execution/
│   │   ├── architect.py
│   │   ├── builder.py
│   │   ├── auditor.py
│   │   ├── stuck_resolver.py
│   │   ├── packets.py
│   │   └── scheduler.py
│   │
│   ├── discovery/
│   │   ├── observations.py
│   │   ├── discoveries.py
│   │   ├── validator.py
│   │   ├── spec_patch.py
│   │   └── cumulative_audit.py
│   │
│   ├── learning/
│   │   ├── experiences.py
│   │   ├── lessons.py
│   │   ├── evaluator.py
│   │   └── retrieval.py
│   │
│   ├── evidence/
│   │   ├── events.py
│   │   ├── ledger.py
│   │   ├── receipts.py
│   │   ├── reducers.py
│   │   └── provenance.py
│   │
│   ├── repository/
│   │   ├── adapter.py
│   │   ├── git.py
│   │   ├── worktrees.py
│   │   └── identity.py
│   │
│   ├── tools/
│   │   ├── runtime.py
│   │   ├── permissions.py
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   └── tests.py
│   │
│   ├── models/
│   │   ├── provider.py
│   │   ├── router.py
│   │   ├── contracts.py
│   │   └── structured.py
│   │
│   ├── context/
│   │   ├── assembler.py
│   │   ├── selection.py
│   │   └── provenance.py
│   │
│   └── storage/
│       ├── database.py
│       ├── schema.py
│       └── migrations.py
│
├── skills/
│   └── engineering/
│       ├── skill.yaml
│       ├── architect.md
│       ├── builder.md
│       ├── auditor.md
│       ├── stuck_resolver.md
│       └── lesson_evaluator.md
│
├── schemas/
│   ├── mission.schema.json
│   ├── build_packet.schema.json
│   ├── audit.schema.json
│   ├── discovery.schema.json
│   └── lesson.schema.json
│
├── tests/
│   ├── core/
│   ├── product/
│   ├── execution/
│   ├── discovery/
│   ├── evidence/
│   ├── repository/
│   └── integration/
│
└── docs/
    ├── FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md
    ├── FORGE_AGENT_V0_PRD.md
    └── adr/
```

That's enough structure without turning V0 into an enterprise platform.

---

# 185. CLI

V0 should feel simple.

```bash id="oj1qft"
forge init
```

creates:

```text id="c9u96g"
.forge/
forge.yaml
north-star.md
specification.md
finish-contract.yaml
```

Then:

```bash id="c6jqr2"
forge run
```

or:

```bash id="lttyn7"
forge run \
  --repo C:\Projects\sentinel \
  --mission "Implement telemetry ingestion"
```

And:

```bash id="nwknvb"
forge status
forge inspect BUILD-019
forge inspect DISC-004
forge pause
forge resume
forge report
```

That's enough V0 UX.

---

# 186. Initialization

`forge init` should inspect the repository before generating anything.

```text id="tdq0f7"
IDENTIFY REPOSITORY
       ↓
INSPECT FILE TREE
       ↓
INSPECT DOCS
       ↓
INSPECT TESTS
       ↓
INSPECT BUILD SYSTEM
       ↓
INSPECT GIT
       ↓
GENERATE PROVISIONAL PRODUCT MODEL
       ↓
OWNER SUPPLIES / CONFIRMS NORTH STAR
```

Forge shouldn't assume every repo starts with perfect Forge documentation.

---

# 187. PRD ingestion

Forge accepts normal Markdown PRDs.

We do **not** require you to manually author machine schemas.

```text id="n1ljke"
PRD.md
  ↓
Specification Parser
  ↓
requirements
assumptions
constraints
acceptance criteria
unknowns
```

Forge then produces structured internal state.

Human-readable Markdown remains the editing surface.

---

# 188. PRD quality audit

Before execution, Forge audits the initial PRD.

It asks:

```text id="o5q7vi"
Are requirements testable?

Are important terms undefined?

Are assumptions hidden?

Are requirements contradictory?

Are acceptance criteria missing?

Does the PRD conflict with repository reality?

Does the Finish Contract actually prove the North Star?
```

But Forge should **not block execution merely because the PRD isn't perfect**.

The whole system exists partly because it won't be.

---

# 189. Initial unknown registry

Forge explicitly creates:

```text id="trzq9a"
KNOWN UNKNOWNS
```

during bootstrap.

Example:

```text id="wmlfgj"
UNKNOWN-001
Telemetry source ordering guarantees.

UNKNOWN-002
Whether historical observations may be corrected.

UNKNOWN-003
Maximum expected ingestion rate.
```

Then implementation may expose **unknown unknowns**, which become Observations/Discoveries.

This gives us both sides of uncertainty.

---

# 190. V0 Finish Contract

The Forge V0 proving mission itself needs a Finish Contract.

For the target product mission, Forge must demonstrate:

```text id="epu4v6"
1. At least one meaningful feature implemented.

2. Builder candidate independently audited.

3. At least one deliberately seeded or naturally
   occurring implementation failure recovered without
   owner intervention.

4. At least one stuck condition correctly detected OR
   a deterministic test demonstrates stuck detection.

5. At least one material observation enters the
   Discovery Engine.

6. Discovery is supported/rejected through evidence,
   not merely accepted by model opinion.

7. A validated discovery can modify the Living Spec.

8. Execution graph can change because of that spec change.

9. Subsequent Builder work uses the evolved specification.

10. Completion depends on current evidence.

11. Event ledger survives restart.

12. Repository state reconciles after restart.

13. Builder cannot self-verify.

14. Protected governance cannot be modified by ordinary
    Builder authority.

15. Final report reconstructs what Forge built,
    discovered, changed and learned.
```

If we prove those 15 things, **Forge is real**.

---

# 191. First proving ground

I still recommend **Sentinel**.

Not Nucleus.

Not GridLens.

Why Sentinel works well:

```text id="etn9jo"
real product
real domain model
meaningful architecture
telemetry complexity
enough unknowns
manageable repository
easy-to-test behaviors
lower ingestion/data-source complexity than GridLens
```

Most importantly, we can recognize whether Forge's discoveries are actually intelligent.

---

# 192. Don't seed the main discovery

I would **not intentionally tell Forge what discovery to find**.

That would contaminate the experiment.

We give it the best Sentinel PRD we currently have.

Then observe whether implementation reveals something real.

We can seed **engineering failures** for deterministic testing of stuck recovery, but product discovery should preferably emerge naturally.

---

# 193. Baseline comparison

Before Forge touches Sentinel, record:

```text id="iz79he"
initial commit
initial PRD
initial architecture
initial tests
known requirements
known assumptions
```

After the mission:

```text id="q4y8a4"
final commit
final specification
new requirements
superseded requirements
discoveries
rejected discoveries
architecture changes
tests
lessons
```

Then we can actually judge what Forge contributed.

---

# 194. Human evaluation

For V0, you remain the ultimate evaluator of whether discoveries made the **product better**.

Forge can measure technical outcomes.

But "this is a materially better Sentinel" is partly a product judgment.

We'll examine:

```text id="fftxlq"
Did Forge identify something we missed?

Was it actually important?

Did the resulting architecture improve?

Would we have made the same decision?

Did Forge create unnecessary complexity?

Did it stay aligned with the North Star?
```

This is where we pressure-test the thesis.

---

# 195. V0 success metrics

I care about these:

```text id="0l8vzw"
verified requirement completion
audit pass/failure rate
successful autonomous repairs
stuck recovery quality
useful discovery rate
false discovery rate
specification improvement
repeat-error avoidance
owner intervention frequency
mission completion
cost
wall time
```

I do **not** care much about:

```text id="q8d07p"
tokens generated
commits produced
agent messages
lines of code
number of discoveries
```

Those are activity metrics.

---

# 196. Discovery precision matters more than volume

If Forge produces:

```text id="shc60v"
30 discoveries
```

and 25 are unnecessary architecture ideas, that's bad.

I'd rather see:

```text id="b3g56i"
3 discoveries
2 genuinely useful
1 correctly rejected
```

Forge should be **conservative about changing product truth** and aggressive about investigating material evidence.

---

# 197. Autonomous PR approval

For ordinary A1/A2 work:

```text id="itx8dj"
Builder
 ↓
candidate
 ↓
Auditor
 ↓
PASS
 ↓
Governor eligibility
 ↓
MERGE
```

Forge can merge without asking you every time.

Otherwise it isn't meaningfully autonomous.

Protected changes remain owner-gated.

---

# 198. Merge is not the end

This is another canonical rule:

> **A merge closes an implementation candidate. It does not close learning from that implementation.**

After merge:

```text id="r89l6g"
MERGE
 ↓
OUTCOME EVALUATION
 ↓
CUMULATIVE PATTERN ANALYSIS
 ↓
LESSON / DISCOVERY
 ↓
NEXT WORK
```

This directly captures the behavior you originally described.

---

# 199. Auditor as continuous product observer

The Auditor therefore becomes more than a code reviewer.

Its broader responsibility is:

> **Continuously compare what Forge is learning from implementation against what Forge currently believes about the product.**

That's a central architectural statement.

Builder asks:

> How do I build this?

Architect asks:

> What should we build next?

Auditor asks:

> **What is reality telling us that our current model doesn't understand yet?**

That's the role that makes Forge special.

---

# 200. Architect + Auditor tension

These roles should intentionally pull in different directions.

**Architect:**

> Move the product forward.

**Auditor:**

> Prove that forward movement is justified.

Builder sits between them:

> Make the proposed reality exist.

Governor surrounds them:

> Keep the whole process legitimate.

That's a very strong system.

---

# 201. Discovery Engine as epistemic firewall

The Discovery Engine should be thought of as an **epistemic firewall**.

It sits between:

```text id="vq8bwo"
WHAT AN AGENT THINKS IT NOTICED
             ↓
       DISCOVERY ENGINE
             ↓
WHAT THE PRODUCT IS ALLOWED TO BELIEVE
```

That framing matters.

Without it, "living PRD" becomes "LLM rewrites PRD whenever inspired."

With it, product evolution becomes evidence-governed.

---

# 202. Governor as authority firewall

Similarly:

```text id="cs68hg"
WHAT AN AGENT WANTS TO DO
             ↓
          GOVERNOR
             ↓
WHAT THE SYSTEM IS AUTHORIZED TO DO
```

Forge therefore has two critical firewalls:

```text id="zfd2qe"
GOVERNOR
Authority firewall

DISCOVERY ENGINE
Epistemic firewall
```

I would freeze those terms.

---

# 203. Auditor as reality sensor

And one more useful framing:

```text id="l6n6hl"
BUILDER
changes reality

AUDITOR
measures reality

DISCOVERY ENGINE
updates understanding

ARCHITECT
changes direction

GOVERNOR
controls authority
```

That is Forge Agent in five lines.

---

# 204. Learning Engine as experience compiler

The Learning Engine:

```text id="6i3bvn"
raw experience
      ↓
repeated evidence
      ↓
validated pattern
      ↓
reusable engineering knowledge
```

So I would describe it as an:

> **Experience compiler**

It compiles messy build history into reusable engineering knowledge.

Another term worth keeping.

---

# 205. Product Brain as evolving model

Product Brain is:

> **Forge's current evidence-backed model of what the product is, why it exists, what must be true, what remains unknown, and how current implementation relates to that understanding.**

Not a document store.

Not chat memory.

A structured evolving product model.

---

# 206. Forge intelligence model

We can now describe Forge's intelligence as four interacting capabilities:

```text id="2gnzvy"
EXECUTION INTELLIGENCE
Can we build it?

EPISTEMIC INTELLIGENCE
Do we actually know this is true?

PRODUCT INTELLIGENCE
Are we building the right thing?

EXPERIENTIAL INTELLIGENCE
What should past outcomes teach future work?
```

Governor provides the fifth dimension:

```text id="3bln8n"
GOVERNANCE
Are we authorized to do it?
```

---

# 207. Forge control model

So the complete conceptual model is:

```text id="3y0pcd"
                    OWNER INTENT
                         │
                         ▼
                     GOVERNOR
                Authority Firewall
                         │
                         ▼
                     ARCHITECT
                  Select Direction
                         │
                         ▼
                      BUILDER
                   Change Reality
                         │
                         ▼
                      AUDITOR
                   Measure Reality
                         │
                         ▼
                 DISCOVERY ENGINE
                 Epistemic Firewall
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        PRODUCT BRAIN         OUTCOME ENGINE
              │                     │
              │                     ▼
              │               LEARNING ENGINE
              │              Experience Compiler
              │                     │
              └──────────┬──────────┘
                         ▼
                     ARCHITECT
                         │
                        ...
```

This is the architecture I'd put on page one.

---

# 208. Canonical product doctrine

Freeze:

> **Forge Agent does not execute a static specification. It maintains and implements the best evidence-supported specification currently consistent with owner intent.**

And:

> **Every implementation is both a product change and an opportunity to learn whether Forge's understanding of the product is incomplete.**

And:

> **Plans are hypotheses. Code is a candidate. Tests are evidence. Audits are judgments. Discoveries are hypotheses. Outcomes create lessons. Owner intent remains authoritative.**

# 209. Canonical autonomy doctrine

Freeze:

> **Forge continues autonomously while valid, authorized, evidence-producing work remains.**

Forge does not require human prompting merely to advance from one valid engineering action to the next.

It stops only when:

```text id="p4h3fm"
Finish Contract satisfied
OR
owner authority genuinely required
OR
budget exhausted
OR
safe progress is impossible
OR
integrity cannot be established
```

Autonomy is therefore bounded by **authority and evidence**, not arbitrary turn count.

---

# 210. Canonical stuck doctrine

Freeze:

> **Repeated activity without material evidence improvement is not progress.**

When Forge stops making progress, it must not simply increase persistence.

It changes abstraction level:

```text id="vkg0m8"
implementation
     ↓
strategy
     ↓
architecture
     ↓
specification
     ↓
assumption
     ↓
owner intent / external constraint
```

Forge searches upward until it identifies the actual blocker.

Then it chooses a materially different valid path.

---

# 211. Canonical discovery doctrine

Freeze:

> **Unexpected implementation evidence is a potential source of product knowledge.**

Forge must actively capture surprises rather than treating them as noise.

But:

> **An observation is not automatically a requirement.**

Every material discovery moves through evidence and validation before modifying canonical product understanding.

---

# 212. Canonical specification doctrine

Freeze:

> **The specification is authoritative but revisable.**

It represents the best current evidence-supported understanding of how to satisfy the North Star.

Therefore requirements may be:

```text id="tdf4z3"
added
split
merged
clarified
reordered
superseded
strengthened
```

when evidence warrants it.

Specification evolution must preserve lineage.

---

# 213. Canonical evidence doctrine

Freeze:

> **Forge believes receipts over narratives.**

A statement like:

> "All tests pass."

is not sufficient.

Forge wants the test invocation, revision, result and provenance.

A statement like:

> "The architecture supports restart."

is not sufficient.

Forge wants evidence demonstrating restart behavior.

Claims become engineering truth only through appropriate evidence.

---

# 214. Canonical verification doctrine

Freeze:

> **No producer may be the sole authority certifying its own output.**

Builder produces.

Auditor independently judges.

Governor determines eligibility.

This separation applies not just to code but eventually to:

```text id="s9zq93"
skill changes
prompt changes
lessons
spec patches
architecture changes
Forge self-modifications
```

The higher the consequence, the stronger the independent evidence requirement.

---

# 215. Canonical unknown doctrine

Freeze:

> **Forge is allowed to not know.**

Valid outputs include:

```text id="hpz4bc"
UNKNOWN
INCONCLUSIVE
INSUFFICIENT_EVIDENCE
OWNER_DECISION_REQUIRED
```

This is a feature.

A system that must always produce an answer will eventually fabricate certainty.

---

# 216. Canonical learning doctrine

Freeze:

> **Experience does not become knowledge merely because it happened.**

A lesson requires evidence that the pattern is useful beyond the single event.

Forge should be willing to say:

```text id="xkkc4m"
Interesting experience.
Not enough evidence to learn from yet.
```

This protects future runs from bad memory.

---

# 217. Canonical negative-knowledge doctrine

Freeze:

> **Failed approaches are valuable when Forge understands the conditions under which they failed.**

Forge preserves:

```text id="96fzhv"
strategy attempted
context
failure
diagnosis
alternative that succeeded
scope of lesson
```

This prevents repeated dead ends.

---

# 218. Canonical simplicity doctrine

Freeze:

> **Discovery must not become an excuse for complexity.**

When multiple solutions satisfy current evidence, Forge should prefer:

```text id="0fwpt4"
fewer moving parts
clearer ownership
stronger deterministic behavior
better testability
greater reversibility
lower operational burden
```

unless evidence justifies the additional complexity.

---

# 219. Canonical scope doctrine

Freeze:

> **Forge improves the product it was asked to build; it does not endlessly invent adjacent products.**

Useful discoveries outside the mission become backlog opportunities.

They do not automatically redirect execution.

This is essential for finishing.

---

# 220. Canonical owner doctrine

Freeze:

> **Forge should minimize owner interruptions without minimizing owner authority.**

That means:

```text id="klfsc8"
don't ask Nick things Forge can determine from evidence

don't ask Nick for routine engineering preferences

don't stop all work because one decision is blocked

do ask when genuine product preference or protected
authority is required
```

And batch owner questions where possible.

---

# 221. Canonical self-improvement doctrine

Freeze:

> **Forge may improve the machinery that helps it reason and execute, but may not autonomously weaken the machinery that governs and verifies it.**

Mutable:

```text id="mzg2tm"
skills
prompts
context strategies
planning strategies
tool strategies
lesson retrieval
model routing
```

Protected:

```text id="x2f7l1"
authority
audit independence
security
event integrity
Finish Contract protections
North Star ownership
protected policy
```

---

# 222. Canonical self-hosting doctrine

Freeze:

> **Forge earning the ability to improve Forge is a maturity milestone, not a starting assumption.**

Self-hosting comes only after Forge demonstrates reliable engineering on external repositories.

That prevents us from spending six months building an agent framework whose main accomplishment is modifying its own agent framework.

---

# 223. Canonical architecture doctrine

Freeze:

> **Probabilistic intelligence proposes. Deterministic infrastructure controls. Evidence decides.**

That's probably the shortest technical description of Forge.

---

# 224. Canonical product statement

Forge Agent:

> **An autonomous, evidence-governed engineering runtime that builds software, discovers deficiencies in its own product understanding through implementation, evolves living specifications within owner intent, independently verifies its work, recovers from failure, and converts validated outcomes into better future engineering behavior.**

That should be the official long-form definition.

---

# 225. Short product statement

For README/header use:

> **Forge builds, verifies, discovers, adapts, and learns.**

---

# 226. Internal tagline

I like:

> **Build what we know. Discover what we don't.**

It captures the reason this architecture exists.

No need to turn this into a branding exercise yet, but I would keep it.

---

# 227. The core five

If we stripped Forge down to its conceptual essentials:

```text id="2v8vtc"
GOVERNOR
Controls authority.

ARCHITECT
Chooses direction.

BUILDER
Changes reality.

AUDITOR
Measures reality.

DISCOVERY ENGINE
Changes understanding.
```

Then:

```text id="p74ebx"
LEARNING ENGINE
Improves future behavior.
```

Everything else supports these functions.

---

# 228. Core data objects

V0 should have approximately these first-class objects:

```text id="y9grqu"
Mission
NorthStar
Requirement
Assumption
Invariant
Decision
FinishContract
ExecutionGraph
BuildPacket
InvestigationPacket
Candidate
Evidence
Audit
Observation
Discovery
SpecPatch
Contradiction
Outcome
Lesson
OwnerRequest
Event
```

That's enough.

Avoid inventing 100 domain objects before implementation forces us to.

---

# 229. Core relationships

```text id="uc2kxr"
NorthStar
   ↓ constrains
Requirement

Requirement
   ↓ depends on
Assumption

Requirement
   ↓ produces
BuildPacket

BuildPacket
   ↓ produces
Candidate

Candidate
   ↓ produces
Evidence

Evidence
   ↓ informs
Audit

Audit
   ↓ may produce
Observation

Observation
   ↓ may become
Discovery

Discovery
   ↓ may produce
SpecPatch

SpecPatch
   ↓ changes
Requirement

Merge
   ↓ produces
Outcome

Outcome
   ↓ informs
Lesson

Lesson
   ↓ informs
Future Architect
```

That's the fundamental Forge data graph.

---

# 230. Core runtime path

Normal happy path:

```text id="bfnhw0"
forge run
   ↓
Governor loads Mission
   ↓
Product Brain reconstructed
   ↓
Architect selects BUILD-001
   ↓
Governor authorizes
   ↓
Worktree created
   ↓
Builder implements
   ↓
Tests execute
   ↓
Candidate frozen
   ↓
Auditor independently evaluates
   ↓
PASS
   ↓
Governor checks merge eligibility
   ↓
Merge
   ↓
Outcome recorded
   ↓
Cumulative discovery check
   ↓
Finish Contract?
   ↓
NO
   ↓
Architect selects BUILD-002
```

That is V0's primary execution loop.

---

# 231. Discovery runtime path

```text id="u8lbds"
Auditor observes anomaly
   ↓
OBS-001
   ↓
Discovery Engine triage
   ↓
Material?
   ↓ YES
DISC-001
   ↓
Evidence sufficient?
   ↓ NO
INVEST-001
   ↓
Investigation evidence
   ↓
DISC-001 VALIDATED
   ↓
Authority classification
   ↓ A2
SPEC-PATCH-001
   ↓
Impact analysis
   ↓
Requirements evolve
   ↓
Execution graph recalculated
   ↓
Current future Build Packet superseded
   ↓
Architect selects new work
```

This path is equally important to the normal build path.

---

# 232. Stuck runtime path

```text id="7x57u8"
BUILD-014
   ↓
failure
   ↓
repair strategy A
   ↓
same failure
   ↓
repair strategy B
   ↓
no material evidence improvement
   ↓
STUCK
   ↓
Stuck Resolver
   ↓
minimal reproduction
   ↓
assumption A-017 contradicted
   ↓
DISC-006
   ↓
architecture change
   ↓
BUILD-014 superseded
   ↓
BUILD-014A
   ↓
PASS
```

Notice something important:

**Stuck recovery itself can create product discovery.**

That's exactly what we want.

---

# 233. Learning runtime path

```text id="8s4ozw"
BUILD-014 failure
BUILD-031 similar failure
BUILD-058 similar failure
       ↓
pattern detected
       ↓
LESSON-CANDIDATE-007
       ↓
Lesson Evaluator
       ↓
scope = SQL migration strategy
       ↓
PROMOTE
       ↓
future Architect retrieves lesson
       ↓
BUILD-074 avoids known failure
       ↓
outcome reinforces lesson
```

Now Forge is genuinely improving.

---

# 234. Owner runtime path

```text id="fbiz74"
DISC-019
   ↓
two valid product directions
   ↓
evidence cannot decide preference
   ↓
A3
   ↓
OWNER-REQUEST-003
   ↓
Forge continues unrelated work
   ↓
Nick chooses option B
   ↓
DEC-031
   ↓
Product Brain updates
   ↓
affected graph recalculated
   ↓
execution resumes
```

This is how Forge remains autonomous without pretending engineering evidence can answer every product decision.

---

# 235. Protected files

Forge itself should designate protected surfaces.

Likely:

```text id="u2q5g4"
forge/core/governor.py
forge/core/authority.py
forge/core/policies.py
forge/evidence/ledger.py
forge/evidence/reducers.py
constitution
protected schemas
```

Ordinary Forge self-builds cannot modify these without elevated workflow.

For external target repositories, their own `.forge/forge.yaml` can define protected paths.

---

# 236. Forge configuration

Example:

```yaml id="c1vp5m"
forge:
  version: 1

mission:
  autonomy: balanced

repository:
  canonical_branch: main

authority:
  autonomous_merge: true
  protected_paths:
    - infrastructure/production/**
    - .forge/north-star.md

verification:
  independent_auditor: required

discovery:
  enabled: true
  cumulative_audit_every_merges: 5

learning:
  enabled: true
  auto_promote_global_lessons: false

budgets:
  wall_time_hours: 8
```

Simple enough to understand.

---

# 237. V0 model strategy

Don't overcomplicate routing initially.

Use:

```text id="6v7bqd"
Architect       strongest reasoning/coding-capable model
Builder         strongest coding-capable model
Auditor         strongest reasoning model, fresh context
Stuck Resolver  strongest reasoning model
Lesson Eval     strongest reasoning model
```

Then optimize cost **after we have traces showing where intelligence actually matters**.

Premature cheap-model routing could make it harder to diagnose architecture failures.

---

# 238. V0 learning scope

I would deliberately constrain learning initially.

Forge V0 can create:

```text id="i0yywu"
Candidate Lessons
Repository Lessons
```

But **global automatic lesson promotion should remain disabled**.

We first learn whether the Lesson Engine itself produces high-quality knowledge.

Once trusted:

```text id="d7uqv1"
repo → domain → global
```

promotion can become governed automation.

---

# 239. V0 discovery scope

Discovery V0 should support:

```text id="5tzhnf"
requirement missing
requirement incorrect
assumption contradicted
architecture mismatch
hidden dependency
missing invariant
unnecessary planned work
```

That's enough.

We don't initially need autonomous business-model discovery, UX strategy, market research, etc.

Those can become future skills.

---

# 240. V0 autonomous merge policy

For the Sentinel proving ground:

**Yes, let Forge merge ordinary verified work.**

Otherwise we aren't actually testing autonomous engineering.

But:

```text id="sbg2px"
North Star changes
protected architecture boundaries
production deployment
secrets
destructive external operations
Forge trust-kernel changes
```

remain owner-gated.

---

# 241. V0 stuck test

We should deliberately include deterministic scenarios proving:

```text id="zj92dx"
same strategy repeatedly fails
      ↓
progress detector notices
      ↓
STUCK state entered
      ↓
Stuck Resolver receives attempt history
      ↓
materially different strategy required
```

This can be tested independently of whether Sentinel naturally causes Forge to become stuck.

---

# 242. V0 discovery test

Likewise, unit/integration tests should prove:

```text id="4n12v0"
Observation
  ↓
Discovery Candidate
  ↓
Evidence
  ↓
Validation
  ↓
Spec Patch
  ↓
Requirement version changes
  ↓
Execution graph changes
```

The Sentinel trial then tells us whether the **reasoning quality** is good, not whether the machinery works at all.

---

# 243. V0 independence test

Must prove:

```text id="80i62c"
Builder context != Auditor context

Builder cannot emit PASS receipt

candidate SHA frozen before audit

candidate modification invalidates audit

only Governor can mark merge eligible
```

This is non-negotiable.

---

# 244. V0 restart test

Simulate interruption at:

```text id="vl80zf"
during implementation
after candidate creation
after audit
before merge
after merge before state reduction
```

Forge should reconcile correctly.

Long-running autonomy is worthless if a process crash corrupts mission state.

---

# 245. V0 integrity tests

Must prove fail-closed behavior for:

```text id="2mr17j"
wrong repository
dirty canonical worktree
candidate SHA mismatch
missing evidence
invalid state transition
protected-path violation
malformed agent output
ledger inconsistency
```

These are trust-kernel tests.

---

# 246. V0 proving sequence

I recommend exactly this sequence:

```text id="35zwdg"
PHASE 1
Forge trust kernel

PHASE 2
Product Brain + Living Specification

PHASE 3
Architect → Builder → Auditor loop

PHASE 4
Repository isolation + autonomous merge

PHASE 5
Failure repair + stuck resolution

PHASE 6
Discovery Engine + spec evolution

PHASE 7
Outcome + candidate learning

PHASE 8
Restart/reconciliation

PHASE 9
Sentinel controlled trial

PHASE 10
Post-trial architecture review
```

Do not build everything simultaneously.

---

# 247. Phase 1 exit condition

Trust kernel proves:

```text id="2qetmf"
state machine deterministic
authority enforced
event ledger replayable
repository identity known
protected actions denied
invalid transitions fail closed
```

No useful coding agent yet.

That's okay.

Foundation first.

---

# 248. Phase 2 exit condition

Forge can:

```text id="e0k82g"
ingest North Star
ingest PRD
create requirements
track assumptions
version requirements
maintain Finish Contract
detect simple contradictions
```

Now it understands what it's supposed to build.

---

# 249. Phase 3 exit condition

One Build Packet can go:

```text id="0bnm2d"
Architect
→ Builder
→ candidate
→ tests
→ independent Auditor
→ PASS
```

No autonomous continuation yet required.

---

# 250. Phase 4 exit condition

Forge can:

```text id="gq15z0"
create isolated candidate
freeze SHA
audit exact candidate
determine merge eligibility
merge
reconcile canonical repository
select next Build Packet
```

At this point Forge becomes an **autonomous builder**.

---

# 251. Phase 5 exit condition

Forge can:

```text id="ny0sl5"
detect failure
repair
measure progress
detect repeated non-progress
enter STUCK
generate materially different strategy
resume
```

At this point Forge becomes **stuck-resistant**.

---

# 252. Phase 6 exit condition

Forge can:

```text id="j1h3eu"
capture observation
form discovery
gather evidence
validate/reject
patch specification
version requirement
recalculate graph
redirect Builder
```

At this point Forge becomes the system you originally described.

**It can learn what the product needs while building it.**

---

# 253. Phase 7 exit condition

Forge can:

```text id="w4q9h8"
connect discovery → change → build → outcome

create candidate lesson

validate/reject repository-level lesson

retrieve relevant validated lesson later
```

At this point Forge becomes **self-improving across engineering work**.

---

# 254. Phase 8 exit condition

Kill Forge mid-mission.

Restart it.

It:

```text
reconstructs state
inspects repository reality
detects the incomplete action
reconciles the last durable event
marks ambiguous external effects UNKNOWN
refuses blind replay
resumes from the highest valid checkpoint
```

Phase 8 exits only when restart behavior is deterministic, incomplete actions are recoverable or explicitly escalated, and no restart path can silently duplicate a merge, weaken authority, or lose a receipt.

---

# 255. Phase 9 — Sentinel proving ground

Forge is not ready for broad production use after the trust kernel and core loop alone. It needs a deliberately small proving ground.

The proving ground must be:

```text
small enough to understand
real enough to expose engineering ambiguity
safe enough to reset
rich enough to create genuine discoveries
```

The Sentinel repository should contain a modest product with:

- a living specification;
- intentional but recoverable requirements gaps;
- deterministic tests;
- a few bounded integrations;
- protected paths;
- a Finish Contract;
- seeded failure scenarios;
- no production credentials or irreversible external side effects.

Forge must complete ordinary verified work, recover from at least one seeded failure, surface at least one material discovery, validate or reject that discovery, and continue after a governed specification change.

---

# 256. Phase 9 acceptance evidence

The proving ground produces a release packet containing:

```text
mission snapshot
repository identity
initial specification hash
execution graph
build packets
candidate SHAs
test receipts
audit receipts
repair history
discovery records
specification patch history
restart receipts
merge receipts
outcome evaluation
lesson candidates
Finish Contract evaluation
```

A green test run by itself is insufficient. The packet must show that Forge maintained authority boundaries and produced a causally coherent history.

---

# 257. Phase 10 — controlled external repository trial

Only after the Sentinel packet satisfies its gates may Forge operate on a carefully selected external repository.

The trial repository must be:

- owner-controlled;
- recoverable from version control;
- free of production secrets;
- bounded in scope;
- equipped with a measurable Finish Contract;
- configured with explicit protected paths;
- safe for autonomous ordinary merges if the owner authorizes that policy.

The first external trial is an engineering experiment, not a claim of general autonomy.

---

# 258. Phase 10 exit condition

Phase 10 exits when Forge completes a bounded external objective with:

- no unauthorized scope expansion;
- no protected-path violation;
- independent audit evidence;
- reproducible candidate identity;
- correct restart behavior;
- accurate UNKNOWN handling;
- at least one independently verified outcome;
- a reviewable final evidence packet.

Any unresolved integrity contradiction blocks advancement.

---

# 259. What V0 deliberately excludes

V0 does not include:

```text
vector database
complex embeddings pipeline
agent swarm
multi-provider orchestration
automatic cloud deployment
production environment writes
full browser automation
voice interface
mobile app
visual workflow builder
marketplace
plugin ecosystem
automatic model training
distributed memory
complex reinforcement learning
self-modification of protected governance
```

If one becomes necessary to prove the V0 thesis, add the smallest governed capability required. Otherwise it remains outside V0.

---

# 260. V0 technology stack

The recommended initial stack is:

```text
Python 3.12+
Typer
Pydantic
SQLite
thin persistence layer
subprocess-based Git adapter
provider abstraction
pytest
YAML configuration
JSON/Pydantic structured receipts
stdlib structured logging
```

The architecture belongs to Forge; no framework is allowed to become the architecture by accident.

---

# 261. V0 process architecture

One local Forge process is sufficient for V0.

```text
Governor
State machine
Event ledger
Product Brain
Context engine
Model router
Tool runtime
Repository adapter
```

The process may call model APIs, Git, the filesystem, and deterministic validation commands. Multi-process coordination is deferred until evidence requires it.

---

# 262. V0 model strategy

Use a simple role-based route initially:

```text
Architect       strongest reasoning/coding-capable model
Builder         strongest coding-capable model
Auditor         strong reasoning model with fresh context
Stuck Resolver  strong reasoning model
Lesson Evaluator strong reasoning model
```

Optimize cost only after traces show where intelligence is actually needed. Routing changes remain policy changes with receipts.

---

# 263. V0 learning boundary

V0 may create candidate repository lessons and validated repository-scoped lessons.

Global automatic promotion is disabled.

Promotion follows:

```text
repository → domain → global
```

only after separately governed validation. A lesson may never weaken authority, verification independence, security, event integrity, the Finish Contract, or North Star ownership.

---

# 264. V0 discovery boundary

V0 supports discovery candidates for:

```text
missing requirement
incorrect requirement
contradicted assumption
architecture mismatch
hidden dependency
missing invariant
unnecessary planned work
```

It does not autonomously invent adjacent business products, market strategy, or owner preferences.

---

# 265. V0 autonomous merge policy

On the Sentinel proving ground, Forge may merge ordinary verified work when policy permits it.

The following remain owner-gated:

```text
North Star changes
protected architecture boundaries
production deployment
secrets
destructive external operations
Forge trust-kernel changes
```

A merge receipt must identify the exact candidate, audit result, policy decision, and resulting revision.

---

# 266. V0 deterministic test matrix

V0 must prove at least:

```text
same strategy repeatedly fails → STUCK_RESOLUTION
observation → discovery candidate → evidence → validation → spec patch
builder context differs from auditor context
builder cannot emit a valid PASS receipt
candidate mutation invalidates prior audit
only Governor can mark merge eligible
restart at each critical interruption point
wrong repository fails closed
dirty canonical worktree fails closed
candidate SHA mismatch fails closed
missing evidence fails closed
invalid transition fails closed
protected-path violation fails closed
malformed model output fails closed
ledger inconsistency fails closed
```

These are acceptance tests for the architecture, not optional polish.

---

# 267. V0 proving sequence

Run the proving sequence in this order:

```text
Phase 1  trust kernel
Phase 2  Product Brain and Living Specification
Phase 3  Architect → Builder → Auditor loop
Phase 4  Evidence Ledger and replay
Phase 5  Discovery and governed specification evolution
Phase 6  Stuck Resolver and bounded recovery
Phase 7  Outcome and Lesson Engines
Phase 8  restart and interruption proving
Phase 9  Sentinel proving ground
Phase 10 controlled external repository trial
```

Do not skip directly to long-running autonomy because a single happy-path build passed.

---

# 268. Canonical invariants

The following invariants are frozen for v1:

1. Owner intent and North Star remain authoritative.
2. Lower layers may challenge higher layers but cannot silently mutate them.
3. Every meaningful state transition produces a durable receipt.
4. Candidate identity is exact and immutable for audit.
5. A builder cannot certify its own output.
6. Audit context is independent of builder context.
7. Only the Governor can authorize effects and merge eligibility.
8. Missing or ambiguous evidence remains UNKNOWN.
9. Protected paths require elevated authority.
10. Retries must change strategy when evidence is not improving.
11. Discovery is a hypothesis until validated.
12. Specification evolution preserves lineage.
13. Lessons require evidence, scope, attribution, and validation.
14. Negative knowledge is retained.
15. External side effects are explicit and policy-controlled.
16. Restart must not duplicate effects or lose history.
17. Finish requires evidence, not task exhaustion.
18. Simplicity and reversibility are preferred when evidence is equal.
19. Self-improvement may not weaken governance.
20. V0 is intentionally narrow.

---

# 269. Canonical finish contract

Forge Agent Canonical Architecture v1 is complete as an architecture artifact when:

```text
all numbered sections are present
the continuation from Section 254 is complete
the Governor, authority model, state machine, Product Brain,
Architect, Builder, Auditor, Discovery Engine, Evidence Ledger,
Stuck Resolver, Outcome Engine, Lesson Engine, contradiction handling,
restart behavior, proving sequence, V0 boundaries, and invariants
are specified
the architecture has a coherent numbered requirement set
the PRD is derived without adding unauthorized product intent
the two artifacts pass structural validation
```

This contract defines artifact completion. It does not authorize implementation.

---

# 270. Final architecture decision

Build Forge Agent as a separate, local-first, evidence-governed engineering runtime.

Build only the V0 proving sequence first.

Preserve the following as canonical:

```text
Stable Intent
→ Living Specification
→ Adaptive Execution
→ Evidence
→ Discovery
→ Better Specification
→ Validated Learning
```

The final decision is:

```text
PROCEED WITH ARCHITECTURE AND PRD
DO NOT START IMPLEMENTATION IN THIS ARTIFACT
```

Forge Agent is not a collection of agents prompting one another.

It is a governed engineering operating system in which probabilistic intelligence proposes, deterministic infrastructure controls, and evidence decides.
