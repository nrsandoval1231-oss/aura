# FORGE-AUDIT-BIND-001 — Bind pending review to the exact committed candidate

**Node:** FORGE-AUDIT-BIND-001 (repair of merged audit code under DEC-006)
**Status:** IN_PROGRESS; no new READY graph node is required for this restoration
**Repository:** nrsandoval1231-oss/forge-agent
**Branch/worktree:** codex/forge-v0-completion in the isolated managed worktree
**Base SHA:** 92147655b78d020409f4f0a4b35212119baa9707
**Authority:** A3; owner explicitly approved this bounded protected audit-gate repair on 2026-09-22
**Risk:** HIGH; this code decides whether external review can authorize a candidate
**Retry budget:** two materially different bounded repairs

## Objective

Repair the merged pending-slice audit check exposed by the independent FIX on
FORGE-VAL-LF-001. The slice's process-local ledger records a pre-commit
`base+worktree` identity and a selected-file hash. The detached audit verifier
correctly requires a clean exact Git commit and complete tracked manifest. The
pending check currently passes the former identity to the latter, so no signed
receipt can ever pass. It also checks a committed pre-audit validation artifact
whose gate set predates the new LF ledger stream.

## Allowed files

- `scripts/run_slice.py`
- `src/forge/audit_receipts.py` (only if required for exact-commit binding)
- `tests/test_slice_contexts.py`
- `tests/test_audit_receipts.py`
- `.agent/artifacts/FORGE-INTEGRATED-001/VALIDATION.json`
- `docs/packets/FORGE-AUDIT-BIND-001.md`
- `.agent/artifacts/FORGE-AUDIT-BIND-001/**`

## Exclusions

Do not change the canonical architecture, PRD, Finish Contract, protected trust
record, Governor, policy registry, validation runner, LF source fix, historical
ledgers, preliminary receipts, or any auditor private key. No live model call,
push, merge, deployment, or external communication under this packet.

## Invariants

1. A process-local simulated PASS or MERGE_ELIGIBLE receipt alone is never
   independent authorization.
2. The stored slice ledger, checkpoint, candidate digest, changed-file set,
   selected-file hash, receipt ordering, and append-only history are still
   checked. Do not reinterpret their pre-commit hash as a Git tree.
3. The external signed receipt binds the clean current HEAD, Git tree, complete
   tracked manifest, packet ID, approved owner public-key fingerprint, auditor
   identity, and current pre-audit gate results. Mutation or missing evidence
   fails closed.
4. The prior FORGE-VAL-LF-001 PRELIMINARY.* evidence remains explicitly
   unaccepted. Do not replace or erase it.

## Acceptance

1. Reproduce the existing impossible binding in a regression test before the
   production fix.
2. A valid signed exact-commit LF receipt can pass pending validation after
   current gate results are recorded; the simulated worktree receipt alone fails.
3. Stale head/tree, incomplete or altered manifest, wrong packet, missing or
   invalid signature, wrong owner-pinned key, changed selected-file content,
   stale checkpoint, and missing/current gate mismatches fail closed.
4. Run focused tests, Ruff, `git diff --check`, and `scripts/validate.sh` locally
   on the frozen candidate. Until an external auditor signs the exact candidate,
   only the independent-audit gate may remain red.
5. Sol reruns deterministic checks, freezes an exact commit, obtains independent
   strategic audit, and records the one graph direction. A signed receipt needs
   separate owner approval of any new one-time public fingerprint.

## Handoff

Builder returns a completion artifact with base/candidate identity, every
changed path, commands and exit codes, negative-case evidence, migration impact,
and remaining UNKNOWNs. Builder does not certify, alter graph status, commit,
push, merge, sign, or deploy. Sol controls integration and external audit.
