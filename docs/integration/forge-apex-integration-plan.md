# Forge × APEX Integration Plan

**Status:** Proposal for owner review
**Scope:** Fix identified Forge weaknesses; integrate APEX speed, anti-stuck, and learning machinery without weakening Forge's governance.
**Governing documents:** `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md`, `FORGE_AGENT_V0_PRD.md`, `docs/finish-contract.md`, `docs/self-improvement-acceptance.md`
**Prime directive for this plan:** Every change must be expressible as a Forge bounded packet. Protected-surface changes are marked **[OWNER-GATED]**. Nothing in this plan authorizes weakening the trust kernel, audit independence, evidence requirements, or the Finish Contract.

---

## 1. Design tension being resolved

Forge and APEX optimize for different failure modes:

| | Forge | APEX |
|---|---|---|
| Primary fear | Unauthorized/incorrect action | Stalling, drift, slowness |
| Speed strategy | Deferred | Parallel DAG, context budgets, model tiering |
| Trust strategy | Deterministic governor, receipts, fail-closed | Watchdog, canary benchmark |
| Verification | Fresh-context Auditor, UNKNOWN verdict | Cross-vendor critic, adversarial agent |
| Learning | Causal-chain proof, scope-gated lessons | Retrieval, routing stats, prompt A/B tests |

**Resolution principle:** Forge owns the *constitution* (authority, evidence, identity, learning validity). APEX contributes the *engine* (throughput, context economics, recovery speed). Where they conflict, Forge wins on anything touching authority, evidence, or verification validity; APEX wins on anything touching scheduling, context, and cost — provided the APEX mechanism is implemented as deterministic Governor infrastructure, not as agent discretion.

---

## 2. Phase 0 — Fix what's broken in Forge first

These are cheap, independent, and unblock everything else.

### FORGE-FIX-001: Eliminate hand-maintained status (fixes the README contradiction)
**Problem:** README says "Implementation: Not started" while three merged subsystems exist in `src/forge/`. `.agent/CURRENT_STATE.md` is hand-maintained and will drift again.
**Fix:** Derive all outward-facing status from the work graph + evidence ledger.
- `README.md` status block becomes generated (or reduced to a pointer: "see `.agent/graph/work-graph.json`").
- Add a deterministic CI/pre-merge check: if `work-graph.json` node status != what docs claim, fail the check.
- Canonical rule to add: *No human-maintained file may assert execution state. Execution state is derived from the ledger.*
**Governance class:** A1 (autonomous-safe), except the new invariant goes in AGENTS.md **[OWNER-GATED]**.

### FORGE-FIX-002: Resolve the model-provider unknown (minimal version)
**Problem:** Model provider is listed as a "known unknown," but the entire execution loop is dead without it. It's on the critical path in disguise.
**Fix:** Implement the thinnest possible `ModelProvider` — one provider, Pydantic-validated structured output, hard failure on schema-invalid responses (Canonical S52, S99). Candidate implementation: `src/forge/providers/model_provider.py` on branch `codex/forge-ing-001`.
**Governance class:** A1.

### FORGE-FIX-003: Pull an end-to-end signal forward
**Problem:** Forge's proving sequence is back-loaded — the first real empirical signal is the Sentinel trial (phase 9 of 10). Risk of building 10 phases of control plane before discovering the Builder prompt quality is the actual bottleneck.
**Fix:** Add one minimal vertical-slice milestone immediately after FORGE-FIX-002: a single real Build Packet executed end-to-end on Forge's own repo, with full packet → build → audit → merge → receipt → replay. Ugly is fine. Small is fine. Real is mandatory.
**Governance class:** A1.

---

## 3. Phase 1 — The speed engine, grafted onto the Governor

All speed machinery is implemented as **deterministic Governor infrastructure**. Agents never see it, control it, or influence it.

