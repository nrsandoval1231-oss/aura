# AURA-M0-CLI-003 — Fresh integrated M0 CLI evidence

Status: BLOCKED until owner-signed AURA-TRUST-002 exact-candidate attestation.
This is an evidence successor for the already implemented M0 CLI. It preserves
all AURA-M0-CLI-001 and -002 ledgers and slice artifacts unchanged.

## Objective

Bind the existing six-command Aura M0 CLI and the approved Aura trust verifier
to one exact integrated candidate with a fresh append-only local slice, a
separate independent review, and owner-signed detached receipt. Keep `build`
truthfully blocked until a real authorized builder is connected.

## Base

- `cc3e78f74f0dac4982cafb6398bbd71fc1b0e521` on
  `codex/aura-m0-evidence-successor` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M0-CLI-003.md`
- `.agent/artifacts/AURA-M0-CLI-003/**`
- `.agent/ledger/AURA-M0-CLI-003.*`
- `docs/packets/AURA-M0-CLI-003.md`

## Exclusions

No edits to the M0 CLI implementation, inherited Forge trust, Aura verifier,
validation gates, historical ledgers/slice files, PRD/architecture, provider
routing, or executor. The local `run_slice.py` model roles and MERGE_ELIGIBLE
state are simulated proof, never an external audit or merge authority.

## Acceptance and handoff

First verify the owner signature and packet-specific detached check against
clean exact `cc3e78f`, with the independent ACCEPT and pre-audit gates bound
to that commit. Then transition AURA-TRUST-002 to COMPLETE in this graph,
recording that the trust packet itself passed while the old M0 binding kept the
repository-wide slice gate red. Only then activate AURA-M0-CLI-003. Run
the new packet's local slice into new ledger/artifact paths without `--rebind`.
Record exact candidate, required green pre-audit gates, new ledger verification,
fresh independent review, owner-signed external receipt, and full
`./scripts/validate.sh` output. Preserve UNKNOWN on absent/ambiguous effects.
No provider call or merge. Protected evidence risk, two materially distinct
repair attempts maximum. Handoff includes base/head/tree, changed paths,
commands and exits, raw reviewer verdict, signed receipt verification, and
measured versus UNKNOWN spend.
