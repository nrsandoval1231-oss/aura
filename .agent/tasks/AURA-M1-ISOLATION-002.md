# AURA-M1-ISOLATION-002 — Reproducible isolation feasibility

Status: READY. Repair-only successor to independently rejected exact d2f9627.

## Base

- `d2f96278e479da7bc1d786fc12824cacd640b4de` on
  `codex/aura-m1-executor-spike` in `nrsandoval1231-oss/aura`.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-ISOLATION-002.md`
- `.agent/tasks/AURA-M1-ISOLATION-003.md`
- `.agent/artifacts/AURA-M1-ISOLATION-001/REVIEW-d2f9627.json`
- `.agent/artifacts/AURA-M1-ISOLATION-002/**`
- `.agent/ledger/AURA-M1-ISOLATION-002.*`
- `docs/packets/AURA-M1-ISOLATION-002.md`

## Objective

Retain runnable scripts and raw outputs for filesystem/network, Git local
configuration, fixed unittest candidate, and process-restart UNKNOWN probes.
Report exact exit codes and environmental limits. Freeze a separate proposed
implementation packet with exact files, invariants, finite budgets, checks,
rollback and owner authority. Do not change executor code or activate a
provider, CLI dispatch, trust pin, or production sandbox.

## Acceptance and validation

Probe scripts rerun from a clean repo checkout and capture raw stdout/stderr
without credentials. Their results distinguish observed denial from an absent
runtime or untested boundary. `AURA-M1-ISOLATION-003` is a bounded implementation
proposal, not READY until this correction receives independent audit. Run
focused probe checks, graph/ledger/diff checks, full `./scripts/validate.sh`
on the frozen candidate, then a fresh independent Astra review. Preserve the
historical d2f9627 slice and raw CORRECT. One bounded repair attempt remains.
