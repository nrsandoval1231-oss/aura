"""Role contexts in the real harness (FORGE-INT-001).

Audit F15 found the Context Engine among roughly 1,760 lines that
`execution_loop.py` did not import. Its independence properties were real but were
properties of a library nothing called. These tests exercise the harness's own
assembly, so the guarantee belongs to the run that produces candidate evidence.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from forge import Authority
from forge.context_engine import ROLE_POLICY, AgentRole, SourceType
from forge.ledger_store import LedgerStore
from forge.trust_kernel import CandidateIdentity, ForgeError, Ledger, Receipt

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def slicer():
    spec = importlib.util.spec_from_file_location("run_slice", ROOT / "scripts" / "run_slice.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# The two independence properties, checked on the harness's own assembly
# ---------------------------------------------------------------------------


def test_the_builder_policy_forbids_every_specification_source():
    """A Builder cannot be given the specification — structurally, not by prompt."""
    builder = ROLE_POLICY[AgentRole.BUILDER]
    for source in (SourceType.NORTH_STAR, SourceType.DECISION, SourceType.ASSUMPTION):
        assert source not in builder


def test_the_auditor_policy_forbids_builder_reasoning():
    assert SourceType.BUILDER_REASONING not in ROLE_POLICY[AgentRole.AUDITOR]


def test_no_role_may_receive_builder_reasoning_except_by_explicit_decision():
    """The allow-list direction: a new source type reaches nobody until someone says so."""
    for role, allowed in ROLE_POLICY.items():
        if role is AgentRole.BUILDER:
            continue
        assert SourceType.BUILDER_REASONING not in allowed, role


# ---------------------------------------------------------------------------
# The harness actually calls the assembler
# ---------------------------------------------------------------------------


def test_the_slice_assembles_contexts_through_the_context_engine(slicer):
    """F15: the seam exists in the harness, not only in the library."""
    import inspect

    source = inspect.getsource(slicer.assemble_role_contexts)
    assert "ContextAssembler()" in source
    assert "AgentRole.ARCHITECT" in source
    assert "AgentRole.BUILDER" in source
    assert "AgentRole.AUDITOR" in source


def test_the_slice_drives_the_loop_with_a_governor_owned_budget(slicer):
    import inspect

    source = inspect.getsource(slicer.main)
    assert "BudgetLedger(" in source
    assert "budget_ledger=governor_budget" in source


def test_the_builder_item_list_contains_no_specification_source(slicer):
    """Written per role rather than filtered, so the guarantee is not in a filter."""
    import inspect

    source = inspect.getsource(slicer.assemble_role_contexts)
    builder_block = source.split('"builder": assembler.assemble(')[1].split('"auditor"')[0]
    for forbidden in ("SourceType.NORTH_STAR", "SourceType.DECISION", "SourceType.ASSUMPTION"):
        assert forbidden not in builder_block


def test_canonical_sources_are_not_flattened_to_the_default_authority(slicer):
    import inspect

    source = inspect.getsource(slicer.assemble_role_contexts)
    assert "authority=Authority.A3" in source
    assert Authority.A3.value == "A3"


def test_pending_audit_packets_are_default_binding_targets(slicer, tmp_path, monkeypatch):
    """AWAITING_AUDIT remains an active candidate until independent review."""
    (tmp_path / ".agent" / "tasks").mkdir(parents=True)
    (tmp_path / ".agent" / "graph").mkdir(parents=True)
    (tmp_path / ".agent" / "graph" / "work-graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "PENDING",
                        "status": "AWAITING_AUDIT",
                        "packet": ".agent/tasks/PENDING.md",
                    },
                    {"id": "COMPLETE", "status": "COMPLETE", "packet": ".agent/tasks/COMPLETE.md"},
                    {"id": "READY", "status": "READY", "packet": ".agent/tasks/READY.md"},
                ]
            }
        ),
        encoding="utf-8",
    )
    for packet_id in ("PENDING", "COMPLETE", "READY"):
        (tmp_path / ".agent" / "tasks" / f"{packet_id}.md").write_text("packet", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "TASKS", tmp_path / ".agent" / "tasks")
    assert slicer.active_packet_ids() == ("PENDING", "READY")


def test_active_packet_reference_is_fail_closed_when_missing(slicer, tmp_path, monkeypatch):
    (tmp_path / ".agent" / "graph").mkdir(parents=True)
    (tmp_path / ".agent" / "graph" / "work-graph.json").write_text(
        json.dumps({"nodes": [{"id": "PENDING", "status": "AWAITING_AUDIT"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "TASKS", tmp_path / ".agent" / "tasks")
    with pytest.raises(SystemExit, match="no packet reference"):
        slicer.active_packet_ids()


def test_pending_candidate_mutation_is_rejected_even_when_tree_is_unchanged(
    slicer, tmp_path, monkeypatch, capsys
):
    """Retained SLICE metadata cannot be edited around the ledger candidate."""
    artifact_root = tmp_path / "artifacts" / "PENDING"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("PENDING", "test", ("source.py",))
    tree = slicer.tree_hash(packet.allowed_paths)
    candidate = CandidateIdentity("repo", "rev+worktree", tree, packet.id)
    evidence = {
        "candidate_digest": "forged",
        "candidate_tree": tree,
        "audit": {"bound_to_candidate": True},
        "merge_eligibility": {"candidate_digest": candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    loaded = SimpleNamespace(
        receipts=(
            SimpleNamespace(
                event="CANDIDATE_REGISTERED",
                payload={"handoff": {"candidate": dataclasses.asdict(candidate)}},
            ),
        ),
        checkpoint=SimpleNamespace(head_hash="head"),
        verify=lambda: None,
    )
    store = SimpleNamespace(load=lambda: loaded)
    assert slicer.check_recorded_evidence(store, packet) == 1
    assert "candidate binding mismatch" in capsys.readouterr().err.lower()


def test_pending_candidate_requires_audit_and_eligibility_receipts(
    slicer, tmp_path, monkeypatch, capsys
):
    artifact_root = tmp_path / "artifacts" / "PENDING"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("PENDING", "test", ("source.py",))
    tree = slicer.tree_hash(packet.allowed_paths)
    candidate = CandidateIdentity("repo", "rev+worktree", tree, packet.id)
    evidence = {
        "candidate_digest": candidate.digest,
        "candidate_tree": tree,
        "audit": {"bound_to_candidate": True},
        "merge_eligibility": {"candidate_digest": candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    candidate_receipt = SimpleNamespace(
        event="CANDIDATE_REGISTERED",
        payload={"handoff": {"candidate": dataclasses.asdict(candidate)}},
    )
    audit_receipt = SimpleNamespace(
        event="AUDIT_RECORDED", payload={"candidate_digest": candidate.digest}
    )
    loaded = SimpleNamespace(
        receipts=(candidate_receipt,),
        checkpoint=SimpleNamespace(head_hash="head"),
        verify=lambda: None,
    )
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 1
    assert "audit_recorded" in capsys.readouterr().err.lower()
    loaded.receipts = (candidate_receipt, audit_receipt)
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 1
    assert "merge_eligibility_granted" in capsys.readouterr().err.lower()


def test_local_simulated_audit_cannot_make_successor_green(slicer, tmp_path, monkeypatch, capsys):
    """A local AuditReport(PASS) is not independent approval."""
    artifact_root = tmp_path / "artifacts" / "SUCCESSOR"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("SUCCESSOR", "test", ("source.py",))
    tree = slicer.tree_hash(packet.allowed_paths)
    candidate = CandidateIdentity("repo", "rev+worktree", tree, packet.id)
    evidence = {
        "candidate_digest": candidate.digest,
        "candidate_tree": tree,
        "audit": {"bound_to_candidate": True},
        "merge_eligibility": {"candidate_digest": candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    candidate_receipt = SimpleNamespace(
        event="CANDIDATE_REGISTERED",
        payload={"handoff": {"candidate": dataclasses.asdict(candidate)}},
    )
    audit_receipt = SimpleNamespace(
        event="AUDIT_RECORDED", payload={"candidate_digest": candidate.digest}
    )
    eligibility_receipt = SimpleNamespace(
        event="MERGE_ELIGIBILITY_GRANTED", payload={"candidate_digest": candidate.digest}
    )
    loaded = SimpleNamespace(
        receipts=(candidate_receipt, audit_receipt, eligibility_receipt),
        checkpoint=SimpleNamespace(head_hash="head"),
        verify=lambda: None,
    )
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 1
    assert "external audit" in capsys.readouterr().err.lower()


def test_pending_slice_uses_an_exact_commit_for_external_audit(slicer, tmp_path, monkeypatch):
    """Regression: a pre-commit ``HEAD+worktree`` receipt cannot be signed.

    The persisted slice candidate remains the evidence identity for its ledger and
    selected-file hash.  Its external authorization must instead bind the clean
    committed candidate that the detached verifier is designed to validate.
    """
    artifact_root = tmp_path / "artifacts" / "PENDING"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("PENDING", "test", ("source.py",))
    selected_tree = slicer.tree_hash(packet.allowed_paths)
    worktree_candidate = CandidateIdentity("repo", "base+worktree", selected_tree, packet.id)
    committed_candidate = CandidateIdentity("repo", "c" * 40, "d" * 40, packet.id)
    evidence = {
        "candidate_digest": worktree_candidate.digest,
        "candidate_tree": selected_tree,
        "audit": {"bound_to_candidate": True},
        "merge_eligibility": {"candidate_digest": worktree_candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    loaded = SimpleNamespace(
        receipts=(
            SimpleNamespace(
                event="CANDIDATE_REGISTERED",
                payload={"handoff": {"candidate": dataclasses.asdict(worktree_candidate)}},
            ),
            SimpleNamespace(
                event="AUDIT_RECORDED", payload={"candidate_digest": worktree_candidate.digest}
            ),
            SimpleNamespace(
                event="MERGE_ELIGIBILITY_GRANTED",
                payload={"candidate_digest": worktree_candidate.digest},
            ),
        ),
        checkpoint=SimpleNamespace(head_hash="head", sequence=3),
        verify=lambda: None,
    )
    monkeypatch.setattr(slicer, "exact_candidate", lambda root, packet_id: committed_candidate)

    def verify_only_the_exact_commit(root, candidate):
        if candidate != committed_candidate:
            raise ForgeError("AUDIT_CANDIDATE_MISMATCH", "wrong detached-audit candidate")
        return {"auditor_id": "independent"}

    monkeypatch.setattr(slicer, "verify_detached_audit", verify_only_the_exact_commit)
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 0


@pytest.mark.parametrize("mutation", ["selected_file", "checkpoint"])
def test_pending_slice_rejects_stale_local_evidence_before_detached_audit(
    slicer, tmp_path, monkeypatch, capsys, mutation
):
    """An exact external receipt cannot override stale local ledger evidence."""
    artifact_root = tmp_path / "artifacts" / "PENDING"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("approved\n", encoding="utf-8")
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("PENDING", "test", ("source.py",))
    selected_tree = slicer.tree_hash(packet.allowed_paths)
    candidate = CandidateIdentity("repo", "base+worktree", selected_tree, packet.id)
    evidence = {
        "candidate_digest": candidate.digest,
        "candidate_tree": selected_tree,
        "audit": {"bound_to_candidate": True},
        "merge_eligibility": {"candidate_digest": candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    if mutation == "selected_file":
        source.write_text("mutated\n", encoding="utf-8")
        checkpoint = SimpleNamespace(head_hash="head", sequence=3)
    else:
        checkpoint = SimpleNamespace(head_hash="stale", sequence=3)
    loaded = SimpleNamespace(
        receipts=(
            SimpleNamespace(
                event="CANDIDATE_REGISTERED",
                payload={"handoff": {"candidate": dataclasses.asdict(candidate)}},
            ),
            SimpleNamespace(event="AUDIT_RECORDED", payload={"candidate_digest": candidate.digest}),
            SimpleNamespace(
                event="MERGE_ELIGIBILITY_GRANTED", payload={"candidate_digest": candidate.digest}
            ),
        ),
        checkpoint=checkpoint,
        verify=lambda: None,
    )
    monkeypatch.setattr(
        slicer,
        "verify_detached_audit",
        lambda *args: pytest.fail("stale local evidence must block before external audit"),
    )
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 1
    assert (
        "audited files have changed"
        if mutation == "selected_file"
        else "ledger head does not match"
    ) in capsys.readouterr().err.lower()


def test_forged_external_audit_claim_cannot_make_successor_green(
    slicer, tmp_path, monkeypatch, capsys
):
    """A matching JSON claim is still untrusted without external key custody."""
    artifact_root = tmp_path / "artifacts" / "SUCCESSOR"
    artifact_root.mkdir(parents=True)
    source = tmp_path / "source.py"
    source.write_text("pass\n", encoding="utf-8")
    audit_path = tmp_path / ".agent" / "external-audit.json"
    audit_path.parent.mkdir(parents=True)
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "ARTIFACT_ROOT", tmp_path / "artifacts")
    packet = slicer.Packet("SUCCESSOR", "test", ("source.py",))
    tree = slicer.tree_hash(packet.allowed_paths)
    candidate = CandidateIdentity("repo", "rev+worktree", tree, packet.id)
    audit_path.write_text(
        json.dumps(
            {
                "verdict": "PASS",
                "candidate_digest": candidate.digest,
                "candidate_tree": tree,
                "auditor_id": "attacker",
                "evidence_digest": "forged",
                "trust_status": "EXTERNAL_REVIEW_PENDING_SOL_VERIFICATION",
            }
        ),
        encoding="utf-8",
    )
    evidence = {
        "candidate_digest": candidate.digest,
        "candidate_tree": tree,
        "audit": {
            "bound_to_candidate": True,
            "external_audit_artifact": ".agent/external-audit.json",
        },
        "merge_eligibility": {"candidate_digest": candidate.digest},
        "changed_paths": ["source.py"],
        "ledger": {"head_hash": "head"},
    }
    (artifact_root / "SLICE.json").write_text(json.dumps(evidence), encoding="utf-8")
    receipts = (
        SimpleNamespace(
            event="CANDIDATE_REGISTERED",
            payload={"handoff": {"candidate": dataclasses.asdict(candidate)}},
        ),
        SimpleNamespace(event="AUDIT_RECORDED", payload={"candidate_digest": candidate.digest}),
        SimpleNamespace(
            event="MERGE_ELIGIBILITY_GRANTED", payload={"candidate_digest": candidate.digest}
        ),
    )
    loaded = SimpleNamespace(
        receipts=receipts,
        checkpoint=SimpleNamespace(head_hash="head"),
        verify=lambda: None,
    )
    assert slicer.check_recorded_evidence(SimpleNamespace(load=lambda: loaded), packet) == 1
    assert "external audit" in capsys.readouterr().err.lower()


def test_integrated_successor_uses_detached_audit_without_generic_slice_evidence(
    slicer, monkeypatch, capsys
):
    """The successor's trust path is deliberately disjoint from simulated receipts."""
    candidate = CandidateIdentity("repo", "a" * 40, "b" * 40, "FORGE-INTEGRATED-001")
    calls: list[str] = []

    monkeypatch.setattr(slicer, "exact_candidate", lambda root, packet_id: candidate)
    monkeypatch.setattr(
        slicer,
        "verify_detached_audit",
        lambda root, bound: calls.append("audit") or {"auditor_id": "detached"},
    )

    assert slicer.check_integrated_audit() == 0
    assert calls == ["audit"]
    assert "detached pass" in capsys.readouterr().out.lower()


