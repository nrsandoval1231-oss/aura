# WSL runner acceptance transcript

Exact command (PowerShell, repository root):

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
& 'C:/Users/nrsan/.codex/worktrees/aura-m0-m1/Aura/.venv/Scripts/python.exe' -m pytest tests/test_aura_sandbox.py -q -x -k real_wsl_runner_denies
```

Result: exit 0, 1 passed, 3 deselected in 5.00s (raw command output: `focused-wsl-runner.raw.txt`).

The disposable task changed `src/value.py` and added `tests/test_value.py` under objective “Change the bounded example value to two and test it.” It returned `REVIEW_REQUESTED`, never approval. Evidence is in `successful-run-evidence.json`; patch is in `candidate-result`. Source base: 6b4d3dd87cbad3c2e5e70d61dff3438ba998233a; candidate: e080f2292ec0e01b917101bddb74161a38f8b5a5; tree: 0402c3c97a85ceadcc9f9caa43d38180e50e9b3b.

Observed denial report: CPU limit ENFORCED; memory limit ENFORCED; max fork count 5 under the NPROC=8 regression; 65,536-byte per-file cap; 5,242,880-byte candidate tmpfs with measured fill 4,886,528 bytes; network errno 101; host file invisible; outside writes false; adversarial fsmonitor, filter, and hook invoked without escape. Separate verifier returned `VERIFIED`, read-only check `PASS`, and reran the fixed unittest with matching output hash. Provider call false; measured spend $0.
