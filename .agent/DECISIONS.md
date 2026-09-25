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
- AURA-D008: The owner approved public PEM SHA-256
  `55faf401c993f16fd0a9d4f0e9d58babd61ccb018f6bd6cb2a9c7087505de1c1`
  for an owner-held encrypted audit key. Its private half and passphrase remain
  outside Aura/Codex. The key ID is derived from this fingerprint and is an
  attestor identity distinct from the independent reviewer. Pinning the public
  fingerprint authorizes the protected verifier migration only; exact-candidate
  review, owner signing, and all normal gates are still required.