def test_check_orders_reconciliation_before_integrated_detached_audit(
    slicer, monkeypatch, tmp_path
):
    graph = tmp_path / ".agent" / "graph"
    graph.mkdir(parents=True)
    (graph / "work-graph.json").write_text('{"nodes": [{"id": "OLD", "status": "REDIRECTED"}]}')
    monkeypatch.setattr(slicer, "ROOT", tmp_path)
    monkeypatch.setattr(slicer, "git", lambda *args: "test-identity")
    candidate = CandidateIdentity("repo", "a" * 40, "b" * 40, "FORGE-INTEGRATED-001")
    calls: list[str] = []
    monkeypatch.setattr(slicer, "verify_reconciliation_records", lambda: calls.append("evid"))
    monkeypatch.setattr(slicer, "exact_candidate", lambda root, packet_id: candidate)
    monkeypatch.setattr(
        slicer,
        "verify_detached_audit",
        lambda root, bound: calls.append("audit") or {"auditor_id": "detached"},
    )
    assert slicer.main(["--check", "--packet", "FORGE-INTEGRATED-001"]) == 0
    assert calls == ["evid", "audit"]


def _reconciliation_fixture(tmp_path, packet_id="OLD"):
    ledger_root = tmp_path / ".agent" / "ledger"
    old_store = LedgerStore(ledger_root, packet_id)
    old_ledger = Ledger(stream_id=packet_id)
    candidate = CandidateIdentity("repo", "revision", "tree", packet_id)
    first = Receipt.create(
        1,
        "CANDIDATE_REGISTERED",
        None,
        None,
        {"handoff": {"candidate": dataclasses.asdict(candidate)}},
        None,
    )
    old_ledger.append(first)
    old_ledger.append(Receipt.create(2, "EVENT", None, None, {"ok": True}, first.receipt_hash))
    old_store.write(old_ledger)
    artifact = tmp_path / ".agent" / "artifacts" / packet_id
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "SLICE.json").write_text(
        json.dumps(
            {
                "candidate_digest": candidate.digest,
                "ledger": {"head_hash": old_ledger.checkpoint.head_hash},
            }
        ),
        encoding="utf-8",
    )
    graph_root = tmp_path / ".agent" / "graph"
    graph_root.mkdir(parents=True, exist_ok=True)
    (graph_root / "work-graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": packet_id,
                        "status": "REDIRECTED",
                        "packet": f".agent/tasks/{packet_id}.md",
                        "redirected_to": "FORGE-INTEGRATED-001",
                    },
                    {"id": "FORGE-INTEGRATED-001", "status": "PROPOSED"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return old_ledger


def _write_reconciliation(tmp_path, payloads, stream_id="FORGE-EVID-003"):
    ledger_root = tmp_path / ".agent" / "ledger"
    reconciliation = Ledger(stream_id=stream_id)
    previous = None
    for sequence, payload in enumerate(payloads, 1):
        receipt = Receipt.create(sequence, "RECONCILIATION_RECORDED", None, None, payload, previous)
        reconciliation.append(receipt)
        previous = receipt.receipt_hash
    LedgerStore(ledger_root, stream_id).write(reconciliation)


def _present_reconciliation(old_ledger, **overrides):
    old_candidate = old_ledger.receipts[0].payload["handoff"]["candidate"]
    packet_id = overrides.get("packet_id", "OLD")
    payload = {
        "packet_id": "OLD",
        "status": "REDIRECTED",
        "evidence_class": "FULL_SLICE_AND_LEDGER",
        "old_candidate_digest": CandidateIdentity(**old_candidate).digest,
        "old_ledger_head": old_ledger.checkpoint.head_hash,
        "reason": "integrated tree changed",
        "successor_packet_id": "FORGE-INTEGRATED-001",
        "slice_path": f".agent/artifacts/{packet_id}/SLICE.json",
        "old_ledger_stream": packet_id,
    }
    payload.update(overrides)
    return payload


def test_reconciliation_requires_a_persisted_record(slicer, tmp_path):
    with pytest.raises(ForgeError, match="No persisted reconciliation ledger stream") as exc:
        slicer.verify_reconciliation_records(tmp_path)
    assert exc.value.code == "LEDGER_NOT_FOUND"


def test_reconciliation_verifies_old_candidate_and_checkpoint(slicer, tmp_path):
    valid_root = tmp_path / "valid"
    old_valid = _reconciliation_fixture(valid_root)
    _write_reconciliation(valid_root, [_present_reconciliation(old_valid)])
    assert slicer.verify_reconciliation_records(valid_root) == ("OLD",)
    wrong_root = tmp_path / "wrong"
    old_wrong = _reconciliation_fixture(wrong_root)
    _write_reconciliation(
        wrong_root, [_present_reconciliation(old_wrong, old_candidate_digest="wrong")]
    )
    with pytest.raises(SystemExit, match="identity mismatch"):
        slicer.verify_reconciliation_records(wrong_root)
    head_root = tmp_path / "head"
    old_head = _reconciliation_fixture(head_root)
    _write_reconciliation(head_root, [_present_reconciliation(old_head, old_ledger_head="wrong")])
    with pytest.raises(SystemExit, match="identity mismatch"):
        slicer.verify_reconciliation_records(head_root)


def test_reconciliation_rejects_duplicates_and_truncated_checkpoint(slicer, tmp_path):
    duplicate_root = tmp_path / "duplicate"
    old_duplicate = _reconciliation_fixture(duplicate_root)
    payload = _present_reconciliation(old_duplicate)
    _write_reconciliation(duplicate_root, [payload, payload])
    with pytest.raises(SystemExit, match="duplicate"):
        slicer.verify_reconciliation_records(duplicate_root)

    truncated_root = tmp_path / "truncated"
    old_truncated = _reconciliation_fixture(truncated_root)
    _write_reconciliation(truncated_root, [_present_reconciliation(old_truncated)])
    stream = truncated_root / ".agent" / "ledger" / "FORGE-EVID-003.jsonl"
    stream.write_bytes(stream.read_bytes()[:-100])
    with pytest.raises(ForgeError):
        slicer.verify_reconciliation_records(truncated_root)


def test_reconciliation_rejects_false_absence_and_cross_packet_paths(slicer, tmp_path):
    absent_root = tmp_path / "false-absent"
    _reconciliation_fixture(absent_root)
    artifact = absent_root / ".agent" / "artifacts" / "OLD"
    artifact.mkdir(parents=True, exist_ok=True)
    (artifact / "SLICE.json").write_text("{}", encoding="utf-8")
    payload = {
        "packet_id": "OLD",
        "status": "REDIRECTED",
        "evidence_class": "NO_LEGACY_EVIDENCE",
        "reason": "missing",
        "successor_packet_id": "FORGE-INTEGRATED-001",
    }
    _write_reconciliation(absent_root, [payload])
    with pytest.raises(SystemExit, match="No-evidence"):
        slicer.verify_reconciliation_records(absent_root)

    cross_root = tmp_path / "cross-packet"
    old = _reconciliation_fixture(cross_root)
    _write_reconciliation(
        cross_root,
        [
            _present_reconciliation(
                old, old_ledger_stream="OTHER", slice_path=".agent/artifacts/OTHER/SLICE.json"
            )
        ],
    )
    with pytest.raises(SystemExit, match="Legacy ledger path"):
        slicer.verify_reconciliation_records(cross_root)


def test_reconciliation_rejects_unrelated_events_and_false_ledger_only(slicer, tmp_path):
    extra_root = tmp_path / "extra-event"
    old = _reconciliation_fixture(extra_root)
    ledger_root = extra_root / ".agent" / "ledger"
    reconciliation = Ledger(stream_id="FORGE-EVID-003")
    payload = _present_reconciliation(old)
    first = Receipt.create(1, "RECONCILIATION_RECORDED", None, None, payload, None)
    reconciliation.append(first)
    reconciliation.append(Receipt.create(2, "UNRELATED", None, None, {}, first.receipt_hash))
    LedgerStore(ledger_root, "FORGE-EVID-003").write(reconciliation)
    with pytest.raises(SystemExit, match="unrelated event"):
        slicer.verify_reconciliation_records(extra_root)

    ledger_only_root = tmp_path / "false-ledger-only"
    old = _reconciliation_fixture(ledger_only_root)
    _write_reconciliation(
        ledger_only_root,
        [_present_reconciliation(old, evidence_class="LEDGER_ONLY", old_candidate_digest=None)],
    )
    with pytest.raises(SystemExit, match="Ledger-only evidence has a retained slice"):
        slicer.verify_reconciliation_records(ledger_only_root)


def test_reconciliation_requires_exact_graph_packet_set_and_successor(slicer, tmp_path):
    root = tmp_path / "graph-mismatch"
    old = _reconciliation_fixture(root)
    graph = root / ".agent" / "graph"
    graph.mkdir(parents=True, exist_ok=True)
    (graph / "work-graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "OLD",
                        "status": "REDIRECTED",
                        "packet": ".agent/tasks/OLD.md",
                        "redirected_to": "FORGE-INTEGRATED-001",
                    },
                    {
                        "id": "MISSING",
                        "status": "REDIRECTED",
                        "packet": ".agent/tasks/MISSING.md",
                        "redirected_to": "FORGE-INTEGRATED-001",
                    },
                    {"id": "FORGE-INTEGRATED-001", "status": "PROPOSED"},
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_reconciliation(root, [_present_reconciliation(old)])
    with pytest.raises(SystemExit, match="lack reconciliation records"):
        slicer.verify_reconciliation_records(root)

    wrong_successor = tmp_path / "wrong-successor"
    old = _reconciliation_fixture(wrong_successor)
    _write_reconciliation(
        wrong_successor,
        [_present_reconciliation(old, successor_packet_id="OTHER")],
    )
    with pytest.raises(SystemExit, match="successor mismatch"):
        slicer.verify_reconciliation_records(wrong_successor)


def test_reconciliation_accepts_explicit_per_node_successors(slicer, tmp_path):
    root = tmp_path / "multiple-successors"
    old = _reconciliation_fixture(root)
    second = _reconciliation_fixture(root, "SECOND")
    graph = root / ".agent" / "graph" / "work-graph.json"
    graph.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "OLD",
                        "status": "REDIRECTED",
                        "packet": ".agent/tasks/OLD.md",
                        "redirected_to": "FORGE-INTEGRATED-001",
                    },
                    {
                        "id": "SECOND",
                        "status": "REDIRECTED",
                        "packet": ".agent/tasks/SECOND.md",
                        "redirected_to": "FORGE-EXT-003",
                    },
                    {"id": "FORGE-INTEGRATED-001", "status": "COMPLETE"},
                    {"id": "FORGE-EXT-003", "status": "COMPLETE"},
                ]
            }
        ),
        encoding="utf-8",
    )
    second_payload = _present_reconciliation(
        second,
        packet_id="SECOND",
        successor_packet_id="FORGE-EXT-003",
        old_ledger_stream="SECOND",
        slice_path=".agent/artifacts/SECOND/SLICE.json",
    )
    _write_reconciliation(root, [_present_reconciliation(old), second_payload])
    assert slicer.verify_reconciliation_records(root) == ("OLD", "SECOND")


