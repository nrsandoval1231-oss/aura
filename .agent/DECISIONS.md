# Decisions

## DEC-001 — Separate repository

**Status:** Accepted
**Decision:** Forge Agent is an independent repository and product boundary.
**Reason:** It must remain reusable and must not inherit authority from Nucleus, Hermes, GridLens, or any proving-ground repository.

## DEC-002 — Documentation-first foundation

**Status:** Accepted
**Decision:** The first repository slice contains canonical product authority, governance, graph state, ADRs, and validation scaffolding only.
**Reason:** Implementation must not accidentally redefine the product before authority and completion boundaries are durable.

## DEC-003 — Local-first V0

**Status:** Accepted
**Decision:** V0 begins as one local process with deterministic control and explicit external effects.
**Reason:** This is the smallest architecture capable of proving the core thesis.

## DEC-004 — Final proving sequence precedence

**Status:** Accepted
**Decision:** Architecture Section 267 controls ordering; Sections 247–258 remain mandatory capability gates mapped by function.
**Reason:** The final sequence is the latest explicit ordering, while the earlier sections contain requirements that must not be discarded.

## DEC-005 — Trust-kernel packet and learning evidence boundary

**Status:** Accepted for FORGE-TK-001
**Decision:** Begin the deterministic trust kernel on a dedicated feature branch. The packet must preserve attributable outcome, candidate-lesson, scope, retrieval, changed-decision, metric, and rollback evidence for the later self-improvement proof, while automatic global promotion and protected self-modification remain disabled in V0.
**Reason:** Canonical Sections 216–222, 233, 238, 263, and 268 require validated experience to change future engineering behavior without weakening governance.

## DEC-006 — Phase 0 repair packet and the repair carve-out

**Status:** Accepted
**Decision:** Authorize `FORGE-FIX-000` to absorb FORGE-FIX-001/002/003 as a single
bounded packet, and amend `AGENTS.md` so that repair of a defect in already-merged
code does not require a new `READY` graph node.
**Reason:** The 2026-09-21 audit found a critical defect on the `HIGH_REASONING`
route that had survived merge precisely because nothing executed it. Under the
unamended rule, fixing a known-broken critical path was procedurally blocked until a
new node was authorized. Governance that obstructs its own repairs gets bypassed,
which costs both the repair and the governance. The carve-out is bounded: it permits
restoring merged code to its already-approved intent, and it permits nothing new.

## DEC-007 — Durable evidence ledger

**Status:** Accepted
**Decision:** The evidence ledger persists as append-only JSONL with a separate
checkpoint file, under `.agent/ledger/`.
**Reason:** The Finish Contract's replay and interrupted-effect reconciliation
obligations cannot be satisfied by an in-memory ledger at any future date. A
separate checkpoint makes truncation detectable rather than silent. JSONL is chosen
over a database because V0 is local-first and the append-only property should be
visible in the file format itself.

## DEC-008 — Provider adapters are per-family, not per-registry-row

**Status:** Accepted
**Decision:** Each provider family supplies its own transport adapter. Model
identifiers come from configuration with no in-code fallback.
**Reason:** Treating Anthropic as an OpenAI-compatible registry row produced four
simultaneous defects on the most important route. In-code default model ids also
decay silently; absent configuration must fail closed rather than reach for a stale
identifier.

## DEC-009 — Validation is local, not hosted

**Status:** Accepted
**Decision:** `scripts/validate.sh` is the single validation authority. The
GitHub Actions workflow is removed, and no hosted runner gates this repository.
**Reason:** The workflow never once scheduled a job — four attempts across three
commits and a manual re-run all died before executing a step — so it enforced
nothing while appearing to. A gate that cannot run is worse than no gate: it
produces a red badge everyone learns to ignore, which is how a real failure gets
ignored too. Local validation is honest about where the authority sits, and the
owner controls the machine it runs on.
**Obligation this creates:** nothing runs the gates on anyone's behalf. A
validation claim without a recorded local run is UNKNOWN, not a pass, and
`tests/test_gate_parity.py` now asserts the required gate set directly because
the second copy that used to catch a dropped gate is gone.

## DEC-011 — One protected-surface registry, asserted against the filesystem

**Status:** Accepted
**Decision:** `src/forge/policy.py` is the single source of truth for which paths
require A3 owner authority. Declared surfaces that exist are listed in
`PROTECTED_PATHS` and `tests/test_policy.py` asserts every one of them is present
in the working tree; surfaces that do not exist yet live in a separate
forward-looking set, which is deliberately exempt from that assertion.
`execution_loop._path_requires_a3` delegates here and keeps no list of its own.
**Reason:** The 2026-09-22 audit (F9) measured the previous denylist against the
real tree and found it protecting two surfaces out of twelve. It had been written
against a file layout nobody built — `governor.py`, `authority.py`,
`evidence_ledger.py`, `secrets.py` — while the real evidence ledger
(`ledger_store.py`), the real secrets surface (`config.py`), the sole validation
authority (`scripts/validate.sh`), and the sole authority on node status
(`.agent/graph/work-graph.json`) were all writable by a routine A1 packet. A
builder could have promoted its own node to READY and deleted the gate that would
have caught it.

The root cause is not the missing entries. It is that a list of names nobody checks
against the filesystem decays silently, and decays toward permitting more. So the
correction is the existence assertion rather than a longer list: a protected
surface that stops being real now fails the build instead of quietly protecting
nothing.
**Obligation this creates:** moving or renaming a governed module is no longer a
free refactor — the registry entry moves with it or the build fails, which is the
intended cost. Adding a governance module means adding it here in the same packet.

## DEC-012 — Recovery from a crash between the two ledger writes

**Status:** Accepted
**Decision:** A ledger stream whose JSONL is *ahead* of its checkpoint is
recoverable, not corrupt. `load` reports it as `LEDGER_CHECKPOINT_BEHIND` and
refuses; a separate `recover` re-pins the checkpoint after verifying that the
receipts the old checkpoint pinned are still exactly what it pinned. A stream whose
JSONL is *behind* its checkpoint is still refused outright.
**Reason:** Audit F10 found that a crash in the one-line window between the receipt
write and the checkpoint write made a stream permanently unloadable, since `load`
is the only reader and `verify` and `replay` both route through it. The only escape
was `rebind`, which discards evidence. A module whose stated purpose is satisfying
the Finish Contract's interrupted-effect obligation could not survive an
interruption in its own write path.

Recovery is deliberate rather than automatic because the checkpoint's security value
is pinning the head: the chain is hash-linked with no secret, so anyone who can
write the JSONL can append a well-formed continuation. Silently accepting any chain
that extended the pinned head would leave the sidecar detecting truncation only,
trading F10 for a worse defect. The prefix check is what makes the explicit call
safe.
**Obligation this creates:** the two directions of checkpoint disagreement must stay
distinguishable. Collapsing them back into one error code re-opens F10.

## DEC-010 — Credentials live in an ignored `.env`, names in `.env.example`

**Status:** Accepted
**Decision:** Provider credentials and model ids are read from the environment,
loaded from a git-ignored `.env` at the repository root. `.env.example` carries
every variable name and no value.
**Reason:** Model ids are configuration, not code, and secrets must never be
committed. Keeping the example in the repository means a missing credential is a
named, discoverable stop rather than a mystery, while the value itself never
enters version control. `load_env` refuses to override a variable already set, so
a deliberate shell export always beats a file on disk.
