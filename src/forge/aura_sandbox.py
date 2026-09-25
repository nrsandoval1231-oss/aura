"""Unwired offline proposal runner confined to a pinned WSL Bubblewrap sandbox.

This module is a reviewable M1 spike. It does not call a provider or dispatch
through Aura's CLI/Governor. Durable intent is appended before the first WSL or
target Git effect; an interrupted invocation remains UNKNOWN and cannot retry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from forge.ledger_store import LedgerStore
from forge.trust_kernel import ForgeError, Ledger, Receipt

STREAM_ID = "AURA-M1-ISOLATION-003"
EXPECTED_DISTRO = "Ubuntu"
EXPECTED_BWRAP = "bubblewrap 0.11.1"
EXPECTED_PYTHON = "Python 3.14.4"
EXPECTED_GIT = "git version 2.53.0"
EXPECTED_BINARIES = {
    "/usr/bin/bwrap": "8e19e40e7d5f7a7e8b488c7926feb040eab6ed10c58fa360e266d2f70670e92b",
    "/usr/bin/python3": "fa9796cd3a30878e11a2f40372f773d3fcd913fff35e5bee8dd9a036e22e93ab",
    "/usr/bin/git": "5516c9f362c29376ab9a499a33082f9f611941d8c75930c880e30ad109e39c9a",
    "/usr/bin/prlimit": "00be18793391b9222a041277a088022cc58088690cb0e851383bd8ec73f0fefb",
    "/usr/bin/timeout": "48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0",
}
MAX_FILES = 2
MAX_FILE_BYTES = 16 * 1024
MAX_PROPOSAL_BYTES = 32 * 1024
MAX_CAPTURE_BYTES = 1024 * 1024
MAX_CANDIDATE_BYTES = 5 * 1024 * 1024
SANDBOX_SECONDS = 90
GIT_SECONDS = 10
TEST_SECONDS = 30


class SandboxError(Exception):
    """Stable fail-closed error from the experimental offline runner."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _store(root: Path) -> LedgerStore:
    return LedgerStore(root, STREAM_ID)


def _load(store: LedgerStore) -> Ledger:
    if store.receipts_path.exists() != store.checkpoint_path.exists():
        raise SandboxError(
            "LEDGER_PAIR_INCOMPLETE", "Sandbox receipt/checkpoint pair is incomplete"
        )
    if not store.exists:
        return Ledger(stream_id=STREAM_ID)
    try:
        return store.load()
    except ForgeError as exc:
        raise SandboxError(exc.code, str(exc)) from exc


def _append(store: LedgerStore, ledger: Ledger, event: str, payload: dict[str, Any]) -> None:
    previous = ledger.receipts[-1].receipt_hash if ledger.receipts else None
    receipt = Receipt.create(len(ledger.receipts) + 1, event, None, None, payload, previous)
    ledger.append(receipt)
    try:
        store.append(receipt, ledger)
    except ForgeError as exc:
        raise SandboxError(exc.code, str(exc)) from exc


def _runs(ledger: Ledger) -> dict[str, dict[str, Any]]:
    runs: dict[str, dict[str, Any]] = {}
    for receipt in ledger.receipts:
        payload = dict(receipt.payload)
        run_id = payload.get("run_id")
        if not run_id:
            continue
        if receipt.event == "AURA_SANDBOX_INTENT":
            runs[run_id] = {"status": "UNKNOWN", "intent": payload}
        elif run_id in runs:
            runs[run_id] = {
                **runs[run_id],
                "status": payload.get("status", "UNKNOWN"),
                "result": payload,
            }
    return runs


