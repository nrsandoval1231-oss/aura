# Repository Finish Contract

The Forge Agent repository is not complete because files exist or tests are green.

## V0 completion requires

- every active V0 requirement has candidate-bound evidence;
- the Governor enforces state, scope, authority, budgets, and valid transitions;
- builder and auditor authority are separated;
- candidate mutation invalidates audit;
- append-only receipts support deterministic replay;
- interrupted actions reconcile without duplicate effects;
- UNKNOWN blocks unsafe continuation;
- discovery can validate or reject specification changes with lineage;
- stuck resolution requires materially different strategies;
- outcome and lesson records are attributable and scoped;
- self-improvement is demonstrated by a validated lesson changing a later
  engineering decision and improving a named outcome, with demotion or rollback
  available when the lesson is harmful;
- the Sentinel proving ground produces a reviewable evidence packet;
- a controlled external repository trial satisfies its bounded objective;
- critical contradictions and discoveries are resolved or owner-governed;
- independent strategic audit returns a completion-candidate verdict;
- local, remote, and any runtime state are separately reconciled.

The self-improvement obligation is governed by
[docs/self-improvement-acceptance.md](self-improvement-acceptance.md). Storing
lessons or prompts is insufficient: a later bounded build must provide the
retrieval, changed-decision, metric, attribution, and rollback evidence.

These obligations incorporate the canonical architecture's proving-ground thesis and test matrix, especially Sections 180, 190, 241–245, 255–258, and 266. Completion therefore requires demonstrated failure recovery, observation-to-discovery processing, governed specification evolution, and subsequent execution that uses the evolved specification; producing a packet alone is insufficient.

## Repository-foundation checkpoint

The foundation checkpoint passes when canonical documents, governance, graph state, ADRs, validation surfaces, exact Git identity, independent review, remote synchronization, and a clean worktree are proven. This checkpoint does not complete V0.
