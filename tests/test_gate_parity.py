"""The local runner is the validation authority, so it gets its own tests.

This file used to compare `scripts/validate.sh` against a GitHub Actions
workflow. The workflow is gone (DEC-009): validation is local. That removes the
second copy that used to catch a dropped gate by disagreeing with the first, so
the required gate set is asserted here directly instead. Without this, a gate
could be deleted from the script and nothing anywhere would notice.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "validate.sh"

#: Every gate the runner must invoke, identified by a distinctive fragment of
#: its command. Removing a gate means deleting a line here too, which is a
#: visible decision rather than an omission.
REQUIRED_GATES = {
    "python floor": "requires-python",
    "import surface": "forge.__all__",
    "lint": "ruff check",
    "format": "ruff format --check",
    "tests": "pytest -q",
    "doc/graph consistency": "graph check",
    "ledger integrity": "ledger verify",
    "candidate binding": "run_slice.py --check",
    "self-improvement": "prove_self_improvement.py --check",
    "governed evolution": "prove_governed_evolution.py --check",
}

#: Paths every static check must cover. A path checked in one gate and not
#: another is a hole.
REQUIRED_PATHS = {"src", "tests", "scripts"}


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_every_required_gate_is_present(script):
    missing = [name for name, fragment in REQUIRED_GATES.items() if fragment not in script]
    assert not missing, f"validate.sh no longer runs: {missing}"


@pytest.mark.parametrize("tool", ["ruff check", "ruff format --check"])
def test_static_checks_cover_every_source_tree(script, tool):
    match = re.search(re.escape(tool) + r"([^\n]*)", script)
    assert match, f"{tool} not found"
    covered = {token.rstrip("/") for token in match.group(1).split() if "/" in token}
    assert REQUIRED_PATHS <= covered, f"{tool} covers {covered}, missing {REQUIRED_PATHS - covered}"


def test_runner_is_executable():
    assert _runner_is_executable(SCRIPT, ROOT)
    if os.name != "nt":
        assert SCRIPT.stat().st_mode & stat.S_IXUSR, (
            "scripts/validate.sh must have the owner execute bit on POSIX"
        )


def test_runner_checkout_is_forced_to_lf(tmp_path):
    """A fresh autocrlf checkout must keep tracked shell scripts as LF."""
    repo = tmp_path
    attributes = repo / ".gitattributes"
    runner = repo / "scripts" / "validate.sh"
    runner.parent.mkdir()
    attributes.write_bytes((ROOT / ".gitattributes").read_bytes())
    runner.write_bytes(b"#!/bin/sh\necho valid\n")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    assert git("init", "-q", "-b", "main").returncode == 0
    assert git("config", "core.autocrlf", "true").returncode == 0
    assert git("add", ".gitattributes", "scripts/validate.sh").returncode == 0
    runner.unlink()
    restored = git("checkout-index", "--force", "--", "scripts/validate.sh")
    assert restored.returncode == 0, restored.stderr
    assert b"\r\n" not in runner.read_bytes()
    eol = git("ls-files", "--eol", "scripts/validate.sh")
    assert eol.returncode == 0, eol.stderr
    assert "i/lf    w/lf" in eol.stdout


def _runner_is_executable(path: Path, repo_root: Path) -> bool:
    """Require Git's executable mode, with a POSIX filesystem check when applicable.

    NTFS does not expose the mode bit that Git records for an executable file.
    The index is therefore the cross-platform authority for the repository's
    tracked runner; POSIX still needs the actual owner execute bit as well.
    ``--error-unmatch`` makes an untracked or missing path fail closed.
    """
    if not path.is_file():
        return False
    relative = path.relative_to(repo_root).as_posix()
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--stage", "--error-unmatch", "--", relative],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    entries = [line for line in result.stdout.splitlines() if line]
    if len(entries) != 1 or entries[0].split(maxsplit=3)[0] != "100755":
        return False
    return os.name == "nt" or bool(path.stat().st_mode & stat.S_IXUSR)


@pytest.fixture
def isolated_runner_repo(tmp_path):
    runner = tmp_path / "scripts" / "validate.sh"
    runner.parent.mkdir()
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    for key, value in (("user.email", "test@example.test"), ("user.name", "Test")):
        subprocess.run(["git", "config", key, value], cwd=tmp_path, check=True)
    return tmp_path, runner


@pytest.mark.parametrize("git_mode, expected", [("+x", True), ("-x", False)])
def test_git_executable_mode_is_authoritative_in_isolated_fixture(
    isolated_runner_repo, git_mode, expected
):
    repo_root, runner = isolated_runner_repo
    if os.name != "nt":
        runner.chmod(runner.stat().st_mode | stat.S_IXUSR)
    subprocess.run(["git", "add", "scripts/validate.sh"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "update-index", f"--chmod={git_mode}", "scripts/validate.sh"],
        cwd=repo_root,
        check=True,
    )
    assert _runner_is_executable(runner, repo_root) is expected


def test_untracked_runner_fails_closed_in_isolated_fixture(isolated_runner_repo):
    repo_root, runner = isolated_runner_repo
    assert _runner_is_executable(runner, repo_root) is False


def test_tracked_but_missing_runner_fails_closed_in_isolated_fixture(isolated_runner_repo):
    repo_root, runner = isolated_runner_repo
    if os.name != "nt":
        runner.chmod(runner.stat().st_mode | stat.S_IXUSR)
    subprocess.run(["git", "add", "scripts/validate.sh"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "update-index", "--chmod=+x", "scripts/validate.sh"],
        cwd=repo_root,
        check=True,
    )
    runner.unlink()
    assert _runner_is_executable(runner, repo_root) is False


def test_every_gate_runs_even_after_one_fails(script):
    """`set -e` would stop at the first failure and hide the rest.

    The script collects failures instead. That is deliberate: when validation is
    the only authority, seeing one failure and nothing else costs a whole cycle.
    """
    assert "set -e" not in script, "errexit would abort the run at the first failing gate"
    assert "failures+=" in script
    assert "exit 1" in script


def test_ledger_gate_covers_every_stream(script):
    """Naming one stream would stop covering the repository the moment a second existed."""
    assert ".agent/ledger/*.jsonl" in script


def test_no_github_actions_workflow_remains():
    """Validation is local (DEC-009).

    A leftover workflow would be worse than none: it would report a status
    nobody is maintaining, and a red badge that everyone has learned to ignore
    is how a real failure gets ignored too.
    """
    workflows = ROOT / ".github" / "workflows"
    assert not workflows.exists() or not list(workflows.glob("*.yml"))


#: The governed record is exempt from the reference scan below. A completed
#: packet's scope declaration and evidence name the paths that packet actually
#: touched; the workflow was one of them, and it was real at the time. Editing
#: them to match the present tree would falsify an audit record to satisfy a
#: lint — the opposite of what evidence is for. The record says what was true;
#: the operational surfaces below say what is.
HISTORICAL_RECORD = (".agent/", "docs/audit/")


def test_nothing_operational_still_references_the_removed_workflow():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" + os.sep in str(path):
            continue
        if path.suffix not in {".md", ".sh", ".py", ".toml", ".json"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.name == "test_gate_parity.py":
            continue
        if relative.startswith(HISTORICAL_RECORD):
            continue
        if ".github/workflows" in path.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(relative)
    assert not offenders, f"still reference the removed workflow: {offenders}"