def _safe_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(ch) < 32 for ch in value)
        or "\\" in value
    ):
        raise SandboxError(
            "PATH_DENIED", "Proposal paths must be safe repository-relative POSIX paths"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SandboxError("PATH_DENIED", f"Unsafe proposal path: {value!r}")
    if path.parts[0] == ".git" or value.startswith(".agent/aura"):
        raise SandboxError("PATH_DENIED", f"Protected proposal path: {value!r}")
    return path.as_posix()


def _validate_input(
    repo: Path,
    *,
    objective: str,
    base_sha: str,
    allowed_paths: Sequence[str],
    files: Mapping[str, str],
    state_root: Path,
    result_root: Path,
) -> dict[str, bytes]:
    if not objective.strip() or len(objective.encode("utf-8")) > 4096:
        raise SandboxError("INVALID_REQUEST", "Objective must be non-empty and at most 4 KiB")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", base_sha):
        raise SandboxError("INVALID_REQUEST", "Base must be an exact lowercase Git SHA")
    if not isinstance(repo, Path):
        repo = Path(repo)
    try:
        repo = repo.resolve(strict=True)
    except OSError as exc:
        raise SandboxError("REPO_NOT_FOUND", "Target repository path is unavailable") from exc
    if not repo.is_dir() or not (repo / ".git").is_dir():
        raise SandboxError("REPO_INVALID", "Target must be a normal Git working tree root")
    for parent in (state_root.resolve(), result_root.resolve()):
        if parent == repo or repo in parent.parents:
            raise SandboxError(
                "STATE_PATH_DENIED",
                "State and result directories must be outside the target repository",
            )
    if len(files) < 1 or len(files) > MAX_FILES:
        raise SandboxError("BUDGET_EXCEEDED", "A proposal must contain one or two files")
    normalized_allow = tuple(_safe_path(path) for path in allowed_paths)
    if len(set(normalized_allow)) != len(normalized_allow) or len(normalized_allow) > MAX_FILES:
        raise SandboxError(
            "PATH_DENIED", "Allowed paths must be unique and contain at most two files"
        )
    normalized_files: dict[str, bytes] = {}
    total = 0
    for raw_path, content in files.items():
        path = _safe_path(raw_path)
        if path in normalized_files or path not in normalized_allow:
            raise SandboxError("PATH_DENIED", "Proposal contains a duplicate or unauthorized path")
        if not isinstance(content, str):
            raise SandboxError("INVALID_REQUEST", "Proposal contents must be UTF-8 text")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise SandboxError("BUDGET_EXCEEDED", f"Proposal file {path} exceeds 16 KiB")
        total += len(encoded)
        if total > MAX_PROPOSAL_BYTES:
            raise SandboxError("BUDGET_EXCEEDED", "Proposal exceeds 32 KiB")
        normalized_files[path] = encoded
        cursor = repo
        for part in PurePosixPath(path).parts[:-1]:
            cursor /= part
            if cursor.is_symlink():
                raise SandboxError("PATH_DENIED", f"Symlink in target path: {path}")
        target = repo / path
        if target.is_symlink():
            raise SandboxError("PATH_DENIED", f"Symlink target is denied: {path}")
    if set(normalized_files) != set(normalized_allow):
        raise SandboxError(
            "PATH_DENIED", "Proposal paths must exactly match the authorized allowlist"
        )
    return normalized_files


def _wsl_path(path: Path) -> str:
    win = PureWindowsPath(str(path))
    if not win.drive or win.drive[1:] != ":" or win.drive.startswith("\\"):
        raise SandboxError(
            "PATH_DENIED", "Only local drive-letter paths supported by Ubuntu WSL are accepted"
        )
    tail = "/".join(part.replace(":", "") for part in win.parts[1:])
    return f"/mnt/{win.drive[0].lower()}/{tail}"


def _runtime_probe() -> list[str]:
    code = (
        "import hashlib,json,platform,pathlib,sys;"
        "p=pathlib.Path('/etc/os-release').read_text();"
        "expected={'/usr/bin/bwrap':'"
        + EXPECTED_BINARIES["/usr/bin/bwrap"]
        + "','/usr/bin/python3':'"
        + EXPECTED_BINARIES["/usr/bin/python3"]
        + "','/usr/bin/git':'"
        + EXPECTED_BINARIES["/usr/bin/git"]
        + "','/usr/bin/prlimit':'"
        + EXPECTED_BINARIES["/usr/bin/prlimit"]
        + "','/usr/bin/timeout':'"
        + EXPECTED_BINARIES["/usr/bin/timeout"]
        + "'};"
        "from subprocess import run;"
        "versions={x:run([x,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0] for x in ['/usr/bin/bwrap','/usr/bin/python3','/usr/bin/git']};"
        "actual={x:hashlib.sha256(pathlib.Path(x).read_bytes()).hexdigest() for x in expected};"
        "ok=('VERSION_ID=\"26.04\"' in p and versions['/usr/bin/bwrap']=='"
        + EXPECTED_BWRAP
        + "' and versions['/usr/bin/python3']=='"
        + EXPECTED_PYTHON
        + "' and versions['/usr/bin/git']=='"
        + EXPECTED_GIT
        + "' and actual==expected);"
        "print(json.dumps({'ok':ok,'versions':versions,'binary_sha256':actual},sort_keys=True));sys.exit(0 if ok else 41)"
    )
    return ["wsl.exe", "-d", EXPECTED_DISTRO, "--exec", "/usr/bin/python3", "-I", "-B", "-c", code]


def _resource_child() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_CAPTURE_BYTES, MAX_CAPTURE_BYTES))


def _driver_source() -> str:
    return _WORKER_TEMPLATE.replace("__SECURITY_PROBE__", repr(_SECURITY_PROBE))


def _verifier_source() -> str:
    return Path(__file__).with_name("aura_sandbox_verifier.py").read_text(encoding="utf-8")


