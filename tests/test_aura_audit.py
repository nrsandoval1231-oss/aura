from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import forge.aura_audit as aura_audit
from forge.audit_receipts import (
    _openssl,
    manifest_digest,
    required_pre_audit_gates,
    signed_payload,
    tracked_manifest,
)
from forge.aura_audit import exact_aura_candidate, verify_aura_detached_audit
from forge.trust_kernel import ForgeError


def _run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def _signed_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    packet_id: str = "AURA-TRUST-001",
):
    root = tmp_path / "repo"
    root.mkdir()
    _run("git", "init", "-q", cwd=root)
    _run("git", "config", "user.email", "audit@example.invalid", cwd=root)
    _run("git", "config", "user.name", "Audit", cwd=root)
    _run(
        "git",
        "remote",
        "add",
        "origin",
        "https://example.invalid/nrsandoval1231-oss/aura.git",
        cwd=root,
    )
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    _run("git", "add", "tracked.txt", cwd=root)
    _run("git", "commit", "-qm", "base", cwd=root)
    base = _run("git", "rev-parse", "HEAD", cwd=root)

    public = tmp_path / "owner-public.pem"
    private = tmp_path / "test-only-private.pem"
    _run(
        _openssl(),
        "genpkey",
        "-algorithm",
        "RSA",
        "-pkeyopt",
        "rsa_keygen_bits:2048",
        "-out",
        str(private),
        cwd=tmp_path,
    )
    _run(_openssl(), "pkey", "-in", str(private), "-pubout", "-out", str(public), cwd=tmp_path)
    fingerprint = hashlib.sha256(public.read_bytes()).hexdigest()
    monkeypatch.setattr(aura_audit, "APPROVED_PUBLIC_KEY_SHA256", fingerprint)
    trust = root / aura_audit.AURA_TRUST_FILE
    trust.parent.mkdir(parents=True, exist_ok=True)
    trust.write_text(
        json.dumps({"schema_version": 1, "public_key_sha256": fingerprint}), encoding="utf-8"
    )
    validation_rel = Path(".agent") / "artifacts" / packet_id / "VALIDATION.json"
    validation = root / validation_rel
    validation.parent.mkdir(parents=True, exist_ok=True)
    validation.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pre_audit_gates": {name: 0 for name in sorted(required_pre_audit_gates(root))},
                "slice_gate": "PENDING_SIGNATURE",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _run("git", "add", ".agent", cwd=root)
    _run("git", "commit", "-qm", "candidate evidence", cwd=root)
    candidate = exact_aura_candidate(root, packet_id)
    manifest = tracked_manifest(root)
    reviewer = tmp_path / "reviewer.json"
    reviewer_payload = {
        "reviewer_id": "astra-reviewer",
        "verdict": "PASS",
        "packet_id": packet_id,
        "base_sha": base,
        "candidate_digest": candidate.digest,
        "candidate_tree": candidate.tree,
    }
    reviewer.write_text(json.dumps(reviewer_payload, sort_keys=True), encoding="utf-8")
    signature = tmp_path / "owner.sig"
    receipt = {
        "domain": aura_audit.AURA_AUDIT_DOMAIN,
        "repository_digest": candidate.repository_digest,
        "packet_id": packet_id,
        "base_sha": base,
        "head": candidate.revision,
        "git_tree": candidate.tree,
        "tree": candidate.tree,
        "candidate_digest": candidate.digest,
        "manifest": manifest,
        "manifest_digest": manifest_digest(manifest),
        "validation_artifact": validation_rel.as_posix(),
        "validation_digest": hashlib.sha256(validation.read_bytes()).hexdigest(),
        "reviewer_id": "astra-reviewer",
        "reviewer_evidence_file": str(reviewer),
        "reviewer_evidence_sha256": hashlib.sha256(reviewer.read_bytes()).hexdigest(),
        "reviewer_verdict": "PASS",
        "attestor_id": f"owner-sha256:{fingerprint}",
        "signature_file": str(signature),
    }
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    payload = tmp_path / "payload.json"
    payload.write_bytes(signed_payload(receipt))
    _run(
        _openssl(),
        "dgst",
        "-sha256",
        "-sign",
        str(private),
        "-out",
        str(signature),
        str(payload),
        cwd=tmp_path,
    )
    private.unlink()
    return root, candidate, receipt_path, public, reviewer


