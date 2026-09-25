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
ACCEPT at `0e4f838`. The first verifier candidate `b23e3c8` received independent
CORRECT: its new authority surfaces were unregistered and its external public
key was read twice. AURA-TRUST-002 repaired both and received independent
ACCEPT at `b4d0889`. Fresh local trust slice evidence is retained at `cc3e78f`
and independently ACCEPTed for that bounded checkpoint. Its owner signature
is pending. On this successor branch, the slice gate instead reports the
AURA-TRUST-002 selected-file binding as stale because this packet changed the
graph and current state. The trust packet must finish at its exact `cc3e78f`
candidate before this successor is activated.

The graph tracks remaining Aura milestones; no Forge completion status is inherited.
The scope cleanup removes unrelated UI, optional decision services, external product
trial runners, and historical execution records. Source history remains in Git.

The first CLI candidate 53fb0e3 received independent CORRECT for a partial-ledger
loss defect. AURA-M0-CLI-002 code was corrected at `581c450`, but its local
slice binding is stale on the integrated tree. AURA-M0-CLI-003 is BLOCKED until
the exact trust checkpoint has owner attestation; it will create new evidence
without replacing the old ledger.

Next: verify owner attestation for exact `cc3e78f`, activate the M0 evidence
successor, then connect one governed task before two-lane scheduling.