### FORGE-SPD-001: Parallel packet scheduler (implements Canonical S30–31 now instead of "eventually")
The work graph is already a DAG. Add a scheduler that:
- selects all READY nodes whose dependencies are COMPLETE;
- checks **write-scope disjointness** from packet `allowed_paths` (already in the packet schema);
- checks **semantic conflicts** via `assumptions_touched` / `invariants_touched` metadata (add these optional fields to packets; conservative default: no metadata = no parallelism);
- launches each packet in its own git worktree (RepositoryAdapter already specifies `create_worktree()`);
- enforces a global concurrency cap and per-mission budget.

**What stays Forge:** only the Governor marks merge-eligible; parallel candidates queue through the same audit → freeze → eligibility → merge path, serialized at merge. Candidate mutation still invalidates audit. **[OWNER-GATED]:** scheduler lives in Governor/core = trust-kernel-adjacent; requires owner approval per the trust-kernel change policy (Canonical S111).

### FORGE-SPD-002: Context Engine with budgets (implements Canonical S32–33)
Build the Context Assembler as specified, with one APEX addition: **hard context budgets per role**.
- Builder receives: packet + whitelisted file slices + relevant requirements/lessons. Not the repo. Not the spec. Not the chat history.
- Auditor receives: fresh context (already canonical) + frozen diff + acceptance criteria + evidence. Explicitly excludes Builder reasoning.
- Every context item carries provenance (Canonical S33).
- Log actual context size per packet; this data feeds the routing model in Phase 4.

### FORGE-SPD-003: Speculative execution
While the Auditor reviews candidate N, the scheduler may start packet N+1 *on the assumption* N passes (N+1's worktree branches from N's candidate). If N fails, N+1's worktree is discarded — zero cost, since worktrees are already isolated.
**Constraint:** speculative candidates may never enter the merge queue until their actual base passes audit. This is a scheduling optimization only; it changes no authority semantics.
**[OWNER-GATED]** (scheduler/Governor).

### FORGE-SPD-004: Verification impact analysis (implements Canonical S78)
Run the smallest sufficient evidence set per diff: changed files → affected requirements/invariants → required tests. Full suite only at merge and Finish Contract evaluation. Pure win, already canonical.

---

## 4. Phase 2 — Anti-stuck machinery upgrade

Forge's semantic stuck detection (S16, S57, S210) is the right design. Add two cheap deterministic tripwires in front of it.

### FORGE-STK-001: Patch-hash loop detection
Before every repair attempt, hash the proposed diff. If identical to any prior attempt on this packet → hard-stop, force STUCK_RESOLUTION. Catches the most common agent failure (repeating the exact same fix) in O(1), deterministically, no LLM judgment required. Feeds directly into the existing "no material strategy change" detector.

### FORGE-STK-002: Non-LLM watchdog
A plain-code monitor inside the Governor: tokens burned, wall-clock, tool calls per packet, each with budgets (Canonical S59 already specifies the primitives). 3× the per-task median → forced escalation. LLMs are bad at noticing they're spinning; counters aren't.
**[OWNER-GATED]** (Governor).

### FORGE-STK-003: Abstraction-ladder escalation (canonical S210, made concrete)
Wire the existing Stuck Resolver contract to explicitly climb: implementation → strategy → architecture → assumption → spec → owner. Each rung requires a *materially different* strategy receipt naming what changed versus prior rungs. The "climb" is already doctrine; this makes it a state-machine requirement rather than a prompt hope.

---

## 5. Phase 3 — Verification upgrades

### FORGE-VER-001: Cross-family auditor (deliberately overriding Canonical S51)
Canonical S51 says fresh *context* is sufficient independence and multi-provider is unnecessary V0 complexity. Respectfully: context independence stops narrative contamination, but same-family models share blind spots and will approve each other's characteristic mistakes. Once FORGE-FIX-002's provider abstraction exists, adding a second provider for the Auditor is a day of work, not an architecture change.
**Compromise to stay V0-legal:** V0 keeps single-provider as default config; the provider abstraction must *support* a different auditor model family, and the Sentinel trial must run with cross-family audit enabled. Update S51 via ADR **[OWNER-GATED]**.

