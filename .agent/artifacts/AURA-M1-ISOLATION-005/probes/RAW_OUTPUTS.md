# Captured command output

Each `*.raw.b64` file is the exact raw console byte stream encoded as Base64.
Decode with PowerShell:

```powershell
$bytes = [Convert]::FromBase64String([IO.File]::ReadAllText('FILE.raw.b64'))
[IO.File]::WriteAllBytes('FILE.raw.txt', $bytes)
```

The SHA-256 below is of the decoded raw bytes, not the Base64 text.

| File | Decoded SHA-256 | Command and exit |
|---|---|---|
| `review-patch-base-regression.raw.b64` | `6f7f3eed1e9d629ec0dfd6425ab2a7178608f46780a4e30341daf09b307a248a` | command in `review-patch-base-regression.command.txt`; exit 1, expected sentinel assertion on source base `83775200a99914f97bb2ec3f62cc24b76d5efdd9` |
| `review-patch-diagnostic.raw.b64` | `5fa1d14a6e733f38f8d79e5bc9e44f92919bdb39f0e8d26af0b2b0e10e20db20` | `pytest tests/test_aura_sandbox.py -q -s -x -k review_patch_comes_from_verified_objects`; exit 1, fixture diagnosis |
| `review-patch-debug.raw.b64` | `f7dce82e5e6bad5c06714568eff59347b5a4617d3938de4c5eb16b9bd1289727` | same focused regression; exit 1, shows elapsed-time output difference |
| `review-patch-repair.raw.b64` | `3599a8824e52cfb62d42deda2a8c64a887547284935133f09b2f95bdfc2a352a` | focused patch and elapsed-normalization regressions; exit 0 |
| `restart-and-denial.raw.b64` | `a9fecaeb90c5bad21d70f70d8d38e94fbf3d8c7993ff7aaa966cd4b270bb4e6d` | `pytest tests/test_aura_sandbox.py -q -s -k 'killed_wsl_child_restart or real_wsl_runner_denies_local_effects'`; exit 0 |
| `full-sandbox-tests.raw.b64` | `334d6954c2dfe4cd8c7c1f09d398f687e4a302f267cf59cd1a2292879f78bf14` | `pytest tests/test_aura_sandbox.py -q`; exit 0 |
| `full-repo-pytest.raw.b64` | `142e9297831ab522e72f14daa69ad39cf6fd2027ec69c4f69f14e368e9f79032` | `pytest -q`; exit 1, 582 passed, 1 skipped, 1 unrelated timeout-budget failure |
| `aura-executor-timeout-isolated.raw.b64` | `866d58cf3cc739a8e97325d38fdbb3b7f535812f6c9b4afa3c6bc5fd83da8601` | isolated failing executor test; exit 1 |
| `run-slice.raw.b64` | `962f0981ed69bc95eaca9e8db41602be918f00f39e6f100fb8fb46ce6c4275dd` | canonical slice attempt, exit 1. It overlapped a duplicate local invocation; summary was 3 failures. A later serialized full pytest established the single deterministic failure. No 005 slice or ledger was written. |
| `run-slice-916c416.raw.b64` | `9981f7a83c8d5b5ac06374e91c7997a3cfeae367c386f71fb8d7ae253f3a4088` | `python scripts/run_slice.py --packet AURA-M1-ISOLATION-005` with `PYTHONPATH=src` and `FORGE_SLICE_BASE=83775200a99914f97bb2ec3f62cc24b76d5efdd9`; exit 0, serialized, no `--rebind`. Local simulated Auditor and merge eligibility only. |
