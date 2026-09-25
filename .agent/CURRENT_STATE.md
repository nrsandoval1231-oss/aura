# Aura current state

Repository: nrsandoval1231-oss/aura. Canonical branch: main.

Scope: AURA_ARCHITECTURE.md and AURA_PRD.md.
The inherited core and adaptive controller exist and have offline regression coverage.
The M0 CLI records durable bounded requests and refuses builder dispatch. There is no
operational single-builder or two-builder runner. Recovery remains advisory until integrated.
Production role routing and review verification are not configured. Audit trust
still fails closed. No live Aura performance improvement is claimed.
The owner generated an encrypted private key outside the Aura and Codex workspaces,
retains its passphrase, and approved public PEM SHA-256
`55faf401c993f16fd0a9d4f0e9d58babd61ccb018f6bd6cb2a9c7087505de1c1`.
The private key is not in this repository. AURA-TRUST-PLAN-001 received independent
ACCEPT at `0e4f838`; AURA-TRUST-001 is now READY for a protected Aura-specific
verifier migration. This is not audit activation or candidate acceptance.

The graph tracks remaining Aura milestones; no Forge completion status is inherited.
The scope cleanup removes unrelated UI, optional decision services, external product
trial runners, and historical execution records. Source history remains in Git.

The first CLI candidate 53fb0e3 received independent CORRECT for a partial-ledger
loss defect. AURA-M0-CLI-002 is the active repair and exact-candidate review packet.
The full gate's slice check remains red without owner-pinned detached audit trust.

Next: validate the corrected CLI, provision trusted review, then connect one
governed task and prove it before two-lane scheduling, stuck recovery, and learning.
