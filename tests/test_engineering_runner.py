from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from forge.engineering_runner import Check, EngineeringRunner, Packet


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(tmp_path, "init", str(root))
    _git(root, "config", "user.email", "runner@test.invalid")
    _git(root, "config", "user.name", "Runner Test")
    (root / "one.txt").write_text("base\n", encoding="utf-8")
    (root / "two.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    return root, _git(root, "rev-parse", "HEAD")


def _packet(name: str, base: str, filename: str) -> Packet:
    return Packet(name, base, (filename,), (Check("python", (sys.executable, "-c", "pass")),))


def test_one_lane_creates_review_gated_candidate_and_persists_worktree(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    verifier_calls: list[tuple[str, str]] = []
    runner = EngineeringRunner(
        repo,
        tmp_path / "state",
        review_policy_id="pinned-v1",
        verify_review=lambda digest, proof: (
            verifier_calls.append((digest, proof)) is None and proof == "trusted"
        ),
    )

    def builder(task):
        (task.worktree / "one.txt").write_text("implemented\n", encoding="utf-8")

    result = runner.run(
        (_packet("packet-1", base, "one.txt"),), {"deepseek": builder, "luna": builder}
    )["packet-1"]
    assert result["status"] == "REVIEW_PENDING", result
    assert (
        Path(runner._read()["runs"]["packet-1"]["worktree"]) / "one.txt"
    ).read_text() == "implemented\n"
    assert runner.review("packet-1", "trusted")["status"] == "REVIEWED"
    assert verifier_calls == [(result["review_digest"], "trusted")]


def test_two_disjoint_lanes_run_concurrently_and_missing_check_stays_unknown(
    tmp_path: Path,
) -> None:
    repo, base = _repo(tmp_path)
    runner = EngineeringRunner(
        repo, tmp_path / "state", review_policy_id="pinned-v1", verify_review=lambda *_: True
    )

    arrived = threading.Barrier(2)

    def builder(task):
        arrived.wait(timeout=5)
        target = task.worktree / ("one.txt" if task.packet_id == "first" else "two.txt")
        target.write_text(task.lane, encoding="utf-8")

    results = runner.run(
        (_packet("first", base, "one.txt"), _packet("second", base, "two.txt")),
        {"deepseek": builder, "luna": builder},
    )
    assert {value["status"] for value in results.values()} == {"REVIEW_PENDING"}, results
    assert runner._read()["runs"]["first"]["lane"] == "deepseek"
    assert runner._read()["runs"]["second"]["lane"] == "luna"
    with pytest.raises(ValueError, match="overlapping"):
        runner.run(
            (_packet("third", base, "one.txt"), _packet("fourth", base, "one.txt")),
            {"deepseek": builder, "luna": builder},
        )


def test_unstartable_fixed_check_produces_unknown(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    runner = EngineeringRunner(
        repo, tmp_path / "state", review_policy_id="pinned-v1", verify_review=lambda *_: True
    )
    packet = Packet(
        "missing-check",
        base,
        ("one.txt",),
        (Check("unavailable", (str(tmp_path / "absent-command"),)),),
    )

    def builder(task):
        (task.worktree / "one.txt").write_text("changed\n", encoding="utf-8")

    result = runner.run((packet,), {"deepseek": builder, "luna": builder})["missing-check"]
    assert result["status"] == "UNKNOWN"


def test_review_rejects_caller_supplied_approval_and_restart_blocks_replay(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    state_dir = tmp_path / "state"
    runner = EngineeringRunner(
        repo, state_dir, review_policy_id="pinned-v1", verify_review=lambda *_: False
    )

    def builder(task):
        (task.worktree / "one.txt").write_text("change\n", encoding="utf-8")

    runner.run((_packet("packet", base, "one.txt"),), {"deepseek": builder, "luna": builder})
    restarted = EngineeringRunner(
        repo, state_dir, review_policy_id="pinned-v1", verify_review=lambda *_: False
    )
    with pytest.raises(ValueError, match="trusted"):
        restarted.review("packet", "approved")
    with pytest.raises(RuntimeError, match="durable state"):
        restarted.run((_packet("packet", base, "one.txt"),), {"deepseek": builder, "luna": builder})


def test_corrupt_restart_state_is_unknown(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    (state / "engineering-runner.json").write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="UNKNOWN"):
        EngineeringRunner(repo, state, review_policy_id="pinned-v1", verify_review=lambda *_: True)


def test_candidate_mutation_after_checks_invalidates_pending_review(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    runner = EngineeringRunner(
        repo, tmp_path / "state", review_policy_id="pinned-v1", verify_review=lambda *_: True
    )

    def builder(task):
        (task.worktree / "one.txt").write_text("checked\n", encoding="utf-8")

    runner.run((_packet("mutation", base, "one.txt"),), {"deepseek": builder, "luna": builder})
    worktree = Path(runner._read()["runs"]["mutation"]["worktree"])
    (worktree / "one.txt").write_text("mutated after checks\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mutated"):
        runner.review("mutation", "otherwise-valid-proof")
