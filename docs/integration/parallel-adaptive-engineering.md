# Parallel adaptive engineering — owner direction, 2026-09-25

## Product objective

Build our own agent on the Forge codebase. Hermes remains the owner's existing
tool and a reference. This work does not fork Hermes. Later engineering slices
must be able to use attributable, reviewed knowledge from earlier slices.
More slices do not by themselves prove better capability or statistical significance.

## Approved role structure

| Role | Assignment | Responsibility |
| --- | --- | --- |
| Engineering Lead | Sol | Intent, architecture, decomposition, shared contracts, replanning |
| Builder lane A | DeepSeek V4.1 Flash | Bounded implementation and repair |
| Builder lane B | Luna 6 | Second independent bounded implementation and repair |
| Independent Auditor | Astra, fresh session per candidate | Candidate verification, discovery and lesson review |
| Utility worker | MiniMax | Evidence extraction, research, summaries and candidate lesson preparation |
| Governor | Deterministic code | Scheduling, scope, budget, state and integration eligibility |

These are owner-selected role labels. Exact provider model IDs and credentials
remain deployment configuration; they have not been verified or activated by this
packet. Existing provider routing is unchanged. The existing cross-family audit
rule needs a separate explicit reconciliation before an OpenAI Luna/Astra runtime
path can operate; never silently bypass that rule.

## Two execution loops, one shared experience history

1. Sol divides work into independently verifiable slices with shared interfaces
   agreed before dispatch. A different path is not sufficient proof of independence.
2. The Governor assigns distinct worktrees, write scopes, dependencies and budgets.
3. Each lane starts a slice against a frozen specification, context protocol and
   snapshot of applicable validated lessons. The snapshot digest is retained.
4. Builders execute their own inspect/edit/test loops. Required checks are fixed
   at slice start; omitting a check produces UNKNOWN, never green.
5. Astra reviews each exact candidate independently. Passing local checks does not
   mean the build has passed independent audit or become merge eligible.
6. The integration gate checks the combined candidate. A merge conflict, changed
   base or integration repair requires validation bound to the resulting candidate.
7. Accepted lessons become available at the next slice boundary in either lane.
   Active snapshots do not mutate when the other lane learns something.

## Stuck resolution

The controller reuses `StuckDetector`: normalized patch fingerprints, declared
strategy rung/mechanism, failing check sets and at most two material repairs.
The abstraction ladder is local edit, mechanism, interface, design, then intent.

`recovery_plan(packet_id, proposed_strategy)` is called before another repair:

| Action | Runtime response |
| --- | --- |
| BUILD | First authorized attempt; Governor still checks all permissions |
| REPAIR | A bounded, materially different strategy remains |
| ESCALATE | Return to Sol for a different higher-rung approach |
| REPLAN | Reload intent, requirements, relevant decisions and failed approaches; revise packet |
| RECONCILE | Recover missing test/effect evidence before continuing |
| AUDIT | Local checks passed; send exact candidate to independent audit |
| OWNER | Resolve an actual intent/authority question; other authorized work may continue |

`attempt_recorded` captures what actually happened, even if a caller ignored the
advice. Historical evidence must not disappear to make the process look compliant.
The controller itself never invokes a paid model, repeats a tool effect or grants
scope. Live-runtime enforcement of the returned action is an integration obligation.

## Athena adaptation

Reviewed sources: Athena commit `f630acec86f1ff4aa03c0307fc77bd66a3f6bdc5`:
`src/athena_arena/evaluation.py`, `contracts.py`, `evolution.py`,
`docs/ATHENA_DOMAIN_BOUNDARY.md`, `docs/ATHENA_CONSTRAINTS_V1.md`.

The engineering adapter ports the directional comparison from `compare_vectors`:
delta = observed - baseline; improvement requires delta times metric direction > 0.
Engineering metric directions are explicit, avoiding a trading-specific name map.
Missing/incompatible evidence stays UNKNOWN. Faster failure is HARMED, not better.

The implemented scoped learning chain is:

    outcome -> candidate lesson -> authenticated independent review
      -> future-slice retrieval -> changed strategy -> later outcome
      -> attributable comparison -> retain or demote

