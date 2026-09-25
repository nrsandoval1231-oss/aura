# FORGE-EVID-002 — Truthful reconciliation and detached independent audit

**Node:** FORGE-EVID-002
**Status:** READY_AUTHORIZED under the owner's V0 completion direction
**Authority:** A3 evidence and validation boundary repair
**Risk:** HIGH (false audit acceptance would defeat the Finish Contract)
**Retry budget:** two materially different bounded repairs

## Objective

Replace the rejected FORGE-EVID-001 reconciliation claim with truthful, independently checkable evidence. Retain its eight receipts as negative history. Record the actual old evidence class for each redirected packet, preserve the five old slice streams, and make the repository gate accept an integrated successor only when a detached, independently signed exact-commit audit is verified against an owner-supplied trust anchor outside the candidate worktree.

## Base

- `a530abc7a5af9cdba097e8385eedc8564426434e` (rejected reconciliation candidate; preserve its evidence)

## Allowed files

- `scripts/run_slice.py`
- `src/forge/audit_receipts.py`
- `src/forge/cli.py`
- `tests/test_slice_contexts.py`
- `tests/test_audit_receipts.py`
- `tests/test_cli.py`
- `tests/test_gate_parity.py`
- `.agent/tasks/FORGE-EVID-002.md`
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/artifacts/FORGE-EVID-002/**`
- `.agent/ledger/FORGE-EVID-002.*`

## Exclusions

- No modification, rebind, or deletion of any pre-existing ledger or slice artifact, including the rejected FORGE-EVID-001 ledger.
- No changes to canonical architecture, PRD, Finish Contract, trust-kernel authority logic, or the self-improvement mandatory gate.
- No production key embedded in source, test, packet, ledger, or candidate artifact. Test keys are temporary test fixtures only.
- No provider call, spending, external trial push, merge, or deployment.

## Dependencies

- Independent Astra FIX on exact a530abc identified false ABSENT, cross-packet path substitution, graph/ledger mismatch, and an audit gate with no valid acceptance path.
- Sol separately controls graph transitions, integrated-successor scope, and the independent auditor dispatch.

## Invariants

- `REJECTED` FORGE-EVID-001 has no completion or dependency credit. Its ledger remains readable as negative evidence.
- Every redirected graph packet is represented exactly once in the new core reconciliation ledger; no extra records, duplicate records, arbitrary events, nonexistent packet, missing successor, or mixed successors pass.
- The old evidence class is derived from canonical packet paths: `FULL_SLICE_AND_LEDGER`, `LEDGER_ONLY`, or `NO_LEGACY_EVIDENCE`. Half-present streams fail. The LIVE packet is `LEDGER_ONLY`; STATE and Windows have no old slice stream. Satellite graph nodes sharing a packet inherit that packet's one reconciliation record and receive no separate completion credit.
- A full slice checks its canonical `SLICE.json`, old ledger, checkpoint, and registered candidate identity. A ledger-only packet checks its canonical ledger and checkpoint. A no-evidence packet proves all canonical old evidence paths absent. Any mismatch or truncation fails closed.
- No local process key, arbitrary JSON PASS, caller-supplied public key, or text field in the candidate can substitute for an independent auditor signature. The auditor's trusted public key or allowed-signers file and detached receipt are supplied outside the candidate worktree. Missing trust material keeps the gate red.
- A signed audit binds repository identity, full clean HEAD commit and tree, an explicit candidate manifest, validation digest, verdict, auditor identity, and signature domain. A dirty tree, mutated candidate, wrong key, wrong manifest, non-PASS verdict, or missing signature fails closed.
- A detached audit is written only after the final candidate commit and does not mutate it. The generic simulated `run_slice.py` producer cannot be used to claim independent approval.
- `FORGE-SI-001` stays `MANDATORY_V0_GATE`; repository gate success alone is not V0 completion.

## Acceptance

1. Tests reproduce the a530abc false-absence and cross-packet substitution cases, plus missing/extra/duplicate graph records, arbitrary event, partial ledger, truncation, and wrong successor.
2. Tests use an independent temporary signing key to prove one valid detached audit passes and forged, self-issued, missing, wrong-key, wrong-commit/tree/manifest, dirty-tree, and tampered receipts fail.
3. The new reconciliation stream reloads and verifies under the core ledger. Old ledger and artifact bytes remain unchanged.
4. Run affected tests, canonical `scripts/validate.sh`, graph check, all-ledger verify, and diff check. Report exact exits, candidate SHA, residual red gates, and unknowns.
5. Independent Astra audits the exact repair candidate before Sol changes any graph status or claims integrated acceptance. Final integrated successor requires its own separate exact-commit audit.

## Handoff

Luna owns the code, tests, and new EVID-002 ledger under the allowed paths. Sol controls graph/state and the trust-anchor setup decision. Astra independently audits the exact candidate. No Builder may sign or certify its own implementation.
