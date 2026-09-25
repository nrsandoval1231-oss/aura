# Aura product requirements — v1

Owner: Nick Sandoval
Status: Build specification; live acceptance pending
Product: Autonomous engineering agent controlled through a CLI and persistent local or cloud runtime

## Objective and first user experience

Aura turns a plain-language engineering objective into a reviewable change in a named Git repository. Nick talks primarily to Sol. Aura plans bounded work, assigns independent slices to DeepSeek and Luna, checks and integrates results under deterministic authority, and learns from independently reviewed outcomes. Nick can disconnect and later inspect what happened without Aura repeating an uncertain effect.

The first useful release accepts one small issue in a disposable repository and returns a tested, independently reviewed candidate with evidence and a concise account of changes, blockers, and cost. Later milestones add persistent cloud operation, two builders, and measured learning. Existing offline tests do not establish live readiness.

## Operator contract

These are **target commands**, not commands that work today. Keep their semantics stable; spelling changes need an explicit reviewed CLI contract change.

```bash
aura init /projects/my-app
aura build "Add customer login and account settings" --repo /projects/my-app
aura status
aura inspect <run-id>
aura pause <run-id>
aura resume <run-id>
```

`init` checks the repository, base, policy, and credentials without initiating a paid effect. `build` records an objective, frozen base, authority and budget, returns a run ID, and hands execution to the persistent runtime. `status` shows run and lane states, current slices, blockers, spend and next controlled action. `inspect` exposes evidence, checks, reviews, changes and event history. `pause` stops *new dispatch* at a safe boundary, leaving in-flight effects pending or UNKNOWN until reconciled. `resume` reloads durable state and reconciles before more work. The CLI uses a trusted runtime on the same machine first. For cloud operation Nick connects to that machine through an authenticated channel. A browser dashboard and public control API can wait.

## Roles and boundaries

| Role | Assignment | Boundary |
| --- | --- | --- |
| Lead | Sol | Decomposes, agrees interfaces, allocates, integrates, replans; cannot grant itself authority |
| Builder A | DeepSeek V4.1 Flash, intended label | Bounded coding and repairs in its own worktree |
| Builder B | Luna 6 | Independent bounded coding and repairs in its own worktree |
| Utility | MiniMax | Bounded support; cannot approve candidates or lessons |
| Auditor | Astra | Fresh independent review of exact candidates and lesson evidence |
| Governor | Deterministic software | State, dependencies, scope, budgets, effects and integration eligibility |

Provider IDs and credentials require verification before activation. The inherited cross-family audit rule conflicts with Luna/Astra; that route remains blocked until an explicit owner-approved reconciliation. No fallback may impersonate a role. Existing `forge` imports and CLI remain for compatibility while `aura` is introduced as the user command.

## Requirements

### Intake and repository

1. Aura SHALL accept a named local Git repository and plain-language objective, retain the owner's original words, and return a stable run ID.
2. Intake SHALL identify remote, branch, worktree cleanliness, exact base commit and tree, and reject ambiguous repository states before dispatch.
3. Sol SHALL produce bounded slices with dependencies, agreed interfaces, allowed paths, exclusions, invariants, acceptance checks and completion criteria.
4. The plan SHALL surface material owner decisions and otherwise proceed only within granted run authority and budget.
5. Material discovery that changes requirements SHALL retain specification lineage and obtain applicable authority before revised work.

### CLI and persistence

6. `init`, `build`, `status`, `inspect`, `pause` and `resume` SHALL offer concise human-readable and stable machine-readable output with run and event IDs.
7. Before the first billable or mutating effect, `build` SHALL display frozen repository, objective, authority and spend ceiling; absent authority fails closed.
8. Status SHALL distinguish READY, RUNNING, WAITING_REVIEW, BLOCKED, PAUSED, RECONCILING, FAILED, COMPLETE and UNKNOWN without calling an unreviewed candidate complete.
9. Inspect SHALL show slice base and candidate, checks, review, integration verdicts, failures, lesson applications and usage/cost receipts; absent values are UNKNOWN.
10. Pause SHALL prevent new dispatch without deleting evidence or assuming cancellation of an in-flight effect.
11. Resume SHALL reconstruct state from durable records, reconcile interruptions, and refuse duplicate effects while their prior outcomes are uncertain.
12. A long-running runtime SHALL survive CLI disconnection and process restart; status and inspect SHALL not depend on the original CLI process's memory.
13. SQLite MAY serve as a rebuildable query projection, but the append-only event ledger and independently verifiable checkpoint SHALL remain authoritative.

### Governed execution

