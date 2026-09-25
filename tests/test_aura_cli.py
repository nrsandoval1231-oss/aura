"""Machine-readable six-command CLI tests."""

from __future__ import annotations

import json

import pytest
from test_aura_runtime import _repo

from forge.aura_cli import main


@pytest.fixture(autouse=True)
def isolated_state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_HOME", str(tmp_path / "aura-state"))


def _invoke(capsys, *args):
    code = main(list(args))
    output = json.loads(capsys.readouterr().out)
    return code, output


def test_six_commands_emit_json_with_durable_state(tmp_path, capsys):
    repo = _repo(tmp_path)
    code, initialized = _invoke(capsys, "init", str(repo))
    assert code == 0
    assert initialized["status"] == "READY"

    blocked = _invoke(
        capsys,
        "build",
        "CLI smoke",
        "--repo",
        str(repo),
        "--allow",
        "src/value.py",
        "--budget-attempts",
        "1",
        "--authorization-id",
        "owner-request-unknown",
    )[1]
    assert blocked["status"] == "BLOCKED"
    assert blocked["provider_call"] is False
    task_id = blocked["run_id"]

    assert _invoke(capsys, "status", "--repo", str(repo))[1]["tasks"][0]["task_id"] == task_id
    assert _invoke(capsys, "inspect", task_id, "--repo", str(repo))[1]["status"] == "BLOCKED"

    # Init can also create a bounded task without dispatching any work.
    pending = _invoke(
        capsys,
        "init",
        "--repo",
        str(repo),
        "--objective",
        "Pause flow",
        "--allow",
        "src/value.py",
    )[1]["task"]
    pending_id = pending["task_id"]
    assert _invoke(capsys, "pause", pending_id, "--repo", str(repo))[1]["status"] == "PAUSED"
    assert _invoke(capsys, "resume", pending_id, "--repo", str(repo))[1]["status"] == "READY"


def test_cli_reports_blocked_as_json(tmp_path, capsys):
    code, result = _invoke(capsys, "--repo", str(tmp_path), "inspect", "aura-absent")
    assert code == 2
    assert result["status"] == "BLOCKED"
    assert result["code"] == "NOT_FOUND"
