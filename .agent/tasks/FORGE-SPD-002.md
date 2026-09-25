# FORGE-SPD-002 — Context Engine with role budgets

## Objective

Implement the Context Engine specified by Canonical Sections 32 and 33: assemble
role-specific context from governed sources, attach provenance to every item, and
enforce a hard per-role budget. Context stops being "whatever we paste in" and
becomes a governed resource with a manifest.

Two properties are structural rather than prompt-based, because a prompt cannot
guarantee either: a Builder never receives the specification, and an Auditor never
receives Builder reasoning. Supplying a forbidden source to a role is an error at
assembly time, not a instruction the model is trusted to follow.

## Base identity

- Repository: `nrsandoval1231-oss/forge-agent`
- Remote: `https://github.com/nrsandoval1231-oss/forge-agent.git`
- Branch: `claude/forge-spd-002`
- Base SHA: `cbb63f16febe0b189694b1664db66d2065affb25`
- Python: `>=3.12`

## Authority

- **Owner authorization:** explicit owner instruction to proceed with the next
  builder session (2026-09-21).
- **Authority class:** A2. This packet deliberately touches no protected surface.
  `trust_kernel.py`, `execution_loop.py`, `product_brain.py`, `AGENTS.md`,
  `DECISIONS.md`, and the Finish Contract are all excluded; the Context Engine is
  additive and is wired in by callers rather than by editing the loop.

## Allowed files

- `src/forge/context_engine.py`
- `src/forge/__init__.py`
- `scripts/run_slice.py`
- `scripts/validate.sh`
- `.github/workflows/validate.yml`
- `tests/**`
- `.agent/tasks/FORGE-SPD-002.md`
- `.agent/artifacts/FORGE-SPD-002/**`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`

## Explicit exclusions

The trust kernel, execution loop, and Product Brain modules; `AGENTS.md`;
`.agent/DECISIONS.md`; the Finish Contract; the canonical architecture and PRD;
the parallel scheduler (FORGE-SPD-001); speculative execution; verification impact
analysis; any live model provider call; any retrieval backend.

## Dependencies and invariants

- Depends on FORGE-FIX-000 (COMPLETE): the shared path primitives and the
  governed-loop harness this packet extends.
- Every context item carries provenance: source type, source id, version,
  authority, and confidence. (Canonical S33)
- Role source policy is an allow-list. A source type absent from a role's policy
  is refused at assembly time, never silently filtered.
- A Builder context never contains the North Star, decision records, or Builder
  reasoning from a prior attempt.
- An Auditor context never contains Builder reasoning. This is the independence
  guarantee; it does not depend on any prompt.
- Budget overflow drops items deterministically and records every drop with its
  reason. Context the Builder did not receive is evidence, so it is never
  discarded silently.
- Assembly is pure and deterministic: identical inputs produce an identical
  digest, on any machine.

## Acceptance checks

1. Every assembled item carries complete provenance; an item without it is refused.
2. Supplying a forbidden source type for a role raises, naming role and source.
3. A Builder context cannot be assembled containing the North Star or Builder
   reasoning; an Auditor context cannot be assembled containing Builder reasoning.
4. Budget enforcement is deterministic and every dropped item is recorded with a
   reason; the manifest accounts for every supplied item as included or dropped.
5. The same inputs produce the same digest across runs and process boundaries.
6. Context size per role is reported in a receipt shape suitable for the ledger,
   which is the measurement FORGE-LRN-002 later consumes.
7. `scripts/run_slice.py` drives this packet by id, reading its scope from this
   file rather than from a second copy of it in code.
8. The gates verify every ledger chain, not one. A second packet exists now, and
   a gate naming a single stream would have stopped covering the repository the
   moment it did.

## Scope amendment

`scripts/validate.sh` and `.github/workflows/validate.yml` were added to the
allowed files after the loop refused the candidate for touching them. Generalising
the harness to drive any packet is not finished while the gates still verify one
hardcoded packet, so the change belongs to this packet rather than a follow-up.
The amendment is recorded here rather than made silently, because the packet
document is the authority the loop validates against.

## Retry budget

Two materially different bounded repairs per failing acceptance check.

## Required handoff artifacts

- `.agent/artifacts/FORGE-SPD-002/COMPLETION.json`
- `.agent/artifacts/FORGE-SPD-002/REVIEW.json`
- `.agent/artifacts/FORGE-SPD-002/SLICE.json`
- `.agent/ledger/FORGE-SPD-002.jsonl` and its checkpoint
