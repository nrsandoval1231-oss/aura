import copy
from dataclasses import asdict
from decimal import Decimal

import pytest

from forge import (
    Assumption,
    AssumptionStatus,
    Authority,
    DecisionRecord,
    DiscoveryRecord,
    FinishContract,
    ForgeError,
    Invariant,
    LedgerCheckpoint,
    NorthStar,
    ProductBrain,
    Requirement,
    RequirementStatus,
)
from forge.trust_kernel import ActionKind, AuthorityGrant, Receipt

OWNER_KEY = b"product-owner-key"


def owner_grant(brain: ProductBrain, event: str, data: dict) -> AuthorityGrant:
    scope = brain.protected_scope_digest(event, data)
    return AuthorityGrant.issue(
        Authority.A3, ActionKind.PROTECTED, scope, "OWNER", signing_key=OWNER_KEY
    )


def initialized_brain() -> ProductBrain:
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    north_star = NorthStar("Build an evidence-governed runtime", "OWNER-001")
    brain.ingest_north_star(
        north_star,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "NORTH_STAR_INGESTED", asdict(north_star)),
    )
    contract = FinishContract(("all active requirements have evidence",))
    brain.set_finish_contract(
        contract,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "FINISH_CONTRACT_SET", asdict(contract)),
    )
    return brain


def discovery(identifier: str = "DISC-001") -> DiscoveryRecord:
    return DiscoveryRecord(
        identifier,
        ("EVIDENCE-001",),
        "Validated product learning",
        "Requirement wording and proof contract",
        True,
    )


def checkpoint_for(records: list[dict]) -> LedgerCheckpoint:
    return LedgerCheckpoint(len(records), records[-1]["receipt_hash"] if records else None)


def bind_record_owner_grant(record: dict) -> None:
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    grant = owner_grant(brain, record["event"], record["payload"]["data"])
    record["payload"]["authority_grant"] = asdict(grant)


def test_ingests_structured_product_state_and_records_receipts():
    brain = initialized_brain()
    brain.add_assumption(
        Assumption(
            "A-001", "One local process is sufficient", "ADR-0001", 0.9, AssumptionStatus.ACTIVE
        ),
        authority=Authority.A2,
    )
    brain.add_requirement(
        Requirement(
            "R-001",
            1,
            "Preserve owner intent",
            "PRD-1",
            assumptions=("A-001",),
            evidence_required=("governor_test",),
        ),
        authority=Authority.A2,
    )
    brain.add_decision(
        DecisionRecord(
            "DEC-001", "Runtime topology", "one process", ("ADR-0001",), Authority.A2, True
        ),
        authority=Authority.A2,
    )
    brain.add_invariant(
        Invariant("INV-001", "Builder cannot audit itself", "L1", ("governor_test",)),
        authority=Authority.A2,
    )
    assert len(brain.ledger.receipts) == 6
    assert brain.contradictions() == ()
    assert brain.specification_hash


def test_owner_controlled_records_require_a3():
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    with pytest.raises(ForgeError, match="higher authority"):
        brain.ingest_north_star(NorthStar("Intent", "OWNER"), authority=Authority.A2)
    intent = NorthStar("Intent", "OWNER")
    with pytest.raises(ForgeError, match="signed owner grant"):
        brain.ingest_north_star(intent, authority=Authority.A3)
    brain.ingest_north_star(
        intent,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "NORTH_STAR_INGESTED", asdict(intent)),
    )
    with pytest.raises(ForgeError, match="higher authority"):
        brain.replace_north_star(NorthStar("Changed", "OWNER", 2), authority=Authority.A2)
    with pytest.raises(ForgeError, match="version one"):
        ProductBrain().ingest_north_star(NorthStar("Skipped", "OWNER", 2), authority=Authority.A3)
    with pytest.raises(ForgeError, match="cannot be blank"):
        NorthStar("", "")
    with pytest.raises(ForgeError, match="cannot be blank"):
        FinishContract(("",))
    with pytest.raises(ForgeError, match="cannot be blank"):
        NorthStar(1, "OWNER")