def _verify(root, candidate, receipt, public, reviewer=None):
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    return verify_aura_detached_audit(
        root,
        candidate,
        packet_id=candidate.packet_id,
        base_sha=receipt_data["base_sha"],
        receipt_path=receipt,
        trust_anchor=public,
        reviewer_evidence_path=reviewer,
    )


def test_owner_attested_reviewer_receipt_accepts_exact_aura_candidate(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    result = _verify(root, candidate, receipt, public, reviewer)
    assert result["reviewer_id"] == "astra-reviewer"
    assert result["attestor_id"].startswith("owner-sha256:")


@pytest.mark.parametrize(
    "mutation", ["domain", "base_sha", "reviewer_id", "reviewer_verdict", "candidate_digest"]
)
def test_modified_aura_receipt_fails_closed(tmp_path, monkeypatch, mutation):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data[mutation] = "tampered"
    receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError):
        _verify(root, candidate, receipt, public, reviewer)


def test_missing_reviewer_evidence_dirty_tree_and_wrong_key_fail(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    reviewer.unlink()
    with pytest.raises(ForgeError, match="reviewer evidence"):
        _verify(root, candidate, receipt, public)
    reviewer.write_text("{}", encoding="utf-8")
    (root / "local-change").write_text("dirty", encoding="utf-8")
    with pytest.raises(ForgeError, match="clean checkout"):
        _verify(root, candidate, receipt, public)


def test_modified_validation_artifact_is_rejected(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    (root / ".agent" / "artifacts" / candidate.packet_id / "VALIDATION.json").write_text(
        "{}", encoding="utf-8"
    )
    with pytest.raises(ForgeError):
        _verify(root, candidate, receipt, public, reviewer)


def test_inline_signature_or_key_and_in_tree_external_material_are_rejected(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["signature"] = "inline"
    receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError):
        _verify(root, candidate, receipt, public, reviewer)
    data.pop("signature")
    data["public_key"] = "inline"
    receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError, match="missing or unexpected"):
        _verify(root, candidate, receipt, public, reviewer)
    with pytest.raises(ForgeError, match="outside candidate"):
        verify_aura_detached_audit(
            root,
            candidate,
            packet_id=candidate.packet_id,
            base_sha=data["base_sha"],
            receipt_path=root / "receipt.json",
            trust_anchor=public,
        )


def test_aura_m0_packet_uses_its_parsed_packet_and_base(tmp_path, monkeypatch):
    packet_id = "AURA-M0-CLI-002"
    root, candidate, receipt, public, reviewer = _signed_fixture(
        tmp_path, monkeypatch, packet_id=packet_id
    )
    assert candidate.packet_id == packet_id
    assert _verify(root, candidate, receipt, public, reviewer)["packet_id"] == packet_id


def test_aura_packet_id_and_base_are_validated(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    with pytest.raises(ForgeError, match="packet ID"):
        verify_aura_detached_audit(
            root,
            candidate,
            packet_id="../FORGE-INTEGRATED-001",
            base_sha=json.loads(receipt.read_text(encoding="utf-8"))["base_sha"],
            receipt_path=receipt,
            trust_anchor=public,
            reviewer_evidence_path=reviewer,
        )
    with pytest.raises(ForgeError, match="base must be a full commit SHA"):
        verify_aura_detached_audit(
            root,
            candidate,
            packet_id=candidate.packet_id,
            base_sha="53fb0e3",
            receipt_path=receipt,
            trust_anchor=public,
            reviewer_evidence_path=reviewer,
        )
