# AURA-DIRECTION-001: personal autonomous coding CLI

Owner authority: Nick Sandoval approved the architecture image and requested pushing
this direction to Aura on September 25, 2026, America/Chicago. This authorizes saving
product documentation and the image; it grants no provider spending or live execution.

Objective: preserve the agreed roles while specifying persistent personal/project
memory, skills, resumable execution, and an incremental path to unattended builds.
Base: 0dd62aae4959227a5c5a2d7cb618bbd7616bfef4; clean checkout verified before editing.
Branch: codex/aura-personal-coding-direction.
Node: documentation refinement of AURA-SCOPE-001; no runtime milestone completed.
Allowed paths: README.md, AURA_ARCHITECTURE.md, AURA_PRD.md,
.agent/DECISIONS.md, .agent/CURRENT_STATE.md, docs/packets/AURA-DIRECTION-001.md,
docs/AURA_HANDOFF.md, docs/finish-contract.md,
docs/product/AURA_PRODUCT_DIRECTION.md, docs/product/AURA_BUILDER_HANDOFF.md,
docs/product/assets/aura-agent-structure.png.
Exclusions: source, tests, policy, trust, graph statuses, ledgers, historical evidence,
other repositories, provider calls, branch deletion, unrelated PR merges.
Dependencies: existing scope and owner direction; no runtime dependencies for documentation.
Invariants: retain role assignments, independent review, bounded recovery, UNKNOWN
handling and historical evidence. Distinguish target behavior from implemented state.
Acceptance: <=50 numbered PRD requirements; coherent local document/image links;
readable image matching intended roles; full local validation attempted with raw output;
independent review of exact committed candidate before advancement.
Risk: conflicting draft PR specifications. Handoff must require current-source reconciliation.
Repair budget: two materially different corrections, then replan.
Handoff: product direction, updated canonical docs, image, and builder instructions.
