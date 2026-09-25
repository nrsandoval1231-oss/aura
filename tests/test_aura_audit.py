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
from forge.trust_kernel import CandidateIdentity, ForgeError


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


def test_external_public_key_is_read_once_and_snapshot_is_verified(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    original = public.read_bytes()
    reads = 0

    def read_once():
        nonlocal reads
        reads += 1
        if reads == 1:
            return original
        return b"changed key bytes"

    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(
        aura_audit.Path,
        "read_bytes",
        lambda self: read_once() if self == public else original_read_bytes(self),
    )
    # OpenSSL must receive the verifier-owned snapshot of the bytes fingerprinted above.
    real_run = subprocess.run
    verified_keys = []

    def inspect_run(args, **kwargs):
        if "-verify" in args:
            verified_keys.append(Path(args[args.index("-verify") + 1]).read_bytes())
        return real_run(args, **kwargs)

    monkeypatch.setattr(aura_audit.subprocess, "run", inspect_run)
    assert _verify(root, candidate, receipt, public, reviewer)["reviewer_id"] == "astra-reviewer"
    assert reads == 1
    assert verified_keys == [original]


@pytest.mark.parametrize("key_state", ["missing", "wrong"])
def test_missing_or_wrong_external_key_fails_closed(tmp_path, monkeypatch, key_state):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    if key_state == "missing":
        public.unlink()
        expected = "External public key is absent"
    else:
        other = tmp_path / "wrong-public.pem"
        other.write_text("not a public key", encoding="utf-8")
        public = other
        expected = "does not match owner approval"
    with pytest.raises(ForgeError, match=expected):
        _verify(root, candidate, receipt, public, reviewer)


def test_missing_or_invalid_signature_fails_closed(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    signature = Path(data["signature_file"])
    signature.unlink()
    with pytest.raises(ForgeError, match="detached signature"):
        _verify(root, candidate, receipt, public, reviewer)
    signature.write_bytes(b"bad signature")
    with pytest.raises(ForgeError, match="attestation is invalid"):
        _verify(root, candidate, receipt, public, reviewer)


@pytest.mark.parametrize("mutation", ["head", "tree", "repository"])
def test_changed_candidate_identity_and_repository_fail_closed(tmp_path, monkeypatch, mutation):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    if mutation == "head":
        changed = CandidateIdentity(
            candidate.repository_digest, "0" * 40, candidate.tree, candidate.packet_id
        )
    elif mutation == "tree":
        changed = CandidateIdentity(
            candidate.repository_digest, candidate.revision, "0" * 40, candidate.packet_id
        )
    else:
        changed = CandidateIdentity(
            "0" * 64, candidate.revision, candidate.tree, candidate.packet_id
        )
    with pytest.raises(ForgeError, match="Candidate has wrong Aura repository|exact HEAD/tree"):
        _verify(root, changed, receipt, public, reviewer)


def test_non_green_validation_gate_fails_closed(tmp_path, monkeypatch):
    root, candidate, receipt, public, reviewer = _signed_fixture(tmp_path, monkeypatch)
    validation = root / ".agent" / "artifacts" / candidate.packet_id / "VALIDATION.json"
    data = json.loads(validation.read_text(encoding="utf-8"))
    data["pre_audit_gates"][next(iter(data["pre_audit_gates"]))] = 1
    validation.write_text(json.dumps(data), encoding="utf-8")
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    receipt_data["validation_digest"] = hashlib.sha256(validation.read_bytes()).hexdigest()
    receipt.write_text(json.dumps(receipt_data, sort_keys=True), encoding="utf-8")
    # Isolate the gate check from the earlier dirty-checkout rejection.
    original_git = aura_audit._git
    monkeypatch.setattr(
        aura_audit,
        "_git",
        lambda root, *args: "" if args == ("status", "--porcelain") else original_git(root, *args),
    )
    with pytest.raises(ForgeError, match="green pre-audit gates"):
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
