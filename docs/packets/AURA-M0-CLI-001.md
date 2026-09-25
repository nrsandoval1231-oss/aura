# AURA-M0-CLI-001 decision record

## Opening Tribunal (one decision)

- **Objective:** one disposable Git task reaches a tested, independently reviewed candidate through a durable CLI run.
- **Build now:** six state-connected commands, single isolated builder lane, bounded packet and attempt, append-only run evidence, exact-candidate checks and review request.
- **Do not build yet:** second lane, dashboard, cloud runtime, general policy evolution, 30-slice demonstration.
- **Architecture:** retain the Forge Governor and ledger; add a thin Aura operator layer. The initial local builder adapter is for nonbillable mechanism proof only. Production role activation requires verified wire, account access, explicit spend budget, and trusted review.
- **Assumptions:** `origin/main` at `a581d1485ceb9317dc15ad80f8fd4144be82c875`; draft PR #1's 44 requirements guide the CLI contract but do not replace the accepted 22-requirement PRD.
- **Major risks:** replay after interruption, scope escape, secrets in builder worktree, an unauthenticated review treated as acceptance, and stale candidate identity.
- **Sequence:** CLI and ledger → one isolated task → restart refusal/reconciliation → independent audit → reviewable PR.
- **Decision:** Proceed within AURA-M0-CLI-001; keep paid and production trust activation blocked.

## Proposed cross-family audit resolution (inactive)

The inherited policy requires the reviewer to come from a different provider family. That blocks Luna (`openai`) paired with Astra (`openai`) even though the owner chose Astra as auditor. Proposed narrowly scoped rule: allow this one pairing only when the builder and reviewer are distinct configured identities, the reviewer receives a fresh context that excludes builder reasoning and credentials, review is bound to the exact repository, packet, base, candidate tree and required checks, and a detached receipt verifies against an owner-pinned trust root. Any missing field or candidate/check mutation refuses acceptance. DeepSeek and Astra remain cross-family. The rule needs an owner decision, a separate protected policy packet and independent review before activation.

Required tests for that future packet: same identity refusal; absent trust refusal; caller-supplied key refusal; missing review context refusal; leaked builder reasoning refusal; changed tree, base, packet or checks refusal; valid distinct Luna/Astra identities under owner-pinned trust acceptance; DeepSeek/Astra existing cross-family path unchanged; restart preserves reviewer and evidence binding. The current packet does not change policy.

## Provider verification boundary

Published IDs on 2026-09-25: DeepSeek V4.1 Flash uses `deepseek-flash`; OpenAI Sol, Luna and Astra use `gpt-6-sol`, `gpt-6-luna`, and `gpt-6-astra`. MiniMax publishes `MiniMax-M3`, but owner selection of a utility variant remains open. Published IDs are not account access, adapter validation, or call authority. The inherited provider registry has a DeepSeek adapter and an OpenAI adapter, but no MiniMax entry and no verified GPT-6 Responses role routing. No live call is in scope.

Sources: https://api-docs.deepseek.com/quick_start/pricing/ ; https://developers.openai.com/api/docs/models ; https://platform.minimax.io/docs/guides/text-generation
