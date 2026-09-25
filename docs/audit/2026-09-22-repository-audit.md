# Repository audit — 2026-09-22

Independent audit of `main` at `df51dfa`, commissioned by the owner. Every finding
below was reproduced by execution, not inferred from reading.

## Verified state

All nine gates green under Python 3.12: 222 tests, lint, format, import surface,
document/graph consistency, three ledger chains, slice bind-check. No secrets in
history. Working tree clean. The eight findings of the 2026-09-21 audit are
genuinely closed rather than papered over.

## Findings

### F9 — The A3 guardrail protects 2 of 12 governance surfaces (severity: critical)

`_path_requires_a3` in `execution_loop.py` decides which packets need explicit
owner authority. Its denylist was written against a hypothetical file layout —
`governor.py`, `authority.py`, `policy.py`, `evidence_ledger.py`, `secrets.py` —
and **none of those files exist in this repository**. Measured against the real tree:

| path | requires A3 |
| --- | --- |
| `src/forge/trust_kernel.py` | yes |
| `AGENTS.md` | yes |
| `src/forge/ledger_store.py` | **no** |
| `src/forge/config.py` | **no** |
| `src/forge/paths.py` | **no** |
| `src/forge/cli.py` | **no** |
| `src/forge/providers/model_provider.py` | **no** |
| `src/forge/decisions/jev_decisions.py` | **no** |
| `src/forge/context_engine.py` | **no** |
| `scripts/validate.sh` | **no** |
| `scripts/run_slice.py` | **no** |
| `.agent/graph/work-graph.json` | **no** |

`AGENTS.md` protects "future Governor, authority, policy, and evidence-ledger
modules". The evidence-ledger module in this repository is named
`ledger_store.py`, so the guardrail does not see it. `AGENTS.md` protects
secrets; the secrets surface here is `config.py`, which the guardrail does not
see either.

The sharpest pair is `scripts/validate.sh` and `.agent/graph/work-graph.json`.
Under DEC-009 `validate.sh` is the *sole* validation authority, and the graph is
the sole authority on node status. Both are writable by a routine A1 packet. A
builder could promote its own node to READY and delete the gate that would have
caught it, and no authority check would fire. The guardrail is a denylist
maintained by hand against names that were never real.

### F10 — A crash between receipt and checkpoint bricks a ledger stream (severity: high)

`LedgerStore.append` writes and fsyncs the JSONL record, then writes the
checkpoint. A crash in that window leaves the JSONL at N+1 and the checkpoint at
N. `load()` re-derives the chain, compares it to the sidecar, and raises
`LEDGER_CHECKPOINT_MISMATCH` — permanently, because `load()` is the only reader
and `verify`, `replay`, and the `validate.sh` ledger gates all route through it.
The only escape is `rebind()`, which discards the evidence.

Reproduced by rewinding a real checkpoint one receipt behind its JSONL.
`tests/test_ledger_store.py:122` covers the opposite direction (JSONL behind the
checkpoint) and nothing covers this one. The module exists to satisfy the Finish
Contract's "interrupted actions reconcile without duplicate effects"; it cannot
currently survive an interruption in its own write path. The parent directory is
also never fsynced after `os.replace`, so the checkpoint rename is not durable on
all filesystems.

### F11 — `AUDITOR_MODEL` is unreachable; routine audits use `EXEC_MODEL` (severity: high)

`ProviderSpec.model_env` is keyed to the provider, not the capability.
`ROUTINE_AUDIT` and `EXEC_DEBUG` both route to `kimi`, so both resolve
`EXEC_MODEL`. `AUDITOR_MODEL` belongs to the `openai` spec, and no capability
routes to `openai`, so the variable `.env.example` documents as "ROUTINE_AUDIT —
per-packet review" is never read by anything.

`independent_auditor()`'s fallback compounds it: it returns the first
different-family provider in `PROVIDERS` insertion order, which for a
moonshot-produced candidate is `anthropic`. A routine audit then silently runs on
`ARCHITECT_MODEL`, inverting the "cheap builder, strong independent auditor"
economics the module documents, with no receipt recording the escalation.

### F12 — The F3 fix is guarded by tests that cannot fail if it is wrong (severity: high)

`tests/test_model_provider.py:62-90` asserts that the Anthropic adapter sends
`/v1/messages`, `x-api-key`, and `output_config`, against an injected fake
transport. It asserts that the adapter sends what its author wrote it to send.
That pins a belief about the wire contract, not the contract.

