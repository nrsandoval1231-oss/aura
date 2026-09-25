# Current State

> This file is narrative. It does not assert execution state — the work graph
> and the evidence ledger do. `forge graph check` fails the build if this or any
> other document contradicts them. (DEC-006, FORGE-FIX-001)

## Repository

- Repository: `nrsandoval1231-oss/forge-agent`
- Canonical branch: `main`
- Phase: Phase 0 repair complete; governed loop proven end to end on this repository

## Canonical authority

- Architecture: `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md`
- V0 PRD: `FORGE_AGENT_V0_PRD.md`
- Finish Contract: `docs/finish-contract.md`
- Initial ADR: `docs/adr/0001-local-first-evidence-governed-v0.md`
- Sequence precedence: `docs/adr/0002-proving-sequence-precedence.md`
- Source lineage: `docs/source-lineage.md`
- Latest repository reaudit document: `docs/audit/2026-09-22-repository-audit.md`
- Validation authority: `scripts/validate.sh`, run locally (DEC-009)

## Active graph

Run `forge graph check` for authoritative node status.

## Current direction (2026-09-23)

`FORGE-EXT-001` is REDIRECTED after its one authorized request failed closed.
The HTTP 200 response passed schema parsing and was refused during proposal
validation with sanitized `ValueError`; the specific rejected rule was not retained
and cannot be reconstructed. The core stream has three receipts at head `ff73ef89`,
and the retained claim blocks retry. Hallam remains unchanged at clean `2d687fe`;
no branch was pushed, merged, or deployed. The packet proved its one-call and
fail-closed boundaries but did not satisfy the external-trial objective. Astra
directed a separate local diagnostic-recovery packet before any materially
different future request. This result makes no self-improvement claim.
`FORGE-EXT-DIAG-001` is COMPLETE under independent Astra ACCEPT at exact clean
`2db548693bcace2606e459b962571b6b47960e81`. After two bounded repairs, 42
focused tests, 630 full tests, and 12 independent escaped-credential probes
passed. The runner now retains allowlisted refusal reasons and content-free hunk
metadata without persisting sensitive response-derived digests. This local
repair grants no call authority.

`FORGE-EXT-LESSON-001` is COMPLETE. Independent Astra ACCEPT at exact
`3c9691a71f66db5d1cfd5f1b17151b03547fd1fa` validated lesson `ab743a3c`
for Forge repository scope, bound to real EXT-001 outcome `8f8f74e3` and
baseline `unexplained_external_refusals=1`. A paid external call must use
audited, content-safe refusal diagnostics before execution. No application,
measurement, or self-improvement credit is claimed until a later packet
retrieves the lesson, changes its strategy, and measures the result.

`FORGE-EXT-002` is REDIRECTED after its independently accepted runner made its
one request. The HTTP 200 result failed closed with reconstructable
`SELECTION_INVALID`: the retained selection named only `industry`, while the
bounded contract required `company`, `title`, and `industry`. The three-receipt
stream verifies at head `2b4d9e9c`; usage and billing remain UNKNOWN. The
validated lesson was retrieved and changed the execution strategy, and the
Learning Engine independently measured `unexplained_external_refusals` from 1
to 0 (`IMPROVED`). That is diagnostic improvement, not Hallam task success.
Hallam remains clean at `2d687fe`, and the retained claim blocks retry.

`FORGE-EXT-003` is COMPLETE. Independent Astra ACCEPT bound exact Forge
`9698102cc4187bfc10eb233d31805e7d59df5668` and Hallam
`93a2015e58f2c7be7fe95c6676279d1e4a54ec13`. One 1,024-token-bounded request
returned a valid decision using 730 input and 26 output tokens. Trusted code
created exactly two Hallam edits; 8 focused and all 185 offline tests passed.
The verified remote `codex/forge-external-trial` branch resolves exactly to the
audited Hallam SHA. Actual billing remains UNKNOWN. Nothing was merged or deployed.