def _invoke_wsl(repo: Path, staged: Path, *, verify: bool) -> dict[str, Any]:
    repo_wsl = _wsl_path(repo)
    stage_wsl = _wsl_path(staged)
    role = "verify" if verify else "run"
    entrypoint = "/input/verifier.py" if verify else "/input/runner.py"
    command = [
        "wsl.exe",
        "-d",
        EXPECTED_DISTRO,
        "--exec",
        "/usr/bin/timeout",
        "-k",
        "1",
        "90",
        "/usr/bin/bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/bin",
        "/bin",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--ro-bind",
        "/etc/os-release",
        "/etc/os-release",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--ro-bind",
        repo_wsl,
        "/source",
        "--ro-bind",
        stage_wsl,
        "/input",
        "--size",
        str(MAX_CANDIDATE_BYTES),
        "--tmpfs",
        "/out",
        "--setenv",
        "HOME",
        "/nonexistent",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--setenv",
        "GIT_CONFIG_NOSYSTEM",
        "1",
        "--setenv",
        "GIT_CONFIG_GLOBAL",
        "/dev/null",
        "--setenv",
        "GIT_TERMINAL_PROMPT",
        "0",
        "--setenv",
        "GIT_ALLOW_PROTOCOL",
        "file",
        "--setenv",
        "GIT_PROTOCOL_FROM_USER",
        "0",
        "--",
        "/usr/bin/prlimit",
        "--cpu=30",
        "--as=536870912",
        "--nproc=32",
        "--fsize=1048576",
        "--core=0",
        "--",
        "/usr/bin/python3",
        "-I",
        "-B",
        entrypoint,
    ]
    if not verify:
        command.append("run")
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=SANDBOX_SECONDS + 5, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxError(
            "UNKNOWN_EFFECT", "WSL invocation ended without a conclusive result"
        ) from exc
    if len(completed.stdout) > MAX_CAPTURE_BYTES or len(completed.stderr) > MAX_CAPTURE_BYTES:
        raise SandboxError("UNKNOWN_EFFECT", "Sandbox output exceeded the 1 MiB capture limit")
    try:
        response = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        detail = completed.stderr.decode("utf-8", "replace")[-4096:]
        raise SandboxError(
            "UNKNOWN_EFFECT",
            f"Sandbox did not return a complete structured result (exit {completed.returncode}): {detail}",
        ) from exc
    if completed.returncode != 0 or not isinstance(response, dict):
        detail = completed.stderr.decode("utf-8", "replace")[-4096:]
        raise SandboxError(
            "UNKNOWN_EFFECT",
            f"WSL sandbox failed without a verified result ({completed.returncode}): {detail} {response!r}",
        )
    response["sandbox_role"] = role
    response["stderr_sha256"] = _hash(completed.stderr)
    return response


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def execute_proposal(
    repository: Path | str,
    *,
    objective: str,
    base_sha: str,
    allowed_paths: Sequence[str],
    files: Mapping[str, str],
    state_root: Path | str,
    result_root: Path | str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Apply one text proposal, test an exact Git commit and independently recheck it.

    A caller retry is idempotent only after a completed result. Any unresolved
    intent raises ``UNKNOWN_EFFECT`` and cannot launch WSL a second time.
    """

    repo = Path(repository).resolve(strict=True)
    state = Path(state_root).resolve()
    results = Path(result_root).resolve()
    normalized = _validate_input(
        repo,
        objective=objective,
        base_sha=base_sha,
        allowed_paths=allowed_paths,
        files=files,
        state_root=state,
        result_root=results,
    )
    runner_source = _driver_source()
    verifier_source = _verifier_source()
    request_hash = _hash(
        json.dumps(
            {
                "repo": str(repo),
                "objective": objective.strip(),
                "base": base_sha,
                "paths": sorted(normalized),
                "files": {k: _hash(v) for k, v in sorted(normalized.items())},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    stable_run_id = run_id or f"aura-sandbox-{request_hash[:32]}"
    if not re.fullmatch(r"aura-sandbox-[a-f0-9]{32}", stable_run_id):
        raise SandboxError(
            "INVALID_RUN_ID", "run_id must use the stable aura-sandbox- plus 32 hex form"
        )
    store = _store(state)
    ledger = _load(store)
    existing = _runs(ledger).get(stable_run_id)
    if existing:
        if existing["intent"].get("request_hash") != request_hash:
            raise SandboxError(
                "RUN_ID_CONFLICT", "Stable run id is already bound to another request"
            )
        if existing["status"] == "REVIEW_REQUESTED":
            evidence_path = Path(existing["result"]["evidence_path"])
            patch_path = Path(existing["result"]["patch_path"])
            if not evidence_path.is_file() or not patch_path.is_file():
                raise SandboxError(
                    "RESULT_MISSING", "Completed result artifact is missing; refusing to rerun"
                )
            return {**existing["result"], "idempotent_replay": True}
        raise SandboxError(
            "UNKNOWN_EFFECT", "UNKNOWN_EFFECT: unresolved or rejected run cannot be retried"
        )

    intent = {
        "run_id": stable_run_id,
        "request_hash": request_hash,
        "objective": objective.strip(),
        "repository": str(repo),
        "base_sha": base_sha,
        "allowed_paths": sorted(normalized),
        "proposal_sha256": {k: _hash(v) for k, v in sorted(normalized.items())},
        "runner_sha256": _hash(runner_source.encode("utf-8")),
        "verifier_sha256": _hash(verifier_source.encode("utf-8")),
        "provider_call": False,
        "provider_spend_usd": 0,
    }
    _append(store, ledger, "AURA_SANDBOX_INTENT", intent)

    try:
        with tempfile.TemporaryDirectory(prefix="aura-sandbox-input-") as temp_name:
            staged = Path(temp_name)
            driver = staged / "runner.py"
            driver.write_text(runner_source, encoding="utf-8", newline="\n")
            proposal = {
                "base_sha": base_sha,
                "files": {k: base64.b64encode(v).decode("ascii") for k, v in normalized.items()},
            }
            (staged / "proposal.json").write_text(
                json.dumps(proposal, sort_keys=True), encoding="utf-8"
            )
            runtime = subprocess.run(_runtime_probe(), capture_output=True, timeout=12, check=False)
            if len(runtime.stdout) > 8192 or len(runtime.stderr) > 8192 or runtime.returncode != 0:
                raise SandboxError("UNKNOWN_EFFECT", "Pinned WSL runtime identity check failed")
            try:
                runtime_evidence = json.loads(runtime.stdout.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise SandboxError(
                    "UNKNOWN_EFFECT", "Pinned WSL runtime check returned ambiguous output"
                ) from exc
            first = _invoke_wsl(repo, staged, verify=False)
            if first.get("status") != "CANDIDATE_READY":
                raise SandboxError("UNKNOWN_EFFECT", "Sandbox did not create a complete candidate")
            bundle = base64.b64decode(first["bundle_b64"], validate=True)
            if len(bundle) > MAX_CANDIDATE_BYTES or len(bundle) > MAX_CAPTURE_BYTES:
                raise SandboxError("UNKNOWN_EFFECT", "Candidate bundle exceeds output bounds")
            verify_stage = staged / "verify-input"
            verify_stage.mkdir()
            (verify_stage / "verifier.py").write_text(
                verifier_source, encoding="utf-8", newline="\n"
            )
            (verify_stage / "proposal.json").write_text(
                json.dumps(proposal, sort_keys=True), encoding="utf-8"
            )
            (verify_stage / "candidate.bundle").write_bytes(bundle)
            verify = _invoke_wsl(repo, verify_stage, verify=True)
            if (
                verify.get("status") != "VERIFIED"
                or verify.get("candidate_sha") != first.get("candidate_sha")
                or verify.get("tree_sha") != first.get("tree_sha")
                or verify.get("changed_paths") != first.get("changed_paths")
                or verify.get("test_output_sha256") != first.get("test_output_sha256")
            ):
                raise SandboxError(
                    "UNKNOWN_EFFECT", "Independent read-only verifier rejected or changed candidate"
                )
            patch = base64.b64decode(first["patch_b64"], validate=True)
            if len(patch) > MAX_PROPOSAL_BYTES + 8192:
                raise SandboxError("UNKNOWN_EFFECT", "Review patch exceeds bounded proposal output")
            output_dir = results / stable_run_id
            patch_path = output_dir / "candidate.patch"
            evidence_path = output_dir / "evidence.json"
            evidence = {
                "run_id": stable_run_id,
                "status": "REVIEW_REQUESTED",
                "objective": objective.strip(),
                "repository": str(repo),
                "base_sha": base_sha,
                "candidate_sha": first["candidate_sha"],
                "tree_sha": first["tree_sha"],
                "changed_paths": first["changed_paths"],
                "proposal_sha256": intent["proposal_sha256"],
                "patch_sha256": _hash(patch),
                "test_output_sha256": first["test_output_sha256"],
                "test_output": first["test_output"],
                "denial_probe": first["denial_probe"],
                "independent_verifier": verify,
                "runtime": runtime_evidence,
                "provider_call": False,
                "provider_spend_usd": 0,
                "production_authority": "ABSENT",
                "approval": "ABSENT",
            }
            evidence_bytes = (json.dumps(evidence, indent=2, sort_keys=True) + "\n").encode("utf-8")
            if len(evidence_bytes) > MAX_CAPTURE_BYTES:
                raise SandboxError("UNKNOWN_EFFECT", "Evidence output exceeds 1 MiB")
            _atomic_write(patch_path, patch)
            _atomic_write(evidence_path, evidence_bytes)
            completed = {
                "run_id": stable_run_id,
                "status": "REVIEW_REQUESTED",
                "base_sha": base_sha,
                "candidate_sha": first["candidate_sha"],
                "tree_sha": first["tree_sha"],
                "changed_paths": first["changed_paths"],
                "patch_path": str(patch_path),
                "evidence_path": str(evidence_path),
                "patch_sha256": _hash(patch),
                "provider_call": False,
                "provider_spend_usd": 0,
            }
            ledger = _load(store)
            _append(store, ledger, "AURA_SANDBOX_REVIEW_REQUESTED", completed)
            return completed
    except BaseException as exc:
        try:
            ledger = _load(store)
            current = _runs(ledger).get(stable_run_id)
            if current and current["status"] == "UNKNOWN":
                _append(
                    store,
                    ledger,
                    "AURA_SANDBOX_UNKNOWN",
                    {
                        "run_id": stable_run_id,
                        "status": "UNKNOWN",
                        "code": getattr(exc, "code", "UNKNOWN_EFFECT"),
                    },
                )
        except Exception:
            pass
        if isinstance(exc, SandboxError):
            raise
        raise SandboxError(
            "UNKNOWN_EFFECT", "Sandbox execution stopped after durable intent"
        ) from exc


_WORKER_TEMPLATE = r"""import base64,hashlib,json,os,pathlib,resource,socket,subprocess,sys
MAX_LOG = 1024*1024
TIMEOUT_GIT = 10
TIMEOUT_TEST = 30
BASE = '/source'
OUT = pathlib.Path('/out')
WORK = OUT / 'worktree'
GITDIR = OUT / 'candidate.git'
ENV = {'HOME':'/nonexistent','PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
       'PYTHONDONTWRITEBYTECODE':'1','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null',
       'GIT_TERMINAL_PROMPT':'0','GIT_ALLOW_PROTOCOL':'file','GIT_PROTOCOL_FROM_USER':'0',
       'GIT_OPTIONAL_LOCKS':'0','GIT_ATTR_NOSYSTEM':'1'}
GC = ['-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-c',
      'core.untrackedCache=false','-c','core.attributesFile=/dev/null','-c',
      'core.autocrlf=false','-c','commit.gpgsign=false','-c','tag.gpgsign=false']

def emit(obj, code=0):
    data=(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode()
    if len(data)>MAX_LOG: raise SystemExit(72)
    sys.stdout.buffer.write(data); sys.stdout.buffer.flush(); raise SystemExit(code)

def limits():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
    resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_LOG,MAX_LOG))

