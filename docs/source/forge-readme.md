# Forge Agent

Forge Agent is a local-first, evidence-governed engineering runtime.

> Build what we know. Discover what we don't.

Forge turns owner intent into bounded engineering work, executes that work inside explicit authority, independently verifies candidates, captures discoveries from implementation evidence, evolves a living specification, recovers from failure, and retains validated lessons.

## Repository status

**Phase:** Phase 0 complete — governed loop proven end to end on this repository
**Implementation:** Derived from [`.agent/graph/work-graph.json`](.agent/graph/work-graph.json)
**Canonical product authority:** [FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md](FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md)
**V0 requirements:** [FORGE_AGENT_V0_PRD.md](FORGE_AGENT_V0_PRD.md)

No document in this repository asserts execution state. The work graph and the
evidence ledger hold it; prose points at them. `forge graph check` fails the
build when a document contradicts the graph — the drift that survived five
merges before it existed.

Run `forge graph check` for node status and `forge ledger verify <packet>` for
the receipts behind a completed packet.

## Validation

```bash
pip install -e ".[dev]"
./scripts/validate.sh
```

**This is the only validation authority.** There is no CI; validation runs
locally, on a machine the owner controls, and its result is recorded as evidence
(DEC-009). Nothing runs these gates on your behalf, so "validated" means somebody
ran this and read the output. An unrun gate is UNKNOWN, never a pass.

The gates: import surface, lint, format, tests, document/graph consistency,
ledger chain integrity for every stream, and candidate binding for packets under
development. `tests/test_gate_parity.py` asserts the set, so a gate cannot be
dropped silently now that no second copy exists to disagree.

## Credentials

```bash
cp .env.example .env     # then fill in the values
```

`.env` is git-ignored; `.env.example` carries names only. Model ids are
configuration with no in-code default, so an unset variable stops the call
rather than reaching for a stale identifier. No test needs credentials — every
test injects a fake transport, and none may make a live model call.

`BUILDER_MODEL` takes a DeepSeek API model ID such as `deepseek-flash`, not its display name.

## Canonical doctrine

```text
Stable Intent
→ Living Specification
→ Adaptive Execution
→ Evidence
→ Discovery
→ Better Specification
→ Validated Learning
```

Probabilistic intelligence proposes. Deterministic infrastructure controls. Evidence decides.

## V0 sequence

Phase 0 (`FORGE-FIX-000`) is complete: the runtime is installable, deterministic
gates run locally under `./scripts/validate.sh` (DEC-009 — there is no CI), the
evidence ledger is durable, and one real Build Packet has
been driven through packet → build → audit → merge-eligibility → receipt →
reload. Evidence: [`.agent/artifacts/FORGE-FIX-000/`](.agent/artifacts/FORGE-FIX-000/).

1. Trust kernel
2. Product Brain and Living Specification
3. Architect–Builder–Auditor loop
4. Evidence ledger and replay
5. Discovery and governed specification evolution
6. Stuck resolution and bounded recovery
7. Outcome and lesson engines
8. Restart and interruption proving
9. Sentinel proving ground
10. Controlled external repository trial

## Design system

The product's user interface is built in a separate design-system kit:
[`renzo-ui/`](renzo-ui/) — a warm-ivory, EB Garamond, classic-gold aesthetic
inspired by Renzo Piano. The kit ships seven screens (Home, Building, Done,
First-visit, Manifesto, Journal, Landing) plus a printable A4 Studio Card.
See [`renzo-ui/README.md`](renzo-ui/README.md) for the full kit.

The product running on this runtime surfaces only three moments: a question,
a quiet "working on it," and a "here you go." All internal architecture
(the Architect–Builder–Auditor loop, the evidence ledger, the Governor) is
invisible to the user. The design system enforces that.

## Repository map

```text
.agent/graph/           the work graph — the authority on node status
.agent/ledger/          durable append-only evidence receipts
.agent/tasks/           bounded task packets
.agent/artifacts/       per-packet completion, review, and slice evidence
docs/adr/               architectural decision records
docs/audit/             independent repository audits
docs/finish-contract.md repository-level completion contract
src/forge/              trust kernel, product brain, execution loop, providers
scripts/run_slice.py    drives one real packet end to end
scripts/validate.sh     runs every gate; the only validation authority (DEC-009)
tests/                  deterministic validation surface
```

## Current boundary

No deployment, production integration, external communication, spending, or
destructive action is authorized. Model provider calls are implemented but are
never made by the test suite or by any gate; agent roles in the proving slice are
simulated, and the slice's own evidence records that limit rather than eliding
it. Merge eligibility is computed by the Governor and acted on by a human.