The bounded live-call result passed an independent review at local commit
`48c0d05fb3a88d0a6d3850d2167431cf6ef6bc91`. The later state narrative passed
its own review at `67bd702fea097493d22d49b10bde238166e10d4f`.
One owner-authorized DeepSeek Builder request from its clean execution base
`d5fec8d27f89b4ca7f3b410c9045a2865fbdc223` produced a schema-valid proposal
that was applied to the README Credentials section. The core `FORGE-LIVE-001`
(REDIRECTED) ledger
reloads two receipts with checkpoint head
`eb6b5f5dd1d365176abe425f3d01bf0f345017210dd81574e317e6020d271cd5`:
226 input tokens, 833 output tokens, and provider billing **UNKNOWN**. An independent
audit passed this bounded effect at `48c0d05`; it did not certify the repository
gate or V0. No new work has been pushed, merged, or deployed. Remote PR #13 remains
open at `d26bdafe`, and remote `main` remains at `fce96b75` as independently checked
in this task.

The 2026-09-22 reaudit is at `docs/audit/2026-09-22-repository-audit.md`.
Five old slice bindings are stale on the integrated tree. The new core
`FORGE-EVID-003` (COMPLETE) stream retains their candidate digests and checkpoint heads,
records LIVE as ledger-only, and records STATE and Windows as having no legacy
slice evidence. All eight packet references are REDIRECTED to the integrated
`FORGE-INTEGRATED-001` (COMPLETE): history is retained. Independent review passed
the historical reconciliation at `461228cec486f19ed23b653a9753ad10fd4ce3d9`.
The owner approved a one-time auditor public-key fingerprint; a detached PASS
receipt binds clean `15366f908e201debe4c6d6c443ca0e243208fd9b`. Under that
receipt, 557 tests and all 20 local gates passed, exit 0. This accepts only the
bounded integrated slice; any changed candidate needs fresh review. The first
two reconciliation candidates, `FORGE-EVID-001` (REJECTED) and `FORGE-EVID-002`
(REJECTED), remain negative evidence.

`FORGE-FIX-004` is REDIRECTED. Its historical build addressed six of eight findings; the one that
mattered most was F9:
the check deciding which packets need owner authority was a denylist written against
files nobody ever created, and it protected two of twelve real surfaces. The evidence
ledger, the secrets surface, `scripts/validate.sh` and the work graph itself were all
writable by a routine packet, so a builder could have promoted its own node to READY
and deleted the gate that would have caught it. There is now one registry,
`src/forge/policy.py`, and a test asserts every surface it names exists, because the
root cause was a list nobody checked against the filesystem. F10, F11, F13, F14 and
F16 are closed too (DEC-011, DEC-012).

`FORGE-LRN-000` is REDIRECTED. It implemented three Finish Contract obligations that
had no implementation at all: stuck resolution with materially-different-strategy
enforcement, the outcome and lesson engines, and the causal-chain proof that
At that checkpoint, the real self-improvement gate was still open. It spans `FORGE-STK-001`
(REDIRECTED), `FORGE-STK-003` (REDIRECTED) and `FORGE-LRN-001`
(REDIRECTED), on the precedent DEC-006 set for FORGE-FIX-000.

The proof derives rather than asserts: one planner function, called twice with and
without the retrieved lesson, opens at a different rung, the named metric
`attempts_to_green` moves 3 to 1, and a lesson that harms its own metric is measured
HARMED and rolled back out of retrieval. The nine evidence mechanisms in
`docs/self-improvement-acceptance.md` are exercised in that simulated proof, and
the gate re-derives it on every run rather than trusting the committed artifact.
That simulated proof alone did not meet real V0 self-improvement acceptance, so
the mandatory gate remained open at that checkpoint for two reasons that
are in the evidence, not hidden: whether a
repair reaches the defect is simulated, so that proof fixed no real defect and
made no model call; and the builder of a proof cannot be its independent auditor.

`FORGE-GOV-001` is REDIRECTED. It implemented the one item of the Finish Contract's
Governor clause with no implementation: it names "state, scope, authority, budgets, and
valid transitions", and budgets had none. `BuildPacket.retry_limit` was declared by
every packet and read by nothing. Budgets belong to the Governor rather than the loop,
because a loop accepts exactly one candidate and a per-loop budget could never be
exhausted.

