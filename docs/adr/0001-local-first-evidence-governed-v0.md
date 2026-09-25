# ADR-0001: Local-first evidence-governed V0

**Status:** Accepted
**Date:** 2026-09-18

## Context

Forge must prove bounded autonomy, deterministic authority, exact candidate identity, independent verification, restart reconciliation, discovery, and validated learning. Distributed infrastructure is not required to prove those properties.

## Decision

V0 will be a separate local-first Python runtime. Probabilistic components may propose work, but deterministic software controls state transitions, authority, effects, candidate identity, evidence, and completion eligibility.

## Consequences

- One local process and SQLite are sufficient initial boundaries.
- Model and tool integrations remain adapters rather than architectural authorities.
- Protected governance surfaces require elevated workflow.
- Distributed workers, cloud deployment, and production writes remain deferred.
