from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from forge.aura_executor import Check, ExecutorLimits, Proposal, execute_proposal
from forge.ledger_store import LedgerStore
from forge.trust_kernel import ForgeError


def git(path: Path, *args: str) -> str:
    result = subprocess.run(("git", *args), cwd=path, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def repo_at(path: Path, *, object_format: str | None = None) -> str:
    path.mkdir()
    args = ["init", "-q"]
    if object_format:
        args.append(f"--object-format={object_format}")
    git(path, *args)
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")
    git(path, "config", "core.autocrlf", "false")
    (path / "README.md").write_text("base\n")
    git(path, "add", "README.md")
    git(path, "commit", "-qm", "base")
    return git(path, "rev-parse", "HEAD")


def run(tmp_path: Path, *, edits=None, invocation="one", checks=None):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    proposal = Proposal(
        invocation,
        base,
        edits or {"tests/test_candidate.py": "def test_real_check():\n    assert 2 + 2 == 4\n"},
    )
    result = execute_proposal(
        repo,
        proposal,
        allowed_paths=tuple(proposal.edits),
        checks=checks or (Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    return repo, base, result


def test_real_fixed_check_returns_exact_review_candidate_without_touching_source(tmp_path):
    repo, base, result = run(tmp_path)
    assert result["status"] == "REVIEW_REQUESTED"
    assert result["approval"] == "ABSENT"
    assert result["merge_eligible"] is False
    assert result["base_revision"] == base
    assert result["candidate"]["revision"] != base
    assert result["candidate"]["tree"] == git(Path(result["worktree"]), "rev-parse", "HEAD^{tree}")
    assert result["checks"][0]["returncode"] == 0
    successful_result = LedgerStore(tmp_path / "receipts", "aura-executor-effects").load()
    success_receipt = successful_result.receipts[-1]
    assert success_receipt.event == "AURA_EXEC_RESULT"
    assert success_receipt.payload["checks"][0]["status"] == "PASS"
    assert success_receipt.payload["checks"][0]["stdout_digest"]
    assert git(repo, "rev-parse", "HEAD") == base
    assert git(repo, "status", "--porcelain") == ""


def test_sha256_repository_uses_sha256_blob_binding(tmp_path):
    repo = tmp_path / "repo-sha256"
    try:
        base = repo_at(repo, object_format="sha256")
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Installed Git does not support SHA-256 repositories: {exc}")
    proposal = Proposal(
        "sha256",
        base,
        {"tests/test_candidate.py": "def test_sha256_tree():\n    assert True\n"},
    )
    result = execute_proposal(
        repo,
        proposal,
        allowed_paths=tuple(proposal.edits),
        checks=(Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    assert len(base) == 64
    assert len(result["candidate"]["revision"]) == 64
    assert result["status"] == "REVIEW_REQUESTED"


def test_refuses_passing_test_that_rewrites_its_own_candidate_bytes(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    test_body = (
        "from pathlib import Path\n"
        "def test_rewrite_source_after_collection():\n"
        "    source = Path(__file__)\n"
        "    source.write_text(source.read_text().replace('assert True', 'assert False'))\n"
        "    assert True\n"
    )
    proposal = Proposal("rewrite", base, {"tests/test_candidate.py": test_body})
    with pytest.raises(ForgeError, match="(?i)candidate.*changed"):
        execute_proposal(
            repo,
            proposal,
            allowed_paths=tuple(proposal.edits),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    receipts = LedgerStore(tmp_path / "receipts", "aura-executor-effects").load()
    failed_result = receipts.receipts[-1]
    assert failed_result.payload["status"] == "FAILED"
    assert failed_result.payload["checks"][0]["status"] == "PASS"
    candidate_revision = failed_result.payload["revision"]
    candidate_tree = failed_result.payload["tree"]
    target = tmp_path / "worktrees" / "rewrite"
    assert git(target, "rev-parse", "HEAD") == candidate_revision
    assert git(target, "rev-parse", "HEAD^{tree}") == candidate_tree
    assert git(target, "show", f"{candidate_revision}:tests/test_candidate.py") + "\n" == test_body
    assert git(target, "status", "--porcelain")


def test_pytest_ignores_proposal_module_and_config_shadowing(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    edits = {
        "tests/test_candidate.py": "def test_real_check():\n    assert True\n",
        "pytest.py": "raise SystemExit('proposal module shadowed pytest')\n",
        "pytest.ini": "[pytest]\naddopts = --invalid-proposal-option\n",
    }
    proposal = Proposal("pytest-shadow", base, edits)
    result = execute_proposal(
        repo,
        proposal,
        allowed_paths=tuple(edits),
        checks=(Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    assert result["status"] == "REVIEW_REQUESTED"
    assert result["checks"][0]["status"] == "PASS"


def test_git_uses_clean_environment_device_hooks_and_finite_timeout(tmp_path, monkeypatch):
    from forge import aura_executor

    repo = tmp_path / "repo"
    base = repo_at(repo)
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "hostile-git-dir"))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(repo / ".git" / "hooks"))
    original = aura_executor.subprocess.run
    observed = []

    def inspect(command, *args, **kwargs):
        if isinstance(command, tuple) and command and command[0] == "git":
            observed.append((command, kwargs))
            assert kwargs["timeout"] == 10
            assert "GIT_DIR" not in kwargs["env"]
            assert "GIT_CONFIG_COUNT" not in kwargs["env"]
            if "worktree" in command or "commit" in command:
                assert f"core.hooksPath={os.devnull}" in command
        return original(command, *args, **kwargs)

    monkeypatch.setattr(aura_executor.subprocess, "run", inspect)
    proposal = Proposal(
        "clean-git",
        base,
        {
            "candidate.txt": "ok\n",
            "tests/test_candidate.py": "def test_real_check():\n    assert True\n",
        },
    )
    result = execute_proposal(
        repo,
        proposal,
        allowed_paths=tuple(proposal.edits),
        checks=(Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    assert result["status"] == "REVIEW_REQUESTED"
    assert observed


def test_git_timeout_fails_before_recording_effect(tmp_path, monkeypatch):
    from forge import aura_executor

    repo = tmp_path / "repo"
    base = repo_at(repo)
    original = aura_executor.subprocess.run

    def timeout(command, *args, **kwargs):
        if isinstance(command, tuple) and command and command[0] == "git":
            raise subprocess.TimeoutExpired(command, timeout=kwargs["timeout"])
        return original(command, *args, **kwargs)

    monkeypatch.setattr(aura_executor.subprocess, "run", timeout)
    with pytest.raises(ForgeError, match="Git operation.*10 second"):
        execute_proposal(
            repo,
            Proposal("git-timeout", base, {"candidate.txt": "ok\n"}),
            allowed_paths=("candidate.txt",),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    assert not (tmp_path / "receipts").exists()


@pytest.mark.parametrize("bad", ["../escape", "/absolute", "src\\escape", "AGENTS.md"])
def test_refuses_escape_and_protected_paths_before_effect(tmp_path, bad):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    with pytest.raises(ForgeError):
        execute_proposal(
            repo,
            Proposal("one", base, {bad: "bad"}),
            allowed_paths=(bad,),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    assert not (tmp_path / "receipts").exists()


def test_rejects_drive_paths_and_state_roots_inside_source(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    with pytest.raises(ForgeError, match="Invalid|Protected"):
        execute_proposal(
            repo,
            Proposal("drive", base, {"C:/outside.txt": "x"}),
            allowed_paths=("C:/outside.txt",),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    with pytest.raises(ForgeError, match="outside"):
        execute_proposal(
            repo,
            Proposal("nested", base, {"inside.txt": "x"}),
            allowed_paths=("inside.txt",),
            checks=(Check("pytest"),),
            receipt_root=repo / "receipts",
            worktree_root=tmp_path / "worktrees",
        )


def test_case_colliding_allowlist_is_refused_before_effect(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    with pytest.raises(ForgeError, match="case-colliding"):
        execute_proposal(
            repo,
            Proposal("collision", base, {"File.txt": "x"}),
            allowed_paths=("File.txt", "file.txt"),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    assert not (tmp_path / "receipts").exists()


def test_symlink_path_is_refused(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    try:
        (repo / "link").symlink_to("README.md")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"OS cannot create symlinks: {exc}")
    git(repo, "config", "core.symlinks", "true")
    git(repo, "add", "link")
    git(repo, "commit", "-qm", "add symlink")
    base = git(repo, "rev-parse", "HEAD")
    with pytest.raises(ForgeError, match="symlink"):
        execute_proposal(
            repo,
            Proposal("symlink", base, {"link/child.txt": "x"}),
            allowed_paths=("link/child.txt",),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )


def test_check_environment_drops_credentials(tmp_path, monkeypatch):
    from forge import aura_executor

    repo = tmp_path / "repo"
    base = repo_at(repo)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    seen = {}
    original = aura_executor.subprocess.run

    def capture(command, *args, **kwargs):
        if isinstance(command, tuple) and "pytest" in command:
            seen.update(kwargs["env"])
        return original(command, *args, **kwargs)

    monkeypatch.setattr(aura_executor.subprocess, "run", capture)
    proposal = Proposal(
        "sanitized",
        base,
        {"tests/test_candidate.py": "def test_check():\n    assert True\n"},
    )
    execute_proposal(
        repo,
        proposal,
        allowed_paths=tuple(proposal.edits),
        checks=(Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    assert "OPENAI_API_KEY" not in seen
    assert "PYTHONNOUSERSITE" in seen and "PYTHONPATH" not in seen


def test_dirty_base_and_stale_base_are_refused(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    (repo / "README.md").write_text("dirty\n")
    kwargs = dict(
        allowed_paths=("tests/test_candidate.py",),
        checks=(Check("pytest"),),
        receipt_root=tmp_path / "receipts",
        worktree_root=tmp_path / "worktrees",
    )
    with pytest.raises(ForgeError, match="clean"):
        execute_proposal(repo, Proposal("dirty", base, {"tests/test_candidate.py": ""}), **kwargs)
    git(repo, "checkout", "--", "README.md")
    with pytest.raises(ForgeError, match="base"):
        execute_proposal(
            repo, Proposal("stale", "0" * 40, {"tests/test_candidate.py": ""}), **kwargs
        )


def test_fixed_check_failure_is_receipted_and_does_not_commit(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    with pytest.raises(ForgeError, match="failed"):
        execute_proposal(
            repo,
            Proposal(
                "failure", base, {"tests/test_candidate.py": "def test_fail():\n    assert False\n"}
            ),
            allowed_paths=("tests/test_candidate.py",),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
    assert git(repo, "rev-parse", "HEAD") == base
    records = (tmp_path / "receipts" / "aura-executor-effects.jsonl").read_text()
    assert "AURA_EXEC_INTENT" in records and "AURA_EXEC_RESULT" in records
    result_receipt = LedgerStore(tmp_path / "receipts", "aura-executor-effects").load().receipts[-1]
    assert result_receipt.event == "AURA_EXEC_RESULT"
    failure_check = result_receipt.payload["checks"][0]
    assert failure_check["status"] == "FAIL"
    assert failure_check["returncode"] != 0
    assert failure_check["stderr_digest"]
    assert "stderr" not in failure_check
    with pytest.raises(ForgeError, match="UNKNOWN"):
        execute_proposal(
            repo,
            Proposal("different", base, {"tests/test_candidate.py": ""}),
            allowed_paths=("tests/test_candidate.py",),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "retry-worktrees",
        )


def test_rejects_files_created_by_a_check_and_check_timeout(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    edit = {
        "tests/test_candidate.py": (
            "from pathlib import Path\n"
            "def test_adds_unapproved_file():\n"
            "    Path('surprise.txt').write_text('extra')\n"
        )
    }
    with pytest.raises(ForgeError, match="changed|scope"):
        execute_proposal(
            repo,
            Proposal("extra", base, edit),
            allowed_paths=tuple(edit),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts-extra",
            worktree_root=tmp_path / "worktrees-extra",
        )

    repo2 = tmp_path / "repo-timeout"
    base2 = repo_at(repo2)
    slow = {"tests/test_candidate.py": "import time\ndef test_slow():\n    time.sleep(2)\n"}
    with pytest.raises(ForgeError, match="timed out"):
        execute_proposal(
            repo2,
            Proposal("timeout", base2, slow),
            allowed_paths=tuple(slow),
            checks=(Check("pytest"),),
            receipt_root=tmp_path / "receipts-timeout",
            worktree_root=tmp_path / "worktrees-timeout",
            limits=ExecutorLimits(timeout_seconds=0.2, total_seconds=1),
        )


def test_intent_without_result_and_missing_checkpoint_fail_closed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    receipt_root = tmp_path / "receipts"
    # Simulate a process interruption after the durable intent append.
    from forge import aura_executor

    original = aura_executor._append

    def interrupt(store, ledger, event, payload):
        original(store, ledger, event, payload)
        if event == "AURA_EXEC_INTENT":
            raise RuntimeError("simulated interruption")

    monkeypatch.setattr(aura_executor, "_append", interrupt)
    arguments = dict(
        allowed_paths=("tests/test_candidate.py",),
        checks=(Check("pytest"),),
        receipt_root=receipt_root,
        worktree_root=tmp_path / "worktrees",
    )
    proposal = Proposal("interrupted", base, {"tests/test_candidate.py": ""})
    with pytest.raises(RuntimeError):
        execute_proposal(repo, proposal, **arguments)
    monkeypatch.setattr(aura_executor, "_append", original)
    with pytest.raises(ForgeError, match="UNKNOWN"):
        execute_proposal(repo, proposal, **arguments)
    (receipt_root / "aura-executor-effects.checkpoint.json").unlink()
    with pytest.raises(ForgeError):
        execute_proposal(repo, Proposal("another", base, proposal.edits), **arguments)


def test_rejects_unknown_check_name_without_running_caller_argv(tmp_path):
    repo = tmp_path / "repo"
    base = repo_at(repo)
    with pytest.raises(ForgeError, match="registered"):
        execute_proposal(
            repo,
            Proposal("bad-check", base, {"a.txt": "x"}),
            allowed_paths=("a.txt",),
            checks=(Check("pytest && echo unsafe"),),
            receipt_root=tmp_path / "receipts",
            worktree_root=tmp_path / "worktrees",
        )