`FORGE-INT-001` is REDIRECTED. It implemented F15 for the Context Engine and the
budgets: the slice now assembles each role's context under the real policy and records,
per role, what the policy refused. Both independence properties are asserted negatively
from the assembled items. F15 stays open for `providers` and `ingestion`.

`FORGE-EVO-001` is REDIRECTED. It demonstrated two Finish Contract clauses that had
implementations and no demonstration: discovery validating or rejecting a specification
change with lineage, and local, remote and runtime effects reconciling separately. The
contract says producing a packet is insufficient, so the proof registers a packet
against the evolved specification hash and shows one against the superseded hash
refused. Restart from disk replaying to the same state is proved in the same packet.

The trust-pinned `FORGE-INTEGRATED-001` (COMPLETE) candidate `15366f9` passed
detached independent review. With its external receipt, `scripts/validate.sh`
passed all 20 gates, including 557 tests, exit 0. No V0 completion claim follows.
`FORGE-SENTINEL-001` (BLOCKED) is a local proving run against a
resettable Sentinal clone: six baseline Windows validation tests fail, 411 other
tests pass, and three skip. Its first owner-authorized DeepSeek invocation ended
UNKNOWN without a provider receipt or proposal; billing is UNKNOWN. The core
ledger verifies two receipts at checkpoint head 3bfd2bf; the claim remains and
blocks retry. At that checkpoint the Sentinal clone was unchanged. See the packet's UNKNOWN artifact.
The owner reports that first attempt charged $0.03; this is owner-reported
billing, not a recovered provider response. `FORGE-SENTINEL-002` (COMPLETE)
used a separate claim, disabled thinking, and recorded response diagnostics.
Its one authorized call returned a schema-valid proposal under a three-receipt
ledger at head `aee9d815`. Astra returned FIX for first local target `a9c464b`;
a bounded local repair produced clean target `61258ab`. Its 422 tests pass with 3
skips, and the research runner passes with the isolated venv active. A fresh
independent review passed exact Forge `8c6cbfd` and Sentinal `61258ab`. This
completes the bounded local run; there is no remote effect or V0
completion claim.

## Completion audit correction (2026-09-23)

The controlled Hallam trial is complete and independently accepted. Exact Hallam
commit `93a2015e58f2c7be7fe95c6676279d1e4a54ec13` is available on verified remote
branch `codex/forge-external-trial`; it remains unmerged and undeployed.

The controller repairs discovered by final validation are independently accepted:
`FORGE-EXT-TEST-001` is COMPLETE, `FORGE-RECON-004` is COMPLETE,
`FORGE-VAL-LF-001` is COMPLETE, and `FORGE-EXT-PORT-001` is COMPLETE. The core
reconciliation stream retains its first eight receipts byte-for-byte and now has
11 verified receipts at head `7976fc9958c86a69b6392e165cade9cf0b8cb89ea4b9f3ac2e718e8346878f46`.
Fresh Windows checkouts preserve the validation runner as LF/mode 100755, the
external-trial tests no longer read a mutable Hallam checkout, and audited lesson
artifacts verify across LF and CRLF without weakening their authority fields.

No additional provider call occurred during these repairs. Nothing in Forge was
pushed, merged, or deployed. The independent audit of exact `efed3e8` returned
CORRECT and opened `FORGE-SENTINEL-003`, which is now COMPLETE after an
independent Astra ACCEPT on exact Forge candidate `0ede5c8`. The retained release
packet binds the actual Sentinel discovery and corrected requirement to a current
post-evolution revalidation of exact Sentinel `61258ab`, its earlier independent
audit, and remote merge `7c2f639`, without claiming that the later specification
hash retrospectively governed the historical repair. The 14-receipt core stream
reloads and resumes from its receipt-seven checkpoint without repeating the target
test effect; its head is `06dcd5773eaaab4bbce804a53696a8dda744027d46a993d20ba2211e07c00c5f`.

## Finish Contract, clause by clause

