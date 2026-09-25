# FORGE-AUDIT-MANIFEST-001 — Make exact-candidate manifests checkout independent

**Node:** FORGE-AUDIT-MANIFEST-001 (repair of merged protected audit code under DEC-006)
**Status:** IN_PROGRESS; no new READY graph node is required for this restoration
**Repository:** nrsandoval1231-oss/forge-agent
**Branch/worktree:** codex/audit-manifest-repair in an isolated worktree
**Base SHA:** 3260cd1934177560c047b38cfb8da1cf3761dda1
**Authority:** A3; owner explicitly approved this bounded protected audit-boundary repair on 2026-09-22
**Risk:** HIGH; this code determines whether a detached audit binds the exact candidate
**Retry budget:** two materially different bounded repairs

## Objective

Repair the merged detached-audit manifest so the same clean Git commit has the
same complete manifest in every checkout. The current implementation hashes
working-copy bytes, so Git line-ending conversion can make an independently
signed exact candidate unverifiable in another clean Windows checkout. Bind the
manifest to committed Git object bytes while retaining the clean-worktree,
complete-manifest, exact-HEAD/tree, trust, signature, and validation checks.

## Allowed files

- `src/forge/audit_receipts.py`
- `tests/test_audit_receipts.py`
- `tests/test_slice_contexts.py` only if required for the end-to-end regression
- `docs/packets/FORGE-AUDIT-MANIFEST-001.md`
- `.agent/artifacts/FORGE-AUDIT-MANIFEST-001/**`

## Exclusions

Do not change canonical architecture, PRD, Finish Contract, graph state,
Governor, policy registry, trust record, validation runner, historical ledgers,
or any existing receipt, signature, or auditor key. Do not make a model call,
push, merge, deploy, spend, or communicate externally.

## Invariants

1. The manifest covers every path in the exact committed candidate once and
   hashes the committed Git blob bytes, independent of checkout filters.
2. Only ordinary committed blobs are accepted. Symlinks, submodules, malformed
   entries, duplicate paths, missing objects, and ambiguous state fail closed.
3. The repository must remain clean and its current HEAD/tree must equal the
   candidate. Deriving the manifest from HEAD must not permit local mutation.
4. Repository identity, exact candidate digest, complete manifest, owner-pinned
   external key, auditor identity, validation artifact, and detached signature
   remain mandatory.
5. The rejected receipt under
   `C:/Users/nrsan/AppData/Local/ForgeAgent/audit-receipts/forge-val-lf-b7b42ac-91b0d143d97b`
   is retained unchanged as negative evidence.

## Acceptance

1. Reproduce the checkout-byte mismatch with a regression that materializes the
   same commit under different line-ending settings and proves one manifest.
2. A clean exact candidate verifies with a manifest generated from committed
   bytes even when its working copy uses different line endings.
3. Dirty worktrees, incomplete manifests, altered committed content, wrong
   HEAD/tree, symlinks, submodules, malformed paths, missing blobs, wrong trust,
   invalid signatures, and stale validation evidence fail closed.
4. Run focused audit tests, Ruff, format check, `git diff --check`, and the full
   local `scripts/validate.sh` gate on the frozen candidate.
5. Sol reruns the checks in two clean checkouts, freezes the exact candidate,
   obtains an independent Astra verdict, and requests approval of a fresh
   one-time auditor fingerprint before any new signed receipt is accepted.

## Handoff

The builder writes `.agent/artifacts/FORGE-AUDIT-MANIFEST-001/COMPLETION.json`
with base/candidate state, changed paths, exact commands and exit codes,
negative-case evidence, migration impact, and remaining unknowns. The builder
does not certify, commit, push, merge, sign, alter graph status, or deploy.
