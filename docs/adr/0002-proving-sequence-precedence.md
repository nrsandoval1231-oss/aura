# ADR-0002: Proving-sequence precedence

**Status:** Accepted
**Date:** 2026-09-18

## Context

Architecture Sections 246–254 define detailed capability exits using an earlier phase sequence. Sections 255–267 complete and restate the sequence, but renumber evidence/replay, discovery, recovery, and the final trial. The V0 PRD derives from the later final sequence.

## Decision

Section 267 controls phase ordering because it is the final explicit canonical sequence. Sections 247–258 remain mandatory capability acceptance criteria and are mapped by capability rather than by their earlier phase number:

- trust-kernel and ledger obligations apply to Phases 1 and 4;
- repository isolation, exact-candidate audit, and merge eligibility remain gates before autonomous continuation;
- discovery obligations map to Phase 5;
- stuck-recovery obligations map to Phase 6;
- outcome and lesson obligations map to Phase 7;
- restart obligations map to Phase 8;
- Sentinel obligations map to Phase 9;
- the controlled external trial and post-trial architecture review both apply to Phase 10.

No displaced obligation is dropped. If implementation reveals a material conflict in this mapping, execution stops at the affected gate and raises a governed specification decision.

## Consequences

- Work graph nodes use the Section 267 order.
- Tests and Finish Contract checks retain all earlier exit criteria.
- Phase labels cannot be used to bypass a capability obligation.
