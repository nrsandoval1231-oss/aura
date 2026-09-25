# AURA-TRUST-002 — Authority and key snapshot repair

Status: READY. Successor to independently CORRECTed AURA-TRUST-001 at
`b23e3c87a512b6279df3ea11831ccfa499ee3eaf`; retain that candidate and
its review unchanged. Owner approved the exact public PEM SHA-256 already
pinned in the Aura-only trust record. This packet authorizes the narrow
protected registry and verifier repair; it does not authorize signing, merge,
provider spend, or live activation.

## Objective

Make Aura's active verifier and trust record require owner authority. Use the
same fingerprint-checked public-key bytes for cryptographic verification so a
mutable external path cannot change the key between check and OpenSSL use.
Add adversarial regression tests for both defects and missing negative cases.

## Base

- `b23e3c87a512b6279df3ea11831ccfa499ee3eaf` on
  `codex/aura-trust-authority-repair` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-TRUST-002.md`
- `.agent/artifacts/AURA-TRUST-001/REVIEW-b23e3c8.json`
- `.agent/artifacts/AURA-TRUST-002/**`
- `src/forge/policy.py`
- `src/forge/aura_audit.py`
- `tests/test_policy.py`
- `tests/test_aura_audit.py`
- `docs/packets/AURA-TRUST-002.md`

## Exclusions and acceptance

No historical ledger or slice rewrite; no change to Forge trust, validation
gates, provider routing, or executor. `requires_owner_authority` and
`pattern_reaches_protected_surface` must return true for both new Aura trust
surfaces. Verifier must pin exact external public bytes once before signature
verification and fail closed on missing/wrong key, missing/mismatched signature,
changed candidate/repository/tree, invalid gate evidence, or dirty checkout.
Run focused tests and `./scripts/validate.sh`; inspect all failures. Fresh
independent exact-candidate security review required. Red historical slice
evidence is retained, not silently rebound. Two distinct repair attempts max.
