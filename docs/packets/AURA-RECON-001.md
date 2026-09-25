# AURA-RECON-001 — Preserve Forge history while verifying Aura redirects

Parent: AURA-INTEGRATED-002. Base: `bd534f7c8b4aa7c93b2e1550ee3fbb953a4121ca`.
The first integrated attempt is retained under AURA-INTEGRATED-001 and rejected
because the full slice gate was red. This is the first materially different repair.

## Objective

Verify Aura's new redirected packet history using a separate append-only
`AURA-EVID-001` stream while continuing to verify the unchanged Forge
`FORGE-EVID-003` stream. Do not make the gate optional or accept missing records.

## Allowed files

- `scripts/run_slice.py`
- `tests/test_slice_contexts.py`
- `.agent/ledger/AURA-EVID-001.jsonl`
- `.agent/ledger/AURA-EVID-001.checkpoint.json`
- `docs/packets/AURA-RECON-001.md`

## Exclusions

No edit, rebind, or replacement of Forge ledgers, checkpoints, receipts, slices,
audit trust, canonical documents, or validation authority script. No model
call, external effect, push, merge, or deployment.

## Invariants

The gate must match the union of authenticated records across the Forge and
Aura streams to the exact set of redirected graph packet references. A missing,
duplicate, forged, truncated, wrong-successor, or false-evidence-class record
fails closed. Existing Forge tests and bytes stay unchanged. For FORGE-ADAPT-001,
AURA-MIG-001, and AURA-RUN-001, `NO_LEGACY_EVIDENCE` refers specifically to
the absence of canonical SLICE.json and core ledger; other completion artifacts
remain historical evidence and cannot be called Aura acceptance.

## Acceptance

Add adversarial tests for the two-stream union and all absence/mismatch cases;
run affected tests, Ruff, graph and ledger verification. Sol reruns the full
gate and exact candidate binding under AURA-INTEGRATED-002. Independent Astra
reviews the frozen integrated candidate; the builder does not certify it.

## Authority and handoff

A3 protected gate repair under the owner's explicit Aura migration and
integration direction. Two materially different repairs maximum. Luna owns
only the five allowed paths and produces command exits, file hashes, and
remaining uncertainty. Sol owns graph and current state. No completion or
merge claim from local tests.
