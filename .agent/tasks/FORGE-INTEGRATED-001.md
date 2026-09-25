# FORGE-INTEGRATED-001 — Exact clean-commit integrated audit

**Node:** FORGE-INTEGRATED-001
**Status:** COMPLETE for the exact signed `15366f908e201debe4c6d6c443ca0e243208fd9b` bounded candidate
**Authority:** A3 evidence and audit boundary; one-time auditor key and exact public fingerprint approved by owner
**Risk:** HIGH (a false PASS would certify an unaudited integrated tree)
**Retry budget:** two materially different bounded repairs

## Objective

Make the repository's candidate-bound gate accept the integrated tree only after an independent auditor signs a detached receipt for the exact clean commit. The gate must independently derive repository identity, full HEAD and Git tree, complete tracked-file manifest, and validation-artifact digest; verify an owner-approved public key fingerprint pinned in the candidate; and reject the generic slice runner's simulated PASS as independent authority. The eight historical packet references remain REDIRECTED to this successor, with their old ledgers preserved.

## Base

- `461228cec486f19ed23b653a9753ad10fd4ce3d9` (independent PASS on historical reconciliation only)

## Allowed files

- `scripts/run_slice.py`
- `src/forge/audit_receipts.py`
- `src/forge/cli.py` if needed for a diagnostic command (not the authority gate)
- `tests/test_slice_contexts.py`
- `tests/test_audit_receipts.py`
- `tests/test_gate_parity.py`
- `.agent/tasks/FORGE-INTEGRATED-001.md`
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/artifacts/FORGE-INTEGRATED-001/**`
- `.agent/audit-trust.json` (Sol only, after owner approves the exact public-key fingerprint)
- `src/forge/policy.py` and `tests/test_policy.py` only if required to protect the new trust file (Sol-approved A3 change)

## Exclusions

- No old ledger, checkpoint, slice artifact, or rejected EVID-001/EVID-002 evidence may be rewritten or removed.
- No embedded private key, credential, simulated audit PASS, automatic signing, or caller-selected trust key in the authoritative gate.
- No change to canonical architecture, PRD, Finish Contract, trust-kernel authority logic, or self-improvement mandatory gate.
- No new provider call, spending, external trial push, merge, or deployment.

## Dependencies

- EVID-003 historical reconciliation passed independently at exact `461228cec486f19ed23b653a9753ad10fd4ce3d9`.
- The owner authorized preparing a one-time independent auditor key outside the repository. The owner must approve its public fingerprint before final validation.
- Sol controls graph state, trust-file pinning, and auditor dispatch; Luna builds code/tests without the private key.

## Invariants

- The authoritative `run_slice.py --check` special-cases only this integrated successor. It verifies the EVID-003 core ledger and exact graph mapping first, then verifies the detached audit against current clean HEAD. The generic producer's process-local Auditor and `HEAD+worktree` receipt cannot satisfy it.
- Repository identity comes from the actual `origin` URL, not a caller argument. Candidate revision is full HEAD; candidate tree is Git's `HEAD^{tree}`; both are independently re-derived.
- The signed manifest covers every tracked file exactly once, with its SHA-256 digest, and the verifier compares it to the current tracked tree. A committed validation artifact is hashed and compared with the signed validation digest; its content distinguishes pre-audit deterministic gates from the slice gate pending signature.
- The owner-approved public-key fingerprint is pinned in `.agent/audit-trust.json`, a protected A3 file, before final candidate audit. The authoritative gate compares it with the supplied external public key. A Builder cannot choose or replace the trust root through an environment variable or CLI argument alone.
- The independent auditor holds the one-time private key outside the candidate. The external public key, detached signature, and audit receipt are never committed after the candidate audit. Receipt domain, repository, commit, tree, manifest, validation digest, verdict, and auditor identity are signed together.
- Missing/malformed trust material, wrong fingerprint, forged or substituted key, wrong or incomplete manifest, wrong validation digest, dirty worktree, wrong commit/tree/repository, non-PASS verdict, or interrupted evidence fails closed.
- Passing this packet's audit gate does not satisfy real self-improvement, Sentinel proving ground, external trial, or V0 completion by itself.

## Acceptance

1. Regression tests show the generic simulated slice cannot certify this successor, while an independently signed exact clean commit can pass `run_slice.py --check` with all other pending packets redirected or complete.
2. Test forged self-issued external key, wrong approved fingerprint, missing key/receipt/signature, modified candidate, omitted tracked file, wrong validation artifact/digest, wrong origin, wrong HEAD/tree, wrong verdict, and dirty worktree.
3. Run focused tests and canonical `scripts/validate.sh` before signing; record the expected red slice gate, all other gate exits, clean candidate SHA/tree, manifest and validation digests.
4. Independent Astra audits the final clean candidate. A separate auditor prepares a one-time key and reports the public fingerprint; Sol requests owner approval for that fingerprint, pins it, then the auditor signs the final exact commit. Re-run full validation and report exact outcome.
5. No packet or V0 status is promoted by a Builder claim or merely by local unit tests.

## Handoff

Luna owns only the allowed verifier/test code and draft validation artifact. Sol serializes graph and trust pinning. Astra performs an independent code/evidence review of the exact candidate and, after owner fingerprint approval, holds the signing key and signs the detached receipt. All external audit materials stay outside the repository.
