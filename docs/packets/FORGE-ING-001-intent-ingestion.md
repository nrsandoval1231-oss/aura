# FORGE-ING-001 — Intent Ingestion Protocol

**Status:** PROPOSED (awaiting owner approval → READY_AUTHORIZED)
**Node type:** Feature (new subsystem)
**Authority:** A1 implementation; the signed North Star artifact it produces is owner-controlled by definition.
**Dependencies:** FORGE-TK-001 (complete), FORGE-PB-001 (complete), FORGE-LOOP-001 (complete)
**Feeds:** every future mission — this manufactures the North Star, Living Spec seed, and Finish Contract that the execution loop consumes.

---

## 1. Objective

Turn a beginner's free-text intent ("I want to build an ERP for my business") into a **signed, evidence-ready Mission** through a four-stage governed pipeline:

```text
FREE-TEXT INTENT
      │
      ▼
DECOMPOSE ──► provisional North Star + requirement skeleton + AMBIGUITY MAP
      │
      ▼
CALIBRATE ──► Jev-ranked interview (max 5 questions, value-of-information order)
      │
      ▼
REFINE ─────► plain-language contract read-back, correction loop, OWNER SIGNATURE
      │
      ▼
HANDOFF ────► Mission object → Governor (existing FORGE-LOOP machinery)
```

The interview is **derived, not scripted**: questions exist only where an answer would change the architecture. Beginners are never asked engineering questions; engineering uncertainty becomes registered Known Unknowns with defaults.

## 2. Core data objects

### 2.1 Ambiguity Map (output of DECOMPOSE)

```yaml
ambiguity:
  id: AMB-003
  dimension: "users.scale"          # dotted taxonomy path
  question_if_asked: "Roughly how many people will use this?"
  current_assumption: "single business, < 50 users"
  assumption_confidence: 0.55        # frontier model's estimate
  blast_radius: high                 # low | medium | high — how much architecture changes if wrong
  resolvable_by_default: true        # can a sensible default carry us to V1?
```

### 2.2 Interview Question (output of CALIBRATE)

```yaml
interview_question:
  id: IQ-001
  ambiguity: AMB-003
  plain_language: "How many people at your company would log into this?"
  why_we_ask: "This decides whether we build simple logins or full team permissions."
  answer_format: free_text           # always free text; never forms with jargon
  voi_score: 0.91                    # value-of-information, Jev-scored
```

### 2.3 Owner Contract (output of REFINE — the signature artifact)

```yaml
owner_contract:
  mission_id: MISSION-xxx
  north_star_plain: |                # plain language, <= 120 words, zero jargon
    "A web app where Acme staff can create invoices, track inventory,
    and see every customer order — with every change recorded."
  in_scope: ["invoicing", "inventory tracking", "customer records"]
  out_of_scope: ["payroll", "tax filing", "mobile app"]   # shown explicitly
  finish_contract_plain: |           # how the human will KNOW it's done
    "Done means: you can create a real customer, invoice them, mark it paid,
    and watch the inventory count drop — end to end, in your browser."
  assumptions_accepted:              # defaults the owner saw and accepted
    - {id: A-001, plain: "Fewer than 50 users", confidence: 0.55}
  known_unknowns_registered: [U-001, U-002]
  owner_signature:                   # explicit approval event, receipted
    approved_by: owner
    approved_at: ...
```

## 3. Stage contracts

### DECOMPOSE (frontier model, Capability.HIGH_REASONING)
- Input: raw free-text intent (+ optional uploaded docs).
- Output (Pydantic-validated): provisional North Star, requirement skeleton (max 12 seed requirements), Ambiguity Map, Known Unknowns registry seed.
- Everything labeled `PROVISIONAL` with confidence. (Canonical §66)
- **Anti-overreach rule:** seed requirements must be traceable to the intent text or flagged as `inferred`. No silent scope invention.