14. The Governor SHALL enforce transitions, repository identity, write scope, dependency readiness, time/token/cost/attempt ceilings and effect authorization before worker or tool invocation.
15. Each builder SHALL have a separate worktree, frozen base, task packet, context, candidate identity and attempt budget; builder reasoning SHALL not enter audit context.
16. Slices MAY run concurrently only when Sol declares independent outcomes and the Governor verifies dependencies and nonconflicting integration plans; different file paths alone are insufficient.
17. The runtime SHALL treat worker output as an untrusted proposal, apply only authorized changes, rerun required deterministic checks and retain exact candidate receipts.
18. Astra SHALL audit the exact candidate with independent context. Builders and MiniMax SHALL not approve their own candidate, audit or lesson.
19. Integration SHALL serialize conflicts, rebase or regenerate against the current integration base when needed, and rerun checks and review on the combined candidate.
20. Mutation of a candidate, base, required checks or governance SHALL invalidate prior verification or audit for that candidate.
21. Protected governance, secrets, trust anchors, destructive actions, deployment, publication and external communication SHALL retain explicit owner authority separate from test success or model advice.

### Stuck recovery and restart

22. The runtime SHALL record actual attempts and detect repeated patch fingerprints, recurring failing checks, lack of progress and exhausted budgets, including out-of-policy attempts.
23. The Governor SHALL enforce recovery advice *before* another effect: at most two materially different bounded repairs, then Sol replanning.
24. Recovery SHALL distinguish coding defects, environment faults, missing access, missing evidence and owner intent/authority questions, routing each appropriately.
25. Interrupted or ambiguous model, tool, Git or remote effects SHALL remain UNKNOWN pending reconciliation; a timeout is not proof of failure or permission to retry.

### Reviewed learning

26. Each slice SHALL record intended and actual strategy, exact candidate, required checks, quality outcome, named directional metric, and cost/latency when known.
27. A lesson SHALL trace to a real observed outcome and receive authenticated independent review before retrieval by either builder.
28. Both builder lanes SHALL share validated project-scoped lessons at slice boundaries; active slices SHALL keep immutable lesson/context/check snapshots.
29. Application SHALL record retrieval, changed strategy, candidate, later outcome and baseline; incompatible context, checks or metrics SHALL yield UNKNOWN.
30. Quality SHALL be a guardrail before repair count, latency, cost or owner interruptions can count as improvement.
31. Harmful lessons SHALL be withdrawn from future retrieval without erasing historical applications or negative evidence.
32. Changes to routing, budget, prompt or decomposition policy SHALL require separately governed challenger and holdout trials before promotion.
33. The slice-30 objective SHALL be measured on comparable tasks or held-out evaluations; 30 unrelated slices SHALL not be reported as statistical or model-weight improvement.

### Routing, trust and observation

34. Production activation SHALL verify provider IDs, wire formats, credentials and bounded calls for Sol, DeepSeek, Luna, MiniMax and Astra; missing configuration stops the affected route.
35. The Luna/Astra audit policy conflict SHALL be resolved explicitly by review of context separation, evidence, candidate binding and reviewer identity before pairing them.
36. Review receipts SHALL bind repository, run, exact candidate, evidence and pinned reviewer trust; caller-supplied keys or author labels confer no authority.
37. Credentials, signing keys and trust roots SHALL remain outside builder worktrees and model context; logs, errors and receipts SHALL avoid secrets.
38. The operator SHALL see activity, spend and remaining budget, check failures, blocking decisions and next action without reading ledger JSON.

### Milestones and acceptance

39. **M0, runnable foundation:** install package, expose `aura`, reconcile role and audit policy, provision production review trust, run the local gate, and exercise CLI state transitions offline without paid effects.
40. **M1, one real task:** execute one bounded builder slice for a small disposable-repository issue, run tests, get independent exact-candidate audit and leave a reviewable change without unauthorized merge or deployment.
41. **M2, persistent cloud operation:** disconnect and restart during a run, reconnect to the same run, pause/resume safely and reconcile a deliberately interrupted effect.
42. **M3, two lanes:** run two independent slices concurrently in separate worktrees, keep a dependent or conflicting slice queued, and verify the integrated combined candidate.
43. **M4, recovery and learning:** force repeated failures, show two materially distinct repairs and Sol replanning, then review a lesson that changes a later comparable strategy and outcome; withdraw a harmful lesson.
44. Completion SHALL require local deterministic validation, independent audit of the exact integrated candidate, local/remote/runtime reconciliation and the live finish contract; offline proofs alone SHALL not satisfy it.

## Delivery decisions

Start with one trusted Python runtime and one repository. Reuse the ledger, Governor contracts, context isolation, stuck detector and learning controller. Add SQLite only as a projection if ledger replay and simple files prove cumbersome; do not create a second authority. Implement the six CLI operations over a narrow local control channel. Add separate worktrees and the second builder after M1 is observed end to end. Move the process to a cloud machine after restart and secret handling are proved, accessed through an authenticated connection rather than a public service in v1.

A first-task acceptance packet must retain original objective, frozen base, approved budget, changed files, test output, independent audit receipt, final candidate, effect/restart history and a plain-language result. Missing evidence stays UNKNOWN and blocks the corresponding completion claim.
