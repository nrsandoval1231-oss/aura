"""Append-only local control plane for Aura's six-command M0 CLI.

No builder or provider is configured here. Build requests are durably recorded
as BLOCKED until an isolated, trusted adapter is available.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from forge.ledger_store import LedgerStore
from forge.trust_kernel import ForgeError, Ledger, Receipt

STREAM_ID = "AURA-RUNTIME"
DEFAULT_STATE_HOME = Path.home() / ".aura"
EVENT_TASK_CREATED = "AURA_TASK_CREATED"


class RuntimeErrorDetail(Exception):
    """Expected fail-closed runtime error with a stable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeErrorDetail("GIT_ERROR", result.stderr.strip() or "Git command failed")
    return result.stdout.strip()


def _store(repo: Path) -> LedgerStore:
    state_home = Path(os.environ.get("AURA_STATE_HOME", DEFAULT_STATE_HOME))
    repo_key = hashlib.sha256(str(repo.resolve()).encode("utf-8")).hexdigest()
    return LedgerStore(state_home / "repos" / repo_key / "ledger", STREAM_ID)


def _assert_clean_repo(repo: Path) -> None:
    if _git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise RuntimeErrorDetail("DIRTY_BASE", "Aura init requires a clean Git base")


def _load(repo: Path) -> Ledger:
    store = _store(repo)
    receipts_exist = store.receipts_path.exists()
    checkpoint_exists = store.checkpoint_path.exists()
    if receipts_exist != checkpoint_exists:
        raise RuntimeErrorDetail(
            "LEDGER_PAIR_INCOMPLETE",
            "Aura ledger JSONL and checkpoint must both exist; refusing to infer or rewrite missing history",
        )
    if not receipts_exist:
        return Ledger(stream_id=STREAM_ID)
    try:
        return store.load()
    except ForgeError as exc:
        raise RuntimeErrorDetail(exc.code, str(exc)) from exc


def _append(repo: Path, ledger: Ledger, event: str, payload: dict[str, Any]) -> None:
    previous = ledger.receipts[-1].receipt_hash if ledger.receipts else None
    receipt = Receipt.create(len(ledger.receipts) + 1, event, None, None, payload, previous)
    ledger.append(receipt)
    try:
        _store(repo).append(receipt, ledger)
    except ForgeError as exc:
        raise RuntimeErrorDetail(exc.code, str(exc)) from exc


def _tasks(ledger: Ledger) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for receipt in ledger.receipts:
        payload = dict(receipt.payload)
        task_id = payload.get("task_id")
        if not task_id:
            continue
        if receipt.event == EVENT_TASK_CREATED:
            tasks[task_id] = {**payload, "status": "READY", "history": [receipt.event]}
        elif task_id in tasks:
            state = payload.get("status")
            if state:
                tasks[task_id]["status"] = state
            tasks[task_id]["history"].append(receipt.event)
            tasks[task_id]["latest"] = payload
    return tasks


def _require_task(tasks: dict[str, dict[str, Any]], task_id: str) -> dict[str, Any]:
    task = tasks.get(task_id)
    if task is None:
        raise RuntimeErrorDetail("NOT_FOUND", f"No task {task_id}")
    return task


def init_task(repo: Path, *, objective: str, allowed_paths: list[str]) -> dict[str, Any]:
    repo = repo.resolve()
    root = Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo:
        raise RuntimeErrorDetail("REPO_ROOT_MISMATCH", "Repository path must be its Git root")
    _assert_clean_repo(repo)
    head = _git(repo, "rev-parse", "HEAD")
    if not objective.strip() or not allowed_paths:
        raise RuntimeErrorDetail("INVALID_REQUEST", "Objective and allowed paths are required")
    normalized = [path.replace("\\", "/") for path in allowed_paths]
    if len(set(normalized)) != len(normalized) or any(
        not path
        or path.startswith("/")
        or ".." in Path(path).parts
        or path.startswith((".git", ".agent/aura"))
        for path in normalized
    ):
        raise RuntimeErrorDetail(
            "PATH_DENIED", "Allowed paths must be unique safe repository paths"
        )
    ledger = _load(repo)
    task_id = "aura-" + uuid.uuid4().hex
    payload = {
        "task_id": task_id,
        "objective": objective.strip(),
        "allowed_paths": normalized,
        "repository_root": str(root),
        "base_sha": head,
        "builder_adapter": "UNCONFIGURED",
        "independent_review": "UNCONFIGURED",
        "budget": "UNKNOWN",
        "authority": "UNKNOWN",
    }
    _append(repo, ledger, EVENT_TASK_CREATED, payload)
    return {**payload, "status": "READY", "result": "BLOCKED"}


