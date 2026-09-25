"""Verification of detached, independently supplied audit receipts.

The receipt and its public key are inputs to validation, never candidate files.
The candidate may describe neither its auditor nor the key that verifies it.
OpenSSL is used because it is already part of the supported local validation
environment and keeps a private signing key out of the Python runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from forge.trust_kernel import CandidateIdentity, ForgeError

AUDIT_DOMAIN = "forge-agent.detached-audit.v1"
INTEGRATED_PACKET_ID = "FORGE-INTEGRATED-001"
TRUST_FILE = Path(".agent/audit-trust.json")
VALIDATION_ARTIFACT = Path(".agent/artifacts/FORGE-INTEGRATED-001/VALIDATION.json")
PRE_AUDIT_STATIC_GATES = frozenset(
    {
        "python floor",
        "import surface",
        "lint",
        "format",
        "tests",
        "doc/graph",
        "self-improvement",
        "governed evolution",
    }
)


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()


def manifest_digest(manifest: Mapping[str, str]) -> str:
    return hashlib.sha256(_canonical(dict(sorted(manifest.items())))).hexdigest()


def public_key_fingerprint(public_key: Path) -> str:
    """The owner-approved fingerprint of the exact external public-key bytes."""
    try:
        return hashlib.sha256(public_key.read_bytes()).hexdigest()
    except OSError as exc:
        raise ForgeError("AUDIT_TRUST_MISSING", "External auditor public key is absent") from exc


def repository_digest(root: Path) -> str:
    """Derive repository identity from origin, never from a caller argument."""
    origin = _git(root, "remote", "get-url", "origin")
    if not origin:
        raise ForgeError("AUDIT_REPOSITORY_INVALID", "Candidate repository has no origin remote")
    return hashlib.sha256(f"forge-agent.origin.v1\n{origin}\n".encode()).hexdigest()


def tracked_manifest(root: Path, revision: str = "HEAD") -> dict[str, str]:
    """Hash every committed regular blob once, independent of checkout filters.

    The receipt must cover the complete candidate.  Reading blob objects instead
    of working-tree paths keeps a clean commit's manifest stable across
    platforms and Git line-ending settings.  The caller still verifies a clean
    worktree before accepting the manifest, so this does not make local edits
    acceptable.
    """
    try:
        raw = _git_bytes(root, "ls-tree", "-rz", "--full-tree", revision)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ForgeError(
            "AUDIT_MANIFEST_INVALID", "Cannot enumerate committed candidate tree"
        ) from exc
    entries = raw.split(b"\0")
    if entries and entries[-1] == b"":
        entries.pop()
    if not entries:
        raise ForgeError("AUDIT_MANIFEST_INVALID", "Committed candidate tree is empty")
    manifest: dict[str, str] = {}
    for entry in entries:
        metadata, separator, raw_path = entry.partition(b"\t")
        fields = metadata.split(b" ")
        if not separator or len(fields) != 3:
            raise ForgeError("AUDIT_MANIFEST_INVALID", "Committed tree entry is malformed")
        mode, object_type, object_id = fields
        if mode not in {b"100644", b"100755"} or object_type != b"blob":
            raise ForgeError(
                "AUDIT_MANIFEST_INVALID",
                "Committed candidate contains a non-regular or non-blob entry",
            )
        if len(object_id) != 40 or any(byte not in b"0123456789abcdef" for byte in object_id):
            raise ForgeError("AUDIT_MANIFEST_INVALID", "Committed tree object id is malformed")
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ForgeError("AUDIT_MANIFEST_INVALID", "Tracked path is not UTF-8") from exc
        components = path.split("/")
        if (
            not path
            or path in manifest
            or "\\" in path
            or "\x00" in path
            or path.startswith("/")
            or path.endswith("/")
            or any(component in {"", ".", ".."} for component in components)
        ):
            raise ForgeError(
                "AUDIT_MANIFEST_INVALID", "Committed tree path is malformed or duplicated"
            )
        try:
            blob = _git_bytes(root, "cat-file", "blob", object_id.decode("ascii"))
        except (OSError, UnicodeError, subprocess.CalledProcessError) as exc:
            raise ForgeError(
                "AUDIT_MANIFEST_INVALID", "Committed tree blob is unavailable"
            ) from exc
        manifest[path] = hashlib.sha256(blob).hexdigest()
    return dict(sorted(manifest.items()))


def signed_payload(receipt: Mapping[str, Any]) -> bytes:
    """Return the exact bytes an independent auditor signs."""
    body = {key: value for key, value in receipt.items() if key != "signature"}
    return _canonical(body)


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError("AUDIT_RECEIPT_INVALID", f"Cannot read audit receipt: {path}") from exc
    if not isinstance(raw, dict):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Detached audit receipt must be an object")
    return raw


def verify_detached_audit(
    root: Path,
    candidate: CandidateIdentity,
    *,
    receipt_path: Path | None = None,
    trust_anchor: Path | None = None,
    trust_file: Path | None = None,
    validation_artifact: Path | None = None,
) -> Mapping[str, Any]:
    """Verify an external receipt against a clean exact candidate.

    Paths default to environment variables and therefore remain outside the
    candidate. A receipt with an inline key or inline signature is rejected.
    """
    receipt_path = receipt_path or _env_path("FORGE_AUDIT_RECEIPT")
    trust_anchor = trust_anchor or _env_path("FORGE_AUDIT_PUBLIC_KEY")
    trust_file = trust_file or root / TRUST_FILE
    validation_artifact = validation_artifact or root / VALIDATION_ARTIFACT
    if receipt_path is None or trust_anchor is None:
        raise ForgeError(
            "AUDIT_TRUST_MISSING",
            "AUDIT_TRUST_MISSING: external receipt and trust anchor are required",
        )
    if not receipt_path.is_file() or not trust_anchor.is_file() or not trust_file.is_file():
        raise ForgeError(
            "AUDIT_TRUST_MISSING", "AUDIT_TRUST_MISSING: external receipt or trust anchor is absent"
        )
    root = root.resolve()
    for name, path in (("receipt", receipt_path), ("auditor public key", trust_anchor)):
        try:
            path.resolve().relative_to(root)
        except ValueError:
            pass
        else:
            raise ForgeError(
                "AUDIT_TRUST_INVALID", f"AUDIT_TRUST_INVALID: {name} must be outside candidate root"
            )
    trust = _read_json(trust_file)
    expected_trust_keys = {"schema_version", "auditor_id", "public_key_sha256"}
    if set(trust) != expected_trust_keys or trust.get("schema_version") != 1:
        raise ForgeError("AUDIT_TRUST_INVALID", "Owner audit trust record is malformed")
    approved_fingerprint = trust.get("public_key_sha256")
    approved_auditor = trust.get("auditor_id")
    if (
        not isinstance(approved_fingerprint, str)
        or len(approved_fingerprint) != 64
        or approved_fingerprint != public_key_fingerprint(trust_anchor)
        or not isinstance(approved_auditor, str)
        or not approved_auditor
    ):
        raise ForgeError("AUDIT_TRUST_INVALID", "External key does not match owner-approved trust")
    receipt = _read_json(receipt_path)
    required = (
        "domain",
        "repository_digest",
        "head",
        "git_tree",
        "tree",
        "candidate_digest",
        "manifest",
        "validation_digest",
        "validation_artifact",
        "verdict",
        "auditor_id",
        "signature_file",
    )
    if any(
        not isinstance(receipt.get(key), str) or not receipt.get(key)
        for key in required
        if key != "manifest"
    ):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Detached receipt is missing required fields")
    if receipt.get("domain") != AUDIT_DOMAIN or receipt.get("verdict") != "PASS":
        raise ForgeError("AUDIT_REJECTED", "Detached audit domain or verdict is not accepted")
    manifest = receipt.get("manifest")
    if (
        not isinstance(manifest, dict)
        or not manifest
        or any(
            not isinstance(k, str) or not isinstance(v, str) or len(v) != 64
            for k, v in manifest.items()
        )
    ):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Detached receipt manifest is invalid")
    if receipt.get("repository_digest") != candidate.repository_digest:
        raise ForgeError(
            "AUDIT_CANDIDATE_MISMATCH", "Audit repository identity does not match candidate"
        )
    if receipt.get("candidate_digest") != candidate.digest or receipt.get("tree") != candidate.tree:
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Audit is not bound to the exact candidate")
    if receipt.get("head") != candidate.revision:
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Audit head does not match candidate revision")
    if receipt.get("manifest_digest") != manifest_digest(manifest):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Audit manifest digest is invalid")
    status = _git(root, "status", "--porcelain")
    head = _git(root, "rev-parse", "HEAD")
    git_tree = _git(root, "rev-parse", "HEAD^{tree}")
    if status:
        raise ForgeError("AUDIT_DIRTY_TREE", "Independent audit requires a clean candidate tree")
    if (
        repository_digest(root) != candidate.repository_digest
        or head != candidate.revision
        or receipt.get("git_tree") != git_tree
        or candidate.tree != git_tree
    ):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Repository HEAD changed after audit")
    if manifest != tracked_manifest(root, candidate.revision):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Audit manifest is incomplete or differs")
    if (
        _git(root, "status", "--porcelain")
        or repository_digest(root) != candidate.repository_digest
        or _git(root, "rev-parse", "HEAD") != candidate.revision
        or _git(root, "rev-parse", "HEAD^{tree}") != candidate.tree
    ):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Repository changed during audit")
    if receipt.get("auditor_id") != approved_auditor:
        raise ForgeError("AUDIT_TRUST_INVALID", "Receipt auditor does not match owner trust")
    if receipt.get("validation_artifact") != VALIDATION_ARTIFACT.as_posix():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Audit names an unexpected validation artifact")
    if not validation_artifact.is_file():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Committed validation artifact is absent")
    actual_validation_digest = hashlib.sha256(validation_artifact.read_bytes()).hexdigest()
    if receipt.get("validation_digest") != actual_validation_digest:
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Validation artifact digest differs")
    _validate_validation_artifact(root, validation_artifact)
    sig = Path(str(receipt["signature_file"]))
    try:
        sig.resolve().relative_to(root)
    except ValueError:
        pass
    else:
        raise ForgeError(
            "AUDIT_TRUST_INVALID",
            "AUDIT_TRUST_INVALID: detached signature must be outside candidate root",
        )
    if not sig.is_file() or "signature" in receipt:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Detached signature file is required")
    with tempfile.TemporaryDirectory(prefix="forge-audit-") as temp:
        payload = Path(temp) / "payload.json"
        payload.write_bytes(signed_payload(receipt))
        check = subprocess.run(
            [
                _openssl(),
                "dgst",
                "-sha256",
                "-verify",
                str(trust_anchor),
                "-signature",
                str(sig),
                str(payload),
            ],
            capture_output=True,
            text=True,
        )
    if check.returncode != 0 or check.stdout.strip() != "Verified OK":
        raise ForgeError("AUDIT_SIGNATURE_INVALID", "Detached audit signature is not valid")
    return receipt


def exact_candidate(root: Path, packet_id: str = INTEGRATED_PACKET_ID) -> CandidateIdentity:
    """Return the clean-commit identity the detached receipt must bind."""
    return CandidateIdentity(
        repository_digest(root),
        _git(root, "rev-parse", "HEAD"),
        _git(root, "rev-parse", "HEAD^{tree}"),
        packet_id,
    )


def required_pre_audit_gates(root: Path) -> frozenset[str]:
    """The exact `validate.sh` gate set before the detached slice signature.

    Ledger streams are dynamic by design: the validation authority checks every
    current ``.jsonl`` stream.  The slice gate is deliberately excluded here;
    the receipt itself supplies the missing independent signature, and the
    artifact explicitly records that pending state.
    """
    ledgers = root / ".agent" / "ledger"
    return PRE_AUDIT_STATIC_GATES | frozenset(
        f"ledger {path.stem}" for path in ledgers.glob("*.jsonl") if path.is_file()
    )


def _validate_validation_artifact(root: Path, path: Path) -> None:
    artifact = _read_json(path)
    required = {"schema_version", "pre_audit_gates", "slice_gate"}
    if set(artifact) != required or artifact.get("schema_version") != 1:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Validation artifact is malformed")
    gates = artifact.get("pre_audit_gates")
    expected_gates = required_pre_audit_gates(root)
    if (
        not isinstance(gates, dict)
        or set(gates) != expected_gates
        or any(type(value) is not int or value != 0 for value in gates.values())
    ):
        raise ForgeError(
            "AUDIT_RECEIPT_INVALID", "Validation artifact does not record green pre-audit gates"
        )
    if artifact.get("slice_gate") != "PENDING_SIGNATURE":
        raise ForgeError(
            "AUDIT_RECEIPT_INVALID", "Validation artifact does not distinguish pending audit"
        )


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, check=True).stdout


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else None


def _openssl() -> str:
    return shutil.which("openssl") or "C:/Program Files/Git/usr/bin/openssl.exe"
