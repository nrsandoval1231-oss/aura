# Forge Agent Repository Instructions

## Authority order

1. Owner intent
2. `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md`
3. `FORGE_AGENT_V0_PRD.md`
4. Accepted ADRs
5. `docs/finish-contract.md`
6. `.agent/CURRENT_STATE.md`
7. Active bounded task packet

Lower layers may expose conflicts in higher layers but may not silently redefine them.

## Required workflow

- Read `.agent/CURRENT_STATE.md` and `.agent/AGENT_RULES.md` first.
- Establish repository, branch, worktree, and candidate identity before editing.
- Select only READY work from `.agent/graph/work-graph.json`, with one exception:
  repairing a defect in already-merged code does not require a new READY node. A
  repair restores merged code to the intent its own node already approved. It may not
  add capability, widen scope, or touch a protected surface; anything beyond
  restoration is new work and needs a node. Every repair still produces a packet,
  evidence, and an independent audit. (DEC-006)
- Use one bounded packet by default; use two builders only for independent, disjoint nodes.
- Treat every builder handoff as a claim and rerun deterministic validation.
- Deterministic validation is `./scripts/validate.sh`, run locally. There is no
  CI. A change is validated only when someone has run it and read the output;
  absent that, the gate result is UNKNOWN. (DEC-009)
- Bind audit evidence to the exact candidate.
- Require an independent strategic audit at material checkpoints.
- Preserve UNKNOWN when evidence is absent or ambiguous.
- Do not push, merge, deploy, spend, communicate externally, or perform destructive actions without authority.

## Protected surfaces

Changes to these paths require an explicit governance packet and independent audit:

- `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md`
- `FORGE_AGENT_V0_PRD.md`
- `AGENTS.md`
- `.agent/AGENT_RULES.md`
- `.agent/DECISIONS.md`
- `docs/finish-contract.md`
- future Governor, authority, policy, and evidence-ledger modules

Protected governance, North Star, trust-kernel, deployment, secrets, and destructive-effect changes also require explicit owner approval. A graph state, audit verdict, or agent role cannot substitute for owner authority.

## Completion

A green checkpoint is not completion. Completion requires exact-candidate validation, independent audit, repository-state reconciliation, and satisfaction of the governing Finish Contract.
