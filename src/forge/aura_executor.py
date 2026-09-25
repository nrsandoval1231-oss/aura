"""Offline, single-proposal Git candidate executor.

This module is deliberately not connected to the Aura CLI or a provider. Callers
must supply a typed proposal adapter and an external durable receipt directory.
Repository checks execute with the host user's filesystem authority; this offline
mechanism is not an OS sandbox and must not receive production provider proposals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from forge.ledger_store import LedgerStore
from forge.policy import requires_owner_authority
from forge.trust_kernel import CandidateIdentity, ForgeError, Ledger, Receipt

_STREAM = "aura-executor-effects"
_HEX_RE = re.compile(r"^[0-9a-f]+$")
_OBJECT_ID_LENGTHS = {"sha1": 40, "sha256": 64}


@dataclass(frozen=True, slots=True)
class Proposal:
    """Untrusted file content from an explicitly supplied offline adapter."""

    invocation_id: str
    base_revision: str
    edits: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Check:
    """A named fixed check; argv is owned by this module, never by proposals."""

    name: str


@dataclass(frozen=True, slots=True)
class ExecutorLimits:
    timeout_seconds: float = 30.0
    total_seconds: float = 90.0


def execute_proposal(
    repo: Path | str,
    proposal: Proposal,
    *,
    allowed_paths: tuple[str, ...],
    checks: tuple[Check, ...],
    receipt_root: Path | str,
    worktree_root: Path | str,
    limits: ExecutorLimits | None = None,
) -> dict[str, object]:
    """Run fixed checks on one isolated candidate and return a review request.

    A durable intent is recorded before the first Git/filesystem mutation. Any
    surviving intent without a result makes the stream UNKNOWN and blocks replay.
    """
    source = Path(repo).resolve()
    if not isinstance(proposal, Proposal):
        raise ForgeError("INVALID_PROPOSAL", "An explicit Proposal adapter is required")
    limits = limits or ExecutorLimits()
    _validate_invocation(proposal.invocation_id)
    _validate_limits(limits)
    _validate_paths(proposal.edits, allowed_paths)
    receipt_dir = Path(receipt_root).resolve()
    worktree_dir = Path(worktree_root).resolve()
    if _is_within(receipt_dir, source) or _is_within(worktree_dir, source):
        raise ForgeError(
            "STATE_INSIDE_REPOSITORY", "Receipt and worktree roots must be outside source"
        )
    argv_by_name = {
        "pytest": (sys.executable, "-I", "-B", "-m", "pytest", "-p", "no:cacheprovider")
    }
    if not checks or len({check.name for check in checks}) != len(checks):
        raise ForgeError("INVALID_CHECKS", "Checks must be nonempty and unique")
    if any(not isinstance(check, Check) or check.name not in argv_by_name for check in checks):
        raise ForgeError("INVALID_CHECKS", "Only registered fixed checks are available")
    repo_root = Path(_git(source, "rev-parse", "--show-toplevel").strip()).resolve()
    if repo_root != source:
        raise ForgeError("INVALID_REPOSITORY", "Repository argument must be the exact Git root")
    object_format = _git(source, "rev-parse", "--show-object-format").strip()
    if object_format not in _OBJECT_ID_LENGTHS:
        raise ForgeError("UNSUPPORTED_OBJECT_FORMAT", "Only Git SHA-1 and SHA-256 are supported")
    base = _git(source, "rev-parse", "HEAD").strip()
    if (
        len(proposal.base_revision) != _OBJECT_ID_LENGTHS[object_format]
        or not _HEX_RE.fullmatch(proposal.base_revision)
        or base != proposal.base_revision
    ):
        raise ForgeError("STALE_BASE", "Proposal base does not match repository HEAD")
    if _git(source, "status", "--porcelain", "--untracked-files=all").strip():
        raise ForgeError("DIRTY_BASE", "Source repository must be clean")
    git_dir = Path(_git(source, "rev-parse", "--absolute-git-dir").strip()).resolve()
    if git_dir == source or not (source / ".git").exists():
        raise ForgeError("INVALID_REPOSITORY", "Expected a Git working tree")

    store = LedgerStore(receipt_dir, _STREAM)
    if store.receipts_path.exists() != store.checkpoint_path.exists():
        raise ForgeError(
            "LEDGER_SIDECAR_MISSING", "Effect ledger receipt and checkpoint must both exist"
        )
    ledger = store.load() if store.exists else Ledger(stream_id=_STREAM)
    pending: set[str] = set()
    seen: set[str] = set()
    for receipt in ledger.receipts:
        call_id = str(receipt.payload.get("invocation_id", ""))
        if receipt.event == "AURA_EXEC_INTENT":
            pending.add(call_id)
            seen.add(call_id)
        elif receipt.event == "AURA_EXEC_RESULT":
            if receipt.payload.get("status") == "REVIEW_REQUESTED":
                pending.discard(call_id)
    if pending:
        raise ForgeError(
            "UNKNOWN_EFFECT",
            "UNKNOWN effect: an intent has no durable result; execution is blocked",
        )
    if proposal.invocation_id in seen:
        raise ForgeError("DUPLICATE_INVOCATION", "Invocation id already has an effect receipt")

    edit_digest = hashlib.sha256(
        json.dumps(dict(sorted(proposal.edits.items())), sort_keys=True).encode()
    ).hexdigest()
    _append(
        store,
        ledger,
        "AURA_EXEC_INTENT",
        {
            "invocation_id": proposal.invocation_id,
            "base_revision": base,
            "edit_digest": edit_digest,
        },
    )
    target = worktree_dir / proposal.invocation_id
    started = time.monotonic()
    result: dict[str, object]
    check_results: list[dict[str, object]] = []
    revision: str | None = None
    tree: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ForgeError("WORKTREE_EXISTS", "Refusing to reuse an existing candidate path")
        _git(
            source,
            "-c",
            f"core.hooksPath={os.devnull}",
            "worktree",
            "add",
            "--detach",
            str(target),
            base,
        )
        for raw_path, content in proposal.edits.items():
            destination = target.joinpath(*PurePosixPath(raw_path).parts)
            if destination.is_symlink() or any(
                parent.is_symlink() for parent in destination.parents if parent != target.parent
            ):
                raise ForgeError("SYMLINK_PATH", f"Symlink path refused: {raw_path}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="")
        changed = _changed_paths(target)
        if changed != tuple(sorted(proposal.edits)):
            raise ForgeError(
                "SCOPE_VIOLATION", "Candidate changed files differ from proposal edits"
            )
        _validate_paths({path: "" for path in changed}, allowed_paths)
        # Commit the exact proposed bytes first; checks exercise this immutable tree.
        _git(target, "add", "--", *changed)
        _git(
            target,
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "user.name=Aura Offline Executor",
            "-c",
            "user.email=aura-offline@invalid",
            "commit",
            "-m",
            "Aura offline candidate",
        )
        revision = _git(target, "rev-parse", "HEAD").strip()
        tree = _git(target, "rev-parse", "HEAD^{tree}").strip()
        _verify_exact_worktree(target, revision, tree, object_format)
        with tempfile.TemporaryDirectory(prefix="aura-pytest-", dir=target.parent) as config_dir:
            pytest_config = Path(config_dir) / "pytest.ini"
            pytest_config.write_text("[pytest]\naddopts = -p no:cacheprovider\n", encoding="utf-8")
            argv = (*argv_by_name["pytest"], "-c", str(pytest_config))
            for check in checks:
                remaining = limits.total_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise ForgeError("BUDGET_EXCEEDED", "Total check budget exhausted")
                timeout = min(limits.timeout_seconds, remaining)
                try:
                    proc = subprocess.run(
                        argv,
                        cwd=target,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        shell=False,
                        env=_check_environment(),
                    )
                    check_results.append(
                        {
                            "name": check.name,
                            "returncode": proc.returncode,
                            "stdout_digest": _output_digest(proc.stdout),
                            "stderr_digest": _output_digest(proc.stderr),
                            "status": "PASS" if proc.returncode == 0 else "FAIL",
                        }
                    )
                except subprocess.TimeoutExpired as exc:
                    check_results.append(
                        {
                            "name": check.name,
                            "returncode": None,
                            "stdout_digest": _output_digest(exc.stdout),
                            "stderr_digest": _output_digest(exc.stderr),
                            "status": "TIMEOUT",
                        }
                    )
                    raise ForgeError(
                        "CHECK_TIMEOUT", f"Fixed check timed out: {check.name}"
                    ) from exc
                if proc.returncode:
                    raise ForgeError("CHECK_FAILED", f"Fixed check failed: {check.name}")
                # The committed candidate and worktree must still be byte-for-byte
                # the tree that pytest was launched against.
                _verify_exact_worktree(target, revision, tree, object_format)
        repository_digest = hashlib.sha256(str(source).encode()).hexdigest()
        candidate = CandidateIdentity(repository_digest, revision, tree, "AURA-M1-EXEC-002")
        result = {
            "status": "REVIEW_REQUESTED",
            "approval": "ABSENT",
            "merge_eligible": False,
            "candidate": {"revision": revision, "tree": tree, "digest": candidate.digest},
            "base_revision": base,
            "changed_files": list(changed),
            "checks": check_results,
            "worktree": str(target),
        }
    except Exception as exc:
        result = {
            "status": "FAILED",
            "effect": "UNKNOWN",
            "error": getattr(exc, "code", type(exc).__name__),
            "message": str(exc),
            "candidate_worktree": str(target) if target.exists() else None,
        }
        _append(
            store,
            ledger,
            "AURA_EXEC_RESULT",
            {
                "invocation_id": proposal.invocation_id,
                "status": "FAILED",
                "effect": "UNKNOWN",
                "checks": check_results,
                "revision": revision,
                "tree": tree,
                "edit_digest": edit_digest,
            },
        )
        raise
    _append(
        store,
        ledger,
        "AURA_EXEC_RESULT",
        {
            "invocation_id": proposal.invocation_id,
            "status": "REVIEW_REQUESTED",
            "revision": revision,
            "tree": tree,
            "edit_digest": edit_digest,
            "checks": check_results,
        },
    )
    return result


def _append(store: LedgerStore, ledger: Ledger, event: str, payload: dict[str, object]) -> None:
    last = ledger.receipts[-1] if ledger.receipts else None
    receipt = Receipt.create(
        len(ledger.receipts) + 1, event, None, None, payload, last.receipt_hash if last else None
    )
    ledger.append(receipt)
    store.append(receipt, ledger)


def _git(repo: Path, *args: str) -> str:
    return _git_bytes(repo, *args).decode("utf-8", errors="strict")


def _git_bytes(repo: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(
            ("git", *args),
            cwd=repo,
            capture_output=True,
            shell=False,
            check=False,
            timeout=10,
            env=_git_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise ForgeError("GIT_TIMEOUT", "Git operation exceeded the 10 second limit") from exc
    if proc.returncode:
        message = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ForgeError("GIT_FAILED", f"git {' '.join(args)} failed: {message}")
    return proc.stdout


def _validate_paths(edits: Mapping[str, str], allowed_paths: tuple[str, ...]) -> None:
    if not allowed_paths or len(set(allowed_paths)) != len(allowed_paths):
        raise ForgeError("INVALID_ALLOWLIST", "Exact unique allowed paths are required")
    for path in (*allowed_paths, *edits):
        pure = PurePosixPath(path)
        if (
            pure.is_absolute()
            or not path
            or ":" in path
            or "\\" in path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ForgeError("INVALID_PATH", f"Invalid repository-relative path: {path}")
        if str(pure) != path or requires_owner_authority(path):
            raise ForgeError("PROTECTED_PATH", f"Protected or noncanonical path refused: {path}")
    if not edits or any(path not in allowed_paths for path in edits):
        raise ForgeError("SCOPE_VIOLATION", "Proposal edits exceed the exact allowlist")
    folded = [path.casefold() for path in allowed_paths]
    if len(folded) != len(set(folded)):
        raise ForgeError("CASE_COLLISION", "Duplicate or case-colliding paths refused")
    if any(not isinstance(content, str) for content in edits.values()):
        raise ForgeError("INVALID_PROPOSAL", "Proposal file contents must be text")


def _validate_invocation(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value or "") or value in {".", ".."}:
        raise ForgeError("INVALID_INVOCATION", "Invocation id must be a safe simple identifier")


def _validate_limits(limits: ExecutorLimits) -> None:
    if not (0 < limits.timeout_seconds <= 300 and 0 < limits.total_seconds <= 900):
        raise ForgeError(
            "INVALID_BUDGET", "Finite timeout and total execution budgets are required"
        )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _changed_paths(repo: Path) -> tuple[str, ...]:
    try:
        raw = subprocess.run(
            (
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--ignored=matching",
            ),
            cwd=repo,
            capture_output=True,
            check=False,
            timeout=10,
            env=_git_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        raise ForgeError("GIT_TIMEOUT", "Git status exceeded the 10 second limit") from exc
    if raw.returncode:
        raise ForgeError("GIT_FAILED", "Could not inspect all candidate changes")
    entries = raw.stdout.split(b"\0")
    paths: list[str] = []
    for entry in entries:
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b" ":
            raise ForgeError("GIT_STATUS_INVALID", "Unrecognized Git status output")
        paths.append(entry[3:].decode("utf-8", errors="strict"))
    return tuple(sorted(paths))


def _check_environment() -> dict[str, str]:
    """Pass only basic process essentials; never inherit credentials or proxies."""
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
    return env


def _git_environment() -> dict[str, str]:
    env = _check_environment()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def _verify_exact_worktree(repo: Path, revision: str, tree: str, object_format: str) -> None:
    actual_format = _git(repo, "rev-parse", "--show-object-format").strip()
    actual_revision = _git(repo, "rev-parse", "HEAD").strip()
    actual_tree = _git(repo, "rev-parse", "HEAD^{tree}").strip()
    if (
        actual_format != object_format
        or actual_revision != revision
        or actual_tree != tree
        or _changed_paths(repo)
    ):
        raise ForgeError("CHECK_CANDIDATE_CHANGED", "Candidate bytes or tree changed during checks")

    entries = _git_bytes(repo, "ls-tree", "-r", "-z", "--full-tree", revision).split(b"\0")
    for entry in entries:
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ForgeError("TREE_ENTRY_INVALID", "Candidate tree entry is not supported") from exc
        path = repo.joinpath(*PurePosixPath(relative).parts)
        if mode == "120000" or path.is_symlink():
            raise ForgeError("SYMLINK_PATH", f"Symlink in candidate tree refused: {relative}")
        if object_type != "blob" or mode not in {"100644", "100755"} or not path.is_file():
            raise ForgeError("TREE_ENTRY_INVALID", f"Unsupported candidate tree entry: {relative}")
        content = path.read_bytes()
        git_blob_id = hashlib.new(
            object_format, b"blob " + str(len(content)).encode("ascii") + b"\0" + content
        ).hexdigest()
        if git_blob_id != object_id:
            raise ForgeError(
                "CHECK_CANDIDATE_CHANGED", f"Working bytes differ from committed blob: {relative}"
            )


def _output_digest(output: str | bytes | None) -> str:
    if output is None:
        raw = b""
    elif isinstance(output, bytes):
        raw = output
    else:
        raw = output.encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()
