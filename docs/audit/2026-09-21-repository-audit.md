# Repository audit — 2026-09-21

Independent audit of `main` at `5d95622`, commissioned by the owner.

## Findings

### F1 — Nothing in the repository executes (severity: structural)

`trust_kernel.py`, `product_brain.py`, and `execution_loop.py` are a pure in-memory
state machine: no filesystem, subprocess, git, network, model call, or entrypoint.
The 69 passing tests prove the transition rules are correct. They prove nothing about
whether Forge can build software.

### F2 — Ledger has no durable storage (severity: structural)

`Ledger` exists only in process memory. `to_records()` is never written anywhere.
The Finish Contract requires deterministic replay and interrupted-effect
reconciliation; both are unsatisfiable against a ledger that dies with the process.

### F3 — The Anthropic provider route cannot work (severity: critical)

`model_provider.py` routed `HIGH_REASONING` — the Architect seat and the final-gate
audit — through an OpenAI-shaped call to `api.anthropic.com`. Four independent
defects: Anthropic exposes `/v1/messages`, not `/chat/completions`; authenticates
with `x-api-key`, not `Authorization: Bearer`; takes `output_config.format`, not
`response_format`; and the configured model id `claude-fable-5.1` is malformed
(ids use hyphens). The route would 404 on first call. It was never detected because
nothing has ever executed that path.

### F4 — `audit_call` mutated global routing state (severity: high)

Cross-family audit independence was implemented by temporarily mutating a
module-global `ROUTING` dict. Under the planned parallel scheduler (FORGE-SPD-001),
concurrent audits would silently route to each other's provider, defeating the
independence guarantee the architecture treats as structural.

### F5 — Undeclared dependencies made both new modules uninstallable (severity: high)

`pyproject.toml` declared no dependencies while the code imported `httpx`,
`pydantic`, `typesafe-sdk`, and `python-dotenv`. `forge/__init__.py` did not export
either subpackage, so the test suite stayed green while both were unimportable.

### F6 — Decision-layer defects (severity: medium)

Configured timeout never passed to the SDK; client never closed; a second, divergent
`Capability` enum that cannot index the provider routing table; `autonomy_gate`
interpolating a score the module's own docstring declares non-interpolable; and
deterministic glob scope checking delegated to a probabilistic model despite
`trust_kernel` already deciding it with `fnmatch`.

### F7 — No continuous integration (severity: high)

No automated gate of any kind. Tests, lint, and the Python floor were enforced by
memory alone, in a repository whose thesis is that deterministic infrastructure
controls.

**Resolution amended (2026-09-21, DEC-009).** The workflow added for this finding
never scheduled a job: four attempts across three commits and a manual re-run all
died before executing a step, with no logs and an empty check result. The finding
stands, but its resolution is now `scripts/validate.sh` run locally rather than a
hosted runner. The gap this leaves is real and named in DEC-009: nothing runs the
gates on anyone's behalf.

### F8 — Governance drift (severity: medium)

`README.md` claimed implementation had not started while five modules were merged.
`.agent/CURRENT_STATE.md` declared work blocked with no READY node, after which 713
lines of runtime code merged under `PROPOSED` nodes — a direct violation of the
"select only READY work" rule in `AGENTS.md`.

## Verified clean

No secrets in history. `.gitignore` covers `.env` and `.env.*`. Working tree clean.
`typesafe-sdk` and `api.typesafe.ai` confirmed to exist; the decision layer's
question and answer types match the real SDK.

## Disposition

All findings are addressed by packet `FORGE-FIX-000` under owner authorization.