@pytest.mark.parametrize(
    ("graph_node", "expected"),
    [
        ({}, "lacks successor binding"),
        ({"redirected_to": "MISSING"}, "successor is not a graph node"),
        ({"redirected_to": "OLD"}, "self-loops"),
        ({"packet": ""}, "invalid packet binding"),
    ],
)
def test_reconciliation_rejects_invalid_redirect_graph_bindings(
    slicer, tmp_path, graph_node, expected
):
    root = tmp_path / expected.replace(" ", "-")
    old = _reconciliation_fixture(root)
    graph_path = root / ".agent" / "graph" / "work-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"][0].update(graph_node)
    if graph_node == {}:
        graph["nodes"][0].pop("redirected_to")
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    _write_reconciliation(root, [_present_reconciliation(old)])
    with pytest.raises(SystemExit, match=expected):
        slicer.verify_reconciliation_records(root)


def test_reconciliation_accepts_shared_packet_redirect_nodes(slicer, tmp_path):
    root = tmp_path / "shared-packet"
    old = _reconciliation_fixture(root)
    graph_path = root / ".agent" / "graph" / "work-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].insert(
        1,
        {
            "id": "OLD-SATELLITE",
            "status": "REDIRECTED",
            "packet": ".agent/tasks/OLD.md",
            "redirected_to": "FORGE-INTEGRATED-001",
        },
    )
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    _write_reconciliation(root, [_present_reconciliation(old)])
    assert slicer.verify_reconciliation_records(root) == ("OLD",)


