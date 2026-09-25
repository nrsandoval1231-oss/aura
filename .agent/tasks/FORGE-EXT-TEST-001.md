# FORGE-EXT-TEST-001 — Make external-trial tests hermetic

**Status:** COMPLETE
**Repository:** `nrsandoval1231-oss/forge-agent`
**Base:** `024851f47fe56b1e7e853b18014af58899e0da85`
**Authority:** A1 test repair; no product, provider, Hallam, or evidence effect
**Risk:** LOW
**Retry budget:** two materially different local repair attempts

## Objective

Remove the external-trial tests' dependency on the mutable Hallam trial checkout.
The tests must construct faithful temporary pre-change inputs and remain valid
after the real Hallam branch contains the accepted fix.

## Allowed files

- `tests/test_external_trial_recovery.py`
- `tests/test_external_trial_finalize.py`
- `tests/fixtures/external_trial/**`
- `.agent/artifacts/FORGE-EXT-TEST-001/**`

## Exclusions

No production-code change, provider call, Hallam edit, ledger mutation, graph or
state edit, push, merge, deployment, or change to retained EXT-001/002/003 evidence.

## Required behavior

1. Replace hard-coded reads from the live Hallam checkout with repository-owned,
   deterministic test inputs that represent the exact required pre-change shapes.
2. Preserve every existing positive and adversarial assertion, including prompt
   bounds, exact path selection, mutation refusal, credential checks, and trusted
   deterministic reconstruction.
3. Prove the tests do not read the live Hallam trial path.
4. Do not weaken a precondition merely because the real Hallam checkout is now fixed.

## Acceptance

- Both external-trial test modules pass when the live Hallam checkout is present
  at the accepted post-fix candidate.
- A regression assertion fails if either module reintroduces the hard-coded live path.
- Ruff, format, and diff checks pass for the owned files.
- A compact `COMPLETION.json` records exact commands, exits, changed files, and unknowns.

## Handoff

Return the changed paths and deterministic evidence. Do not commit, self-certify,
push, merge, deploy, or modify files outside this packet.
