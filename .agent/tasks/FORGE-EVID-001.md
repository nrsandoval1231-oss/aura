# FORGE-EVID-001 — Reconcile historical slice evidence without rewriting it

**Node:** FORGE-EVID-001
**Status:** READY_AUTHORIZED under the owner's instruction to finish V0
**Authority:** A3 governance and evidence-boundary repair
**Risk:** HIGH (a false green slice gate would misstate candidate approval)
**Retry budget:** two materially different bounded repairs

## Objective

Restore truthful candidate-bound validation on the integrated local tree. Five earlier packet streams have valid retained receipts for historical trees and fail current-tree binding; three newer packets have no slice evidence. Preserve all eight historical packet and ledger paths. Record why historical candidate acceptance is no longer current, and create one integrated successor whose scope covers the affected work and whose approval is an actual independent audit of an exact candidate. The gate must stay red until that audit and exact binding exist.

## Base

- `67bd702fea097493d22d49b10bde238166e10d4f`

## Allowed files

- `scripts/run_slice.py`
- `src/forge/cli.py`
- `tests/test_slice_contexts.py`
- `tests/test_cli.py`
- `tests/test_gate_parity.py`
- `.agent/tasks/FORGE-EVID-001.md`
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/artifacts/FORGE-EVID-001/**`
- `.agent/ledger/FORGE-EVID-001.*`

## Exclusions

- Do not edit or rebind any pre-existing ledger or `SLICE.json` file. Do not delete, replace, or backdate their receipts.
- Do not change canonical architecture, PRD, Finish Contract, trust-kernel authority rules, or the self-improvement mandatory gate.
- Do not treat the script's simulated role keys or simulated `AuditReport(PASS)` as independent approval.
- No new paid call, external trial, push, merge, or deployment.

## Dependencies

- Historical FIX/GOV/EVO/INT/LRN slice streams and the audited live Builder result remain readable.
- Sol controls graph transitions and independent auditor dispatch. Luna owns only the allowed code and test files and proposes graph changes to Sol.

## Invariants

- `REDIRECTED` means retained historical evidence, invalid current acceptance, and no completion or dependency credit. `FORGE-SI-001` remains `MANDATORY_V0_GATE`.
- Each redirected packet has an append-only reconciliation record naming its old candidate digest and ledger head when they exist, explicitly naming any absent evidence otherwise, plus the reason and integrated successor; neither an old ledger nor an old artifact changes.
- A missing, malformed, unverified, self-issued, or wrong-candidate audit keeps the gate red. A builder cannot certify its own candidate through local process keys or text fields.
- The successor binds to every relevant changed file on the integrated candidate; exclusions for self-produced evidence are explicit and narrow. Later mutation of an audited file invalidates the binding.
- The three new packets' runtime results remain historical facts even though they lack old-style slice evidence. The one-call $15 grant cannot be reused.
- Graph and narrative must say what is verified, what is historical, and what is still UNKNOWN.

## Acceptance

1. Reproduce a false-green attempt against missing or forged independent audit evidence, then show the repaired gate refuses it.
2. Verify all historical ledgers and preserve their bytes; verify each reconciliation record and link to the successor.
3. Keep the gate red until the exact integrated candidate receives independent audit. Rerun `scripts/validate.sh`, affected tests, graph check, and `git diff --check`, recording exit codes and candidate SHA.
4. Sol conducts a separate exact-candidate independent audit; only its real verdict can satisfy the successor's audit input. No simulated PASS can do so.
5. Do not promote historical nodes or `FORGE-SI-001` to COMPLETE to make the gate green.

## Handoff

Luna provides changed files, test reproduction, gate exits, unresolved questions, and proposed graph transitions. Sol serializes governance updates and exact-candidate audit. Astra returns PASS/FIX/ESCALATE on the actual integrated candidate.
