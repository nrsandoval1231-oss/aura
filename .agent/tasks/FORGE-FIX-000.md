# FORGE-FIX-000 — Phase 0 repair and first vertical slice

## Objective

Make the merged runtime installable, verifiable, and executable. Close the defects
identified by the repository audit of 2026-09-21, give the evidence ledger durable
storage so the Finish Contract's replay and reconciliation obligations become
satisfiable, and prove the Architect-Builder-Auditor loop once end to end against
this repository.

This packet absorbs FORGE-FIX-001, FORGE-FIX-002, and FORGE-FIX-003. They are merged
into one packet because they are not independent: the vertical slice cannot run until
the dependencies are declared and the provider is correct, and the provider defect is
only observable by running the slice.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Remote: `https://github.com/nrsandoval1231-oss/forge-agent.git`
- Branch: `claude/repo-audit-kzeivx`
- Base SHA: `5d95622cac8ff8838429ad293dfc0791e34095e0`
- Python: `>=3.12`

## Authority

- **Owner authorization:** explicit owner instruction "Proceed with all of your
  suggestions" (2026-09-21), issued in response to the audit that enumerated every
  change in this packet. Authority order places owner intent above all repository
  documents.
- **Authority class:** A1 for source, tests, packaging, and CI. A3 for the
  `AGENTS.md` amendment and `DECISIONS.md` entry, covered by the owner
  authorization above.

## Allowed files

- `src/forge/**`
- `tests/**`
- `pyproject.toml`
- `.github/workflows/**`
- `scripts/**`
- `.agent/tasks/FORGE-FIX-000.md`
- `.agent/artifacts/FORGE-FIX-000/**`
- `.agent/ledger/**`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/DECISIONS.md`
- `AGENTS.md`
- `README.md`
- `docs/audit/**`

## Explicit exclusions

Canonical architecture, V0 PRD, AGENT_RULES, the Finish Contract, intent ingestion
(FORGE-ING-001), the parallel scheduler, the full Learning Engine, autonomous merge,
deployment, secrets, and any outbound network call made as a side effect of the test
suite.

## Dependencies and invariants

- No live model provider call is made by any test. Provider transport is exercised
  through injected fakes only.
- Cross-family audit independence is enforced structurally, never by prompt and never
  by mutable global state.
- Path scope is decided deterministically in code, never delegated to a model.
- Missing or ambiguous evidence remains `UNKNOWN`.
- The ledger remains append-only; persistence adds durability, not mutability.
- Global automatic lesson promotion remains disabled.
- Protected governance remains outside autonomous self-modification; the
  `AGENTS.md` change in this packet is owner-authorized, not self-authorized.

## Acceptance checks

1. `pip install -e .` succeeds on Python 3.12 and `import forge` pulls in the
   providers and decisions subpackages.
2. `pytest` passes; new tests cover the provider routing table, the Anthropic
   adapter shape, audit family independence under concurrency, the decision layer,
   and ledger persistence round-trip.
3. `ruff check` and `ruff format --check` are clean.
4. The doc-vs-graph consistency check fails when a document contradicts
   `work-graph.json` and passes on the reconciled tree.
5. A ledger written to disk reloads, verifies its hash chain, rejects tampering, and
   replays to the same mission state.
6. One real Build Packet completes packet to build to audit to merge-eligibility to
   receipt to replay, with artifacts committed under `.agent/artifacts/FORGE-FIX-000/`.

## Retry budget

Two materially different bounded repairs per failing acceptance check, per
`.agent/AGENT_RULES.md`.

## Required handoff artifacts

- `.agent/artifacts/FORGE-FIX-000/COMPLETION.json`
- `.agent/artifacts/FORGE-FIX-000/REVIEW.json`
- `.agent/artifacts/FORGE-FIX-000/SLICE.json`
- `.agent/ledger/FORGE-FIX-000.jsonl` and its checkpoint
