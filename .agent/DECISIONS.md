# Aura decisions

- AURA-D001: The owner's September 24 scope statement is canonical: two builder loops,
  deterministic governance, stuck recovery, and independently reviewed shared learning.
- AURA-D002: Remove unrelated products and Forge-specific historical trial material from
  the active tree. Preserve Git history. Do not transfer Forge certification or authority.
- AURA-D003: Keep supporting runtime modules and their adversarial tests. Retain the
  `forge` import and CLI namespace to avoid a breaking rename during scope cleanup.
- AURA-D004: Offline deterministic proof fixtures are tests, not Aura live-run evidence.
- AURA-D005: Production audit trust is unprovisioned. Empty trust fields fail verification.
  Another repository's auditor pin must not silently become Aura's trust anchor.
- AURA-D006: Live role routing and Luna/Astra audit-policy reconciliation remain blocked
  pending verified configuration and explicit policy resolution. No silent fallback.
- AURA-D007: Validation is local. Independent review, owner authority, and live acceptance
  are separate from passing tests. No hosted or self-hosted CI runner is introduced.

- AURA-D008 (2026-09-25): Aura's product is a personal autonomous coding CLI with Nick's
  selected agent team. Persistent owner/project memory, on-demand skills and safe resume
  are requirements for the first usable release; target architecture image approved.
- AURA-D009 (2026-09-25): Deliver one complete live coding path, continuity, two lanes,
  then unattended builds. Measure accepted results, time, cost and intervention. Reuse
  useful draft work rather than restarting everything or treating the PR stack as the roadmap.
- AURA-D010 (2026-09-25): Add the user-facing aura CLI while retaining forge compatibility;
  this refines D003's temporary naming choice. Prefer one runtime with SQLite and Markdown,
  preserving clear state authority and existing valid ledgers. These are product targets.