F3 was precisely "four simultaneous defects on the most important route, never
detected because nothing had executed that path". The path still has not
executed. The defect class is unchanged and now has a green test in front of it.
Only one live call, recorded as evidence, closes this. Until then the route is
UNKNOWN, not verified.

### F13 — `.env.example` violates DEC-010 (severity: medium)

DEC-010 states `.env.example` "carries every variable name and no value", and the
file's own header repeats it: "This file carries NAMES ONLY and never a value."
It ships two values: `ARCHITECT_MODEL=claude-fable-5-1` and
`JEV_MODEL=jev-1.13.0`. `README.md` and `.agent/CURRENT_STATE.md` both claim "no
model id is committed to source".

### F14 — Live README contradiction the consistency gate cannot see (severity: medium)

`README.md:31` says "There is no CI". `README.md:69` says "deterministic gates run
in CI". DEC-009 sides with line 31.

`forge graph check` passes because it only tests two things: the literal string
"not started", and whether a node's status word appears within 200 characters of
a **backticked** node id. It is keyword proximity, not contradiction detection.
Unbackticked ids are invisible — `.agent/CURRENT_STATE.md` mentions
`FORGE-FIX-001` that way — and a document asserting a wrong status alongside the
right one passes.

### F15 — Four subsystems are built, tested, and wired to nothing (severity: structural)

`providers/model_provider.py` (408 lines), `decisions/jev_decisions.py` (468),
`context_engine.py` (445), and `ingestion/` (~440) total roughly 1,760 lines that
`execution_loop.py` does not import. `forge/__init__.py:3-7` states the reason
plainly: "They were previously unreferenced." No model call has ever been made
from this repository, and the proving slice's agent roles are simulated.

`forge.ingestion` is not exported from `forge/__init__.py` at all, so the "import
surface" gate — added specifically to catch an undeclared dependency inside a
subpackage nothing imports — does not cover it.

Prior-audit F1 therefore remains substantially open. Eight graph nodes are
COMPLETE; none of them connects owner intent to a model to code.

**Partially resolved (2026-09-22, FORGE-INT-001).** `context_engine.py` and the
Governor's budgets are now wired into `scripts/run_slice.py`: the harness assembles
each role's context under the real policy and per-role budgets, and the slice
evidence records each role's context digest, size receipt, included source types and
the source types the policy refused. Both independence properties are now asserted
negatively from the assembled items rather than claimed in prose.

`providers` and `ingestion` are **not** wired, and this finding stays open for them.
Stages one through three of the Intent Ingestion Protocol call a model, so carrying
a signed `Mission` end to end is blocked on the same live call F12 is blocked on.
`decisions/jev_decisions.py` stays unwired too: it advises a Governor that has no
model to advise about yet. Wiring either to a fake would produce a seam that has
never carried the traffic it exists for, which is the F12 mistake in a new place.

### F16 — `requires-python = ">=3.12"` with no pinned toolchain (severity: low)

The interpreter on PATH here is 3.11, and `pip install -e ".[dev]"` fails on a
Python-version error rather than a diagnosable one. When `validate.sh` is the
only authority and nothing runs it on anyone's behalf, the most likely cause of
an UNKNOWN gate is the operator's interpreter. The floor deserves to be gate
zero.

## Verified clean

Trust kernel fail-closed behaviour holds: HMAC-signed evidence, hash-chained
receipts, replay that revalidates prerequisites, builder/auditor context
disjointness enforced in `__init__`. `paths.py` correctly normalizes traversal
before matching and fails closed on all three empty/unsafe edges.
`LedgerStore.write` refuses to overwrite a divergent history and confines
evidence destruction to an explicit `rebind`. F4 and F6 from the prior audit are
properly fixed, not suppressed.

The honesty discipline is the repository's most valuable asset and is intact:
`run_slice.py:12` states that no model is called rather than implying one is, and
FORGE-ING-001's builder recorded an unrunnable test suite as UNKNOWN rather than
claiming a pass.

## Proportion

8,680 lines of prose, 5,787 of source, 4,219 of tests. The canonical architecture
runs to 7,670 lines describing sections past S266, against 25 graph nodes of
which 14 remain PROPOSED. The governance layer is more mature than the thing it
governs, which is the structural risk: this repository is good enough at proving
things about itself that it can score green indefinitely without executing the
one path that matters.

## Disposition

F9-F11, F13, F14, and F16 are repairs of defects in already-merged code and are
addressed by `FORGE-FIX-004` under DEC-006. F15 is addressed by `FORGE-INT-001`.
F12 cannot be closed without a live model call and is recorded as UNKNOWN.
