# FORGE-RECON-004 — Reconcile successor-specific redirected chains

**Status:** COMPLETE
**Repository:** `nrsandoval1231-oss/forge-agent`
**Base:** `024851f47fe56b1e7e853b18014af58899e0da85`
**Authority:** A3 evidence-gate repair; Sol owns graph and ledger mutations
**Risk:** HIGH because a weak redirect binding could hide missing acceptance
**Retry budget:** two materially different local repair attempts

## Objective

Repair the reconciliation verifier so each redirected packet is bound to its own
explicit graph successor while preserving the append-only `FORGE-EVID-003` core
ledger and every historical receipt. Then make the three later redirect chains
reconcilable without falsely naming the old integrated successor.

## Allowed files

Builder ownership is limited to these paths:

- `scripts/run_slice.py`
- `tests/test_slice_contexts.py`
- `.agent/artifacts/FORGE-RECON-004/COMPLETION.json`

## Sol-only integration files

- `.agent/graph/work-graph.json`
- `.agent/ledger/FORGE-EVID-003.jsonl`
- `.agent/ledger/FORGE-EVID-003.checkpoint.json`
- `.agent/CURRENT_STATE.md`
- `.agent/artifacts/FORGE-RECON-004/**` except the builder completion claim

## Exclusions

Do not edit or replace historical reconciliation receipts. Do not weaken ledger
checkpoint, truncation, duplicate, canonical-path, evidence-class, candidate, or
graph-set validation. No provider call, Hallam edit, spending, push, merge,
deployment, canonical architecture/PRD/Finish Contract change, or completion claim.

## Required behavior

1. Replace the single global successor assumption with an explicit per-node graph
   binding such as `redirected_to`, validated for every `REDIRECTED` packet.
2. Every receipt's `successor_packet_id` must exactly match its source graph node's
   explicit binding and name an existing graph node distinct from the source.
3. Reject missing bindings, missing targets, self-loops, duplicate packet receipts,
   extra/missing packets, altered historical receipts, truncated checkpoints,
   unrelated events, and any receipt/graph successor mismatch.
4. Existing eight EVID-003 records remain byte-for-byte historical prefix evidence
   and continue to bind to `FORGE-INTEGRATED-001`.
5. Sol will add truthful bindings and append exactly three receipts after builder
   handoff: EXT-001 to EXT-DIAG-001, EXT-002 to EXT-003, and
   EXT-002-CORRECTION-002 to EXT-002-CORRECTION-003.

## Acceptance

- Focused tests cover multiple valid successors and every fail-closed case above.
- The old single-successor fixture remains accepted when its graph bindings agree.
- No test obtains authority from narrative state text.
- Sol integration reloads the extended core ledger, verifies its checkpoint, and
  proves the first eight receipt bytes are unchanged.
- Full Git Bash validation, all-ledger verification, graph check, Ruff, format,
  and diff checks report exact exits.
- Independent Astra audits the exact integrated candidate.

## Handoff

Return code/tests and a completion claim only. Do not mutate graph or ledger,
commit, self-certify, push, merge, or deploy. Do not revert concurrent edits.