def test_reconciliation_rejects_conflicting_shared_packet_successors(slicer, tmp_path):
    root = tmp_path / "shared-packet-conflict"
    old = _reconciliation_fixture(root)
    graph_path = root / ".agent" / "graph" / "work-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].extend(
        [
            {
                "id": "OLD-SATELLITE",
                "status": "REDIRECTED",
                "packet": ".agent/tasks/OLD.md",
                "redirected_to": "FORGE-EXT-003",
            },
            {"id": "FORGE-EXT-003", "status": "COMPLETE"},
        ]
    )
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    _write_reconciliation(root, [_present_reconciliation(old)])
    with pytest.raises(SystemExit, match="conflicting successor bindings"):
        slicer.verify_reconciliation_records(root)


def _no_legacy_record(packet_id, successor="AURA-INTEGRATED-002"):
    return {
        "packet_id": packet_id,
        "status": "REDIRECTED",
        "evidence_class": "NO_LEGACY_EVIDENCE",
        "reason": "no canonical SLICE.json or core ledger exists",
        "successor_packet_id": successor,
    }


def _write_aura_reconciliation(root, payloads):
    return _write_reconciliation(root, payloads, stream_id="AURA-EVID-001")


def test_reconciliation_verifies_union_without_rewriting_forge_stream(slicer, tmp_path):
    root = tmp_path / "two-stream-union"
    old = _reconciliation_fixture(root)
    graph_nodes = [
        {
            "id": "OLD",
            "status": "REDIRECTED",
            "packet": ".agent/tasks/OLD.md",
            "redirected_to": "FORGE-INTEGRATED-001",
        },
        {"id": "FORGE-INTEGRATED-001", "status": "PROPOSED"},
    ]
    for packet_id in ("FORGE-ADAPT-001", "AURA-MIG-001", "AURA-RUN-001"):
        graph_nodes.insert(
            -1,
            {
                "id": packet_id,
                "status": "REDIRECTED",
                "packet": f".agent/tasks/{packet_id}.md",
                "redirected_to": "AURA-INTEGRATED-002",
            },
        )
        if packet_id.startswith("AURA-"):
            artifact = root / ".agent" / "artifacts" / packet_id
            artifact.mkdir(parents=True, exist_ok=True)
            (artifact / "COMPLETION.json").write_text("{}", encoding="utf-8")
    graph_nodes.append({"id": "AURA-INTEGRATED-002", "status": "PROPOSED"})
    (root / ".agent" / "graph" / "work-graph.json").write_text(
        json.dumps({"nodes": graph_nodes}), encoding="utf-8"
    )
    forge_payload = _present_reconciliation(old, successor_packet_id="FORGE-INTEGRATED-001")
    _write_reconciliation(root, [forge_payload])
    forge_bytes = (root / ".agent" / "ledger" / "FORGE-EVID-003.jsonl").read_bytes()
    _write_aura_reconciliation(
        root,
        [
            _no_legacy_record("FORGE-ADAPT-001"),
            _no_legacy_record("AURA-MIG-001"),
            _no_legacy_record("AURA-RUN-001"),
        ],
    )

    assert slicer.verify_reconciliation_records(root) == (
        "OLD",
        "FORGE-ADAPT-001",
        "AURA-MIG-001",
        "AURA-RUN-001",
    )
    assert (root / ".agent" / "ledger" / "FORGE-EVID-003.jsonl").read_bytes() == forge_bytes


