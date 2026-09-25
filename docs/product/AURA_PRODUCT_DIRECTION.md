# Aura product direction

Owner: Nick Sandoval. This document records the decisions supplied for the Aura
implementation. It does not grant provider spending, merge, or deployment authority.

## Accepted product decisions

- Aura is Nick's separate autonomous engineering agent. Forge is its source
  lineage; Hermes is a reference. Continue the imported Forge foundation rather
  than forking Hermes or restarting from zero.
- Build a complete governed engineering loop before a UI, more roles, or extra
  infrastructure. Keep operation simple for the owner.
- Sol leads architecture, decomposition, allocation, integration, recovery, and
  replanning. A deterministic Governor owns authority, scope, budgets,
  transitions, scheduling, and integration eligibility.
- Run two independent builder loops when work is ready and disjoint. The
  intended builders are DeepSeek V4.1 Flash and Luna 6. Each gets a separate
  worktree, packet, context, candidate identity, and execution state. Serialize
  dependencies, conflicting files, and integration.
- MiniMax handles bounded support. Astra reviews independently with separate
  context. A builder cannot certify its own candidate.
- Detect repeated patches, recurring failures, and stalled progress. Require a
  materially different bounded repair, then return to Sol for replanning when
  the repair budget is exhausted. Classify credentials, dependencies,
  environment, and owner decisions separately from implementation defects.
- Use verified experience while coding: Intent → Plan → Implement → Verify →
  Learn → Update → Continue. Share accepted lessons at later slice boundaries;
  active slices keep their pinned instructions and lesson snapshots.
- Measure attributable changes in strategy and comparable outcomes. “Slice 30
  evolved from slice 1” is an objective, not a promise of statistical
  significance or model-weight retraining.
- Deterministic checks and independent audit remain separate from builder
  confidence and from authority to execute, merge, deploy, or spend. Learning
  cannot weaken scope, requirements, checks, or audit rules.
- Retain existing `forge` package and CLI names during this integration.

## Existing implementation

The imported source includes Forge's governed loop, providers, policy,
recovery, and learning modules. `src/forge/slice_learning.py` supplies a durable
two-lane learning controller; `src/forge/athena_engineering.py` supplies a
narrow directional outcome comparison. The import has historical focused-test
and independent-review evidence, but that evidence belongs to its source
candidate. The controller is not yet wired to a live two-builder runner.

## Unverified assumptions

- “DeepSeek 4.1 flags” was interpreted as “DeepSeek V4.1 Flash.” DeepSeek's
  [official model documentation](https://api-docs.deepseek.com/quick_start/pricing/)
  identifies its current API name as `deepseek-flash` (checked 2026-09-24).
  Availability to Aura's account and a live adapter call are unverified.
- OpenAI's [official model catalog](https://developers.openai.com/api/docs/models)
  lists `gpt-6-sol`, `gpt-6-luna`, and `gpt-6-astra` (checked 2026-09-24).
  Aura account access, compatible call mode, and role routing are unverified.
- No MiniMax model variant was selected by the owner; its utility-worker API
  identifier remains to be chosen and verified before activation.
- Credentials, trusted review identities and keys, and live billing authority
  have not been verified for Aura.
- The inherited cross-family audit rule may conflict with Luna and Astra in
  one provider family. Resolve it through governance before that runtime path.
- Historical Forge results do not establish Aura's current gate, runtime, or
  deployment state.

## Outstanding integration

Reconcile Aura's current repository state; pass the full local gate against an
exact candidate; connect planning, scheduling, isolated builder execution,
Governor-enforced recovery, deterministic checks, independent review,
attributable outcomes, reviewed lesson retrieval, and serialized integration.
Prove restart without duplicate effects, parallel isolation, changed-strategy
recovery, lesson measurement and withdrawal, and UNKNOWN behavior. Obtain an
independent audit of the integrated Aura candidate.

## Future ideas outside current implementation scope

A UI, additional roles, broad Athena Arena/Gauntlet policy evolution, model
weight retraining, and autonomous deployment are later decisions. They are not
prerequisites for the working loop.
