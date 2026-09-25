"""Fail-closed detached owner attestation for exact Aura audit candidates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path

from forge.audit_receipts import (
    _git,
    _openssl,
    _read_json,
    _validate_validation_artifact,
    manifest_digest,
    public_key_fingerprint,
    signed_payload,
    tracked_manifest,
)
from forge.trust_kernel import CandidateIdentity, ForgeError

AURA_AUDIT_DOMAIN = "aura-agent.detached-audit.v1"
AURA_REPOSITORY_DOMAIN = "aura-agent.origin.v1"
AURA_PACKET_PREFIX = "AURA-"
AURA_TRUST_FILE = Path(".agent/aura-audit-trust.json")
APPROVED_PUBLIC_KEY_SHA256 = "55faf401c993f16fd0a9d4f0e9d58babd61ccb018f6bd6cb2a9c7087505de1c1"


def aura_repository_digest(root: Path) -> str:
    origin = _git(root, "remote", "get-url", "origin")
    if not origin:
        raise ForgeError("AUDIT_REPOSITORY_INVALID", "Aura candidate has no origin remote")
    return hashlib.sha256(f"{AURA_REPOSITORY_DOMAIN}\n{origin}\n".encode()).hexdigest()


def _validate_packet_identity(packet_id: str, base_sha: str) -> Path:
    if not isinstance(packet_id, str) or not re.fullmatch(
        r"AURA-[A-Z0-9]+(?:-[A-Z0-9]+)*", packet_id
    ):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura packet ID is malformed")
    if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura packet base must be a full commit SHA")
    artifact = Path(".agent") / "artifacts" / packet_id / "VALIDATION.json"
    if len(artifact.parts) != 4 or artifact.parts[2] != packet_id:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura validation artifact path is unsafe")
    return artifact


def exact_aura_candidate(root: Path, packet_id: str) -> CandidateIdentity:
    return CandidateIdentity(
        aura_repository_digest(root),
        _git(root, "rev-parse", "HEAD"),
        _git(root, "rev-parse", "HEAD^{tree}"),
        packet_id,
    )


def _external_file(root: Path, path: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return
    raise ForgeError("AUDIT_TRUST_INVALID", f"{label} must be outside candidate root")


def verify_aura_detached_audit(
    root: Path,
    candidate: CandidateIdentity,
    *,
    packet_id: str,
    base_sha: str,
    receipt_path: Path | None = None,
    trust_anchor: Path | None = None,
    reviewer_evidence_path: Path | None = None,
    trust_file: Path | None = None,
    validation_artifact: Path | None = None,
) -> Mapping[str, object]:
    """Verify external reviewer evidence and an owner-signed exact candidate receipt."""
    root = root.resolve()
    artifact_path = _validate_packet_identity(packet_id, base_sha)
    receipt_path = receipt_path or _env_path("AURA_AUDIT_RECEIPT")
    trust_anchor = trust_anchor or _env_path("AURA_AUDIT_PUBLIC_KEY")
    trust_file = trust_file or root / AURA_TRUST_FILE
    validation_artifact = validation_artifact or root / artifact_path
    if receipt_path is None or trust_anchor is None:
        raise ForgeError("AUDIT_TRUST_MISSING", "Aura receipt and external public key are required")
    for label, path in (("receipt", receipt_path), ("public key", trust_anchor)):
        _external_file(root, path, label)
        if not path.is_file():
            raise ForgeError("AUDIT_TRUST_MISSING", f"External {label} is absent")
    trust = _read_json(trust_file)
    if set(trust) != {"schema_version", "public_key_sha256"} or trust.get("schema_version") != 1:
        raise ForgeError("AUDIT_TRUST_INVALID", "Aura owner trust record is malformed")
    approved = trust.get("public_key_sha256")
    if (
        approved != APPROVED_PUBLIC_KEY_SHA256
        or public_key_fingerprint(trust_anchor) != APPROVED_PUBLIC_KEY_SHA256
    ):
        raise ForgeError("AUDIT_TRUST_INVALID", "Aura public key does not match owner approval")

    receipt = _read_json(receipt_path)
    required = {
        "domain",
        "repository_digest",
        "packet_id",
        "base_sha",
        "head",
        "git_tree",
        "tree",
        "candidate_digest",
        "manifest",
        "manifest_digest",
        "validation_artifact",
        "validation_digest",
        "reviewer_id",
        "reviewer_evidence_file",
        "reviewer_evidence_sha256",
        "reviewer_verdict",
        "attestor_id",
        "signature_file",
    }
    if set(receipt) != required:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura receipt fields are missing or unexpected")
    if (
        receipt["domain"] != AURA_AUDIT_DOMAIN
        or receipt["packet_id"] != packet_id
        or receipt["base_sha"] != base_sha
        or receipt["reviewer_verdict"] != "PASS"
    ):
        raise ForgeError(
            "AUDIT_REJECTED", "Aura domain, packet, base, or reviewer verdict is invalid"
        )
    attestor_id = f"owner-sha256:{APPROVED_PUBLIC_KEY_SHA256}"
    if receipt["attestor_id"] != attestor_id:
        raise ForgeError("AUDIT_TRUST_INVALID", "Attestor identity is not derived from owner key")
    reviewer_id = receipt["reviewer_id"]
    if not isinstance(reviewer_id, str) or not reviewer_id or reviewer_id == attestor_id:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Independent reviewer identity is required")
    manifest = receipt["manifest"]
    if not isinstance(manifest, dict) or not manifest:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura candidate manifest is invalid")
    if receipt["manifest_digest"] != manifest_digest(manifest):
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura manifest digest is invalid")

    if candidate.packet_id != packet_id or candidate.repository_digest != aura_repository_digest(
        root
    ):
        raise ForgeError(
            "AUDIT_CANDIDATE_MISMATCH", "Candidate has wrong Aura repository or packet"
        )
    head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    if _git(root, "status", "--porcelain"):
        raise ForgeError("AUDIT_DIRTY_TREE", "Aura detached audit requires a clean checkout")
    if (
        head != candidate.revision
        or tree != candidate.tree
        or receipt["head"] != head
        or receipt["git_tree"] != tree
        or receipt["tree"] != tree
        or receipt["repository_digest"] != candidate.repository_digest
        or receipt["candidate_digest"] != candidate.digest
    ):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Aura receipt does not bind exact HEAD/tree")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", base_sha, head],
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ForgeError(
            "AUDIT_CANDIDATE_MISMATCH", "Aura candidate is not based on approved base"
        ) from exc
    if manifest != tracked_manifest(root, head):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Aura committed manifest differs")
    if receipt["validation_artifact"] != artifact_path.as_posix():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura validation artifact path is unexpected")
    if not validation_artifact.is_file():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Aura validation artifact is absent")
    if hashlib.sha256(validation_artifact.read_bytes()).hexdigest() != receipt["validation_digest"]:
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Aura validation artifact digest differs")
    _validate_validation_artifact(root, validation_artifact)

    evidence_path = reviewer_evidence_path or Path(str(receipt["reviewer_evidence_file"]))
    _external_file(root, evidence_path, "reviewer evidence")
    if not evidence_path.is_file():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "External reviewer evidence is absent")
    evidence_bytes = evidence_path.read_bytes()
    if hashlib.sha256(evidence_bytes).hexdigest() != receipt["reviewer_evidence_sha256"]:
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Reviewer evidence digest differs")
    try:
        evidence = json.loads(evidence_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ForgeError("AUDIT_RECEIPT_INVALID", "Reviewer evidence is not valid JSON") from exc
    if not isinstance(evidence, dict) or any(
        evidence.get(key) != value
        for key, value in {
            "reviewer_id": reviewer_id,
            "verdict": "PASS",
            "packet_id": packet_id,
            "base_sha": base_sha,
            "candidate_digest": candidate.digest,
            "candidate_tree": tree,
        }.items()
    ):
        raise ForgeError(
            "AUDIT_RECEIPT_INVALID", "Reviewer evidence does not attest this candidate"
        )

    signature = Path(str(receipt["signature_file"]))
    _external_file(root, signature, "detached signature")
    if "signature" in receipt or not signature.is_file():
        raise ForgeError("AUDIT_RECEIPT_INVALID", "External detached signature is required")
    if (
        _git(root, "status", "--porcelain")
        or _git(root, "rev-parse", "HEAD") != head
        or _git(root, "rev-parse", "HEAD^{tree}") != tree
        or aura_repository_digest(root) != candidate.repository_digest
    ):
        raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "Aura repository changed during verification")
    with tempfile.TemporaryDirectory(prefix="aura-audit-") as temp:
        payload = Path(temp) / "receipt.json"
        payload.write_bytes(signed_payload(receipt))
        check = subprocess.run(
            [
                _openssl(),
                "dgst",
                "-sha256",
                "-verify",
                str(trust_anchor),
                "-signature",
                str(signature),
                str(payload),
            ],
            capture_output=True,
            text=True,
        )
    if check.returncode != 0 or check.stdout.strip() != "Verified OK":
        raise ForgeError("AUDIT_SIGNATURE_INVALID", "Owner detached attestation is invalid")
    return receipt


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None