def command(argv, *, cwd=None, timeout=TIMEOUT_GIT, env=None):
    logfile=OUT/'command.log'
    logfile.unlink(missing_ok=True)
    try:
        with logfile.open('wb') as sink:
            p=subprocess.run(argv,cwd=cwd,env=ENV if env is None else env,stdout=sink,
                stderr=subprocess.STDOUT,timeout=timeout,check=False,preexec_fn=limits)
        raw=logfile.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('TIMEOUT:'+str(argv[0])) from exc
    if len(raw)>MAX_LOG: raise RuntimeError('OUTPUT_LIMIT:'+str(argv[0]))
    if p.returncode: raise RuntimeError('COMMAND_FAILED:'+str(argv[0])+':'+raw[-2048:].decode('utf-8','replace'))
    return raw.decode('utf-8','replace').strip()

def git(*args,cwd=None,timeout=TIMEOUT_GIT):
    return command(['/usr/bin/git',*GC,*args],cwd=cwd,timeout=timeout)

_SECURITY_PROBE = __SECURITY_PROBE__

def main():
    try:
        release=pathlib.Path('/etc/os-release').read_text()
        binary_hashes={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in {
            '/usr/bin/bwrap':'8e19e40e7d5f7a7e8b488c7926feb040eab6ed10c58fa360e266d2f70670e92b',
            '/usr/bin/python3':'fa9796cd3a30878e11a2f40372f773d3fcd913fff35e5bee8dd9a036e22e93ab',
            '/usr/bin/git':'5516c9f362c29376ab9a499a33082f9f611941d8c75930c880e30ad109e39c9a',
            '/usr/bin/prlimit':'00be18793391b9222a041277a088022cc58088690cb0e851383bd8ec73f0fefb',
            '/usr/bin/timeout':'48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0'}.keys()}
        if 'VERSION_ID="26.04"' not in release or any(binary_hashes[k]!=v for k,v in {
            '/usr/bin/bwrap':'8e19e40e7d5f7a7e8b488c7926feb040eab6ed10c58fa360e266d2f70670e92b',
            '/usr/bin/python3':'fa9796cd3a30878e11a2f40372f773d3fcd913fff35e5bee8dd9a036e22e93ab',
            '/usr/bin/git':'5516c9f362c29376ab9a499a33082f9f611941d8c75930c880e30ad109e39c9a',
            '/usr/bin/prlimit':'00be18793391b9222a041277a088022cc58088690cb0e851383bd8ec73f0fefb',
            '/usr/bin/timeout':'48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0'}.items()):
            emit({'status':'REJECTED','code':'PINNED_RUNTIME_MISMATCH'},40)
    except Exception as exc:
        emit({'status':'REJECTED','code':'PINNED_RUNTIME_MISMATCH','detail':str(exc)},40)
    mode=sys.argv[1]
    proposal=json.loads(pathlib.Path('/input/proposal.json').read_text())
    base=proposal['base_sha']; files={p:base64.b64decode(v,validate=True) for p,v in proposal['files'].items()}
    # First, run jail denial regressions in a nested Bubblewrap namespace.
    probe_source=pathlib.Path('/tmp/security-probe.py')
    probe_source.write_text(_SECURITY_PROBE)
    probe=subprocess.run(['/usr/bin/bwrap','--unshare-all','--die-with-parent','--clearenv',
       '--ro-bind','/usr','/usr','--ro-bind','/bin','/bin','--ro-bind','/lib','/lib',
       '--ro-bind','/lib64','/lib64','--ro-bind','/etc/os-release','/etc/os-release','--proc','/proc','--dev','/dev','--tmpfs','/tmp',
       '--size','5242880','--tmpfs','/out','--setenv','HOME','/nonexistent','--setenv','PATH','/usr/bin:/bin',
       '--setenv','GIT_CONFIG_NOSYSTEM','1','--setenv','GIT_CONFIG_GLOBAL','/dev/null',
       '--ro-bind',str(probe_source),'/probe.py','--','/usr/bin/prlimit','--cpu=5','--as=134217728','--nproc=32','--fsize=1048576','--',
       '/usr/bin/python3','-I','-B','/probe.py'],capture_output=True,timeout=10,env=ENV,check=False,preexec_fn=limits)
    if len(probe.stdout)>MAX_LOG or len(probe.stderr)>MAX_LOG or probe.returncode:
        emit({'status':'REJECTED','code':'ISOLATION_DENIAL_PROBE_FAILED','detail':probe.stderr.decode('utf-8','replace')[-2048:]},45)
    denial=json.loads(probe.stdout.decode())
    # Check target is a normal, clean working tree at the caller's frozen object.
    if pathlib.Path('/source/.git').is_symlink() or not pathlib.Path('/source/.git').is_dir(): raise RuntimeError('SOURCE_GIT_LAYOUT')
    top=git('-C',BASE,'rev-parse','--show-toplevel')
    head=git('-C',BASE,'rev-parse','HEAD')
    if top!='/source' or head!=base: raise RuntimeError('STALE_BASE')
    dirty=git('-C',BASE,'status','--porcelain','--untracked-files=all')
    if dirty: raise RuntimeError('DIRTY_SOURCE')
    objfmt=git('-C',BASE,'rev-parse','--show-object-format')
    if len(base)!=(40 if objfmt=='sha1' else 64 if objfmt=='sha256' else -1): raise RuntimeError('OBJECT_FORMAT_MISMATCH')
    # Share immutable source objects by alternate; only new candidate objects are written in /out.
    GITDIR.mkdir(); (GITDIR/'objects/info').mkdir(parents=True)
    (GITDIR/'objects/info/alternates').write_text('/source/.git/objects\n')
    command(['/usr/bin/git',*GC,'init','--bare','--object-format='+objfmt,str(GITDIR)])
    git('--git-dir='+str(GITDIR),'fetch','--no-tags','--no-recurse-submodules','/source',base)
    git('--git-dir='+str(GITDIR),'worktree','add','--detach',str(WORK),base)
    for path,content in files.items():
        target=WORK/path
        cur=WORK
        for part in pathlib.PurePosixPath(path).parts[:-1]:
            cur=cur/part
            if cur.is_symlink(): raise RuntimeError('PROPOSAL_PATH_SYMLINK')
        if target.is_symlink(): raise RuntimeError('PROPOSAL_PATH_SYMLINK')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(content)
    paths=sorted(files)
    git('-C',str(WORK),'add','--',*paths)
    staged=git('-C',str(WORK),'diff','--cached','--name-only','--no-renames')
    if staged.splitlines()!=paths: raise RuntimeError('STAGED_PATH_MISMATCH')
    env=dict(ENV,GIT_AUTHOR_NAME='Aura Offline Builder',GIT_AUTHOR_EMAIL='offline@example.invalid',
      GIT_COMMITTER_NAME='Aura Offline Builder',GIT_COMMITTER_EMAIL='offline@example.invalid',
      GIT_AUTHOR_DATE='2000-01-01T00:00:00+00:00',GIT_COMMITTER_DATE='2000-01-01T00:00:00+00:00')
    command(['/usr/bin/git',*GC,'-C',str(WORK),'commit','--no-gpg-sign','-m','Aura bounded offline proposal'],env=env)
    candidate=git('-C',str(WORK),'rev-parse','HEAD'); tree=git('-C',str(WORK),'rev-parse','HEAD^{tree}')
    parents=git('-C',str(WORK),'rev-list','--parents','-n','1',candidate).split()
    if parents!=[candidate,base]: raise RuntimeError('CANDIDATE_PARENT_MISMATCH')
    with (OUT/'check.log').open('wb') as sink:
        unittest_code="import os,sys,unittest;sys.path.insert(0,os.getcwd());s=unittest.defaultTestLoader.discover('tests',pattern='test_*.py');r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"
        check=subprocess.run(['/usr/bin/python3','-I','-B','-c',unittest_code],
           cwd=WORK,env=ENV,stdout=sink,stderr=subprocess.STDOUT,timeout=TIMEOUT_TEST,check=False,preexec_fn=limits)
    test_raw=(OUT/'check.log').read_bytes()
    if len(test_raw)>MAX_LOG: raise RuntimeError('TEST_OUTPUT_LIMIT')
    if check.returncode: raise RuntimeError('TEST_FAILED:'+test_raw[-2048:].decode('utf-8','replace'))
    if git('-C',str(WORK),'rev-parse','HEAD')!=candidate or git('-C',str(WORK),'rev-parse','HEAD^{tree}')!=tree: raise RuntimeError('TEST_REWROTE_CANDIDATE')
    if git('-C',str(WORK),'status','--porcelain','--untracked-files=all'): raise RuntimeError('TEST_MUTATED_CANDIDATE')
    for path,content in files.items():
        if (WORK/path).read_bytes()!=content: raise RuntimeError('TEST_REWROTE_PROPOSAL_BYTES')
    diff=git('-C',str(WORK),'diff','--binary','--no-ext-diff',base,candidate,'--',*paths)
    patch=diff.encode()
    git('--git-dir='+str(GITDIR),'update-ref','refs/heads/aura-candidate',candidate)
    bundle_log=command(['/usr/bin/git',*GC,'--git-dir='+str(GITDIR),'bundle','create',str(OUT/'candidate.bundle'),'refs/heads/aura-candidate','^'+base])
    bundle=(OUT/'candidate.bundle').read_bytes()
    if len(bundle)>MAX_LOG: raise RuntimeError('BUNDLE_OUTPUT_LIMIT')
    emit({'status':'CANDIDATE_READY','candidate_sha':candidate,'tree_sha':tree,'changed_paths':paths,
      'patch_b64':base64.b64encode(patch).decode(),'bundle_b64':base64.b64encode(bundle).decode(),
      'test_output':test_raw.decode('utf-8','replace'),'test_output_sha256':hashlib.sha256(test_raw).hexdigest(),
      'denial_probe':denial,'bundle_created':bool(bundle_log is not None)})

