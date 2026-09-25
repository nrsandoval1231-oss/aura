"""Standalone verifier entrypoint run read-only in a fresh Bubblewrap sandbox.

This file is copied into a private read-only input mount by ``aura_sandbox``.
It accepts no command or path from an agent and emits one bounded JSON receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import re
import resource
import subprocess
import sys

MAX_CAPTURE = 1024 * 1024
MAX_FILE = 16 * 1024
ENV = {
    "HOME": "/nonexistent",
    "PATH": "/usr/bin:/bin",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ALLOW_PROTOCOL": "file",
    "GIT_PROTOCOL_FROM_USER": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_ATTR_NOSYSTEM": "1",
}
GIT_CONFIG = [
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "core.attributesFile=/dev/null",
    "-c",
    "core.autocrlf=false",
    "-c",
    "commit.gpgsign=false",
]
PINNED_BINARIES = {
    "/usr/bin/bwrap": "8e19e40e7d5f7a7e8b488c7926feb040eab6ed10c58fa360e266d2f70670e92b",
    "/usr/bin/python3": "fa9796cd3a30878e11a2f40372f773d3fcd913fff35e5bee8dd9a036e22e93ab",
    "/usr/bin/git": "5516c9f362c29376ab9a499a33082f9f611941d8c75930c880e30ad109e39c9a",
    "/usr/bin/prlimit": "00be18793391b9222a041277a088022cc58088690cb0e851383bd8ec73f0fefb",
    "/usr/bin/timeout": "48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0",
}


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_CAPTURE, MAX_CAPTURE))


def _command(args: list[str], *, cwd: str | None = None, timeout: int = 10) -> str:
    with open("/out/verifier.log", "wb") as output:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=ENV,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            preexec_fn=_limits,
        )
    data = pathlib.Path("/out/verifier.log").read_bytes()
    if len(data) > MAX_CAPTURE or result.returncode:
        raise RuntimeError(f"VERIFY_COMMAND_FAILED: {data[-2048:].decode('utf-8', 'replace')}")
    return data.decode("utf-8", "replace").strip()


def _git(*args: str, cwd: str | None = None, timeout: int = 10) -> str:
    return _command(["/usr/bin/git", *GIT_CONFIG, *args], cwd=cwd, timeout=timeout)


def _check_runtime() -> dict[str, str]:
    release = pathlib.Path("/etc/os-release").read_text(encoding="utf-8")
    if 'VERSION_ID="26.04"' not in release:
        raise RuntimeError("WSL_DISTRO_MISMATCH")
    actual = {
        path: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        for path in PINNED_BINARIES
    }
    expected = {
        "/usr/bin/bwrap": "8e19e40e7d5f7a7e8b488c7926feb040eab6ed10c58fa360e266d2f70670e92b",
        "/usr/bin/python3": "fa9796cd3a30878e11a2f40372f773d3fcd913fff35e5bee8dd9a036e22e93ab",
        "/usr/bin/git": "5516c9f362c29376ab9a499a33082f9f611941d8c75930c880e30ad109e39c9a",
        "/usr/bin/prlimit": "00be18793391b9222a041277a088022cc58088690cb0e851383bd8ec73f0fefb",
        "/usr/bin/timeout": "48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0",
    }
    if actual != expected:
        raise RuntimeError("PINNED_BINARY_MISMATCH")
    return actual


def _verify() -> dict[str, object]:
    runtime = _check_runtime()
    proposal = json.loads(pathlib.Path("/input/proposal.json").read_text(encoding="utf-8"))
    base = proposal["base_sha"]
    files = {path: base64.b64decode(raw, validate=True) for path, raw in proposal["files"].items()}
    paths = sorted(files)
    bundle = pathlib.Path("/input/candidate.bundle").read_bytes()
    if len(bundle) > MAX_CAPTURE:
        raise RuntimeError("BUNDLE_TOO_LARGE")

    source_top = _git("-C", "/source", "rev-parse", "--show-toplevel")
    source_head = _git("-C", "/source", "rev-parse", "HEAD")
    source_status = _git("-C", "/source", "status", "--porcelain", "--untracked-files=all")
    if source_top != "/source" or source_head != base or source_status:
        raise RuntimeError("SOURCE_CHANGED_OR_STALE")

    git_dir = pathlib.Path("/out/candidate.git")
    git_dir.mkdir()
    (git_dir / "objects/info").mkdir(parents=True)
    (git_dir / "objects/info/alternates").write_text("/source/.git/objects\n", encoding="ascii")
    _git("--git-dir=" + str(git_dir), "init", "--bare")
    _git(
        "--git-dir=" + str(git_dir),
        "fetch",
        "--no-tags",
        "--no-recurse-submodules",
        "/source",
        base,
    )
    ref_list = _command(["/usr/bin/git", "bundle", "list-heads", "/input/candidate.bundle"])
    refs = [line.split() for line in ref_list.splitlines() if line.split()]
    if len(refs) != 1 or len(refs[0]) != 2:
        raise RuntimeError("BUNDLE_REF_COUNT")
    candidate, advertised_ref = refs[0]
    _git(
        "--git-dir=" + str(git_dir),
        "fetch",
        "--no-tags",
        "/input/candidate.bundle",
        advertised_ref + ":refs/heads/aura-candidate",
    )
    parent_line = _git("--git-dir=" + str(git_dir), "rev-list", "--parents", "-n", "1", candidate)
    if parent_line.split() != [candidate, base]:
        raise RuntimeError("CANDIDATE_PARENT_MISMATCH")
    tree = _git("--git-dir=" + str(git_dir), "rev-parse", candidate + "^{tree}")
    changed = _git(
        "--git-dir=" + str(git_dir),
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "--no-renames",
        base,
        candidate,
    ).splitlines()
    if sorted(changed) != paths:
        raise RuntimeError("CHANGED_PATHS_MISMATCH")
    for path, expected_bytes in files.items():
        with open("/out/blob.bin", "wb") as output:
            result = subprocess.run(
                [
                    "/usr/bin/git",
                    *GIT_CONFIG,
                    "--git-dir=" + str(git_dir),
                    "cat-file",
                    "blob",
                    f"{candidate}:{path}",
                ],
                env=ENV,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
                preexec_fn=_limits,
            )
        actual_bytes = pathlib.Path("/out/blob.bin").read_bytes()
        if result.returncode or len(actual_bytes) > MAX_FILE or actual_bytes != expected_bytes:
            raise RuntimeError("CANDIDATE_CONTENT_MISMATCH")

    worktree = pathlib.Path("/out/worktree")
    _git("--git-dir=" + str(git_dir), "worktree", "add", "--detach", str(worktree), candidate)
    check = (
        "import os,sys,unittest;sys.path.insert(0,os.getcwd());"
        "s=unittest.defaultTestLoader.discover('tests',pattern='test_*.py');"
        "r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())"
    )
    nested = [
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
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/out",
        "--ro-bind",
        str(git_dir),
        "/out/candidate.git",
        "--ro-bind",
        "/source",
        "/source",
        "--ro-bind",
        str(worktree),
        "/candidate",
        "--chdir",
        "/candidate",
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
        "-c",
        check,
    ]
    with open("/out/test.log", "wb") as output:
        checked = subprocess.run(
            nested,
            env=ENV,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
            preexec_fn=_limits,
        )
    test_output = pathlib.Path("/out/test.log").read_bytes()
    if len(test_output) > MAX_CAPTURE or checked.returncode:
        raise RuntimeError(
            "READ_ONLY_TEST_FAILED:" + test_output[-2048:].decode("utf-8", "replace")
        )
    if _git("--git-dir=" + str(git_dir), "rev-parse", candidate + "^{tree}") != tree:
        raise RuntimeError("VERIFIER_TREE_CHANGED")

    patch_path = pathlib.Path("/out/verified.patch")
    patch_stderr_path = pathlib.Path("/out/verified-patch.stderr")
    patch_command = [
        "/usr/bin/git",
        *GIT_CONFIG,
        "--git-dir=" + str(git_dir),
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--binary",
        "--full-index",
        "--no-renames",
        "--no-color",
        base,
        candidate,
        "--",
        *paths,
    ]
    with patch_path.open("wb") as output, patch_stderr_path.open("wb") as errors:
        patch_result = subprocess.run(
            patch_command,
            env=ENV,
            stdout=output,
            stderr=errors,
            timeout=10,
            check=False,
            preexec_fn=_limits,
        )
    patch_bytes = patch_path.read_bytes()
    patch_stderr = patch_stderr_path.read_bytes()
    if (
        patch_result.returncode
        or len(patch_bytes) > MAX_CAPTURE
        or len(patch_stderr) > 8192
        or patch_stderr
    ):
        raise RuntimeError("VERIFIED_PATCH_DERIVATION_FAILED")
    check_digest = hashlib.sha256(
        re.sub(rb"Ran (\d+) tests? in [0-9.]+s", rb"Ran \1 tests in <elapsed>s", test_output)
    ).hexdigest()
    return {
        "status": "VERIFIED",
        "candidate_sha": candidate,
        "tree_sha": tree,
        "changed_paths": paths,
        "test_output_sha256": check_digest,
        "test_output": test_output.decode("utf-8", "replace"),
        "patch_b64": base64.b64encode(patch_bytes).decode("ascii"),
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
        "patch_binding": {
            "candidate_sha": candidate,
            "tree_sha": tree,
            "changed_paths": paths,
            "check_sha256": check_digest,
        },
        "read_only_check": "PASS",
        "runtime_binary_sha256": runtime,
    }


def main() -> None:
    try:
        result = _verify()
        code = 0
    except BaseException as exc:
        result = {"status": "REJECTED", "error": str(exc)}
        code = 1
    output = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(output) > MAX_CAPTURE:
        raise SystemExit(2)
    sys.stdout.buffer.write(output)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
