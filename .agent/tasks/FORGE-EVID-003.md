# FORGE-EVID-003 — Reconcile the actual historical evidence classes

**Node:** FORGE-EVID-003
**Status:** READY_AUTHORIZED under the owner's V0 completion direction
**Authority:** A3 evidence and graph-state repair
**Risk:** HIGH (false redirection could hide missing acceptance)
**Retry budget:** two materially different bounded repairs

## Objective

Record one truthful, append-only reconciliation for each of eight packet streams that block the integrated slice gate. The five old slice packets have a slice and ledger, LIVE has a real call ledger but no slice, and STATE/Windows have neither. Match those records exactly to graph `REDIRECTED` packet references and one proposed `FORGE-INTEGRATED-001` successor. Keep all old evidence unchanged and keep the repository gate red until the integrated successor receives its own valid independent exact-commit audit.

## Base

- `38112f9490b49b4e3237f46236df87ee380b7539` (independent FIX on EVID-002; negative evidence retained)

## Allowed files

- `scripts/run_slice.py`
- `tests/test_slice_contexts.py`
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)
- `.agent/tasks/FORGE-EVID-003.md`
- `.agent/artifacts/FORGE-EVID-003/**`
- `.agent/ledger/FORGE-EVID-003.jsonl`
- `.agent/ledger/FORGE-EVID-003.checkpoint.json`
- `.agent/artifacts/FORGE-EVID-002/AUDIT.md` (Sol only; records the preceding FIX)

## Exclusions

- Do not edit/rebind old ledgers, checkpoints, or SLICE artifacts, including EVID-001.
- Do not accept an unsigned, self-issued, or user-selected key as independent approval. Trusted audit integration is a later bounded packet.
- Do not change canonical architecture, PRD, Finish Contract, trust-kernel authority rules, or self-improvement gate.
- No provider call, spending, external push, merge, or deployment.

## Dependencies

- Independent EVID-001 and EVID-002 FIX verdicts; keep their candidates and receipts as negative history.
- Sol owns graph transitions; Luna owns verifier/tests and new EVID-003 ledger creation.

## Invariants

- Eight reconciliation receipts, one per packet reference. Satellite STK/LRN graph nodes sharing `FORGE-LRN-000` inherit that packet's receipt and receive no independent completion credit.
- `FULL_SLICE_AND_LEDGER` derives canonical slice and ledger paths from packet ID and verifies old SLICE candidate against `CANDIDATE_REGISTERED` and checkpoint.
- `LEDGER_ONLY` derives the canonical ledger, verifies its checkpoint, proves canonical SLICE absent, and records the actual head without inventing a candidate digest. LIVE is this class.
- `NO_LEGACY_EVIDENCE` proves canonical SLICE, JSONL, and checkpoint all absent. STATE and Windows are this class. Half-present state fails.
- Reject any extra event type, duplicate, missing or extra packet, unrelated path, missing or mixed successor, wrong candidate/head, truncation, or graph mismatch.
- Graph status `REDIRECTED` means history retained and current acceptance invalid; it confers no completion or dependency credit. `FORGE-SI-001` stays `MANDATORY_V0_GATE`.
- The candidate remains incomplete and the slice gate remains red until a separate integrated exact-commit audit path is implemented and independently exercised.

## Acceptance

1. Reproduce EVID-001 false ABSENT and cross-packet substitution, and EVID-002 extra-event and false LEDGER_ONLY cases before fixes.
2. New EVID-003 core ledger reloads and verifies; records match canonical paths and graph packet set exactly.
3. Old evidence bytes are unchanged relative to base; graph check, affected tests, all-ledger verification, diff check, and canonical validation report exact exits.
4. Independent Astra audits the exact candidate and determines whether the historical reconciliation is truthful. Do not infer V0 completion or merge eligibility from this audit.

## Handoff

Luna supplies code, tests, new EVID-003 ledger and a completion claim. Sol serializes graph/state updates and reruns checks. Astra independently audits the exact resulting candidate. `FORGE-INTEGRATED-001` remains a separate future packet.