def test_reconciliation_union_rejects_duplicate_cross_stream_record(slicer, tmp_path):
    root = tmp_path / "cross-stream-duplicate"
    old = _reconciliation_fixture(root)
    _write_reconciliation(root, [_present_reconciliation(old)])
    _write_aura_reconciliation(root, [_present_reconciliation(old)])
    with pytest.raises(SystemExit, match="duplicate"):
        slicer.verify_reconciliation_records(root)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (_no_legacy_record("AURA-MIG-001"), None),
        (
            {**_no_legacy_record("AURA-MIG-001"), "successor_packet_id": "OTHER"},
            "successor mismatch",
        ),
        (
            {**_no_legacy_record("AURA-MIG-001"), "evidence_class": "LEDGER_ONLY"},
            "Legacy ledger path",
        ),
        ({**_no_legacy_record("AURA-MIG-001"), "status": "COMPLETE"}, "Invalid or duplicate"),
    ],
)
def test_aura_stream_records_fail_closed_on_claim_mismatch(slicer, tmp_path, payload, expected):
    root = tmp_path / (expected or "valid").replace(" ", "-")
    old_ledger = _reconciliation_fixture(root, "FORGE-OLD")
    graph_path = root / ".agent" / "graph" / "work-graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["nodes"].insert(
        0,
        {
            "id": "AURA-MIG-001",
            "status": "REDIRECTED",
            "packet": ".agent/tasks/AURA-MIG-001.md",
            "redirected_to": "AURA-INTEGRATED-002",
        },
    )
    graph["nodes"].append({"id": "AURA-INTEGRATED-002", "status": "PROPOSED"})
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    _write_reconciliation(
        root,
        [_present_reconciliation(old_ledger, packet_id="FORGE-OLD")],
    )
    _write_aura_reconciliation(root, [payload])
    if expected is None:
        assert slicer.verify_reconciliation_records(root) == ("FORGE-OLD", "AURA-MIG-001")
    else:
        with pytest.raises(SystemExit, match=expected):
            slicer.verify_reconciliation_records(root)


# ---------------------------------------------------------------------------
# The recorded evidence carries the independence records
# ---------------------------------------------------------------------------
