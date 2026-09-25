"""Adversarial checks for the retained Sentinel Phase 9 release packet."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from forge.ledger_store import LedgerStore
from forge.trust_kernel import ForgeError

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def prover():
    spec = importlib.util.spec_from_file_location(
        "prove_sentinel_release", ROOT / "scripts/prove_sentinel_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evidence(prover):
    return prover.prove()


def test_release_has_every_canonical_phase_9_field(evidence):
    assert evidence["finish_contract_evaluation"]["phase_9_release_fields_present"]
    assert (
        evidence["repository_identity"]["remote_merge_sha"]
        == "7c2f639232f231b0e6e748314bce487b452829e5"
    )
    assert (
        evidence["repository_identity"]["corrected_candidate_sha"]
        in evidence["repository_identity"]["remote_merge_parents"]
    )


def test_evolved_specification_is_bound_and_superseded_hash_refused(evidence):
    binding = evidence["specification_binding"]
    assert binding["evolved_packet_accepted"]
    assert binding["superseded_packet_refused"] == "SPECIFICATION_IDENTITY_MISMATCH"
    execution = binding["execution_receipt"]
    assert execution["kind"] == "CURRENT_POST_EVOLUTION_REVALIDATION"
    assert execution["specification_hash"] == evidence["evolved_specification_hash"]
    assert execution["candidate_sha"] == evidence["candidate_shas"]["corrected"]
    assert execution["exit_code"] == 0
    assert execution["output_digest"]


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda value: value.pop("audit_receipts"), "RELEASE_EVIDENCE_MISSING"),
        (
            lambda value: value["audit_receipts"].__setitem__(0, {"verdict": "FIX"}),
            "RELEASE_AUDIT_INVALID",
        ),
        (
            lambda value: value["specification_binding"].__setitem__(
                "superseded_packet_refused", "ACCEPTED"
            ),
            "SUPERSEDED_SPECIFICATION_ACCEPTED",
        ),
    ],
)
def test_missing_unaudited_and_superseded_evidence_fail_closed(prover, evidence, mutate, code):
    altered = copy.deepcopy(evidence)
    altered.pop("release_digest", None)
    altered.pop("ledger", None)
    mutate(altered)
    with pytest.raises(ForgeError) as error:
        prover.verify_release(altered, prover._ledger_for(altered))
    assert error.value.code == code


def test_reordered_and_mismatched_receipts_fail_closed(prover, evidence):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    ledger = prover._ledger_for(release)
    records = ledger.to_records()
    records[2], records[3] = records[3], records[2]
    from forge.trust_kernel import Ledger, LedgerCheckpoint

    with pytest.raises(ForgeError):
        Ledger.from_records(
            records,
            checkpoint=LedgerCheckpoint(
                len(records), records[-1]["receipt_hash"], prover.PACKET_ID
            ),
        )
    mismatched = copy.deepcopy(release)
    mismatched["candidate_shas"]["corrected"] = "0" * 40
    with pytest.raises(ForgeError) as error:
        prover.verify_release(mismatched, ledger)
    assert error.value.code in {"RELEASE_CANDIDATE_MISMATCH", "RELEASE_EXECUTION_MISMATCH"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["specification_binding"].pop("execution_receipt"),
        lambda value: value["specification_binding"]["execution_receipt"].__setitem__(
            "candidate_sha", "0" * 40
        ),
        lambda value: value["specification_binding"]["execution_receipt"].__setitem__(
            "specification_hash", "0" * 64
        ),
    ],
)
def test_missing_or_mismatched_execution_evidence_fails_closed(prover, evidence, mutate):
    release = {
        key: value
        for key, value in copy.deepcopy(evidence).items()
        if key not in {"release_digest", "ledger"}
    }
    ledger = prover._ledger_for(release)
    mutate(release)
    with pytest.raises(ForgeError) as error:
        prover.verify_release(release, ledger)
    assert error.value.code in {"RELEASE_EXECUTION_MISSING", "RELEASE_EXECUTION_MISMATCH"}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda execution: execution.pop("target_before"),
        lambda execution: execution["target_after"].__setitem__("head", "0" * 40),
        lambda execution: execution["packet_identity"].__setitem__("packet_id", "WRONG-PACKET"),
        lambda execution: execution["packet_identity"].__setitem__("base_tree", "0" * 40),
    ],
)
def test_execution_target_and_packet_identity_are_exactly_bound(prover, evidence, mutate):
    release = {
        key: value
        for key, value in copy.deepcopy(evidence).items()
        if key not in {"release_digest", "ledger", "restart"}
    }
    mutate(release["specification_binding"]["execution_receipt"])
    with pytest.raises(ForgeError) as error:
        prover.verify_release(release, prover._ledger_for(release))
    assert error.value.code == "RELEASE_EXECUTION_MISMATCH"


def test_repository_execution_target_cannot_be_rebound_with_execution(prover, evidence):
    release = {
        key: value
        for key, value in copy.deepcopy(evidence).items()
        if key not in {"release_digest", "ledger", "restart"}
    }
    for target in (
        release["repository_identity"]["execution_target"],
        release["specification_binding"]["execution_receipt"]["target_before"],
        release["specification_binding"]["execution_receipt"]["target_after"],
    ):
        target["target_path"] = "C:/forged-target"
    with pytest.raises(ForgeError) as error:
        prover.verify_release(release, prover._ledger_for(release))
    assert error.value.code == "RELEASE_EXECUTION_MISMATCH"


def test_persisted_stream_reloads_and_truncation_fails_closed(prover, evidence, tmp_path):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    store = LedgerStore(tmp_path, prover.PACKET_ID)
    store.write(prover._ledger_for(release))
    assert store.load().checkpoint.head_hash
    lines = store.receipts_path.read_text(encoding="utf-8").splitlines()
    store.receipts_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ForgeError) as error:
        store.load()
    assert error.value.code == "LEDGER_CHECKPOINT_MISMATCH"


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda value: value.__setitem__("discovery_records", []), "RELEASE_DISCOVERY_INVALID"),
        (
            lambda value: value.__setitem__("specification_patch_history", []),
            "RELEASE_SPECIFICATION_HISTORY_INVALID",
        ),
        (lambda value: value.__setitem__("restart_receipts", {}), "RELEASE_RESTART_INVALID"),
        (lambda value: value.__setitem__("merge_receipts", []), "RELEASE_MERGE_INVALID"),
        (lambda value: value.__setitem__("test_receipts", {}), "RELEASE_TEST_EVIDENCE_INVALID"),
    ],
)
def test_conflicting_release_sections_fail_even_with_fresh_chain(prover, evidence, mutate, code):
    release = {
        key: value
        for key, value in copy.deepcopy(evidence).items()
        if key not in {"release_digest", "ledger", "restart"}
    }
    mutate(release)
    with pytest.raises(ForgeError) as error:
        prover.verify_release(release, prover._ledger_for(release))
    assert error.value.code == code


@pytest.mark.parametrize(
    "section,field",
    [
        ("result", "path"),
        ("result", "digest"),
        ("packet", "path"),
        ("packet", "digest"),
        ("completion", "path"),
        ("completion", "digest"),
    ],
)
def test_pinned_historical_provenance_refuses_each_path_or_digest_change(
    prover, evidence, section, field
):
    release = {
        key: value
        for key, value in copy.deepcopy(evidence).items()
        if key not in {"release_digest", "ledger", "restart"}
    }
    release["historical_provenance"][section][field] = "changed"
    with pytest.raises(ForgeError) as error:
        prover.verify_release(release, prover._ledger_for(release))
    assert error.value.code == "RELEASE_PROVENANCE_INVALID"


def test_restart_reloads_prefix_then_continues_once(prover, evidence, tmp_path):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    prefix = prover._ledger_for(release, stop_after="EXECUTION")
    store = LedgerStore(tmp_path, prover.PACKET_ID)
    store.write(prefix)
    assert store.load().checkpoint == prefix.checkpoint
    full = prover._ledger_for(release)
    store.write(full)
    loaded = store.load()
    assert [receipt.event for receipt in loaded.receipts].count("EXECUTION") == 1
    assert loaded.checkpoint == full.checkpoint

    corrupt_root = tmp_path / "corrupt"
    corrupt_store = LedgerStore(corrupt_root, prover.PACKET_ID)
    corrupt_store.write(prefix)
    body = corrupt_store.receipts_path.read_text(encoding="utf-8")
    corrupt_store.receipts_path.write_text(body.replace("MISSION", "XISSION", 1), encoding="utf-8")
    with pytest.raises(ForgeError) as error:
        corrupt_store.load()
    assert error.value.code == "LEDGER_CORRUPT"


def test_resume_uses_authenticated_prefix_without_reexecuting(
    prover, evidence, tmp_path, monkeypatch
):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    store = LedgerStore(tmp_path / ".agent/ledger", prover.PACKET_ID)
    executions = []

    def release_after_one_execution(*_args, **_kwargs):
        executions.append("execution")
        return copy.deepcopy(release)

    original_write = prover.LedgerStore.write

    def interrupt_after_prefix(self, ledger):
        original_write(self, ledger)
        if len(ledger.receipts) == 7:
            raise RuntimeError("injected interruption after execution prefix")

    monkeypatch.setattr(prover, "_release", release_after_one_execution)
    monkeypatch.setattr(prover.LedgerStore, "write", interrupt_after_prefix)
    with pytest.raises(RuntimeError, match="injected interruption"):
        prover.prove(root=tmp_path, persist=True)
    artifact = tmp_path / ".agent/artifacts" / prover.PACKET_ID / "RELEASE.json"
    assert artifact.is_file()
    assert len(store.load().receipts) == 7
    prefix_bytes = store.receipts_path.read_bytes()
    monkeypatch.setattr(prover.LedgerStore, "write", original_write)
    result = prover.prove(root=tmp_path, persist=True)
    loaded = store.load()
    assert store.receipts_path.read_bytes().startswith(prefix_bytes)
    assert len(loaded.receipts) == 14
    assert [receipt.event for receipt in loaded.receipts].count("EXECUTION") == 1
    assert result["ledger"]["head_hash"] == loaded.checkpoint.head_hash
    assert executions == ["execution"]
    assert "restart" in json.loads(artifact.read_text(encoding="utf-8"))


def test_forged_execution_checkpoint_refuses_resume(prover, evidence, tmp_path):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    store = LedgerStore(tmp_path, prover.PACKET_ID)
    prefix = prover._ledger_for(release, stop_after="EXECUTION")
    store.write(prefix)
    checkpoint = json.loads(store.checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["head_hash"] = "0" * 64
    store.checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    with pytest.raises(ForgeError):
        prover._persist_release(release, store)


def test_completed_stream_returns_without_effect(prover, evidence, tmp_path, monkeypatch):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    store = LedgerStore(tmp_path / ".agent/ledger", prover.PACKET_ID)
    store.write(prover._ledger_for(release))
    artifact = tmp_path / ".agent/artifacts" / prover.PACKET_ID / "RELEASE.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(evidence), encoding="utf-8")
    monkeypatch.setattr(
        prover, "_release", lambda *args, **kwargs: pytest.fail("effect was invoked")
    )
    result = prover.prove(root=tmp_path, persist=True)
    loaded = store.load()
    assert len(loaded.receipts) == 14
    assert result["ledger"]["head_hash"] == loaded.checkpoint.head_hash


def test_interrupted_prefix_without_bound_artifact_fails_before_execution(
    prover, evidence, tmp_path, monkeypatch
):
    release = {
        key: value for key, value in evidence.items() if key not in {"release_digest", "ledger"}
    }
    store = LedgerStore(tmp_path / ".agent/ledger", prover.PACKET_ID)
    store.write(prover._ledger_for(release, stop_after="EXECUTION"))
    monkeypatch.setattr(
        prover, "_release", lambda *args, **kwargs: pytest.fail("effect was invoked")
    )
    with pytest.raises(ForgeError) as error:
        prover.prove(root=tmp_path, persist=True)
    assert error.value.code == "RELEASE_RECOVERY_ARTIFACT_MISSING"


@pytest.mark.parametrize("mode", ["alternate", "dirty"])
def test_target_identity_refuses_alternate_or_dirty_target(prover, monkeypatch, tmp_path, mode):
    target = tmp_path / "target"
    target.mkdir()
    values = {
        ("remote", "get-url", "origin"): "https://github.com/nrsandoval1231-oss/sentinal.git",
        ("rev-parse", "HEAD"): prover.CORRECTED,
        ("rev-parse", f"{prover.CORRECTED}^{{tree}} "): "tree",
        ("rev-parse", "HEAD^{tree}"): prover.CORRECTED_TREE,
        ("status", "--porcelain"): "",
    }
    if mode == "alternate":
        values[("remote", "get-url", "origin")] = "https://example.invalid/other.git"
    else:
        values[("status", "--porcelain")] = " M tests/test_ci_local.py"

    def fake_git(_target, *args):
        key = args
        if key == ("rev-parse", f"{prover.CORRECTED}^{{tree}}"):
            return prover.CORRECTED_TREE
        return values[key]

    monkeypatch.setattr(prover, "_git", fake_git)
    with pytest.raises(ForgeError) as error:
        prover._target_identity(target)
    assert error.value.code in {"SENTINEL_REPOSITORY_MISMATCH", "SENTINEL_WORKTREE_DIRTY"}


def test_execution_refuses_target_mutation(prover, monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"
    executable.write_text("", encoding="utf-8")
    identities = iter(
        [
            {"target_path": "target", "origin": "origin", "head": prover.CORRECTED, "tree": "one"},
            {"target_path": "target", "origin": "origin", "head": prover.CORRECTED, "tree": "two"},
        ]
    )
    monkeypatch.setattr(prover, "SENTINEL_VENV_PYTHON", executable)
    monkeypatch.setattr(prover, "_target_identity", lambda _target: next(identities))
    monkeypatch.setattr(
        prover.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="17 passed", stderr=""),
    )
    with pytest.raises(ForgeError) as error:
        prover._execute_evolved_packet("spec", tmp_path, {"packet_id": "P"})
    assert error.value.code == "SENTINEL_EXECUTION_TARGET_MUTATED"


def test_retained_release_is_fresh_and_reloadable(prover):
    assert prover.main(["--check"]) == 0


def test_real_learning_episode_is_separate_from_simulated_rollback(evidence):
    episode = __import__("json").loads(
        (ROOT / ".agent/artifacts/FORGE-SI-001/REAL_EPISODE.json").read_text(encoding="utf-8")
    )
    assert episode["kind"] == "REAL_LEARNING_EPISODE"
    assert episode["metric"]["baseline"] == 1.0
    assert episode["metric"]["observed"] == 0.0
    assert episode["lesson_digest"] == evidence["lesson_candidates"][0]["lesson_digest"]
    assert (ROOT / ".agent/artifacts/FORGE-SI-001/PROOF.json").is_file()
