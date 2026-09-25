"""Run a separate-process interrupted-intent probe for the offline ledger.

Invoke with the repository's tested Python interpreter from the repository root.
This is feasibility evidence, not a sandbox or production executor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from forge.aura_executor import Check, Proposal, execute_proposal
from forge.ledger_store import LedgerStore


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def attempt(root: Path) -> None:
    source = root / "source"
    proposal = Proposal("interrupted", (root / "base.txt").read_text(), {"test.txt": "x"})
    execute_proposal(
        source,
        proposal,
        allowed_paths=("test.txt",),
        checks=(Check("pytest"),),
        receipt_root=root / "receipts",
        worktree_root=root / "worktrees",
    )


def child(root: Path) -> None:
    from forge import aura_executor

    original = aura_executor._append

    def interrupt(store, ledger, event, payload):
        original(store, ledger, event, payload)
        if event == "AURA_EXEC_INTENT":
            os._exit(91)

    aura_executor._append = interrupt
    attempt(root)


def replay(root: Path) -> None:
    try:
        attempt(root)
    except Exception as exc:
        print(f"fresh_process_error={getattr(exc, 'code', type(exc).__name__)}")
    else:
        print("fresh_process_error=UNEXPECTED_SUCCESS")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] in {"child", "replay"}:
        {"child": child, "replay": replay}[sys.argv[1]](Path(sys.argv[2]))
        return

    root = Path(tempfile.mkdtemp(prefix="aura-restart-probe-"))
    source = root / "source"
    source.mkdir()
    git(source, "init", "-q")
    git(source, "config", "user.name", "Probe")
    git(source, "config", "user.email", "probe@example.invalid")
    git(source, "config", "core.autocrlf", "false")
    (source / "README.md").write_text("base\n")
    git(source, "add", "README.md")
    git(source, "commit", "-qm", "base")
    base = git(source, "rev-parse", "HEAD")
    (root / "base.txt").write_text(base)
    assert git(source, "status", "--porcelain", "--untracked-files=all") == ""
    crash = subprocess.run(
        (sys.executable, __file__, "child", str(root)), capture_output=True, text=True
    )
    fresh = subprocess.run(
        (sys.executable, __file__, "replay", str(root)), capture_output=True, text=True
    )
    if crash.returncode != 91:
        print(f"interrupted_process_error={crash.stderr.strip()}")
    if fresh.returncode != 0:
        print(f"fresh_process_error_output={fresh.stderr.strip()}")
    receipts = LedgerStore(root / "receipts", "aura-executor-effects").load().receipts
    data = {
        "probe_root": str(root),
        "base": base,
        "interrupted_process_exit": crash.returncode,
        "fresh_process_exit": fresh.returncode,
        "fresh_process_output": fresh.stdout.strip(),
        "receipt_events": [receipt.event for receipt in receipts],
        "worktree_created": (root / "worktrees" / "interrupted").exists(),
        "source_clean": git(source, "status", "--porcelain") == "",
    }
    print(json.dumps(data, indent=2))
    assert crash.returncode == 91, crash.stderr
    assert fresh.returncode == 0, fresh.stderr
    assert fresh.stdout.strip() == "fresh_process_error=UNKNOWN_EFFECT"
    assert data["receipt_events"] == ["AURA_EXEC_INTENT"]
    assert not data["worktree_created"] and data["source_clean"]
    print("probe_exit=0")


if __name__ == "__main__":
    main()
