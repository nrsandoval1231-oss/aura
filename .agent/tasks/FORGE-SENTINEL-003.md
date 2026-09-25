# FORGE-SENTINEL-003 — Complete the Sentinel Phase 9 release packet

**Status:** COMPLETE after independent Astra ACCEPT on exact Forge candidate `0ede5c883646a283cd9832d09299c49e2dad679b`
**Repository:** `nrsandoval1231-oss/forge-agent`
**Base:** `efed3e8c3ef6345115c3a29c62b705dbc3b2487b`
**Target repository:** `nrsandoval1231-oss/sentinal`
**Authority:** A3 evidence-governance repair under the owner's V0 completion direction; read-only remote verification
**Risk:** HIGH because false retrospective lineage could fabricate Phase 9 completion
**Retry budget:** two materially different local repair attempts

## Objective

Produce and deterministically verify the full Sentinel Phase 9 release packet
from the actual retained episode. Bind the material discovery from the first
candidate's independent FIX to an explicit versioned requirement, prove the
bounded repair executed after that discovery against the corrected requirement,
and retain the later independent PASS and remote merge receipt. Do not invent or
rewrite an event that did not occur.

## Allowed files

- `scripts/prove_sentinel_release.py`
- `tests/test_sentinel_release.py`
- `.agent/artifacts/FORGE-SENTINEL-003/**`
- `.agent/artifacts/FORGE-SI-001/REAL_EPISODE.json`
- `.agent/ledger/FORGE-SENTINEL-003.jsonl`
- `.agent/ledger/FORGE-SENTINEL-003.checkpoint.json`
- `.agent/tasks/FORGE-SENTINEL-003.md` (Sol only)
- `.agent/graph/work-graph.json` (Sol only)
- `.agent/CURRENT_STATE.md` (Sol only)

## Exclusions

No model/provider call, new Sentinel source edit, rewrite of Sentinel history,
mutation of SENTINEL-001/002 evidence, deployment, canonical architecture/PRD/
Finish Contract change, or self-issued completion verdict. Remote Sentinel is
read-only in this packet.

## Required source facts

- Sentinel baseline: `d43e2629f2c3db87fdb1437a16f5e94a37136c53`.
- First candidate: `a9c464bcc2b683014b54082a615501e09bb4df8e`.
- Material discovery: independent Astra FIX found case-sensitive WindowsApps
  handling and invalid POSIX substring rejection.
- Corrected candidate: `61258ab0590ffb65c2c96e2117e547ae38ddfda7`.
- Independent PASS binds Forge `8c6cbfdcdca9534610bdddc3ac18d07c58a73f7b`
  and Sentinel `61258ab0590ffb65c2c96e2117e547ae38ddfda7`.
- Remote Sentinel main later merged that exact candidate in merge commit
  `7c2f639232f231b0e6e748314bce487b452829e5` (PR #16).

## Required behavior

1. Use Product Brain/DiscoveryRecord semantics to retain a validated material
   discovery with evidence, rationale, impact analysis, and requirement lineage.
2. Define an initial requirement matching the first candidate's ambiguous shell
   selection rule and a corrected requirement requiring Windows-only, exact
   path-component, case-insensitive WindowsApps refusal while preserving valid
   non-Windows Bash paths. Derive and retain both specification hashes.
3. Prove the repair packet is bound to the evolved hash; a packet bound to the
   superseded hash must be refused.
4. Bind actual Git ancestry and diffs: first candidate from baseline, corrected
   candidate from first candidate, remote merge containing the corrected exact
   candidate, and only the audited target paths.
5. Use the core LedgerStore to persist the causally ordered episode, reload it
   after a recorded checkpoint to prove restart, and retain exact discovery,
   specification, packet, candidate, test, audit, merge, outcome, lesson, and
   Finish Contract receipts. Ambiguous or absent evidence fails closed.
6. Produce every release-packet field required by Canonical §256 and the V0 PRD:
   mission snapshot, repository identity, initial specification hash, execution
   graph, Build Packets, candidate SHAs, test receipts, audit receipts, repair
   history, discovery records, specification patch history, restart receipts,
   merge receipts, outcome evaluation, lesson candidates, Finish Contract evaluation.
7. Bind the already independently verified real EXT-001 → EXT-002 learning
   episode and named metric 1 → 0 into `FORGE-SI-001/REAL_EPISODE.json`; retain
   the simulated rollback proof as separate evidence.

## Acceptance

- Tests reproduce refusal for missing, reordered, mismatched, truncated, or
  unaudited release evidence and for a superseded specification binding.
- The core stream reloads with an independent checkpoint and preserves every
  referenced historical ledger/artifact unchanged.
- Actual Sentinel affected/full validation is rechecked against the remote merge
  tree or exact merged candidate tree without modifying it.
- Full Forge Git Bash validation, fresh-checkout validation, graph, all ledgers,
  Ruff, format, and diff checks pass after Sol state reconciliation.
- Independent Astra audits the exact clean candidate and the remote Sentinel
  merge before either Sentinel Phase 9 or FORGE-SI-001 is promoted.

## Handoff

Return exact source identities, derived specification hashes, release packet
digest, ledger/checkpoint identity, commands/exits, changed files, and unknowns.
Do not commit, self-certify, push, merge, deploy, or change target source.
