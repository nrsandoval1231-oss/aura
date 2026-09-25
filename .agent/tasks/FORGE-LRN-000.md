# FORGE-LRN-000 — Stuck resolution, the learning engines, and the self-improvement proof

**Nodes:** FORGE-STK-001, FORGE-STK-003, FORGE-LRN-001 (absorbed here), and the
proof obligation of FORGE-SI-001
**Authority:** A3 (owner-authorized; scope reaches protected surfaces)
**Risk:** HIGH
**Retry budget:** 2

## Objective

Implement the three Finish Contract obligations that had no implementation at all,
and demonstrate the one that is a mandatory V0 gate:

- "stuck resolution requires materially different strategies"
- "outcome and lesson records are attributable and scoped"
- "self-improvement is demonstrated by a validated lesson changing a later
  engineering decision and improving a named outcome, with demotion or rollback
  available when the lesson is harmful"

## Base

- `0116fce`

The FORGE-FIX-004 evidence commit. This packet's candidate is what it changed on top
of that, not everything the branch accumulated.

Making that true required a change to the harness, which is why `scripts/run_slice.py`
and `.agent/tasks/FORGE-FIX-004.md` are in this packet's scope. `run_slice` diffed
every packet against `origin/main`, which silently assumes one packet per branch: with
two, each packet's scope check saw the other's changed paths and refused it. It now
reads the base identity `AGENT_RULES` already required a packet to record, and
`FORGE-FIX-004.md` gains the `## Base` section that mechanism reads. The section is
optional, so the packets written before this one still parse.

## Authority note

Scope reaches protected surfaces: `src/forge/policy.py` (registering the two new
governed modules), `scripts/validate.sh`, `.agent/graph/work-graph.json`, and
`src/forge/__init__.py`. It proceeds under direct owner instruction to complete the
V0 build out — authority layer 1 in `AGENTS.md` — recorded here rather than assumed.

`src/forge/stuck.py` and `src/forge/learning.py` are added to the protected-surface
registry in the same packet that creates them, which is the obligation DEC-011
attaches to any new governance module.

## Allowed files

- `src/forge/stuck.py`
- `src/forge/learning.py`
- `src/forge/policy.py`
- `src/forge/__init__.py`
- `scripts/prove_self_improvement.py`
- `scripts/validate.sh`
- `scripts/run_slice.py`
- `.agent/tasks/FORGE-FIX-004.md`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/FORGE-LRN-000.md`
- `.agent/artifacts/FORGE-LRN-000/**`
- `.agent/artifacts/FORGE-SI-001/**`
- `tests/**`

## Exclusions

- No canonical intent changes. No live model call. No global lesson promotion.
- `src/forge/trust_kernel.py` is untouched: neither new module may reach into
  transition validation, which is why both carry their own error type instead of
  importing `ForgeError`.

## Invariants

- A lesson may improve execution but may not weaken requirements or governance.
- Automatic global promotion stays disabled; protected governance stays outside
  autonomous self-modification.
- UNKNOWN is preserved when attribution or evidence is insufficient, and is never
  acted on as if it were a result.
- Recovery is bounded at two materially different repairs.

## Acceptance

1. Repetition is detected on normalised patch content, so the same edit reframed is
   caught.
2. Material difference is decided on declared rung and mechanism, so relabelling an
   approach or pointing it at a different file is not a new strategy.
3. "Evidence does not improve" is decided on a strictly shrinking failing-check set,
   so trading one failure for another returns to intent.
4. Escalation only moves up the abstraction ladder, and exhausting it reaches the
   owner as a stop rather than a permission.
5. A lesson cannot be validated by its author.
6. A lesson proposing to skip, disable, relax, quarantine or bypass a check is
   refused, as is one naming a protected surface.
7. Global promotion is refused in V0.
8. Measurement returns UNKNOWN with a stated reason when there is no baseline, the
   wrong metric, no candidate binding, or no application that changed a strategy.
9. A lesson that harms its own named metric is rolled back and stops being
   retrievable; an UNKNOWN measurement does not demote.
10. `scripts/prove_self_improvement.py` derives the full chain, all nine acceptance
    requirements are met, and the gate re-derives it rather than trusting the
    committed artifact.
11. `./scripts/validate.sh` green.

## Evidence

- `.agent/artifacts/FORGE-SI-001/PROOF.json` — the derived causal chain
- `.agent/artifacts/FORGE-LRN-000/COMPLETION.json`
- `tests/test_stuck.py` — 32 cases
- `tests/test_learning.py` — 58 cases
- `tests/test_self_improvement.py` — 14 cases, including that the demonstration is
  capable of failing

## Stated boundary

The proof's simulated step is isolated in `attempt_result()`: whether a repair
reaches the defect is decided from the rung, because the scenario's defect is by
construction an env-ordering defect a same-level edit cannot reach. No model is
called. What is proved is that the learning machinery changes a later decision and
can measure and revoke it — not that Forge can fix software. The emitted evidence
carries this sentence rather than leaving a reader to infer it.
