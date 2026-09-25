# Opening Tribunal

## Objective

Establish Forge Agent as a separate governed repository whose first implementation target is the deterministic V0 trust kernel.

## Luna — Simplifier

Build the smallest useful foundation: canonical architecture, a maximum-50-requirement PRD, repository rules, Finish Contract, one ADR, graph state, and empty implementation/test surfaces. Defer runtime code and optional infrastructure.

## Terra — Engineer

Use a local-first Python project boundary with deterministic validation and exact Git identity. Preserve extension points for model providers and persistence without selecting integrations prematurely.

## Sol — Architect

The principal risks are governance drift, implementation beginning before the authority hierarchy is durable, and confusing a green scaffold with product completion. Freeze the documents, protect authority surfaces, and gate the first implementation packet on this foundation's independent audit.

## Decision

- **Build now:** governed repository foundation
- **Do not build yet:** runtime, provider integrations, deployment, distributed execution
- **Architecture:** local-first evidence-governed runtime
- **Key assumptions:** one local process is sufficient to prove V0; Git and SQLite can support initial evidence
- **Major risks:** self-certification, ambiguous candidate identity, silent specification drift
- **Execution sequence:** foundation → trust kernel → Product Brain → execution loop → evidence/replay → discovery → recovery → learning → proving grounds
- **Verdict:** PROCEED