def test_requirements_and_validated_discoveries_reject_blank_content():
    with pytest.raises(ForgeError, match="cannot be blank"):
        Requirement("R-001", 1, " ", "PRD")
    with pytest.raises(ForgeError, match="nonblank evidence"):
        DiscoveryRecord("DISC-001", ("",), " ", " ", True)
    with pytest.raises(ForgeError, match="boolean"):
        DiscoveryRecord("DISC-001", ("E-1",), "reason", "impact", "false")
    with pytest.raises(ForgeError, match="cannot be blank"):
        Assumption("", "", "", 0.5, AssumptionStatus.VALIDATED)
    with pytest.raises(ForgeError, match="cannot be blank"):
        Invariant("", "Invariant", "A2", ("test",))
    with pytest.raises(ForgeError, match="verification references"):
        Invariant("I-001", "Invariant", "A2", ())
    with pytest.raises(ForgeError, match="verification references"):
        Invariant("I-001", "Invariant", "A2", (" ",))


def test_decision_records_require_a2_floor():
    brain = initialized_brain()
    decision = DecisionRecord(
        "DEC-A1", "Choose product truth", "unsafe", ("claim",), Authority.A1, True
    )
    with pytest.raises(ForgeError, match="higher authority"):
        brain.add_decision(decision, authority=Authority.A1)


def test_product_brain_state_is_read_only_outside_governed_mutators():
    brain = initialized_brain()
    with pytest.raises(AttributeError):
        brain.north_star = NorthStar("Bypass", "OWNER", 2)
    with pytest.raises(TypeError):
        brain.requirements["R-X"] = Requirement("R-X", 1, "Bypass", "TEST")
    external_ledger = brain.ledger
    before = len(brain.ledger.receipts)
    external_ledger.append(
        Receipt.create(
            len(external_ledger.receipts) + 1,
            "EXTERNAL",
            None,
            None,
            {},
            external_ledger.receipts[-1].receipt_hash,
        )
    )
    assert len(brain.ledger.receipts) == before


def test_requirement_sequence_fields_are_canonicalized_before_storage():
    brain = initialized_brain()
    mutable_evidence = ["unit"]
    requirement = Requirement("R-001", 1, "Canonical", "PRD", evidence_required=mutable_evidence)
    brain.add_requirement(requirement, authority=Authority.A2)
    mutable_evidence.append("integration")
    assert brain.requirements["R-001"].evidence_required == ("unit",)


def test_all_product_record_sequences_are_canonicalized():
    criteria = ["tests pass"]
    dependents = ["R-001"]
    basis = ["ADR-001"]
    verification = ["test"]
    contract = FinishContract(criteria)
    assumption = Assumption("A-001", "Premise", "PRD", 0.5, dependents=dependents)
    decision = DecisionRecord("D-001", "Question", "Choice", basis, Authority.A2, True)
    invariant = Invariant("I-001", "Invariant", "A2", verification)
    criteria.append("mutated")
    dependents.append("R-002")
    basis.append("ADR-002")
    verification.append("mutated")
    assert contract.criteria == ("tests pass",)
    assert assumption.dependents == ("R-001",)
    assert decision.basis == ("ADR-001",)
    assert invariant.verification == ("test",)


def test_requirement_declared_authority_is_enforced():
    brain = initialized_brain()
    protected = Requirement("R-A3", 1, "Owner governed", "OWNER", authority=Authority.A3)
    with pytest.raises(ForgeError, match="higher authority"):
        brain.add_requirement(protected, authority=Authority.A2)
    brain.add_requirement(
        protected,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "REQUIREMENT_ADDED", asdict(protected)),
    )
    with pytest.raises(ForgeError, match="higher authority"):
        brain.transition_requirement("R-A3", RequirementStatus.ACTIVE, authority=Authority.A2)
    transition_data = {"id": "R-A3", "target": RequirementStatus.ACTIVE.value, "evidence": []}
    brain.transition_requirement(
        "R-A3",
        RequirementStatus.ACTIVE,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "REQUIREMENT_TRANSITIONED", transition_data),
    )
    with pytest.raises(ForgeError, match="cannot lower"):
        brain.version_requirement(
            Requirement(
                "R-A3", 2, "Downgrade", "DISC-A3", authority=Authority.A2, supersedes="R-A3:v1"
            ),
            discovery=discovery("DISC-A3"),
            authority=Authority.A3,
        )


