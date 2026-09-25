"""Behavioral checks for the unwired offline Bubblewrap runner."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from forge import aura_sandbox
from forge.ledger_store import LedgerStore


def _write(path: Path, content: str) -> None:
    path.write_bytes(content.encode("utf-8"))


def _repo(root: Path, *, hostile: bool = False) -> tuple[Path, str]:
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Aura test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "core.autocrlf", "false"], check=True)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    _write(repo / "src" / "value.py", "VALUE = 1\n")
    _write(
        repo / "tests" / "test_value.py",
        "import unittest\nfrom src.value import VALUE\n"
        "class ValueTest(unittest.TestCase):\n"
        "    def test_value(self): self.assertEqual(VALUE, 1)\n",
    )
    if hostile:
        script = repo / "fsmonitor.sh"
        _write(script, "#!/bin/sh\necho HOST_FSmonitor_RAN >&2\nexit 0\n")
        script.chmod(0o755)
        extra = repo / "included-config"
        _write(extra, '[filter "probe"]\n clean = /source/filter.sh\n')
        _write(repo / "filter.sh", "#!/bin/sh\ncat\n")
        (repo / "filter.sh").chmod(0o755)
        (repo / "hooks").mkdir()
        _write(repo / "hooks" / "pre-commit", "#!/bin/sh\nexit 0\n")
        (repo / "hooks" / "pre-commit").chmod(0o755)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True
    )
    base = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    if hostile:
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.fsmonitor", "/source/fsmonitor.sh"], check=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "core.hooksPath", "/source/hooks"], check=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "include.path", "/source/included-config"],
            check=True,
        )
    return repo, base


def _call(repo: Path, base: str, root: Path, *, files: dict[str, str] | None = None):
    return aura_sandbox.execute_proposal(
        repo,
        objective="Change the bounded example value to two and test it.",
        base_sha=base,
        allowed_paths=["src/value.py", "tests/test_value.py"],
        files=files
        or {
            "src/value.py": "VALUE = 2\n",
            "tests/test_value.py": "import unittest\nfrom src.value import VALUE\n"
            "class ValueTest(unittest.TestCase):\n"
            "    def test_value(self): self.assertEqual(VALUE, 2)\n",
        },
        state_root=root / "state",
        result_root=root / "results",
    )


def test_rejects_unauthorized_or_oversized_proposals_before_intent(tmp_path):
    repo, base = _repo(tmp_path)
    with pytest.raises(aura_sandbox.SandboxError, match="unauthorized"):
        aura_sandbox.execute_proposal(
            repo,
            objective="bad",
            base_sha=base,
            allowed_paths=["src/value.py"],
            files={"README.md": "unauthorized"},
            state_root=tmp_path / "state",
            result_root=tmp_path / "results",
        )
    assert not (tmp_path / "state" / f"{aura_sandbox.STREAM_ID}.jsonl").exists()


def test_interrupted_invocation_is_durable_unknown_and_never_retried(tmp_path, monkeypatch):
    repo, base = _repo(tmp_path)
    calls = 0

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise aura_sandbox.SandboxError("UNKNOWN_EFFECT", "injected child interruption")

    monkeypatch.setattr(aura_sandbox, "_runtime_probe", lambda: ["probe"])
    monkeypatch.setattr(
        aura_sandbox.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, b'{"ok":true}', b""),
    )
    monkeypatch.setattr(aura_sandbox, "_invoke_wsl", interrupted)
    with pytest.raises(aura_sandbox.SandboxError, match="interruption"):
        _call(repo, base, tmp_path)
    store = LedgerStore(tmp_path / "state", aura_sandbox.STREAM_ID)
    events = [receipt.event for receipt in store.load().receipts]
    assert events == ["AURA_SANDBOX_INTENT", "AURA_SANDBOX_UNKNOWN"]
    with pytest.raises(aura_sandbox.SandboxError, match="UNKNOWN_EFFECT"):
        _call(repo, base, tmp_path)
    assert calls == 1


def _wsl_available() -> bool:
    if shutil.which("wsl.exe") is None:
        return False
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "--exec", "/usr/bin/true"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@pytest.mark.skipif(not _wsl_available(), reason="Ubuntu WSL is unavailable")
def test_real_wsl_runner_denies_local_effects_and_returns_reviewable_exact_candidate(tmp_path):
    repo, base = _repo(tmp_path, hostile=True)
    result = _call(repo, base, tmp_path)
    assert result["status"] == "REVIEW_REQUESTED"
    assert result["provider_call"] is False and result["provider_spend_usd"] == 0
    assert result["base_sha"] == base and len(result["candidate_sha"]) in {40, 64}
    assert result["changed_paths"] == ["src/value.py", "tests/test_value.py"]
    evidence = json.loads(Path(result["evidence_path"]).read_text(encoding="utf-8"))
    assert evidence["independent_verifier"]["read_only_check"] == "PASS"
    assert evidence["independent_verifier"]["test_output_sha256"] == evidence["test_output_sha256"]
    assert evidence["denial_probe"]["outside_writes"] is False
    assert evidence["denial_probe"]["fsmonitor_invoked"] is True
    assert evidence["denial_probe"]["filter_invoked"] is True
    assert evidence["denial_probe"]["hook_invoked"] is True
    assert Path(result["patch_path"]).read_bytes().startswith(b"diff --git")
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == base
    )
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )
    replay = _call(repo, base, tmp_path)
    assert replay["candidate_sha"] == result["candidate_sha"]
    assert replay["idempotent_replay"] is True


@pytest.mark.skipif(not _wsl_available(), reason="Ubuntu WSL is unavailable")
def test_real_wsl_runner_rejects_check_that_rewrites_committed_candidate(tmp_path):
    repo, base = _repo(tmp_path)
    malicious = {
        "src/value.py": "VALUE = 2\n",
        "tests/test_value.py": "from pathlib import Path\nimport unittest\n"
        "class Rewrite(unittest.TestCase):\n"
        "    def test_rewrite(self):\n"
        "        Path(__file__).parents[1].joinpath('src/value.py').write_text('VALUE = 9\\n')\n"
        "        self.assertTrue(True)\n",
    }
    with pytest.raises(aura_sandbox.SandboxError):
        _call(repo, base, tmp_path, files=malicious)
    with pytest.raises(aura_sandbox.SandboxError, match="UNKNOWN_EFFECT"):
        _call(repo, base, tmp_path, files=malicious)
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == base
    )
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        == ""
    )
