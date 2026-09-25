# FORGE-EVID-001 builder handoff

Implementation candidate: `641d2a932f140b8e1f51c0f7d468d764c445c270`
Base: `4810f0114004e2c691b01da7695a22e96d39bd66`

## Changes

- `scripts/run_slice.py` rejects pending evidence unless a trusted external
  verifier is available. Local process keys, simulated `AuditReport(PASS)`, and
  forged JSON artifacts are not accepted as independent approval.
- `scripts/run_slice.py` verifies the new core-ledger reconciliation stream
  against retained SLICE and ledger identities, detects duplicate records and
  checkpoint/truncation corruption, and requires every redirected graph packet
  to be represented. Explicit `ABSENT` evidence covers packets with no old
  slice stream.
- `tests/test_slice_contexts.py` covers the simulated false-green refusal and
  malformed reconciliation refusal.

## Evidence

- `$env:PYTHONPATH='src'; ...python.exe -m pytest -q tests/test_slice_contexts.py tests/test_cli.py tests/test_gate_parity.py` — exit 0, 51 passed.
- `...python.exe -m forge.cli ledger verify FORGE-EVID-001 --root .agent/ledger` — exit 0, 8 receipts.
- `$env:PYTHONPATH='src'; ...python.exe -m ruff check scripts/run_slice.py tests/test_slice_contexts.py` — exit 0.
- `git diff --check` — exit 0.
- `...python.exe scripts/run_slice.py --check` — exit 1 as required while the
  integrated successor has no exact independent audit and historical bindings
  remain stale. No evidence was rewritten.

## Boundary

The repository has no trusted external public-key custody. The slice gate stays
red even when a matching local JSON claim is present; Sol must keep it red until
the independent audit is verified under the repository's chosen trust
arrangement. No paid call or external effect was used.
