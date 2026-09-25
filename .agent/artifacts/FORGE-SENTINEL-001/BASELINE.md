# FORGE-SENTINEL-001 baseline, before a model call

- Forge runner candidate before this record: `26f35ffe555372e0f5686f6019c483942cc36282`.
- Local Sentinal worktree: `C:/Users/nrsan/AppData/Local/ForgeAgent/proving-ground/sentinal-run`, clean branch `codex/forge-sentinel-run`, exact base `d43e2629f2c3db87fdb1437a16f5e94a37136c53` from `nrsandoval1231-oss/sentinal`.
- Canonical Sentinal product direction stops further product build pending field data. This is a local, resettable validation experiment; no remote or product claim is made.
- Isolated Python environment: `C:/Users/nrsan/AppData/Local/ForgeAgent/proving-ground/sentinal-venv/Scripts/python.exe`. `pip install -e '.[dev]'` exited 0.

## Observations on the untouched target

| Command / condition | Exit | Result |
| --- | ---: | --- |
| `python -m pytest -q tests/test_assessment_artifact.py` | 0 | 27 passed |
| `python -m ruff check src tests` | 0 | all checks passed |
| `python -m pytest -q` with ordinary host PATH | 1 | 411 passed, 6 failed, 3 skipped; all six failures in `tests/test_ci_local.py` |
| `python -m pytest -q tests/test_ci_local.py` with `C:/Program Files/Git/bin` prepended to PATH | 0 | 12 passed |

On the ordinary host PATH, `Get-Command bash` resolves to
`C:/Users/nrsan/AppData/Local/Microsoft/WindowsApps/bash.exe`. Its launch
fails with WSL `Bash/Service/E_UNEXPECTED`, so `run_step` returns 1 before the
declared command runs. Git Bash is available at `C:/Program Files/Git/bin/bash.exe`.
The PATH control makes the affected tests pass without changing a file. The
observed failure is shell selection in the local validation runner; it says
nothing about generator reliability or field evidence.

No DeepSeek call, target edit, push, merge, or deployment had occurred at this
baseline checkpoint.
