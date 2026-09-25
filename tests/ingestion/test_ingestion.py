from __future__ import annotations

import pytest

from forge.decisions.jev_decisions import DecisionReceipt, NoulAnswer, ScoreAnswer
from forge.execution_loop import BuildPacket
from forge.ingestion.calibrate import calibrate, record_answer
from forge.ingestion.decompose import Decomposition, decompose
from forge.ingestion.handoff import handoff
from forge.ingestion.models import (
    Ambiguity,
    BlastRadius,
    ConfidenceLabel,
    KnownUnknown,
    ReceiptLedger,
    RequirementSeed,
)
from forge.ingestion.refine import (
    AcceptedAssumption,
    OwnerApproval,
    OwnerContract,
    refine,
    sign_contract,
)
from forge.product_brain import ProductBrain
from forge.providers.model_provider import CallReceipt, Capability
from forge.trust_kernel import (
    ActionKind,
    Authority,
    AuthorityGrant,
    CandidateIdentity,
    RepositoryIdentity,
    TrustKernel,
)


def ambiguity(number: int, radius: BlastRadius = BlastRadius.HIGH) -> Ambiguity:
    return Ambiguity(
        id=f"AMB-{number:03d}",
        dimension=f"area.{number}",
        question_if_asked=f"What should choice {number} be?",
        why_we_ask="This choice changes what the first version needs.",
        current_assumption="Use a simple default",
        assumption_confidence=0.4,
        blast_radius=radius,
        resolvable_by_default=False,
    )


def decomposition() -> Decomposition:
    return Decomposition(
        confidence=ConfidenceLabel.MEDIUM,
        north_star_plain="Help the business track its work.",
        requirements=[
            RequirementSeed(
                id="REQ-001", statement="Track work", source_quote="ERP for my business"
            )
        ],
        ambiguities=[ambiguity(i) for i in range(1, 9)],
        known_unknowns=[KnownUnknown(id="U-001", plain="Number of users")],
    )


def contract() -> OwnerContract:
    return OwnerContract(
        mission_id="MISSION-001",
        north_star_plain="Help staff track sales and stock.",
        in_scope=["sales", "stock"],
        out_of_scope=["payroll"],
        finish_contract_plain=(
            "Done means staff can add a customer, make a bill, and see stock fall."
        ),
        assumptions_accepted=[
            AcceptedAssumption(
                id="A-001",
                plain="Fewer than 50 users",
                confidence=0.5,
                lineage=["AMB-001"],
            )
        ],
        known_unknowns_registered=["U-001"],
        polish_round=0,
    )


OWNER_KEYS = {"owner": b"owner-controlled-test-key-32-bytes!!"}
TRUSTED_REPOSITORY = RepositoryIdentity("remote", "rev", "/work", "branch")


def trusted_authority() -> TrustKernel:
    return TrustKernel(
        TRUSTED_REPOSITORY,
        mission_id="MISSION-001",
        owner_verification_keys=OWNER_KEYS,
    )


def owner_grant(unsigned: OwnerContract) -> AuthorityGrant:
    from forge.ingestion.refine import _contract_hash

    return AuthorityGrant.issue(
        Authority.A1,
        ActionKind.ROUTINE,
        _contract_hash(unsigned),
        "owner",
        signing_key=OWNER_KEYS["owner"],
    )


def signed_contract(ledger: ReceiptLedger) -> OwnerContract:
    unsigned = contract()
    approval = OwnerApproval.issue(unsigned, "owner", signing_key=OWNER_KEYS["owner"])
    return sign_contract(
        unsigned,
        approval,
        ledger,
        trusted_authority=trusted_authority(),
        authority_grant=owner_grant(unsigned),
    )


def build_packet(brain: ProductBrain) -> BuildPacket:
    repository = TRUSTED_REPOSITORY
    base = CandidateIdentity(repository.digest, "rev", "tree", "PACKET-001")
    return BuildPacket(
        id="PACKET-001",
        objective="Build",
        requirements=("REQ",),
        allowed_paths=("src/**",),
        forbidden_paths=(),
        acceptance=("works",),
        evidence_required=("test",),
        dependencies=(),
        invariants=(),
        risk="LOW",
        authority=Authority.A1,
        retry_limit=1,
        base_candidate=base,
        specification_hash=brain.specification_hash,
    )


