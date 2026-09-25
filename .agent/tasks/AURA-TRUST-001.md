# AURA-TRUST-001 — Aura detached audit verifier

Status: READY. Owner approved the exact SHA-256 public PEM fingerprint
`55faf401c993f16fd0a9d4f0e9d58babd61ccb018f6bd6cb2a9c7087505de1c1`.
The owner retains the encrypted private key outside all workspaces. This packet
authorizes public-key pinning and verifier implementation, not owner signing,
merging, provider spend, or activation of Luna/Astra audit pairing.

## Objective

Implement an Aura-specific detached exact-candidate review check while retaining
the Forge verifier and CLI compatibility. Bind the approved public-key fingerprint,
independent reviewer evidence, owner attestation, exact candidate, and gate output.

## Base

- `0e4f8382afe5943ab11296e1bae8ba6e7a4cf431` on
  `codex/aura-trust-verifier` in `nrsandoval1231-oss/aura`; clean isolated worktree.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/DECISIONS.md`
- `.agent/aura-audit-trust.json`
- `.agent/tasks/AURA-TRUST-001.md`
- `.agent/artifacts/AURA-TRUST-001/**`
- `src/forge/aura_audit.py`
- `src/forge/audit_receipts.py`
- `scripts/run_slice.py`
- `tests/test_aura_audit.py`
- `docs/packets/AURA-TRUST-001.md`

## Exclusions

Do not edit historical ledgers or
receipts, canonical PRD/architecture/finish contract, provider credentials,
executor code, or validation gates to make them green.

## Acceptance

1. Fail closed for missing/wrong public key or receipt, changed commit/tree/blob,
   wrong Aura domain/repository/base/packet, changed or absent validation
   artifact, incomplete/failing required gates, missing independent reviewer
   evidence, signature mismatch, inline key/signature, or dirty checkout.
2. Keep reviewer and owner attestor identities distinct. The owner key ID is
   derived from the approved fingerprint; it is not represented as an Astra key.
3. Keep the inherited Forge `.agent/audit-trust.json` unchanged. External
   receipt, public PEM, and detached signature remain outside the
   candidate worktree. Test with ephemeral keys only.
4. Run focused tests, `./scripts/validate.sh`, inspect every failed gate, and
   obtain independent review of the exact frozen candidate before activation.
   Existing stale slice evidence remains red until separately renewed.

Risk: protected trust/security. Two materially distinct repair attempts.
Handoff: exact SHAs, changed paths, command exits, failures, reviewer verdict,
and measured versus UNKNOWN spend. Interrupted or ambiguous effects remain UNKNOWN.
