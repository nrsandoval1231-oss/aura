# FORGE-AUDIT-TRUST-002 — Pin the approved one-time manifest-repair auditor

**Node:** FORGE-AUDIT-TRUST-002 (governed trust update for an accepted protected repair)
**Status:** IN_PROGRESS; no graph transition is authorized by this packet
**Repository:** nrsandoval1231-oss/forge-agent
**Branch/worktree:** codex/audit-manifest-repair in an isolated worktree
**Base SHA:** f0b89694efcf75ffac4c9fd3a15db7b5f6cd2987
**Authority:** A3; owner approved the exact public-key fingerprint on 2026-09-22
**Risk:** HIGH; this record selects the only key accepted for detached audit evidence

## Objective

Replace the already-used one-time auditor trust pin with the fresh one-time
public key approved by the owner for the exact manifest-repair candidate. Keep
all private key, receipt, payload, and signature material outside the repository.

## Approved trust

- Auditor ID: `FORGE-AUDIT-MANIFEST-001-independent-auditor-d05f6366b1b7`
- Public-key SHA-256: `d05f6366b1b769bddc706552155b0e6780baadd82479bd4de3e054264e48f9f6`
- External key directory:
  `C:/Users/nrsan/AppData/Local/ForgeAgent/audit-receipts/forge-audit-manifest-f0b8969-20260922211908`

## Allowed files

- `.agent/audit-trust.json`
- `docs/packets/FORGE-AUDIT-TRUST-002.md`
- `.agent/artifacts/FORGE-AUDIT-TRUST-002/**`

## Exclusions

Do not alter the repair implementation, tests, graph, canonical architecture,
PRD, Finish Contract, validation runner, ledgers, historical receipts, or any
external key bytes. Do not sign, push, merge, deploy, call providers, or spend.

## Acceptance

1. The trust record contains exactly schema version 1, the approved auditor ID,
   and the approved public-key fingerprint.
2. The external public key independently hashes to the pinned fingerprint.
3. The private key, receipt, signature, and signed payload remain outside Git.
4. The resulting exact commit receives a fresh independent audit and detached
   signature before the repository gate can pass.

## Handoff

Record the prior and new trust identities, exact changed paths, validation, and
remaining unsigned state in
`.agent/artifacts/FORGE-AUDIT-TRUST-002/COMPLETION.json`. Do not self-certify,
commit, push, merge, sign, or change graph state.
