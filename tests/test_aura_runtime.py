"""Offline acceptance for Aura's append-only M0 control plane."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from forge import aura_runtime
from forge.trust_kernel import Receipt


@pytest.fixture(autouse=True)
def isolated_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_HOME", str(tmp_path / "aura-state"))


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Aura Test"], check=True)
    (repo / "src").mkdir()
    (repo / "src" / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True
    )
    return repo


def _task(repo: Path) -> dict:
    return aura_runtime.init_task(repo, objective="bounded task", allowed_paths=["src/value.py"])


def test_init_and_pause_resume_persist_across_restart(tmp_path):
    repo = _repo(tmp_path)
    task = _task(repo)
    assert task["status"] == "READY"
    assert task["builder_adapter"] == "UNCONFIGURED"

    assert aura_runtime.pause(repo, task["task_id"])["status"] == "PAUSED"
    # Reconstruct state through the disk-backed ledger, not an in-memory object.
    assert aura_runtime.inspect(repo, task["task_id"])["status"] == "PAUSED"
    assert aura_runtime.resume(repo, task["task_id"])["status"] == "READY"
    state = aura_runtime.status(repo)
    assert state["tasks"][0]["task_id"] == task["task_id"]
    assert state["ledger"]["verified"] is True
    assert state["ledger"]["sequence"] == 3


def test_build_is_honestly_blocked_and_cannot_duplicate_dispatch(tmp_path):
    repo = _repo(tmp_path)
    task = _task(repo)
    result = aura_runtime.build(repo, task["task_id"])
    assert result["status"] == "BLOCKED"
    assert result["provider_call"] is False
    assert result["candidate"] == result["spend"] == "UNKNOWN"
    assert "isolated worktree" in result["reason"]
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="Build is unavailable"):
        aura_runtime.build(repo, task["task_id"])
    assert aura_runtime.inspect(repo, task["task_id"])["status"] == "BLOCKED"


def test_unknown_effect_survives_restart_and_blocks_build_or_resume(tmp_path):
    repo = _repo(tmp_path)
    task = _task(repo)
    ledger = aura_runtime._load(repo)
    payload = {"task_id": task["task_id"], "status": "UNKNOWN", "effect": "UNKNOWN"}
    previous = ledger.receipts[-1].receipt_hash
    receipt = Receipt.create(
        len(ledger.receipts) + 1, "AURA_EFFECT_UNKNOWN", None, None, payload, previous
    )
    ledger.append(receipt)
    aura_runtime._store(repo).append(receipt, ledger)

    assert aura_runtime.inspect(repo, task["task_id"])["status"] == "UNKNOWN"
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="reconciled"):
        aura_runtime.build(repo, task["task_id"])
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="before resume"):
        aura_runtime.resume(repo, task["task_id"])


def test_init_rejects_path_escape_and_unknown_task_is_blocked(tmp_path):
    repo = _repo(tmp_path)
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="safe repository paths"):
        aura_runtime.init_task(repo, objective="unsafe", allowed_paths=["../escape.py"])
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="No task"):
        aura_runtime.inspect(repo, "aura-absent")


def test_init_refuses_dirty_base_without_writing_runtime_state(tmp_path):
    repo = _repo(tmp_path)
    (repo / "local-change.txt").write_text("uncommitted\n", encoding="utf-8")
    with pytest.raises(aura_runtime.RuntimeErrorDetail, match="clean Git base"):
        aura_runtime.init_repository(repo)
    assert not aura_runtime._store(repo).exists


@pytest.mark.parametrize("missing", ["receipts", "checkpoint"])
def test_incomplete_ledger_pair_preserves_unknown_history_and_blocks_all_actions(tmp_path, missing):
    repo = _repo(tmp_path)
    task = _task(repo)
    ledger = aura_runtime._load(repo)
    payload = {"task_id": task["task_id"], "status": "UNKNOWN", "effect": "UNKNOWN"}
    previous = ledger.receipts[-1].receipt_hash
    receipt = Receipt.create(
        len(ledger.receipts) + 1, "AURA_EFFECT_UNKNOWN", None, None, payload, previous
    )
    ledger.append(receipt)
    aura_runtime._store(repo).append(receipt, ledger)

    store = aura_runtime._store(repo)
    missing_path = store.receipts_path if missing == "receipts" else store.checkpoint_path
    surviving_path = store.checkpoint_path if missing == "receipts" else store.receipts_path
    expected_surviving_bytes = surviving_path.read_bytes()
    missing_path.unlink()

    actions = (
        lambda: aura_runtime.status(repo),
        lambda: aura_runtime.inspect(repo, task["task_id"]),
        lambda: aura_runtime.init_repository(repo),
        lambda: aura_runtime.init_task(repo, objective="new task", allowed_paths=["src/value.py"]),
        lambda: aura_runtime.request_build(
            repo,
            objective="new build",
            allowed_paths=["src/value.py"],
            budget_attempts=1,
            authorization_id="test-id",
        ),
        lambda: aura_runtime.build(repo, task["task_id"]),
        lambda: aura_runtime.pause(repo, task["task_id"]),
        lambda: aura_runtime.resume(repo, task["task_id"]),
    )
    for action in actions:
        with pytest.raises(aura_runtime.RuntimeErrorDetail) as error:
            action()
        assert error.value.code == "LEDGER_PAIR_INCOMPLETE"
        assert surviving_path.read_bytes() == expected_surviving_bytes
        assert not missing_path.exists()
