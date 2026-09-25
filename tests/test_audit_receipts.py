from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import forge.audit_receipts as audit_receipts
from forge.audit_receipts import (
    AUDIT_DOMAIN,
    _openssl,
    manifest_digest,
    public_key_fingerprint,
    repository_digest,
    required_pre_audit_gates,
    signed_payload,
    tracked_manifest,
    verify_detached_audit,
)
from forge.trust_kernel import CandidateIdentity, ForgeError


def _candidate(
    tmp_path: Path, packet_id: str = "FORGE-INTEGRATED-001"
) -> tuple[Path, CandidateIdentity, Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "tracked.txt").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Audit"], cwd=root, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.test/forge-agent.git"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "candidate"], cwd=root, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    git_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest = tracked_manifest(root)
    candidate = CandidateIdentity(repository_digest(root), head, git_tree, packet_id)
    key = tmp_path / "audit.key"
    pub = tmp_path / "audit.pub"
    subprocess.run(
        [
            _openssl(),
            "genpkey",
            "-algorithm",
            "EC",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-out",
            str(key),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [_openssl(), "pkey", "-in", str(key), "-pubout", "-out", str(pub)],
        capture_output=True,
        check=True,
    )
    receipt = {
        "domain": AUDIT_DOMAIN,
        "repository_digest": candidate.repository_digest,
        "head": candidate.revision,
        "git_tree": git_tree,
        "tree": candidate.tree,
        "candidate_digest": candidate.digest,
        "manifest": manifest,
        "manifest_digest": manifest_digest(manifest),
        "validation_digest": "validation-digest",
        "verdict": "PASS",
        "auditor_id": "independent-auditor",
    }
    trust = root / ".agent" / "audit-trust.json"
    trust.parent.mkdir()
    trust.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "auditor_id": "independent-auditor",
                "public_key_sha256": public_key_fingerprint(pub),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    validation = root / ".agent" / "artifacts" / "FORGE-INTEGRATED-001" / "VALIDATION.json"
    validation.parent.mkdir(parents=True)
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
    subprocess.run(["git", "add", ".agent"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "audit material"], cwd=root, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    git_tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()
    manifest = tracked_manifest(root)
    candidate = CandidateIdentity(repository_digest(root), head, git_tree, packet_id)
    receipt.update(
        {
            "repository_digest": candidate.repository_digest,
            "head": head,
            "git_tree": git_tree,
            "tree": git_tree,
            "candidate_digest": candidate.digest,
            "manifest": manifest,
            "manifest_digest": manifest_digest(manifest),
            "validation_artifact": ".agent/artifacts/FORGE-INTEGRATED-001/VALIDATION.json",
            "validation_digest": hashlib.sha256(validation.read_bytes()).hexdigest(),
        }
    )
    receipt_path = tmp_path / "audit.json"
    sig_path = tmp_path / "audit.sig"
    receipt["signature_file"] = str(sig_path)
    receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    payload = tmp_path / "payload.json"
    payload.write_bytes(signed_payload(receipt))
    subprocess.run(
        [_openssl(), "dgst", "-sha256", "-sign", str(key), "-out", str(sig_path), str(payload)],
        check=True,
    )
    return root, candidate, receipt_path, pub


def test_valid_detached_audit_is_accepted(tmp_path):
    root, candidate, receipt, pub = _candidate(tmp_path)
    assert (
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)["verdict"]
        == "PASS"
    )


def test_valid_detached_audit_is_accepted_for_a_pending_slice_packet(tmp_path):
    """The receipt binds the supplied packet's exact clean Git candidate."""
    root, candidate, receipt, pub = _candidate(tmp_path, "FORGE-VAL-LF-001")
    assert candidate.packet_id == "FORGE-VAL-LF-001"
    assert (
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)["verdict"]
        == "PASS"
    )


@pytest.mark.parametrize("change", ["candidate_digest", "verdict", "auditor_id"])
def test_tampered_detached_receipt_is_rejected(tmp_path, change):
    root, candidate, receipt, pub = _candidate(tmp_path)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data[change] = "forged"
    receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)


