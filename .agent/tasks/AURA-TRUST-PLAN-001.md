# AURA-TRUST-PLAN-001 — Owner-held detached review plan

Status: READY. Documentation-only governance packet after the owner selected
an owner-held, passphrase-protected audit key arrangement. It does not create
or pin a key or activate trusted review.

## Base

- `581c4506819f8b7e2e393857193cd5f1295ec42a` on
  `codex/aura-trust-bootstrap`, branched from the M0 CLI candidate in
  `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-TRUST-PLAN-001.md`
- `.agent/artifacts/AURA-TRUST-PLAN-001/**`
- `.agent/ledger/AURA-TRUST-PLAN-001.*`
- `docs/packets/AURA-TRUST-PLAN-001.md`
- `docs/AURA_HANDOFF.md`

## Objective

Specify how the owner generates and retains an encrypted private key outside
all Aura/Codex workspaces, approves only the public-key fingerprint, and signs
an exact-candidate receipt after an independent Astra review. Keep reviewer
identity separate from owner attestation. Identify the current Forge-only
verifier bindings and a bounded protected migration plan with fail-closed tests.

## Exclusions, authority and acceptance

No private key or passphrase generation by an agent, no key import, trust pin,
protected verifier edit, gate change, provider call, merge, or production
approval. The owner selected key custody, not a specific key fingerprint. The
plan must enumerate precise migration surfaces, tests for wrong/missing trust
and altered candidate/check evidence, and the bootstrap decision needed from
the owner. Run graph/diff checks, local `./scripts/validate.sh`, retain the
mandatory red gate, and obtain independent audit of the exact plan candidate.
No rewrite of M0 evidence. Retry budget two distinct documentation repairs.