class Provider:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def call(self, capability, schema, system, prompt, **kwargs):
        self.calls.append((capability, schema, system, prompt, kwargs))
        output = next(self.outputs)
        return output, CallReceipt(
            capability=capability,
            provider="mock",
            model="mock",
            model_env="MOCK_MODEL",
            family="mock",
            latency_ms=0,
            schema_valid=True,
            caller_role=kwargs["caller_role"],
            packet_id=kwargs.get("packet_id"),
        )


class Jev:
    def __init__(self, material=0.9, sufficient=0.2):
        self.calls = []
        self.material = material
        self.sufficient = sufficient

    def evaluate(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        answers = {}
        for name in questions:
            if name.endswith("materially_changes"):
                answers[name] = NoulAnswer(type="noul", noul=self.material)
            elif name.endswith("default_sufficient"):
                answers[name] = NoulAnswer(type="noul", noul=self.sufficient)
            else:
                answers[name] = ScoreAnswer(
                    type="score",
                    score=1,
                    confidence=0.3,
                    legend={"1": "low", "2": "medium", "3": "high"},
                    probabilities={"1": 0.7, "2": 0.2, "3": 0.1},
                )
        return answers, DecisionReceipt(
            model_reported="jev-1.13.0",
            model_requested="jev-1.13.0",
            latency_ms=0,
            decision_fn=kwargs["decision_fn"],
            packet_id=kwargs.get("packet_id"),
            answers_summary={},
        )


def test_decompose_broad_intent_is_validated_and_uses_high_reasoning():
    provider = Provider([decomposition()])
    result, _ = decompose("I want to build an ERP for my business", provider)
    assert len(result.ambiguities) >= 8
    assert len(result.requirements) <= 12
    assert provider.calls[0][0] is Capability.HIGH_REASONING
    assert all(item.source_quote or item.inferred for item in result.requirements)


def test_calibrate_fans_out_once_caps_at_five_and_receipts_threshold(tmp_path):
    client = Jev()
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    result, _ = calibrate([ambiguity(i) for i in range(1, 9)], client, ledger=ledger)
    assert len(client.calls) == 1
    assert len(client.calls[0][1]) == 24
    assert len(result.questions) == 5
    assert all(item.materially_changes > 0.6 for item in result.questions)
    assert ledger.payloads("JEV_CALIBRATION")


def test_zero_blocking_ambiguities_produces_zero_questions():
    result, _ = calibrate([ambiguity(1)], Jev(material=0.1))
    assert result.questions == []


def test_refine_contract_rejects_jargon_and_empty_scope():
    with pytest.raises(ValueError):
        contract().model_copy(update={"out_of_scope": []}).model_validate(
            contract().model_dump() | {"out_of_scope": []}
        )
    with pytest.raises(ValueError, match="jargon"):
        OwnerContract.model_validate(contract().model_dump() | {"in_scope": ["ORM"]})


def test_owner_correction_reenters_decompose_and_preserves_lineage(tmp_path):
    updated = decomposition().model_copy(update={"north_star_plain": "Track shop sales only."})
    corrected_contract = contract().model_copy(
        update={
            "assumptions_accepted": [
                AcceptedAssumption(
                    id="A-001",
                    plain="One shop",
                    confidence=0.9,
                    lineage=["original intent", "owner correction"],
                )
            ],
            "polish_round": 1,
        }
    )
    provider = Provider([updated, corrected_contract])
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    result, _, new_decomposition = refine(
        decomposition(),
        provider,
        correction="Only one shop",
        raw_intent="Build an ERP",
        ledger=ledger,
    )
    assert new_decomposition.north_star_plain == "Track shop sales only."
    assert result.assumptions_accepted[0].lineage == ("original intent", "owner correction")
    assert ledger.payloads("OWNER_CORRECTION")[0]["correction"] == "Only one shop"


def test_restart_does_not_reask_answered_question(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    record_answer(ledger, "AMB-001", "Ten people")
    restarted = ReceiptLedger(path)
    client = Jev()
    result, _ = calibrate([ambiguity(1), ambiguity(2)], client, ledger=restarted)
    assert result.answered_ambiguities == ["AMB-001"]
    assert all(question.ambiguity != "AMB-001" for question in result.questions)
    assert len(client.calls) == 1
    assert len(client.calls[0][0]) == 1


def test_handoff_emits_existing_build_packet_unmodified(tmp_path):
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    signed = signed_contract(ledger)
    brain = ProductBrain()
    repository = TRUSTED_REPOSITORY
    base = CandidateIdentity(repository.digest, "rev", "tree", "PACKET-001")
    packet = BuildPacket(
        id="PACKET-001",
        objective="Build first slice",
        requirements=("REQ-001",),
        allowed_paths=("src/**",),
        forbidden_paths=(),
        acceptance=("works",),
        evidence_required=("pytest",),
        dependencies=(),
        invariants=(),
        risk="LOW",
        authority=Authority.A1,
        retry_limit=2,
        base_candidate=base,
        specification_hash=brain.specification_hash,
    )
    mission = handoff(signed, brain, packet, ledger, trusted_authority=trusted_authority())
    assert mission.build_packet is packet
    assert mission.specification_hash == brain.specification_hash
    assert ledger.payloads("MISSION_HANDED_OFF")
    with pytest.raises(AttributeError):
        mission.owner_contract.assumptions_accepted[0].lineage.append("unapproved")


def test_handoff_rejects_modified_specification(tmp_path):
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    signed = signed_contract(ledger)
    brain = ProductBrain()
    repository = TRUSTED_REPOSITORY
    base = CandidateIdentity(repository.digest, "rev", "tree", "PACKET-001")
    packet = BuildPacket(
        id="PACKET-001",
        objective="Build",
        requirements=("REQ",),
        allowed_paths=("src/**",),
        forbidden_paths=(),
        acceptance=("works",),
        evidence_required=("test",),
        dependencies=(),
        invariants=(),
        risk="LOW",
        authority=Authority.A1,
        retry_limit=1,
        base_candidate=base,
        specification_hash="stale",
    )
    with pytest.raises(ValueError, match="Product Brain"):
        handoff(signed, brain, packet, ledger, trusted_authority=trusted_authority())


def test_handoff_rejects_post_signature_contract_change(tmp_path):
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    signed = signed_contract(ledger)
    brain = ProductBrain()
    repository = TRUSTED_REPOSITORY
    base = CandidateIdentity(repository.digest, "rev", "tree", "PACKET-001")
    packet = BuildPacket(
        id="PACKET-001",
        objective="Build",
        requirements=("REQ",),
        allowed_paths=("src/**",),
        forbidden_paths=(),
        acceptance=("works",),
        evidence_required=("test",),
        dependencies=(),
        invariants=(),
        risk="LOW",
        authority=Authority.A1,
        retry_limit=1,
        base_candidate=base,
        specification_hash=brain.specification_hash,
    )
    altered = signed.model_copy(update={"in_scope": ["sales", "stock", "payroll"]})
    with pytest.raises(ValueError, match="contract"):
        handoff(altered, brain, packet, ledger, trusted_authority=trusted_authority())


def test_ingestion_reload_rejects_truncated_stream(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    ledger.append("TWO", {"value": 2})
    path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])
    with pytest.raises(ValueError, match="truncat|checkpoint|mismatch"):
        ReceiptLedger(path)


def test_valid_approval_survives_restart_and_handoff(tmp_path):
    path = tmp_path / "ledger.jsonl"
    signed = signed_contract(ReceiptLedger(path))
    restarted = ReceiptLedger(path)
    brain = ProductBrain()
    mission = handoff(
        signed, brain, build_packet(brain), restarted, trusted_authority=trusted_authority()
    )
    assert mission.signature_receipt_hash == signed.owner_signature.receipt_hash
    assert ReceiptLedger(path).payloads("MISSION_HANDED_OFF")


def test_handoff_rejects_mismatched_signature_and_receipt_data(tmp_path):
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    signed = signed_contract(ledger)
    brain = ProductBrain()
    changed_signature = signed.owner_signature.model_copy(update={"approved_by": "someone else"})
    with pytest.raises(ValueError, match="disagree"):
        handoff(
            signed.model_copy(update={"owner_signature": changed_signature}),
            brain,
            build_packet(brain),
            ledger,
            trusted_authority=trusted_authority(),
        )
    ledger.receipts[-1] = ledger.receipts[-1].model_copy(
        update={"payload": ledger.receipts[-1].payload | {"approved_by": "someone else"}}
    )
    with pytest.raises(ValueError, match="receipt view"):
        handoff(signed, brain, build_packet(brain), ledger, trusted_authority=trusted_authority())


def test_missing_or_untrusted_approval_evidence_is_rejected(tmp_path):
    unsigned = contract()
    ledger = ReceiptLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="approval evidence"):
        sign_contract(
            unsigned,
            "owner",
            ledger,
            trusted_authority=trusted_authority(),
            authority_grant=owner_grant(unsigned),
        )
    forged = OwnerApproval.issue(unsigned, "owner", signing_key=b"untrusted-key")
    forged_grant = AuthorityGrant.issue(
        Authority.A1,
        ActionKind.ROUTINE,
        owner_grant(unsigned).scope_digest,
        "owner",
        signing_key=b"untrusted-key",
    )
    with pytest.raises(ValueError, match="cannot be verified"):
        sign_contract(
            unsigned,
            forged,
            ledger,
            trusted_authority=trusted_authority(),
            authority_grant=forged_grant,
        )
    assert ledger.receipts == []
    with pytest.raises(ValueError, match="extra"):
        OwnerApproval.model_validate(
            {
                "approved_by": "owner",
                "contract_hash": owner_grant(unsigned).scope_digest,
                "proof": "x",
            }
        )
    signed = signed_contract(ledger)
    brain = ProductBrain()
    with pytest.raises(ValueError, match="missing"):
        handoff(
            signed,
            brain,
            build_packet(brain),
            ReceiptLedger(),
            trusted_authority=trusted_authority(),
        )
    with pytest.raises(ValueError, match="cannot be verified"):
        handoff(
            signed,
            brain,
            build_packet(brain),
            ledger,
            trusted_authority=TrustKernel(
                TRUSTED_REPOSITORY, mission_id="MISSION-001", owner_verification_keys={}
            ),
        )