def test_wrong_trust_anchor_is_rejected(tmp_path):
    root, candidate, receipt, pub = _candidate(tmp_path)
    other_key = tmp_path / "other.key"
    other_pub = tmp_path / "other.pub"
    subprocess.run(
        [
            _openssl(),
            "genpkey",
            "-algorithm",
            "EC",
            "-pkeyopt",
            "ec_paramgen_curve:P-256",
            "-out",
            str(other_key),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [_openssl(), "pkey", "-in", str(other_key), "-pubout", "-out", str(other_pub)],
        capture_output=True,
        check=True,
    )
    with pytest.raises(ForgeError):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=other_pub)


@pytest.mark.parametrize("mutate", ["omit", "validation", "origin", "trust"])
def test_complete_manifest_validation_origin_and_owner_fingerprint_are_required(tmp_path, mutate):
    root, candidate, receipt, pub = _candidate(tmp_path)
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if mutate == "omit":
        data["manifest"].pop("tracked.txt")
        data["manifest_digest"] = manifest_digest(data["manifest"])
    elif mutate == "validation":
        (root / ".agent" / "artifacts" / "FORGE-INTEGRATED-001" / "VALIDATION.json").write_text(
            "{}", encoding="utf-8"
        )
    elif mutate == "origin":
        subprocess.run(
            ["git", "remote", "set-url", "origin", "https://attacker.test/repo.git"],
            cwd=root,
            check=True,
        )
    else:
        trust = root / ".agent" / "audit-trust.json"
        payload = json.loads(trust.read_text(encoding="utf-8"))
        payload["public_key_sha256"] = "0" * 64
        trust.write_text(json.dumps(payload), encoding="utf-8")
    if mutate == "omit":
        receipt.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)


@pytest.mark.parametrize("mutation", ["missing", "extra", "boolean"])
def test_validation_artifact_requires_the_exact_documented_gate_set(tmp_path, mutation):
    root, candidate, receipt, pub = _candidate(tmp_path)
    validation = root / ".agent" / "artifacts" / "FORGE-INTEGRATED-001" / "VALIDATION.json"
    payload = json.loads(validation.read_text(encoding="utf-8"))
    gates = payload["pre_audit_gates"]
    if mutation == "missing":
        gates.pop("tests")
    elif mutation == "extra":
        gates["unexpected"] = 0
    else:
        gates["tests"] = False
    validation.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ForgeError):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)


def test_pre_audit_gate_set_derives_each_current_ledger_stream(tmp_path):
    ledger_root = tmp_path / ".agent" / "ledger"
    ledger_root.mkdir(parents=True)
    (ledger_root / "FORGE-X.jsonl").write_text("{}\n", encoding="utf-8")
    assert required_pre_audit_gates(tmp_path) == {
        "python floor",
        "import surface",
        "lint",
        "format",
        "tests",
        "doc/graph",
        "ledger FORGE-X",
        "self-improvement",
        "governed evolution",
    }


