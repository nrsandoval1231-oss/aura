# FORGE-EXT-PORT-001 — Canonicalize retained lesson artifact identity

**Status:** COMPLETE
**Repository:** `nrsandoval1231-oss/forge-agent`
**Base:** `57fb8d2bb45c23b849d1b322fbfa1a5fcbc2bac0`
**Authority:** A3 evidence-boundary repair under DEC-006 and owner V0 completion direction
**Risk:** HIGH because this code verifies independently audited lesson evidence
**Retry budget:** two materially different local repair attempts

## Objective

Make EXT-002 and EXT-003 lesson verification stable across Git checkout line
endings without changing the retained artifacts, their historical audit digests,
or any validated lesson authority field.

## Allowed files

- `scripts/external_trial_recovery.py`
- `scripts/external_trial_finalize.py`
- `tests/test_external_trial_recovery.py`
- `tests/test_external_trial_finalize.py`
- `.agent/artifacts/FORGE-EXT-PORT-001/**`

## Exclusions

No mutation of `FORGE-EXT-LESSON-001` artifacts, historical audit hashes,
lesson content, graph/state by the builder, provider call, Hallam edit, ledger
mutation, push, merge, deployment, or V0 completion claim.

## Required behavior

1. Verify exact retained JSON content through an unambiguous canonical byte form
   that normalizes only CRLF/CR to LF before hashing.
2. Pin the canonical LF hashes independently observed in a fresh checkout:
   CANDIDATE `11d0a682424fcece2a44b4c1d12e55fac7e9f3def2446b44676b78fc16165dda`
   and VALIDATED `01bd1db99b1a18e20dbf0569019bdc34dde005a3e8f9bf488b0a8a7ce1d211ee`.
3. Preserve the legacy audited evidence digest `39658905...` inside the lesson
   decision and every exact authority-field check. Do not reinterpret it as the
   new canonical artifact hash.
4. LF and CRLF representations of the exact artifacts must pass. Any semantic,
   whitespace beyond line endings, encoding, field, or value mutation must fail closed.
5. Both EXT-002 and EXT-003 paths must use the same rule and remain behaviorally aligned.

## Acceptance

- Reproduce the fresh-checkout `SOURCE_INVALID` failures before the repair and
  prove both line-ending forms pass afterward.
- Adversarial tests reject changed JSON values, reordered or reformatted JSON,
  invalid UTF-8, and mutated legacy evidence fields.
- External-trial focused tests, full tests, Ruff, format, graph, ledger, and diff checks pass.
- A disposable fresh core.autocrlf=true checkout passes the external-trial tests.
- Independent Astra accepts the exact clean candidate before graph promotion.

## Handoff

Return exact commands, exits, changed paths, canonicalization rule, retained
legacy evidence relationship, and unknowns. Do not commit, self-certify, push,
merge, deploy, or modify files outside this packet.