def test_interrupted_append_fails_closed_on_reload(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})

    def interrupted(_checkpoint):
        raise OSError("interrupted after receipt write")

    monkeypatch.setattr(ledger._store, "_write_checkpoint", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        ledger.append("TWO", {"value": 2})
    with pytest.raises(ValueError, match="ambiguous"):
        ledger.append("THREE", {"value": 3})
    with pytest.raises(ValueError, match="checkpoint|mismatch"):
        ReceiptLedger(path)


@pytest.mark.parametrize("suffix", [b" ", b"\n"])
def test_whitespace_stream_tail_fails_closed_on_reload(tmp_path, suffix):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    path.write_bytes(path.read_bytes() + suffix)
    with pytest.raises(ValueError, match="blank|incomplete|mismatch"):
        ReceiptLedger(path)


@pytest.mark.parametrize("operation", ["verify", "append"])
@pytest.mark.parametrize("suffix", [b" ", b"\n"])
def test_loaded_ledger_rejects_post_construction_framing_tails(tmp_path, operation, suffix):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    loaded = ReceiptLedger(path)
    path.write_bytes(path.read_bytes() + suffix)
    with pytest.raises(ValueError, match="blank|incomplete|mismatch"):
        if operation == "verify":
            loaded.verify()
        else:
            loaded.append("TWO", {"value": 2})


def test_partial_receipt_and_missing_checkpoint_fail_closed(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    with path.open("ab") as stream:
        stream.write(b'{"sequence": 2')
    with pytest.raises(ValueError, match="checkpoint|receipt|mismatch|incomplete"):
        ReceiptLedger(path)
    path.write_bytes(path.read_bytes().splitlines(keepends=True)[0])
    path.with_suffix(".checkpoint.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        ReceiptLedger(path)


def test_loaded_ledger_cannot_append_after_both_files_disappear(tmp_path):
    path = tmp_path / "ledger.jsonl"
    initial = ReceiptLedger(path)
    initial.append("ONE", {"value": 1})
    loaded = ReceiptLedger(path)
    path.unlink()
    path.with_suffix(".checkpoint.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        loaded.append("TWO", {"value": 2})
    assert not path.exists()
    assert not path.with_suffix(".checkpoint.json").exists()


def test_checkpoint_stream_identity_must_match_ingestion_path(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    checkpoint_path = path.with_suffix(".checkpoint.json")
    checkpoint = checkpoint_path.read_text(encoding="utf-8").replace(
        '"stream_id": "ledger"', '"stream_id": "other"'
    )
    checkpoint_path.write_text(checkpoint, encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        ReceiptLedger(path)


@pytest.mark.parametrize("operation", ["verify", "append"])
def test_loaded_ledger_rechecks_checkpoint_identity(tmp_path, operation):
    path = tmp_path / "ledger.jsonl"
    ledger = ReceiptLedger(path)
    ledger.append("ONE", {"value": 1})
    loaded = ReceiptLedger(path)
    checkpoint_path = path.with_suffix(".checkpoint.json")
    checkpoint = checkpoint_path.read_text(encoding="utf-8").replace(
        '"stream_id": "ledger"', '"stream_id": "other"'
    )
    checkpoint_path.write_text(checkpoint, encoding="utf-8")
    with pytest.raises(ValueError, match="identity"):
        if operation == "verify":
            loaded.verify()
        else:
            loaded.append("TWO", {"value": 2})