main()
"""

_SECURITY_PROBE = r"""import json,pathlib,socket,subprocess,os
def run(a,cwd=None,timeout=5):
 p=subprocess.run(a,cwd=cwd,env={'HOME':'/nonexistent','PATH':'/usr/bin:/bin','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0'},capture_output=True,text=True,timeout=timeout)
 return p
def git(cwd,*a):
 p=run(['/usr/bin/git',*a],cwd)
 if p.returncode: raise RuntimeError(p.stderr[-1000:])
 return p.stdout.strip(),p.stderr
root=pathlib.Path('/out/probe'); src=root/'source'; cand=root/'candidate'; outside=root/'outside'; src.mkdir(parents=True); cand.mkdir(); outside.mkdir()
if pathlib.Path('/mnt/c/Windows/win.ini').exists(): raise RuntimeError('HOST_FILE_VISIBLE')
s=socket.socket();s.settimeout(1); code=s.connect_ex(('1.1.1.1',53));s.close()
if code==0: raise RuntimeError('NETWORK_AVAILABLE')
git(src,'init','-q');git(src,'config','user.name','probe');git(src,'config','user.email','probe@example.invalid')
(src/'README.md').write_text('base\n');git(src,'add','README.md');git(src,'commit','-qm','base')
(src/'fsmonitor.sh').write_text('#!/bin/sh\necho AURA_FSMONITOR_ATTEMPT >&2\necho x >/outside/fsmonitor-marker 2>/dev/null || true\necho x >/repo/source-marker 2>/dev/null || true\nexit 0\n');(src/'fsmonitor.sh').chmod(0o755)
git(src,'add','fsmonitor.sh');git(src,'commit','-qm','fsmonitor');git(src,'config','core.fsmonitor','/repo/fsmonitor.sh')
# Start a nested sandbox with a read-only source, writable candidate, and no outside mount.
p=run(['/usr/bin/bwrap','--unshare-all','--die-with-parent','--clearenv','--ro-bind','/usr','/usr','--ro-bind','/bin','/bin','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(src),'/repo','--bind',str(cand),'/candidate','--setenv','HOME','/nonexistent','--setenv','PATH','/usr/bin:/bin','--setenv','GIT_CONFIG_NOSYSTEM','1','--setenv','GIT_CONFIG_GLOBAL','/dev/null','--','/usr/bin/python3','-I','-B','-c',r"import subprocess; p=subprocess.run(['/usr/bin/git','-C','/repo','status','--porcelain'],capture_output=True,text=True); print(p.stderr); assert 'AURA_FSMONITOR_ATTEMPT' in p.stderr"])
if p.returncode: raise RuntimeError('FSMONITOR_DENIAL_PROBE_FAILED:'+p.stderr[-1000:])
if (outside/'fsmonitor-marker').exists() or (src/'source-marker').exists(): raise RuntimeError('FSMONITOR_ESCAPED')
# Included filter and commit hook execute only in the same nested jail.
git(cand,'init','-q');git(cand,'config','user.name','probe');git(cand,'config','user.email','probe@example.invalid')
(cand/'README.md').write_text('base\n');git(cand,'add','README.md');git(cand,'commit','-qm','base')
(cand/'filter.sh').write_text('#!/bin/sh\necho AURA_FILTER_ATTEMPT >&2\necho x >/repo/filter-marker 2>/dev/null || true\ncat\n');(cand/'filter.sh').chmod(0o755)
(cand/'hook.sh').write_text('#!/bin/sh\necho AURA_HOOK_ATTEMPT >&2\necho x >/repo/hook-marker 2>/dev/null || true\nexit 0\n');(cand/'hook.sh').chmod(0o755)
(cand/'extra-config').write_text('[filter "evil"]\n clean = /candidate/filter.sh\n')
(cand/'.gitattributes').write_text('*.txt filter=evil\n')
(cand/'hooks').mkdir();(cand/'hooks'/'pre-commit').write_text('#!/bin/sh\necho AURA_HOOK_ATTEMPT >&2\necho x >/repo/hook-marker 2>/dev/null || true\nexit 0\n');(cand/'hooks'/'pre-commit').chmod(0o755)
(cand/'.git'/'config').open('a').write('\n[include]\n path = /candidate/extra-config\n[core]\n hooksPath = /candidate/hooks\n')
(cand/'changed.txt').write_text('changed\n')
p=run(['/usr/bin/bwrap','--unshare-all','--die-with-parent','--clearenv','--ro-bind','/usr','/usr','--ro-bind','/bin','/bin','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(src),'/repo','--bind',str(cand),'/candidate','--setenv','HOME','/nonexistent','--setenv','PATH','/usr/bin:/bin','--setenv','GIT_CONFIG_NOSYSTEM','1','--setenv','GIT_CONFIG_GLOBAL','/dev/null','--','/usr/bin/python3','-I','-B','-c',r"import subprocess,os; e=dict(os.environ); a=subprocess.run(['/usr/bin/git','-C','/candidate','add','changed.txt'],capture_output=True,text=True,env=e); print(a.stderr); assert a.returncode==0 and 'AURA_FILTER_ATTEMPT' in a.stderr; c=subprocess.run(['/usr/bin/git','-C','/candidate','commit','-m','probe'],capture_output=True,text=True,env=e); print(c.stderr); assert c.returncode==0 and 'AURA_HOOK_ATTEMPT' in c.stderr"])
if p.returncode: raise RuntimeError('FILTER_OR_HOOK_DENIAL_PROBE_FAILED:'+p.stderr[-1000:])
if list(outside.iterdir()) or (src/'source-marker').exists() or (cand/'.git'/'repo'/'filter-marker').exists(): raise RuntimeError('LOCAL_EFFECT_ESCAPED')
# Check that process resource limits terminate excessive children and writes.
cpu=run(['/usr/bin/prlimit','--cpu=1','--','/usr/bin/python3','-I','-B','-c','while True: pass'],timeout=4)
if cpu.returncode==0: raise RuntimeError('CPU_LIMIT_NOT_ENFORCED')
memory=run(['/usr/bin/prlimit','--as=268435456','--','/usr/bin/python3','-I','-B','-c','bytearray(536870912)'],timeout=5)
if memory.returncode==0: raise RuntimeError('MEMORY_LIMIT_NOT_ENFORCED')
fork_code='import os,signal,time; children=[]\ntry:\n for _ in range(64):\n  pid=os.fork()\n  if pid==0: time.sleep(3);os._exit(0)\n  children.append(pid)\nexcept OSError: pass\nfinally:\n for pid in children:\n  try: os.kill(pid,signal.SIGKILL)\n  except ProcessLookupError: pass\n for pid in children:\n  try: os.waitpid(pid,0)\n  except ChildProcessError: pass\nprint(len(children))'
forks=run(['/usr/bin/prlimit','--nproc=8','--','/usr/bin/python3','-I','-B','-c',fork_code],timeout=5)
try: fork_count=int(forks.stdout.strip())
except ValueError: raise RuntimeError('PROCESS_LIMIT_UNMEASURED:'+forks.stderr[-1000:])
if forks.returncode or fork_count>=64: raise RuntimeError('PROCESS_LIMIT_NOT_ENFORCED')
filecap=run(['/usr/bin/prlimit','--fsize=65536','--','/usr/bin/python3','-I','-B','-c',"open('/out/file-cap','wb').write(b'x'*131072)"],timeout=5)
file_size=(pathlib.Path('/out/file-cap').stat().st_size if pathlib.Path('/out/file-cap').exists() else 0)
if file_size!=65536 or 'File too large' not in filecap.stderr: raise RuntimeError('FILE_OUTPUT_LIMIT_NOT_ENFORCED:'+repr((file_size,filecap.returncode,filecap.stdout,filecap.stderr)))
fill_code="import os,signal,pathlib;signal.signal(signal.SIGXFSZ,signal.SIG_IGN);b=b'x'*65536\nfor i in range(8):\n try:\n  f=open('/out/tmpfs-fill-'+str(i),'wb')\n  while True: f.write(b)\n except OSError: pass\nprint(sum(p.stat().st_size for p in pathlib.Path('/out').glob('tmpfs-fill-*')))"
tmpfs=run(['/usr/bin/prlimit','--fsize=1048576','--','/usr/bin/python3','-I','-B','-c',fill_code],timeout=8)
try: fill_size=int(tmpfs.stdout.strip())
except ValueError: raise RuntimeError('TMPFS_LIMIT_UNMEASURED:'+tmpfs.stderr[-1000:])
if tmpfs.returncode or fill_size>5242880 or fill_size<4*1024*1024: raise RuntimeError('TMPFS_LIMIT_NOT_ENFORCED:'+repr((tmpfs.returncode,fill_size,tmpfs.stderr)))
print(json.dumps({'host_file_visible':False,'network_errno':code,'fsmonitor_invoked':True,'filter_invoked':True,'hook_invoked':True,'outside_writes':False,'cpu_limit':'ENFORCED','memory_limit':'ENFORCED','process_limit':fork_count,'file_size_limit_bytes':file_size,'candidate_tmpfs_limit_bytes':5242880,'tmpfs_fill_bytes':fill_size}))
"""