| clause | state |
| --- | --- |
| candidate-bound evidence per active requirement | met; final exact-candidate validation and completion audit pending |
| Governor enforces state, scope, authority, budgets, transitions | met (budgets: FORGE-GOV-001) |
| builder and auditor authority separated | met, structurally and exercised by independent bounded audits |
| candidate mutation invalidates audit | met |
| append-only receipts support deterministic replay | met, demonstrated |
| interrupted actions reconcile without duplicate effects | met, demonstrated |
| UNKNOWN blocks unsafe continuation | met |
| discovery validates or rejects spec changes with lineage | met; actual Sentinel discovery, lineage, superseded-hash refusal, and current evolved-hash execution independently accepted |
| stuck resolution requires materially different strategies | met |
| outcome and lesson records attributable and scoped | met |
| self-improvement changed a later decision and improved an outcome | met by EXT-001 to EXT-002: a validated lesson changed the real diagnostic strategy and independently measured `unexplained_external_refusals` from 1 to 0; harmful-lesson rollback remains demonstrated |
| Sentinel proving ground produces a reviewable evidence packet | met by independently accepted `FORGE-SENTINEL-003` COMPLETE release packet |
| controlled external repository trial | met by independently accepted FORGE-EXT-003 and verified Hallam remote `93a2015` |
| critical contradictions and discoveries resolved or owner-governed | met; prior completion-audit contradictions resolved by accepted bounded evidence |
| local, remote and runtime state reconciled separately | met, demonstrated and re-derived by the repository gate |
| independent strategic audit returns a completion-candidate verdict | final fresh exact-candidate audit pending after state reconciliation |

## What still blocks V0

The bounded implementation and evidence obligations are met. `FORGE-SENTINEL-003`
and the real `FORGE-SI-001` episode are COMPLETE. Independent Astra returned
`COMPLETE_CANDIDATE` for exact clean candidate
`5fde0fce8103968a57aa4d1f298efadebc71ca0b` after the documented gate and a fresh
`core.autocrlf=true` checkout both passed 766 tests. This is V0 completion evidence
for the owner's merge decision; it does not itself merge or deploy anything.

## Earlier direction

`FORGE-FIX-000` is complete under owner authorization, absorbing FORGE-FIX-001,
-002, and -003. It closed the eight findings of the 2026-09-21 audit: the runtime
is installable, the provider layer speaks each family's actual wire format, audit
independence no longer depends on mutable global state, path scope is decided
deterministically, the evidence ledger is durable, every gate runs in one local command, and
one real Build Packet has been driven through packet → build → audit →
merge-eligibility → receipt → reload against real repository state.

`FORGE-SPD-002` is COMPLETE: the Context Engine with
role budgets (Canonical S32-33). It makes two independence properties structural
rather than prompted — a Builder cannot be given the specification, and an
Auditor cannot be given Builder reasoning — and gives every context item
provenance, a hard per-role budget, and a size receipt that FORGE-LRN-002 will
consume.

The proving harness now drives any packet by id, reading scope from the packet
document rather than a second copy in code, so the governed loop is no longer
tied to the one packet it was written for.

That earlier checkpoint left the real self-improvement gate open. `FORGE-SI-001` is now COMPLETE
through the separately retained real episode; automatic global promotion remains
disabled, and protected governance remains outside autonomous self-modification.

`FORGE-ING-001` is COMPLETE: the Intent Ingestion Protocol turning free-text
owner intent into a signed Mission. It was written before FORGE-FIX-000 declared
the runtime's dependencies, so its own test suite had never executed — its
builder recorded the pytest result honestly as UNKNOWN rather than claiming a
pass. Rebased onto current `main` it runs, and its eight tests pass.

## Known unknowns

- Public licensing has not been selected.
- General model/provider selection remains configurable. One live `Capability.CODING`
  request used the DeepSeek `deepseek-flash` API ID from an ignored `.env` file;
  other routed capabilities and provider families remain unproven live. The
  one-call runner pins that approved ID as a preflight requirement, not as a
  provider fallback. No credential is committed to source.
- Persistence beyond the append-only evidence ledger remains unselected.
- Role signing keys in the proving slice are process-local. Durable key custody
  is unsolved and is not claimed by any completed node.
- Agent roles in the proving slice are simulated. The loop's control flow is
  proven; the quality of real agent output is not yet measured.
- The earlier and final phase numbering differ; ADR-0002 preserves all
  obligations while making the final sequence authoritative.