def test_requirement_lifecycle_and_version_lineage_fail_closed():
    brain = initialized_brain()
    brain.add_requirement(Requirement("R-001", 1, "Initial", "PRD-1"), authority=Authority.A2)
    brain.transition_requirement("R-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    brain.transition_requirement("R-001", RequirementStatus.IMPLEMENTING, authority=Authority.A2)
    with pytest.raises(ForgeError, match="cannot transition"):
        brain.transition_requirement("R-001", RequirementStatus.SATISFIED, authority=Authority.A2)
    brain.version_requirement(
        Requirement("R-001", 2, "Clarified", "DISC-001", supersedes="R-001:v1"),
        discovery=discovery(),
        authority=Authority.A2,
    )
    assert brain.requirement_history["R-001"][0].status is RequirementStatus.SUPERSEDED
    assert brain.requirements["R-001"].version == 2
    with pytest.raises(ForgeError, match="lineage"):
        brain.version_requirement(
            Requirement("R-001", 4, "Bad", "DISC-002", supersedes="R-001:v1"),
            discovery=discovery("DISC-002"),
            authority=Authority.A2,
        )


def test_requirement_evidence_contract_preserves_unknown():
    brain = initialized_brain()
    brain.add_requirement(
        Requirement("R-001", 1, "Prove it", "PRD", evidence_required=("unit", "integration")),
        authority=Authority.A2,
    )
    brain.transition_requirement("R-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    brain.transition_requirement("R-001", RequirementStatus.IMPLEMENTING, authority=Authority.A2)
    with pytest.raises(ForgeError, match="UNKNOWN"):
        brain.transition_requirement(
            "R-001",
            RequirementStatus.EVIDENCED,
            authority=Authority.A2,
            evidence=("unit", "unrelated"),
        )
    brain.transition_requirement(
        "R-001",
        RequirementStatus.EVIDENCED,
        authority=Authority.A2,
        evidence=("unit", "integration"),
    )
    assert brain.requirements["R-001"].evidence == ("integration", "unit")

    no_contract = initialized_brain()
    no_contract.add_requirement(
        Requirement("R-EMPTY", 1, "Prove it", "PRD"), authority=Authority.A2
    )
    no_contract.transition_requirement("R-EMPTY", RequirementStatus.ACTIVE, authority=Authority.A2)
    no_contract.transition_requirement(
        "R-EMPTY", RequirementStatus.IMPLEMENTING, authority=Authority.A2
    )
    with pytest.raises(ForgeError, match="nonempty evidence contract"):
        no_contract.transition_requirement(
            "R-EMPTY", RequirementStatus.EVIDENCED, authority=Authority.A2
        )


def test_requirement_creation_and_versioning_cannot_bypass_lifecycle():
    brain = initialized_brain()
    with pytest.raises(ForgeError, match="no supersedes lineage"):
        brain.add_requirement(
            Requirement("R-LINEAGE", 1, "Bypass", "PRD", supersedes="R-OLD:v1"),
            authority=Authority.A2,
        )
    with pytest.raises(ForgeError, match="begin PROPOSED"):
        brain.add_requirement(
            Requirement("R-001", 1, "Bypass", "PRD", status=RequirementStatus.SATISFIED),
            authority=Authority.A2,
        )
    brain.add_requirement(Requirement("R-001", 1, "Initial", "PRD"), authority=Authority.A2)
    with pytest.raises(ForgeError, match="begin PROPOSED"):
        brain.version_requirement(
            Requirement(
                "R-001",
                2,
                "Bypass",
                "DISC-001",
                status=RequirementStatus.SATISFIED,
                supersedes="R-001:v1",
            ),
            discovery=discovery(),
            authority=Authority.A2,
        )


def test_requirement_versioning_requires_validated_discovery_evidence():
    brain = initialized_brain()
    brain.add_requirement(Requirement("R-001", 1, "Initial", "PRD"), authority=Authority.A2)
    invalid = DiscoveryRecord("DISC-001", (), "", "", False)
    with pytest.raises(ForgeError, match="validated discovery"):
        brain.version_requirement(
            Requirement("R-001", 2, "Changed", "DISC-001", supersedes="R-001:v1"),
            discovery=invalid,
            authority=Authority.A2,
        )


def test_simple_contradictions_are_explicit_and_sorted():
    brain = initialized_brain()
    brain.add_requirement(
        Requirement(
            "R-002",
            1,
            "Dependent",
            "PRD-2",
            assumptions=("A-MISSING",),
            dependencies=("R-MISSING",),
        ),
        authority=Authority.A2,
    )
    findings = brain.contradictions()
    assert [item.code for item in findings] == [
        "MISSING_ASSUMPTION",
        "MISSING_REQUIREMENT_DEPENDENCY",
    ]


def test_rejected_and_contradicted_assumptions_are_not_false_clean():
    brain = initialized_brain()
    brain.add_assumption(
        Assumption("A-REJECTED", "Bad premise", "TEST", 0.1, AssumptionStatus.REJECTED),
        authority=Authority.A2,
    )
    brain.add_assumption(
        Assumption(
            "A-CONTRADICTED", "Disputed premise", "TEST", 0.5, contradictory_evidence=("E-FAIL",)
        ),
        authority=Authority.A2,
    )
    brain.add_requirement(
        Requirement(
            "R-001", 1, "Depends on premises", "PRD", assumptions=("A-REJECTED", "A-CONTRADICTED")
        ),
        authority=Authority.A2,
    )
    assert [item.code for item in brain.contradictions()] == [
        "CONTRADICTED_ASSUMPTION",
        "REJECTED_ASSUMPTION",
    ]

    normalized = Assumption("A-STRING", "Rejected premise", "TEST", 0.1, "REJECTED")
    assert normalized.status is AssumptionStatus.REJECTED


def test_failed_mutation_rolls_back_state_and_receipt():
    brain = initialized_brain()
    before = len(brain.ledger.receipts)
    malformed = DecisionRecord("D-BAD", "Question", Decimal("0.5"), ("basis",), Authority.A2, True)
    with pytest.raises(TypeError):
        brain.add_decision(malformed, authority=Authority.A2)
    assert "D-BAD" not in brain.decisions
    assert len(brain.ledger.receipts) == before


def test_unknown_and_challenged_assumptions_are_explicit_contradictions():
    brain = initialized_brain()
    brain.add_assumption(
        Assumption("A-UNKNOWN", "Unknown premise", "TEST", 0.0), authority=Authority.A2
    )
    brain.add_assumption(
        Assumption("A-CHALLENGED", "Challenged premise", "TEST", 0.4, AssumptionStatus.CHALLENGED),
        authority=Authority.A2,
    )
    brain.add_requirement(
        Requirement(
            "R-001",
            1,
            "Depends on unresolved premises",
            "PRD",
            assumptions=("A-UNKNOWN", "A-CHALLENGED"),
        ),
        authority=Authority.A2,
    )
    assert [item.code for item in brain.contradictions()] == [
        "UNRESOLVED_ASSUMPTION",
        "UNRESOLVED_ASSUMPTION",
    ]


def test_terminal_requirement_does_not_keep_obsolete_contradictions_active():
    brain = initialized_brain()
    brain.add_requirement(
        Requirement("R-OLD", 1, "Obsolete", "PRD", dependencies=("R-MISSING",)),
        authority=Authority.A2,
    )
    brain.transition_requirement("R-OLD", RequirementStatus.REJECTED, authority=Authority.A2)
    assert brain.contradictions() == ()


def test_missing_owner_intent_and_finish_contract_are_not_false_clean():
    findings = ProductBrain().contradictions()
    assert [item.code for item in findings] == ["MISSING_FINISH_CONTRACT", "MISSING_NORTH_STAR"]


def test_specification_hash_is_insertion_order_independent():
    left = initialized_brain()
    right = initialized_brain()
    a = Requirement("R-A", 1, "A", "PRD")
    b = Requirement("R-B", 1, "B", "PRD")
    left.add_requirement(a, authority=Authority.A2)
    left.add_requirement(b, authority=Authority.A2)
    right.add_requirement(b, authority=Authority.A2)
    right.add_requirement(a, authority=Authority.A2)
    assert left.specification_hash == right.specification_hash


def test_receipt_replay_reconstructs_identical_product_brain():
    brain = initialized_brain()
    brain.add_assumption(Assumption("A-001", "Assumption", "PRD", 0.5), authority=Authority.A2)
    brain.add_requirement(
        Requirement("R-001", 1, "Requirement", "PRD", assumptions=("A-001",)),
        authority=Authority.A2,
    )
    brain.transition_requirement("R-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    records = brain.ledger.to_records()
    restored = ProductBrain.from_records(
        records, checkpoint=brain.ledger.checkpoint, owner_verification_keys={"OWNER": OWNER_KEY}
    )
    assert restored.snapshot() == brain.snapshot()
    assert restored.specification_hash == brain.specification_hash


def test_corrupted_replay_hash_and_malformed_event_fail_closed():
    brain = initialized_brain()
    records = brain.ledger.to_records()
    corrupted = copy.deepcopy(records)
    corrupted[0]["payload"]["specification_hash_after"] = "bad"
    with pytest.raises(ForgeError, match="hash does not match"):
        ProductBrain.from_records(
            corrupted,
            checkpoint=brain.ledger.checkpoint,
            owner_verification_keys={"OWNER": OWNER_KEY},
        )
    malformed = [copy.deepcopy(records[0])]
    malformed[0]["event"] = "UNKNOWN_EVENT"
    data = malformed[0]
    bind_record_owner_grant(data)
    rebuilt = Receipt.create(
        data["sequence"],
        data["event"],
        data["state_before"],
        data["state_after"],
        data["payload"],
        data["previous_hash"],
    )
    malformed[0] = {**data, "receipt_hash": rebuilt.receipt_hash}
    with pytest.raises(ForgeError, match="Cannot replay event"):
        ProductBrain.from_records(
            malformed,
            checkpoint=checkpoint_for(malformed),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )


def test_replay_rejects_owner_record_ordering_bypass():
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    intent = NorthStar("Intent", "OWNER")
    brain.ingest_north_star(
        intent,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "NORTH_STAR_INGESTED", asdict(intent)),
    )
    record = copy.deepcopy(brain.ledger.to_records()[0])
    record["event"] = "NORTH_STAR_REPLACED"
    bind_record_owner_grant(record)
    rebuilt = Receipt.create(
        record["sequence"], record["event"], None, None, record["payload"], None
    )
    record["receipt_hash"] = rebuilt.receipt_hash
    with pytest.raises(ForgeError, match="increment exactly one version"):
        ProductBrain.from_records(
            [record],
            checkpoint=checkpoint_for([record]),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )


def test_replay_enforces_recorded_mutation_authority():
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    intent = NorthStar("Intent", "OWNER")
    brain.ingest_north_star(
        intent,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "NORTH_STAR_INGESTED", asdict(intent)),
    )
    record = copy.deepcopy(brain.ledger.to_records()[0])
    record["payload"]["authority"] = Authority.A1.value
    rebuilt = Receipt.create(
        record["sequence"], record["event"], None, None, record["payload"], None
    )
    record["receipt_hash"] = rebuilt.receipt_hash
    with pytest.raises(ForgeError, match="higher authority"):
        ProductBrain.from_records(
            [record],
            checkpoint=checkpoint_for([record]),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )


def test_malformed_specification_payload_returns_structured_error():
    brain = initialized_brain()
    record = copy.deepcopy(brain.ledger.to_records()[0])
    record["payload"]["data"] = {"statement": "missing fields"}
    bind_record_owner_grant(record)
    rebuilt = Receipt.create(
        record["sequence"], record["event"], None, None, record["payload"], None
    )
    record["receipt_hash"] = rebuilt.receipt_hash
    with pytest.raises(ForgeError) as error:
        ProductBrain.from_records(
            [record],
            checkpoint=checkpoint_for([record]),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )
    assert error.value.code == "MALFORMED_SPECIFICATION_RECEIPT"

    non_string = copy.deepcopy(initialized_brain().ledger.to_records()[0])
    non_string["payload"]["data"]["statement"] = 1
    bind_record_owner_grant(non_string)
    rebuilt = Receipt.create(
        non_string["sequence"], non_string["event"], None, None, non_string["payload"], None
    )
    non_string["receipt_hash"] = rebuilt.receipt_hash
    with pytest.raises(ForgeError) as error:
        ProductBrain.from_records(
            [non_string],
            checkpoint=checkpoint_for([non_string]),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )
    assert error.value.code == "INVALID_NORTH_STAR"


def test_replay_rejects_duplicate_product_record_ids():
    brain = initialized_brain()
    brain.add_assumption(Assumption("A-001", "Original", "PRD", 0.5), authority=Authority.A2)
    records = brain.ledger.to_records()
    prior = records[-1]
    duplicate_data = copy.deepcopy(prior["payload"]["data"])
    duplicate_data["statement"] = "Replacement"
    before = prior["payload"]["specification_hash_after"]
    duplicate = Receipt.create(
        prior["sequence"] + 1,
        "ASSUMPTION_ADDED",
        None,
        None,
        {
            "data": duplicate_data,
            "authority": Authority.A2.value,
            "specification_hash_before": before,
            "specification_hash_after": before,
        },
        prior["receipt_hash"],
    )
    with pytest.raises(ForgeError, match="already exists"):
        duplicate_records = [
            *records,
            {
                "sequence": duplicate.sequence,
                "event": duplicate.event,
                "state_before": duplicate.state_before,
                "state_after": duplicate.state_after,
                "payload": dict(duplicate.payload),
                "previous_hash": duplicate.previous_hash,
                "receipt_hash": duplicate.receipt_hash,
            },
        ]
        ProductBrain.from_records(
            duplicate_records,
            checkpoint=checkpoint_for(duplicate_records),
            owner_verification_keys={"OWNER": OWNER_KEY},
        )