### CALIBRATE (Jev decision layer + frontier model phrasing)
- For every ambiguity, Jev answers in ONE parallel call:
  - Noul: "Would the true answer materially change the system architecture?"
  - Noul: "Can a reasonable default carry this to a useful V1?"
  - Score(3): "How confident are we in the default?" — weakly calibrated, used only for ranking.
- **Interview set** = ambiguities where `materially_changes > 0.6 AND NOT default_sufficient > 0.7`, ranked by blast_radius × voi, **capped at 5**.
- **Stopping rule (deterministic):** stop when the interview set is empty OR 5 questions answered OR the owner declines further questions. Never block on perfection (Canonical §188).
- Answers are integrated by the frontier model into revised assumptions; each update preserves lineage.

### REFINE (frontier model, owner in loop)
- Generate the Owner Contract in plain language (readability target: a non-engineer can repeat back what they're getting).
- Contradiction check against the Product Brain before presentation.
- Owner may correct in free text; corrections re-enter DECOMPOSE (max 3 polish rounds, then unresolved deltas become Known Unknowns or owner-gated decisions).
- **Scope honesty invariant:** out_of_scope must be non-empty and shown. If the pipeline cannot name what it is NOT building, the contract is invalid.
- **V1-honesty invariant:** the Finish Contract describes a verifiable vertical slice, not the full dream product. "ERP" → invoicing+inventory+records slice. The pipeline must never promise the totality of a category product.

### HANDOFF (deterministic)
- On owner signature: emit Mission object, freeze spec hash, register Known Unknowns, create initial execution graph skeleton, receipt everything.
- From this point, existing Governor/loop machinery owns execution. Ingestion never touches it again except through owner-decision events.

## 4. Beginner-interface requirements

- All owner-facing text passes a jargon filter (denylist: "ORM", "schema", "endpoint", "multi-tenant"... — replaced with plain equivalents).
- Owner escalations translate bidirectionally: `OWNER-DECISION-004` internals ↔ "When you fix a mistake on an old invoice, keep the original on file, or replace it?"
- Every question shows its `why_we_ask`. Transparency is the trust mechanism for non-technical owners.

## 5. Acceptance criteria (evidence required)

1. Given the raw string "I want to build an ERP for my business", DECOMPOSE produces a valid Ambiguity Map with ≥ 8 ambiguities and a ≤ 12-requirement skeleton. (pytest, schema validation)
2. CALIBRATE asks ≤ 5 questions and every asked question has `materially_changes > 0.6` receipt. (receipt inspection)
3. Deterministic proof: an intent with zero high-blast-radius ambiguities asks ZERO questions. (unit test — no spurious interviews)
4. REFINE produces an Owner Contract passing the jargon filter and the non-empty out_of_scope invariant. (unit test)
5. Owner correction in free text updates assumptions with lineage preserved. (integration test against Product Brain)
6. Handoff emits a Mission object the existing execution loop accepts unmodified. (integration test against FORGE-LOOP-001 machinery)
7. Every stage transition emits a ledger receipt; a crash between CALIBRATE and REFINE resumes without re-asking answered questions. (restart test)

## 6. Boundaries

- **Allowed paths:** `src/forge/ingestion/**`, `tests/ingestion/**`, `schemas/owner_contract.schema.json`
- **Forbidden:** modifying Governor, trust kernel, execution loop internals, Finish Contract semantics, or any protected surface. Ingestion PRODUCES contracts; it does not redefine what contracts mean.
- **Model usage:** HIGH_REASONING for DECOMPOSE/REFINE; Jev for CALIBRATE triage; no other capabilities.
- **Budget:** max 3 polish rounds; max 5 interview questions; 32k token cap per Jev state.
- **V0 explicitly excluded:** voice input, multi-language, file-upload understanding beyond plain text/markdown, automatic North Star mutation after signature.

## 7. Retry budget

2 materially different repairs per acceptance failure, then STUCK_RESOLUTION per canonical doctrine.