### FORGE-VER-002: Adversarial verification agent
Add a post-audit, pre-merge step on a sampling basis (100% in V0, sampled later): an agent whose sole job is to break the candidate — edge cases, hostile inputs, "how does this fail?" This subsumes Canonical S120 (test gaming defense) with an active attacker instead of a checklist. Findings enter as Observations; nothing reaches merge on "probably fine."

### FORGE-VER-003: Canary benchmark (regression yardstick for the whole system)
~20 representative tasks with known-good solutions, runnable headlessly against the *current* Forge configuration. Mandatory run after: any prompt change, any routing change, any lesson promotion that affects planning, any Governor/scheduler change. Score drop → automatic rollback + owner alert. This is the guardrail that makes Phase 4's self-modification safe, and it directly serves the self-improvement acceptance contract's rollback requirement.

---

## 6. Phase 4 — Learning: APEX machinery inside Forge's acceptance contract

Forge's self-improvement acceptance contract (retrieval → changed decision → named metric → rollback) stays exactly as-is. APEX supplies the machinery that makes the chain fire often enough to measure.

### FORGE-LRN-001: Failure-similarity retrieval
Retrieve top-k similar past failures into the Builder's context as "known traps," and into the Architect's context as planning input. Candidate implementation: `relevant_failures()` in `src/forge/decisions/jev_decisions.py` — one Jev Noul per past failure in a single parallel call, no vector DB (Canonical S106 compliant). Retrieval evidence gets logged — exactly the receipt the SI acceptance contract demands (item 5).

### FORGE-LRN-002: Routing stats from execution data
Every packet logs: predicted difficulty, model used, attempts needed, tokens, escalation level, verdict. A simple stats layer (not ML) tunes: which model tier gets which packet class, which context budget sizes work. Starts as a lookup table keyed on packet-type × path-area. Satisfies the SI contract's "named directional metric" (cost per verified requirement, audit pass rate) with real baselines.

### FORGE-LRN-003: Prompt evolution with A/B discipline
Prompts become versioned artifacts (Canonical S95 — keep). Add: 5% of eligible packets run a candidate prompt variant; canary benchmark gates promotion; rollback on regression. No casual self-rewriting — every change carries hypothesis + expected benefit + evaluation, per canonical doctrine.

### FORGE-LRN-004: Mid-mission replanning heartbeat
After every N merges (align with the canonical cumulative-audit trigger, S175) or when escalation rate crosses a threshold, the Architect re-reads actual state — retries, failures, rejected contracts — and revises the remaining execution graph. Forge already has mutable graphs (S40) and cumulative audit (S173–175); this connects them: reflection output *must* produce a graph-version receipt, even if the verdict is "no change."

---

## 7. Decision layer: Jev (TypeSafe AI System One)

Jev is the runtime's fast judgment layer — typed decisions (Noul/Choice/Score) with calibrated confidence, ~100ms, ~$0.042/M input tokens. It cannot generate text or code; it advises the Governor and never grants authority. Integration points:

| Component | Jev question shape |
|---|---|
| Tool-call guardrails (read-only / reversible / irreversible) | Choice + scope Noul |
| Capability routing (which model tier gets a packet) | Choice |
| Semantic stuck detection (materially different strategy?) | Noul |
| Autonomy gates (merge / flag / human-gate) | Score + anomaly Noul |
| Owner escalation (does this genuinely need the owner?) | Noul |
| Failure-log retrieval (is this past failure relevant?) | Noul per candidate, one parallel call |

Operational rules: pin `jev-1.13.0` (never jev-latest when thresholds are tuned); log the versioned model ID from every response; all independent questions in one call; ~32k token state budget; no arithmetic/date/counting questions — pre-digest in code; version questions + thresholds together and replay the canary benchmark on any change. Jev is consistency-optimized, not deterministic — its outputs are evidence inputs to the deterministic Governor, never state transitions themselves.

