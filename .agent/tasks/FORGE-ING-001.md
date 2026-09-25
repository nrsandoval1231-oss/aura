# FORGE-ING-001 — Intent Ingestion Protocol

## Objective

Implement the four-stage Intent Ingestion Protocol that turns a beginner's free-text intent (e.g. "I want to build an ERP for my business") into a signed, evidence-ready Mission: DECOMPOSE (provisional North Star + requirement skeleton + Ambiguity Map), CALIBRATE (Jev-ranked interview, max 5 questions by value-of-information), REFINE (plain-language Owner Contract read-back with correction loop and explicit owner signature), HANDOFF (Mission object into the existing execution loop). Full contract: `docs/packets/FORGE-ING-001-intent-ingestion.md`.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Remote: `https://github.com/nrsandoval1231-oss/forge-agent.git`
- Branch: `codex/forge-ing-001`
- Base SHA: `181a39ef80100fc52d2ec0e148c819b6461aa2ec`
- Python: `>=3.12`

## Allowed files

- `src/forge/ingestion/**`
- `tests/ingestion/**`
- `schemas/owner_contract.schema.json`
- `.agent/tasks/FORGE-ING-001.md`
- `.agent/artifacts/FORGE-ING-001/**`
- `.agent/graph/work-graph.json`
- `pyproject.toml`

## Explicit exclusions

Governor, trust kernel, execution-loop internals, Finish Contract semantics, canonical architecture, PRD, AGENT_RULES, AGENTS.md, protected policy. Ingestion PRODUCES owner contracts; it never redefines what contracts mean. No voice input, no multi-language, no non-text upload parsing, no post-signature North Star mutation.

## Dependencies and invariants

- FORGE-TK-001, FORGE-PB-001, FORGE-LOOP-001 are complete and unchanged.
- Owner authorization is the pasted continuation request for this packet.
- Every stage transition produces a durable receipt; receipts are append-only.
- Missing or ambiguous evidence is UNKNOWN, never success.
- Decompose output is PROVISIONAL with confidence labels (Canonical S66).
- Seed requirements must trace to intent text or be flagged `inferred`.
- Scope honesty invariant: out_of_scope must be non-empty and shown to the owner.
- V1-honesty invariant: the Finish Contract describes a verifiable vertical slice, never the totality of a category product.
- Interview is derived, not scripted: max 5 questions, only where answers change architecture; deterministic zero-question path when no blocking ambiguities exist.
- All owner-facing text passes the jargon filter; every question carries why_we_ask.

## Acceptance checks

1. Raw intent string produces valid Ambiguity Map (>= 8 ambiguities) and <= 12-requirement skeleton. (pytest + schema validation)
2. CALIBRATE asks <= 5 questions; each asked question has materially_changes > 0.6 receipt. (receipt inspection)
3. Zero-blocking-ambiguity intent asks ZERO questions. (unit test)
4. Owner Contract passes jargon filter and non-empty out_of_scope invariant. (unit test)
5. Free-text owner correction updates assumptions with lineage preserved. (integration test vs Product Brain)
6. Handoff Mission is accepted unmodified by FORGE-LOOP-001 machinery. (integration test)
7. Crash between CALIBRATE and REFINE resumes without re-asking answered questions. (restart test)
8. Validation commands pass: `python -m pytest`, `python -m ruff check .`, `python -m compileall -q src tests`, `git diff --check`.

## Authority, risk, and retry budget

- Authority: A1 implementation within this packet; the signed North Star artifact produced at runtime is owner-controlled by definition.
- Risk: beginner-facing contract language must not overpromise; fail closed on contract-invalid output.
- Repair budget: two materially different bounded repairs.

## Model usage

- HIGH_REASONING (Claude Fable 5.1) for DECOMPOSE and REFINE via `src/forge/providers/model_provider.py`.
- Jev (pinned jev-1.13.0) for CALIBRATE triage via `src/forge/decisions/jev_decisions.py`.
- Jev state per call <= 32k tokens; no arithmetic/date questions to Jev.

## Required handoff artifacts

- `.agent/artifacts/FORGE-ING-001/COMPLETION.json`
- `.agent/artifacts/FORGE-ING-001/REVIEW.json`
- exact candidate SHA, tree SHA, changed files, command results, remaining UNKNOWNs.
