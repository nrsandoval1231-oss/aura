# Aura repository instructions

## Authority

Owner intent → AURA_ARCHITECTURE.md → AURA_PRD.md → .agent/DECISIONS.md →
docs/finish-contract.md → .agent/CURRENT_STATE.md → bounded task packet.

Read current state and .agent/AGENT_RULES.md first. Establish repository, branch,
clean worktree, and frozen candidate before editing. Only work within an authorized
packet. Use two builders only on independently verifiable, disjoint work.

Run ./scripts/validate.sh locally and read its output. No GitHub runner is configured.
Bind independent audit to the exact candidate. Builder claims are not verification.
UNKNOWN remains UNKNOWN. A green offline gate does not complete the live product.

Changes to canonical scope, agent rules, decisions, finish contract, graph, validation,
trust, authority, recovery, learning policy, and evidence require owner authority and
independent review. src/forge/policy.py is the executable protected-surface registry.
Do not weaken it to make cleanup or validation pass. Do not push, merge, deploy, spend,
communicate externally, or perform destructive actions without owner authority.

Preserve Aura runtime receipts. Old Forge records removed under the explicit scope
cleanup remain recoverable in Git history; they do not authorize Aura execution.