def test_manifest_uses_committed_bytes_across_checkout_line_endings(tmp_path):
    """A clean commit has one manifest even when checkouts materialize CRLF/LF."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "line.txt").write_bytes(b"one\ntwo\n")
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "audit@example.invalid"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "Audit"], cwd=source, check=True)
    subprocess.run(["git", "add", "line.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "line endings"], cwd=source, check=True)

    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    subprocess.run(["git", "clone", "-q", str(source), str(lf)], check=True)
    subprocess.run(["git", "clone", "-q", str(source), str(crlf)], check=True)
    subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=lf, check=True)
    subprocess.run(["git", "config", "core.autocrlf", "true"], cwd=crlf, check=True)
    (lf / "line.txt").unlink()
    (crlf / "line.txt").unlink()
    subprocess.run(
        ["git", "-c", "core.autocrlf=false", "checkout", "-q", "--force"], cwd=lf, check=True
    )
    subprocess.run(
        ["git", "-c", "core.autocrlf=true", "checkout", "-q", "--force"], cwd=crlf, check=True
    )

    assert (lf / "line.txt").read_bytes() != (crlf / "line.txt").read_bytes()
    assert tracked_manifest(lf) == tracked_manifest(crlf)


@pytest.mark.parametrize(
    "tree_entry",
    [
        b"120000 blob " + b"0" * 40 + b"\tlink",
        b"160000 commit " + b"0" * 40 + b"\tmodule",
        b"100644 blob\tmissing-metadata",
        b"100644 blob " + b"g" * 40 + b"\tbad-object",
    ],
)
def test_manifest_rejects_non_blob_or_malformed_committed_tree(tmp_path, monkeypatch, tree_entry):
    monkeypatch.setattr(audit_receipts, "_git_bytes", lambda root, *args: tree_entry + b"\0")
    with pytest.raises(ForgeError):
        tracked_manifest(tmp_path)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "./alias", "a//b", "a/../b"])
def test_manifest_rejects_non_relative_or_ambiguous_paths(tmp_path, monkeypatch, path):
    tree_entry = b"100644 blob " + b"0" * 40 + b"\t" + path.encode("utf-8")
    monkeypatch.setattr(audit_receipts, "_git_bytes", lambda root, *args: tree_entry + b"\0")
    with pytest.raises(ForgeError):
        tracked_manifest(tmp_path)


def test_candidate_change_during_manifest_generation_fails_closed(tmp_path, monkeypatch):
    root, candidate, receipt, pub = _candidate(tmp_path)
    original = audit_receipts.tracked_manifest
    changed = False

    def race(root, revision="HEAD"):
        nonlocal changed
        manifest = original(root, revision)
        if not changed:
            subprocess.run(
                ["git", "commit", "--allow-empty", "-qm", "audit race"], cwd=root, check=True
            )
            changed = True
        return manifest

    monkeypatch.setattr(audit_receipts, "tracked_manifest", race)
    with pytest.raises(ForgeError, match="changed during audit"):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)


def test_dirty_candidate_and_wrong_head_or_tree_fail_closed(tmp_path):
    root, candidate, receipt, pub = _candidate(tmp_path)
    (root / "untracked.txt").write_text("interrupted audit", encoding="utf-8")
    with pytest.raises(ForgeError, match="clean candidate"):
        verify_detached_audit(root, candidate, receipt_path=receipt, trust_anchor=pub)
    (root / "untracked.txt").unlink()
    wrong_head = CandidateIdentity(
        candidate.repository_digest, "0" * 40, candidate.tree, candidate.packet_id
    )
    wrong_tree = CandidateIdentity(
        candidate.repository_digest, candidate.revision, "0" * 40, candidate.packet_id
    )
    for altered in (wrong_head, wrong_tree):
        with pytest.raises(ForgeError, match="exact candidate"):
            verify_detached_audit(root, altered, receipt_path=receipt, trust_anchor=pub)


def test_missing_external_material_fails_closed(tmp_path, monkeypatch):
    root, candidate, receipt, pub = _candidate(tmp_path)
    monkeypatch.delenv("FORGE_AUDIT_RECEIPT", raising=False)
    monkeypatch.delenv("FORGE_AUDIT_PUBLIC_KEY", raising=False)
    with pytest.raises(ForgeError, match="TRUST_MISSING"):
        verify_detached_audit(root, candidate)


def test_missing_material_case_isolated_from_ambient_audit_environment(tmp_path, monkeypatch):
    """Full-gate signing material must not change this negative test's meaning."""
    root, candidate, receipt, pub = _candidate(tmp_path)
    monkeypatch.setenv("FORGE_AUDIT_RECEIPT", str(receipt))
    monkeypatch.setenv("FORGE_AUDIT_PUBLIC_KEY", str(pub))
    monkeypatch.delenv("FORGE_AUDIT_RECEIPT")
    monkeypatch.delenv("FORGE_AUDIT_PUBLIC_KEY")
    with pytest.raises(ForgeError, match="TRUST_MISSING"):
        verify_detached_audit(root, candidate)


def test_in_repository_trust_material_is_rejected(tmp_path):
    root, candidate, receipt, pub = _candidate(tmp_path)
    local_pub = root / "attacker.pub"
    local_receipt = root / "attacker.json"
    shutil.copyfile(pub, local_pub)
    shutil.copyfile(receipt, local_receipt)
    with pytest.raises(ForgeError, match="TRUST_INVALID"):
        verify_detached_audit(root, candidate, receipt_path=local_receipt, trust_anchor=local_pub)
