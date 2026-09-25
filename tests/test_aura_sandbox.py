"""Behavioral checks for the unwired offline Bubblewrap runner."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
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


def test_check_digest_normalizes_only_unittest_elapsed_time():
    first = b"test_value ... ok\nRan 1 test in 0.001s\n\nOK\n"
    second = b"test_value ... ok\nRan 1 test in 0.000s\n\nOK\n"
    changed_result = b"test_value ... FAIL\nRan 1 test in 0.001s\n\nFAILED\n"
    assert aura_sandbox._check_digest(first) == aura_sandbox._check_digest(second)
    assert aura_sandbox._check_digest(first) != aura_sandbox._check_digest(changed_result)


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


@pytest.mark.skipif(
    os.name != "nt", reason="Process-tree kill regression targets the Windows WSL host"
)
def test_killed_wsl_child_restart_in_fresh_process_stays_unknown(tmp_path):
    if not _wsl_available():
        pytest.skip("Ubuntu WSL is unavailable")
    repo, base = _repo(tmp_path)
    marker = tmp_path / "sandbox-started.json"
    controller = tmp_path / "start_sandbox.py"
    controller.write_text(
        textwrap.dedent(
            """
            import json
            import subprocess
            import sys
            from pathlib import Path
            from forge import aura_sandbox

            repo, base, root, marker = sys.argv[1:]
            marker = Path(marker)
            original_driver = aura_sandbox._driver_source
            def paused_driver():
                source = original_driver()
                sentinel = "main()\\n"
                assert source.endswith(sentinel)
                return source[:-len(sentinel)] + (
                    "print('AURA_SANDBOX_CHILD_STARTED', flush=True)\\n"
                    "import time; time.sleep(120)\\nmain()\\n"
                )
            aura_sandbox._driver_source = paused_driver
            original_run = subprocess.run
            def observe_sandbox(args, *positional, **kwargs):
                if isinstance(args, list) and args[:1] == ['wsl.exe'] and '/usr/bin/timeout' in args:
                    child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    first_line = child.stdout.readline()
                    marker.write_text(json.dumps({
                        'wsl_pid': child.pid,
                        'sandbox_stdout': first_line.decode('utf-8', 'replace').strip(),
                    }))
                    stdout_rest, stderr = child.communicate()
                    return subprocess.CompletedProcess(
                        args, child.returncode, first_line + stdout_rest, stderr
                    )
                return original_run(args, *positional, **kwargs)
            aura_sandbox.subprocess.run = observe_sandbox
            aura_sandbox.execute_proposal(
                repo,
                objective='Change the bounded example value to two and test it.',
                base_sha=base,
                allowed_paths=['src/value.py', 'tests/test_value.py'],
                files={
                    'src/value.py': 'VALUE = 2\\n',
                    'tests/test_value.py': (
                        'import unittest\\nfrom src.value import VALUE\\n'
                        'class ValueTest(unittest.TestCase):\\n'
                        '    def test_value(self): self.assertEqual(VALUE, 2)\\n'
                    ),
                },
                state_root=Path(root) / 'state',
                result_root=Path(root) / 'results',
            )
            raise SystemExit('stalled sandbox unexpectedly returned')
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    first = subprocess.Popen(
        [sys.executable, str(controller), str(repo), base, str(tmp_path), str(marker)],
        cwd=Path(__file__).parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline and first.poll() is None and not marker.exists():
        time.sleep(0.05)
    if not marker.exists():
        first.kill()
        output, _ = first.communicate(timeout=5)
        pytest.fail(f"Sandbox did not reach its started marker; child said: {output}")
    started = json.loads(marker.read_text(encoding="utf-8"))
    ledger_path = tmp_path / "state" / f"{aura_sandbox.STREAM_ID}.jsonl"
    assert ledger_path.is_file(), "durable intent must precede sandbox launch"
    intent_rows = [
        json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in intent_rows] == ["AURA_SANDBOX_INTENT"]
    assert started["sandbox_stdout"] == "AURA_SANDBOX_CHILD_STARTED"

    killed = subprocess.run(
        ["taskkill.exe", "/PID", str(first.pid), "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if first.poll() is None:
        first.wait(timeout=10)
    print(f"controller_pid={first.pid}")
    print(f"wsl_pid={started['wsl_pid']}")
    print(f"sandbox_started_stdout={started['sandbox_stdout']}")
    print(
        f"taskkill_exit={killed.returncode} output={killed.stdout.strip()} {killed.stderr.strip()}".strip()
    )
    print(f"first_process_exit={first.returncode}")
    assert killed.returncode == 0

    retry_probe = tmp_path / "retry-effect-called"
    restart = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import json, sys
                from pathlib import Path
                from forge import aura_sandbox
                repo, base, root, effect_marker = sys.argv[1:]
                def probe():
                    Path(effect_marker).write_text('called')
                    return ['wsl.exe', '-d', 'Ubuntu', '--exec', '/usr/bin/true']
                aura_sandbox._runtime_probe = probe
                try:
                    aura_sandbox.execute_proposal(
                        repo,
                        objective='Change the bounded example value to two and test it.',
                        base_sha=base,
                        allowed_paths=['src/value.py', 'tests/test_value.py'],
                        files={
                            'src/value.py': 'VALUE = 2\\n',
                            'tests/test_value.py': (
                                'import unittest\\nfrom src.value import VALUE\\n'
                                'class ValueTest(unittest.TestCase):\\n'
                                '    def test_value(self): self.assertEqual(VALUE, 2)\\n'
                            ),
                        },
                        state_root=Path(root) / 'state',
                        result_root=Path(root) / 'results',
                    )
                except aura_sandbox.SandboxError as error:
                    print(json.dumps({'status': 'UNKNOWN', 'code': error.code, 'message': str(error)}))
                    raise SystemExit(0 if error.code == 'UNKNOWN_EFFECT' else 4)
                raise SystemExit('retry unexpectedly executed')
                """
            ),
            str(repo),
            base,
            str(tmp_path),
            str(retry_probe),
        ],
        cwd=Path(__file__).parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    events = [row["event"] for row in rows]
    print(f"fresh_process_exit={restart.returncode} output={restart.stdout.strip()}")
    print(f"ledger_events={events} intent_count={events.count('AURA_SANDBOX_INTENT')}")
    print(f"retry_effect_marker_exists={retry_probe.exists()}")
    assert restart.returncode == 0, restart.stderr
    assert json.loads(restart.stdout.strip())["status"] == "UNKNOWN"
    assert events.count("AURA_SANDBOX_INTENT") == 1
    assert not retry_probe.exists(), "a restarted UNKNOWN run must not launch another WSL effect"


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
    print(f"denial_probe={evidence['denial_probe']}")
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
def test_review_patch_comes_from_verified_objects_not_candidate_diff_config(tmp_path):
    repo, base = _repo(tmp_path)
    test_source = (
        "import os, subprocess, unittest\n"
        "class CandidateDiffConfig(unittest.TestCase):\n"
        "    def test_install_candidate_local_textconv(self):\n"
        "        if os.getcwd() == '/out/worktree':\n"
        "            subprocess.run(['/usr/bin/git', 'config', 'diff.hidden.textconv', '/bin/true'], check=True)\n"
        "        self.assertEqual('AURA_REVIEW_PATCH_MUST_SHOW_THIS', 'AURA_REVIEW_PATCH_MUST_SHOW_THIS')\n"
    )
    result = aura_sandbox.execute_proposal(
        repo,
        objective="Add a test that exercises candidate-local diff configuration.",
        base_sha=base,
        allowed_paths=[".gitattributes", "tests/test_candidate_diff_config.py"],
        files={
            ".gitattributes": "tests/test_candidate_diff_config.py diff=hidden\n",
            "tests/test_candidate_diff_config.py": test_source,
        },
        state_root=tmp_path / "state",
        result_root=tmp_path / "results",
    )
    assert result["status"] == "REVIEW_REQUESTED"
    evidence = json.loads(Path(result["evidence_path"]).read_text(encoding="utf-8"))
    patch = Path(result["patch_path"]).read_bytes()
    assert evidence["changed_paths"] == [".gitattributes", "tests/test_candidate_diff_config.py"]
    assert b"tests/test_candidate_diff_config.py diff=hidden" in patch
    assert b"AURA_REVIEW_PATCH_MUST_SHOW_THIS" in patch
    assert evidence["patch_sha256"] == aura_sandbox._hash(patch)
    verifier = evidence["independent_verifier"]
    assert verifier["candidate_sha"] == evidence["candidate_sha"]
    assert verifier["tree_sha"] == evidence["tree_sha"]
    assert verifier["changed_paths"] == evidence["changed_paths"]
    assert base64.b64decode(verifier["patch_b64"], validate=True) == patch
    assert verifier["patch_sha256"] == evidence["patch_sha256"]
    assert verifier["patch_binding"] == evidence["patch_binding"]
    assert verifier["patch_binding"] == {
        "candidate_sha": evidence["candidate_sha"],
        "tree_sha": evidence["tree_sha"],
        "changed_paths": evidence["changed_paths"],
        "check_sha256": verifier["test_output_sha256"],
    }


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