def init_repository(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    root = Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo:
        raise RuntimeErrorDetail("REPO_ROOT_MISMATCH", "Repository path must be its Git root")
    _assert_clean_repo(repo)
    ledger = _load(repo)
    if not ledger.receipts:
        _append(
            repo,
            ledger,
            "AURA_RUNTIME_INITIALIZED",
            {"repository_root": str(root), "base_sha": _git(repo, "rev-parse", "HEAD")},
        )
    return {"status": "READY", "repository_root": str(root), "ledger_stream": STREAM_ID}


def request_build(
    repo: Path,
    *,
    objective: str,
    allowed_paths: list[str],
    budget_attempts: int,
    authorization_id: str,
) -> dict[str, Any]:
    if budget_attempts < 1 or not authorization_id.strip():
        raise RuntimeErrorDetail(
            "AUTHORITY_REQUIRED", "Positive attempt budget and authorization ID are required"
        )
    task = init_task(repo, objective=objective, allowed_paths=allowed_paths)
    ledger = _load(repo.resolve())
    latest = _tasks(ledger)[task["task_id"]]
    latest_payload = {
        "task_id": task["task_id"],
        "budget_attempts": budget_attempts,
        "authorization_id": authorization_id,
        "budget_status": "RECORDED_UNVERIFIED",
        "authority_status": "UNVERIFIED",
    }
    _append(repo.resolve(), ledger, "AURA_BUILD_GUARDRAILS_RECORDED", latest_payload)
    del latest
    return build(repo, task["task_id"])


def build(repo: Path, task_id: str) -> dict[str, Any]:
    repo = repo.resolve()
    ledger = _load(repo)
    tasks = _tasks(ledger)
    task = _require_task(tasks, task_id)
    if task["status"] == "UNKNOWN":
        raise RuntimeErrorDetail(
            "UNKNOWN_EFFECT", "Unknown effect must be reconciled before any retry"
        )
    if task["status"] != "READY":
        raise RuntimeErrorDetail("INVALID_STATE", f"Build is unavailable from {task['status']}")
    payload = {
        "task_id": task_id,
        "run_id": task_id,
        "status": "BLOCKED",
        "reason": "Builder adapter, isolated worktree executor, and owner authority verification are unavailable",
        "provider_call": False,
        "candidate": "UNKNOWN",
        "spend": "UNKNOWN",
    }
    _append(repo, ledger, "AURA_BUILD_BLOCKED", payload)
    return payload


def status(repo: Path) -> dict[str, Any]:
    ledger = _load(repo.resolve())
    tasks = _tasks(ledger)
    return {
        "tasks": [tasks[key] for key in sorted(tasks)],
        "ledger": {
            "stream_id": STREAM_ID,
            "sequence": ledger.checkpoint.sequence,
            "head_hash": ledger.checkpoint.head_hash,
            "verified": True,
        },
    }


def inspect(repo: Path, task_id: str) -> dict[str, Any]:
    ledger = _load(repo.resolve())
    return _require_task(_tasks(ledger), task_id)


def pause(repo: Path, task_id: str) -> dict[str, Any]:
    repo = repo.resolve()
    ledger = _load(repo)
    task = _require_task(_tasks(ledger), task_id)
    if task["status"] == "UNKNOWN":
        raise RuntimeErrorDetail("UNKNOWN_EFFECT", "Unknown effects cannot be paused")
    if task["status"] != "READY":
        raise RuntimeErrorDetail("INVALID_STATE", f"Pause is unavailable from {task['status']}")
    payload = {"task_id": task_id, "status": "PAUSED"}
    _append(repo, ledger, "AURA_TASK_PAUSED", payload)
    return payload


def resume(repo: Path, task_id: str) -> dict[str, Any]:
    repo = repo.resolve()
    ledger = _load(repo)
    task = _require_task(_tasks(ledger), task_id)
    if task["status"] == "UNKNOWN":
        raise RuntimeErrorDetail(
            "UNKNOWN_EFFECT", "Unknown effects must be reconciled before resume"
        )
    if task["status"] != "PAUSED":
        raise RuntimeErrorDetail("INVALID_STATE", f"Resume is unavailable from {task['status']}")
    payload = {"task_id": task_id, "status": "READY"}
    _append(repo, ledger, "AURA_TASK_RESUMED", payload)
    return payload