MiniMax can assemble candidate lessons, but its summary cannot validate them.
Sol can propose a changed strategy. Astra must inspect the bound evidence before
the trusted runtime signs or accepts a review. Author labels alone do not suffice.

This packet reuses Forge's `LessonStore`; it does not create a competing truth
store. It adds durable replay and per-lane boundaries through the existing core
`LedgerStore`, plus a narrow Athena comparison adapter. It does not import the
complete Athena Arena/GenerationRunner/Gauntlet or its trading trial parameters.

### Two speeds of learning

- **Scoped verified lessons:** repository facts, diagnosed failures and tested
  tactics may inform later slices after independent review, with provenance.
- **General policy evolution:** model routing, budget allocation, decomposition
  or prompt policies need controlled challenger/incumbent trials. Athena's evidence
  and holdout rules apply. A single successful slice is not policy-promotion proof.

The current Athena constraints set minimum comparable-pair counts for statistical
claims and promotion. Thirty different slices are not 30 interchangeable samples,
and this controller never emits an Athena `ValidatedExperience` or grants execution
authority based on its descriptive comparison. Full policy evolution remains a
separate integration milestone, not something this implementation claims to finish.

## Runtime API and evidence

`forge.slice_learning.SliceLearning` is a trusted-runtime API. Instantiate it with
the repository digest, ledger directory, pinned review-policy identity, and a
deterministic detached-signature verifier. No permissive default is provided.
The verifier must inspect signatures against an owner-pinned anchor, not accept
keys or an `approved` flag supplied by a model.

Events accepted by `command(stable_id, event, payload, proof=...)`:

| Event | Use |
| --- | --- |
| slice_started | Pin required checks, baseline strategy, comparison context and applicable lessons |
| attempt_recorded | Retain actual candidate, patch, strategy and check evidence; assess stuck state |
| lesson_applied | Bind a retrieved lesson to the actual strategy and candidate |
| outcome_recorded | Close this observed slice and retain the named metric and quality result |
| lesson_proposed | Create an immutable candidate from one attributable source outcome |
| lesson_reviewed | Validate or reject with authenticated review bound to candidate and baseline |
| lesson_measured | Independently attest the comparison against a later outcome; demote harm |

An outcome closes a learning observation; it does not merge or certify the build.
Every event uses an idempotency key. Conflicting reuse is refused. Writer locks
serialize both lanes and separate coordinator instances. Each operation reloads
and verifies the receipt chain, so restarts restore the same projection. Partial
ledger writes remain explicit reconciliation cases; reads do not repin history.
Ledger storage must remain outside builder write scope. Advisory locks and hashes
do not defend against a process that can arbitrarily rewrite the trust store.

Context keys must name a preregistered task class and test/evaluation protocol.
They cannot be invented after observing a desired result. Equality is necessary,
but the independent reviewer must still establish comparability and attribution.

## What evolution should look like over 30 slices

- Early slices accumulate facts, failures, baselines and candidate tactics.
- Later matching slices retrieve reviewed lessons; both builders can benefit.
- Each application records the baseline and actual strategy, exact candidate and
  measured result. Irrelevant lessons are excluded; harmful ones stop new retrieval.
- Progress reports show evidence-linked changes, unchanged results and UNKNOWNs.
- Compare matched tasks or independently held-out evaluations, with quality first,
  then repair count, accepted-result latency, cost and owner interruptions.

"Slice 30 is significantly evolved" is a target to evaluate. The current offline
30-slice test proves the propagation mechanism and persistence, not improvement
in a deployed agent, learned model weights or statistical significance.

## Delivery boundary

This is an additive controller-library implementation, not a complete live agent.
Still required: wire these boundaries into the new live two-builder runner;
authenticate production review receipts; measure real recovery and learning;
complete model routing and integration validation; integrate full Arena/Gauntlet
policy trials if broader adaptation is desired. Reusable recovery and scoped
learning are implemented here so those integrations have one concrete contract.

Independent review and the full repository gate are required before activation.
No hosted or self-hosted GitHub validation runner is introduced.