Candidate implementation: `src/forge/decisions/jev_decisions.py` on branch `codex/forge-ing-001`.

## 8. Model lineup (capability routing, names in env config)

| Role | Model | Notes |
|---|---|---|
| Architect / final-gate reasoning | Claude Fable 5.1 | strongest long-horizon reasoner |
| Builder | DeepSeek V4.1 Flash | ~20x cheaper than premium tiers; audit gate guarantees quality |
| Routine audit / exec-debug | Kimi K2.7 Code | coding specialist |
| Final-gate audit | GPT-6 Astra | cross-family vs. all builders |
| Fast / scoping | Gemini 3.8 Flash | cheap high-volume |
| All bounded decisions | Jev jev-1.13.0 | calibrated, pinned |

Cross-family audit independence is enforced architecturally in `ModelProvider.audit_call()`. DeepSeek off-peak windows (UTC) can be exploited by the scheduler for batch work.

---

## 9. Conflict register — where APEX and Forge disagree, and the ruling

| # | Dispute | Ruling |
|---|---|---|
| 1 | APEX: different-vendor critic mandatory. Forge S51: unnecessary. | **APEX wins for trials, Forge default for V0 dev.** Provider abstraction must support it; S51 amended by ADR. **[OWNER-GATED]** |
| 2 | APEX: parallelism now. Forge S30: "not immediately." | **APEX wins, implemented inside Governor** with conservative semantic-conflict defaults. |
| 3 | APEX: small context via whitelisting. Forge S32: governed context assembly. | **No conflict** — same mechanism; Forge's provenance requirement is stricter and wins. |
| 4 | APEX: auto-merge at high critic confidence. Forge: Governor-only merge eligibility, always. | **Forge wins absolutely.** Confidence never grants authority. |
| 5 | APEX: fine-tune a repo-specialized worker model later. Forge S181/259: no automatic model training in V0. | **Forge wins for V0.** Log the training data now so the option exists post-V0. |
| 6 | APEX: fast/cheap models for trivial tasks. Forge S237/262: strongest model everywhere until traces prove otherwise. | **Forge wins initially, with a timer.** FORGE-LRN-002's stats layer is the trace-collector; tiered routing activates only when data justifies it. |

---

## 10. Proposed graph nodes

See `.agent/graph/work-graph.json` (graph_version 2) on branch `codex/forge-ing-001`: adds FORGE-ING-001 (Intent Ingestion Protocol — packet at `docs/packets/FORGE-ING-001-intent-ingestion.md`) plus the 17 integration nodes across phases 0–4, all status PROPOSED pending owner authorization.

Phase 4 completion feeds directly into **FORGE-SI-001** (the mandatory V0 gate): LRN-001 supplies retrieval evidence, LRN-002 supplies the named metric baseline, VER-003 supplies rollback proof. The self-improvement causal chain becomes demonstrable by construction rather than by luck.

---

## 11. What this plan deliberately does NOT do

- No changes to authority levels, Finish Contract semantics, North Star ownership, audit independence, or receipt integrity. (Constitution is off-limits to the integration itself — law 10.)
- No vector DB, no swarm, no multi-process architecture, no framework adoption. V0 technology boundary stands.
- No weakening of "strongest model until traces prove otherwise" — tiered routing is *earned by data*, not assumed.
- No automatic global lesson promotion. Forge's repo-scoped cap stands.

## 12. Success criteria for the integration itself

1. Sentinel trial completes with **lower wall-time per verified requirement** than the sequential baseline (measured, not asserted).
2. Zero protected-surface violations across all integration packets (the canary benchmark + Governor receipts prove this).
3. FORGE-SI-001 satisfied with the full causal chain on at least one real lesson.
4. Stuck-recovery rate measurable and improving across the trial (watchdog + strategy receipts).
5. The README never contradicts the ledger again (FIX-001's CI check).
