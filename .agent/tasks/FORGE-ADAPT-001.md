# FORGE-ADAPT-001 — Shared slice learning and stuck recovery

Status: READY_AUTHORIZED by owner direction in the 2026-09-25 conversation.

## Objective
Connect Forge's existing stuck detector and lesson engine to a durable two-lane
slice controller, adapting Athena's outcome comparison and lineage principles.

## Identity and authority
- Upstream: nrsandoval1231-oss/forge-agent, main at b525f7d37718a2916b8514020dd90a763a17feac.
- Athena reference: nrsandoval1231-oss/Athena at f630acec86f1ff4aa03c0307fc77bd66a3f6bdc5.
- Local workspace is a selected-file API snapshot, not a full Git clone.
- Owner approved Sol lead, DeepSeek V4.1 Flash and Luna 6 builder lanes,
  MiniMax utility, Astra audit, parallel loops, stuck resolution and Athena learning.
- A3 governance extension under that direction; draft PR only, independent audit
  required. No production activation, automatic merge, paid model call or deployment.

## Scope
Allowed: src/forge/slice_learning.py, src/forge/athena_engineering.py,
src/forge/policy.py (register new protected paths only),
tests/test_slice_learning.py, tests/test_athena_engineering.py,
docs/integration/parallel-adaptive-engineering.md, this packet,
.agent/graph/work-graph.json (this node only), .agent/artifacts/FORGE-ADAPT-001/.

## Invariants
- Reuse LessonStore, StuckDetector and LedgerStore; preserve existing semantics.
- One shared experience history with isolated lane attempts and pinned per-slice lessons.
- A lesson needs independent evidence before future retrieval; never grants authority.
- Unknown/incomplete test evidence does not count as success or improvement.
- Comparisons require matching registered task/protocol class and directional metric.
- Harm demotes future retrieval; running snapshots remain historically immutable.
- Persist transitions and replay after restart; do not repeat external effects.
- No synthetic proof can claim measured live-agent or general policy improvement.

## Acceptance
Focused tests: parallel lane isolation; restart and idempotency; missing evidence;
repetition and strategy escalation; candidate-to-validated lesson-to-later-slice
causal record; rejection and harmful-lesson rollback; real Athena directional
comparison semantics; cross-context comparisons remain UNKNOWN.
Run the full repository gate where a complete checkout is available. Otherwise
record it UNKNOWN explicitly, keep the PR draft and the graph AWAITING_AUDIT.

## Limits and recovery
Two materially different repairs, then revise the packet if evidence is not improving.
Handoff contains file changes, commands/results, source identities, and gaps.
