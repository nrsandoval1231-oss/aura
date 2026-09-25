# Forge Agent V0 Product Requirements Document

**Status:** Derived from the canonical Forge Agent architecture
**Scope:** Architecture and product definition only; this document does not authorize implementation.
**Maximum requirements:** 40

## Product purpose

Forge Agent is a local-first, evidence-governed engineering runtime. It turns owner intent into bounded engineering work, executes that work, independently verifies candidates, captures implementation discoveries, evolves its living specification within authority limits, recovers from failure, and retains validated lessons.

## V0 requirements

1. Forge SHALL preserve owner intent and the North Star as the highest product authority.
2. Forge SHALL represent the product as a living specification with versioned requirements, assumptions, decisions, invariants, and a Finish Contract.
3. Forge SHALL preserve lineage whenever a requirement, assumption, decision, or architecture record changes.
4. Forge SHALL use a deterministic Governor to control state, authority, scope, budgets, retries, tools, escalation, and completion eligibility.
5. Forge SHALL reject unauthorized state transitions.
6. Forge SHALL implement the canonical lifecycle from initialization through understanding, planning, implementation, testing, auditing, merging, outcome evaluation, learning, reconciliation, and finish evaluation.
7. Forge SHALL produce a durable receipt for every meaningful state transition.
8. Forge SHALL maintain an append-only evidence ledger with provenance for runs, builds, commits, diffs, tests, failures, repairs, audits, discoveries, specification changes, decisions, merges, outcomes, and lessons.
9. Forge SHALL identify the exact repository, branch or revision, candidate revision, and relevant worktree for each execution.
10. Forge SHALL fail closed when repository identity, candidate identity, or required provenance cannot be established.
11. Forge SHALL distinguish autonomous action, governed specification evolution, and owner-gated action using explicit authority levels.
12. Forge SHALL permit autonomous routine implementation, testing, refactoring, documentation, bounded dependency changes, and sequencing only within authorized scope.
13. Forge SHALL require a Discovery Record, supporting evidence, rationale, and impact analysis for governed specification evolution.
14. Forge SHALL require owner authority for changes to product purpose, target customer, protected governance, security boundaries, destructive external actions, fundamental scope, or unresolved preference tradeoffs.
15. Forge SHALL allow probabilistic components to propose actions but SHALL reserve authorization and effect control for deterministic infrastructure.
16. Forge SHALL create bounded Build Packets containing objective, requirements, dependencies, allowed paths, exclusions, acceptance criteria, evidence requirements, authority, budgets, and retry limits.
17. Forge SHALL prevent a Builder from expanding its packet, weakening governance, grading itself, changing the North Star, or declaring completion.
18. Forge SHALL freeze a candidate identity before independent audit.
19. Forge SHALL use an Auditor with context independent from the Builder.
20. Forge SHALL prevent a Builder from emitting a valid PASS receipt for its own candidate.
21. Forge SHALL classify implementation results as PASS, FAIL, or UNKNOWN.
22. Forge SHALL classify discovery results as NONE, OBSERVATION, or MATERIAL DISCOVERY.
23. Forge SHALL preserve UNKNOWN, INCONCLUSIVE, INSUFFICIENT_EVIDENCE, and OWNER_DECISION_REQUIRED instead of fabricating certainty.
24. Forge SHALL invalidate an audit when the audited candidate changes.
25. Forge SHALL allow only the Governor to mark a candidate merge-eligible.
26. Forge SHALL support ordinary autonomous merges on the Sentinel proving ground when explicit policy permits them.
27. Forge SHALL keep North Star changes, protected architecture boundaries, production deployment, secrets, destructive external operations, and trust-kernel changes owner-gated.
28. Forge SHALL capture implementation anomalies as observations before treating them as discoveries.
29. Forge SHALL require evidence and validation before a discovery can change the living specification.
30. Forge SHALL support discovery categories for missing or incorrect requirements, contradicted assumptions, architecture mismatches, hidden dependencies, missing invariants, and unnecessary planned work.
31. Forge SHALL recalculate affected dependencies and execution order after an accepted specification patch.
32. Forge SHALL detect repeated attempts that do not materially change strategy or improve evidence.
33. Forge SHALL enter a stuck-resolution state when progress is not occurring.
34. Forge SHALL require a materially different strategy after bounded repair attempts fail to improve evidence.
35. Forge SHALL retain failure conditions, diagnoses, attempted strategies, and useful negative knowledge.
36. Forge SHALL evaluate outcomes after accepted changes and classify them as CONFIRMED, PARTIALLY_CONFIRMED, DISPROVED, or INCONCLUSIVE.
37. Forge SHALL create candidate lessons only from attributable evidence and SHALL validate lessons before promotion.
38. Forge SHALL keep automatic global lesson promotion disabled in V0; repository-scoped lessons are the maximum default promotion scope.
39. Forge SHALL reconcile interrupted runs without duplicating effects, losing receipts, bypassing policy, or blindly replaying ambiguous external actions.
40. Forge SHALL declare the V0 objective complete only when the Finish Contract is satisfied with evidence, critical contradictions are resolved, critical discoveries are resolved or governed, independent verification is complete, and the final evidence packet is reviewable.

## V0 proving sequence

V0 SHALL be proven in this order:

1. trust kernel;
2. Product Brain and Living Specification;
3. Architect–Builder–Auditor loop;
4. evidence ledger and replay;
5. discovery and governed specification evolution;
6. stuck resolution and bounded recovery;
7. outcome and lesson engines;
8. restart and interruption proving;
9. Sentinel proving ground;
10. controlled external repository trial.

## V0 technology and deployment boundary

V0 is local-first and may use one local Forge process, Python 3.12+, Typer, Pydantic, SQLite, a thin persistence layer, a subprocess-based Git adapter, a model-provider abstraction, pytest, YAML configuration, structured JSON receipts, and standard-library logging.

V0 SHALL NOT require a vector database, agent swarm, complex embeddings, automatic cloud deployment, production writes, full browser automation, voice, mobile, a visual workflow builder, a marketplace, automatic model training, distributed memory, complex reinforcement learning, or autonomous weakening of protected governance.

## V0 acceptance evidence

The Sentinel release packet SHALL include mission snapshot, repository identity, specification hash, execution graph, Build Packets, candidate revisions, test receipts, audit receipts, repair history, discovery records, specification lineage, restart receipts, merge receipts, outcome evaluation, lesson candidates, and Finish Contract evaluation.

The V0 PRD and architecture are definition artifacts only. No requirement in this PRD authorizes implementation, deployment, external communication, spending, or destructive action.
