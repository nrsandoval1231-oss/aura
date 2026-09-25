import dataclasses
import json

import pytest

from forge.trust_kernel import (
    ActionKind,
    Authority,
    AuthorityGrant,
    CandidateIdentity,
    CandidateValidation,
    CompletionEvaluation,
    DiscoveryAuthorization,
    EffectDisposition,
    EvidenceStatus,
    ForgeError,
    Ledger,
    LedgerCheckpoint,
    MissionState,
    Receipt,
    ReconciliationEvidence,
    ReconciliationStatus,
    RepositoryIdentity,
    TransitionEvidence,
    TrustKernel,
)

AUDITOR_KEY = b"test-auditor-signing-key"
EVIDENCE_KEY = b"test-evidence-signing-key"
OWNER_KEY = b"test-owner-signing-key"
MISSION_ID = "mission-001"


@pytest.fixture
def repository():
    return RepositoryIdentity("https://example.test/repo", "abc", "C:/repo", "main")


def present(
    repository,
    target: MissionState,
    state_before: str | None = None,
    label: str = "transition-evidence",
) -> TransitionEvidence:
    return TransitionEvidence.issue(
        label, "validator", repository.digest, state_before, target.value, signing_key=EVIDENCE_KEY
    )


def evidence_for(
    kernel: TrustKernel, repository, target: MissionState, label: str | None = None
) -> TransitionEvidence:
    before = kernel.state.value if kernel.state else None
    return present(repository, target, before, label or f"evidence:{target.value}")


def kernel_for(repository, **kwargs) -> TrustKernel:
    mission_id = kwargs.pop("mission_id", MISSION_ID)
    return TrustKernel(
        repository,
        mission_id=mission_id,
        evidence_verification_keys={"validator": EVIDENCE_KEY},
        owner_verification_keys={"OWNER": OWNER_KEY},
        **kwargs,
    )


def grant(action: ActionKind, scope_digest: str, authority: Authority) -> AuthorityGrant:
    return AuthorityGrant.issue(authority, action, scope_digest, "OWNER", signing_key=OWNER_KEY)


def transition_payload(repository, label: str = "persisted-evidence") -> dict:
    return {
        "repository_digest": repository.digest,
        "mission_id": MISSION_ID,
        "evidence": dataclasses.asdict(present(repository, MissionState.INITIALIZING, label=label)),
    }


def checkpoint_for(records: list[dict]) -> LedgerCheckpoint:
    return LedgerCheckpoint(
        len(records), records[-1]["receipt_hash"] if records else None, MISSION_ID
    )


def test_complete_happy_path_transitions_are_deterministic(repository):
    candidate = CandidateIdentity(repository.digest, "abc", "tree", "FORGE-TK-001")
    kernel = kernel_for(
        repository,
        auditor_verification_keys={"auditor": AUDITOR_KEY},
        trusted_builder_contexts=frozenset({"builder"}),
        protected_candidate_digests=frozenset({candidate.digest}),
        finish_contract_digest="finish-contract",
    )
    validation = CandidateValidation.issue(
        candidate.digest, "PASS", "evidence", "auditor", "builder", signing_key=AUDITOR_KEY
    )
    completion = CompletionEvaluation.issue(
        candidate.digest,
        "finish-contract",
        "PASS",
        "completion-evidence",
        "auditor",
        signing_key=AUDITOR_KEY,
    )
    path = [
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
        MissionState.TESTING,
        MissionState.AUDITING,
        MissionState.MERGING,
        MissionState.OUTCOME_EVALUATION,
        MissionState.LEARNING,
        MissionState.RECONCILING,
        MissionState.FINISH_EVALUATION,
        MissionState.COMPLETE,
    ]
    for state in path:
        kwargs = (
            {
                "candidate": candidate,
                "validation": validation,
                "authority_grant": grant(ActionKind.PROTECTED, candidate.digest, Authority.A3),
            }
            if state is MissionState.MERGING
            else {}
        )
        if state is MissionState.COMPLETE:
            stale = CompletionEvaluation.issue(
                candidate.digest,
                "stale-contract",
                "PASS",
                "completion-evidence",
                "auditor",
                signing_key=AUDITOR_KEY,
            )
            with pytest.raises(ForgeError, match="not bound"):
                kernel.transition(
                    state, evidence=evidence_for(kernel, repository, state), completion=stale
                )
            kwargs = {"completion": completion}
        kernel.transition(state, evidence=evidence_for(kernel, repository, state), **kwargs)
    assert kernel.state is MissionState.COMPLETE
    assert kernel.ledger.replay() is MissionState.COMPLETE
    restored = kernel_for(
        repository,
        ledger=kernel.ledger,
        ledger_checkpoint=kernel.ledger.checkpoint,
        auditor_verification_keys={"auditor": AUDITOR_KEY},
        trusted_builder_contexts=frozenset({"builder"}),
        protected_candidate_digests=frozenset({candidate.digest}),
        finish_contract_digest="finish-contract",
    )
    assert restored.state is MissionState.COMPLETE
    with pytest.raises(ForgeError, match="different mission"):
        kernel_for(
            repository,
            mission_id="mission-002",
            ledger=kernel.ledger,
            ledger_checkpoint=kernel.ledger.checkpoint,
            auditor_verification_keys={"auditor": AUDITOR_KEY},
            trusted_builder_contexts=frozenset({"builder"}),
            protected_candidate_digests=frozenset({candidate.digest}),
            finish_contract_digest="finish-contract",
        )
    json_records = json.loads(json.dumps(kernel.ledger.to_records()))
    with pytest.raises(ForgeError, match="Authority grant"):
        TrustKernel(
            repository,
            mission_id=MISSION_ID,
            ledger=Ledger.from_records(json_records, checkpoint=checkpoint_for(json_records)),
            ledger_checkpoint=checkpoint_for(json_records),
            auditor_verification_keys={"auditor": AUDITOR_KEY},
            evidence_verification_keys={"validator": EVIDENCE_KEY},
            trusted_builder_contexts=frozenset({"builder"}),
            protected_candidate_digests=frozenset({candidate.digest}),
            finish_contract_digest="finish-contract",
        )

    with pytest.raises(ForgeError, match="protection policy"):
        kernel_for(
            repository,
            ledger=kernel.ledger,
            ledger_checkpoint=kernel.ledger.checkpoint,
            auditor_verification_keys={"auditor": AUDITOR_KEY},
            trusted_builder_contexts=frozenset({"builder"}),
            finish_contract_digest="finish-contract",
        )


def test_invalid_transition_fails_closed(repository):
    kernel = kernel_for(repository)
    with pytest.raises(ForgeError, match="First mission"):
        kernel.transition(
            MissionState.PLANNING, evidence=evidence_for(kernel, repository, MissionState.PLANNING)
        )
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    with pytest.raises(ForgeError, match="cannot transition"):
        kernel.transition(
            MissionState.COMPLETE, evidence=evidence_for(kernel, repository, MissionState.COMPLETE)
        )


def test_authority_and_unknown_evidence_fail_closed(repository):
    kernel = kernel_for(repository)
    with pytest.raises(ForgeError, match="higher authority"):
        kernel.authorize(
            ActionKind.PROTECTED,
            grant(ActionKind.PROTECTED, "scope", Authority.A2),
            scope_digest="scope",
        )
    with pytest.raises(ForgeError, match="present"):
        kernel.transition(MissionState.INITIALIZING)
    forged_evidence = TransitionEvidence(
        EvidenceStatus.PRESENT,
        "evidence",
        "validator",
        repository.digest,
        None,
        MissionState.INITIALIZING.value,
        "forged",
    )
    with pytest.raises(ForgeError, match="signed"):
        kernel.transition(MissionState.INITIALIZING, evidence=forged_evidence)
    forged_grant = AuthorityGrant(Authority.A3, ActionKind.PROTECTED, "scope", "OWNER", "forged")
    with pytest.raises(ForgeError, match="not authentic"):
        kernel.authorize(ActionKind.PROTECTED, forged_grant, scope_digest="scope")
    with pytest.raises(ForgeError, match="identity and digest"):
        TransitionEvidence.issue(
            "",
            "validator",
            repository.digest,
            None,
            MissionState.INITIALIZING.value,
            signing_key=EVIDENCE_KEY,
        )
    with pytest.raises(ForgeError, match="identity and digest"):
        TransitionEvidence(
            EvidenceStatus.PRESENT,
            "",
            "validator",
            repository.digest,
            None,
            MissionState.INITIALIZING.value,
            "signed",
        )
    with pytest.raises(ForgeError, match="present"):
        kernel.transition(MissionState.INITIALIZING)


def test_candidate_is_repository_bound_and_immutable(repository):
    candidate = CandidateIdentity(repository.digest, "abc", "tree", "FORGE-TK-001")
    kernel = kernel_for(repository)
    kernel.bind_candidate(candidate, repository)
    with pytest.raises(ForgeError, match="different repository"):
        kernel.bind_candidate(dataclasses.replace(candidate, repository_digest="other"), repository)
    other_repository = dataclasses.replace(repository, remote="https://example.test/other")
    other_candidate = dataclasses.replace(candidate, repository_digest=other_repository.digest)
    with pytest.raises(ForgeError, match="different repository"):
        kernel.bind_candidate(other_candidate, other_repository)
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.revision = "changed"


def test_candidate_bound_validation_invalidates_after_candidate_change(repository):
    candidate = CandidateIdentity(repository.digest, "abc", "tree", "FORGE-TK-001")
    validation = CandidateValidation.issue(
        candidate.digest, "PASS", "evidence", "auditor", "builder", signing_key=AUDITOR_KEY
    )
    assert validation.is_valid_for(candidate)
    changed = dataclasses.replace(candidate, revision="new-revision")
    assert not validation.is_valid_for(changed)


def test_receipt_mutation_and_corruption_are_detected(repository):
    kernel = kernel_for(repository)
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    original = kernel.ledger.receipts[0]
    with pytest.raises(TypeError):
        original.payload["tampered"] = True
    changed = dataclasses.replace(original, payload={"tampered": True})
    with pytest.raises(ForgeError, match="content"):
        Ledger([changed])
    with pytest.raises(ForgeError, match="append-only"):
        Ledger(
            [
                original,
                Receipt.create(2, "STATE_TRANSITION", "INITIALIZING", "PLANNING", {}, "wrong"),
            ]
        )


def test_ledger_canonicalizes_direct_receipt_instances():
    mutable = {}
    canonical = Receipt.create(1, "EVENT", None, None, mutable, None)
    direct = Receipt(1, "EVENT", None, None, mutable, None, canonical.receipt_hash)
    ledger = Ledger([direct])
    mutable["tampered"] = True
    ledger.verify()
    assert "tampered" not in ledger.receipts[0].payload


def test_malformed_persisted_record_fails_closed():
    with pytest.raises(ForgeError, match="Persisted record"):
        Ledger.from_records([{"not": "a receipt"}], checkpoint=LedgerCheckpoint(1, "expected"))


def test_receipts_round_trip_through_persisted_records(repository):
    kernel = kernel_for(repository)
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    records = kernel.ledger.to_records()
    restored = Ledger.from_records(records, checkpoint=kernel.ledger.checkpoint)
    assert restored.replay() is MissionState.INITIALIZING

    with pytest.raises(ForgeError, match="truncated"):
        Ledger.from_records(records[:-1], checkpoint=kernel.ledger.checkpoint)

    with pytest.raises(ForgeError, match="checkpoint"):
        kernel_for(repository, ledger=Ledger())
    empty = Ledger(stream_id=MISSION_ID)
    assert kernel_for(repository, ledger=empty, ledger_checkpoint=empty.checkpoint).state is None


def test_replay_mismatch_fails_closed(repository):
    payload = {
        "repository_digest": repository.digest,
        "mission_id": MISSION_ID,
        "evidence": dataclasses.asdict(present(repository, MissionState.INITIALIZING, "PLANNING")),
    }
    receipt = Receipt.create(1, "STATE_TRANSITION", "PLANNING", "INITIALIZING", payload, None)
    ledger = Ledger([receipt], stream_id=MISSION_ID)
    with pytest.raises(ForgeError, match="replay"):
        kernel_for(repository, ledger=ledger, ledger_checkpoint=ledger.checkpoint)


def test_hash_consistent_illegal_transition_fails_replay(repository):
    first = Receipt.create(
        1, "STATE_TRANSITION", None, "INITIALIZING", transition_payload(repository), None
    )
    illegal_payload = {
        "repository_digest": repository.digest,
        "mission_id": MISSION_ID,
        "evidence": dataclasses.asdict(present(repository, MissionState.COMPLETE, "INITIALIZING")),
    }
    illegal = Receipt.create(
        2, "STATE_TRANSITION", "INITIALIZING", "COMPLETE", illegal_payload, first.receipt_hash
    )
    ledger = Ledger([first, illegal], stream_id=MISSION_ID)
    with pytest.raises(ForgeError, match="Illegal replay transition"):
        kernel_for(repository, ledger=ledger, ledger_checkpoint=ledger.checkpoint)


def test_discovery_acceptance_requires_spec_evolution(repository):
    kernel = kernel_for(repository)
    for state in (
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
        MissionState.TESTING,
        MissionState.AUDITING,
        MissionState.DISCOVERY_REVIEW,
        MissionState.ACCEPTED,
    ):
        kernel.transition(state, evidence=evidence_for(kernel, repository, state))
    with pytest.raises(ForgeError, match="cannot transition"):
        kernel.transition(
            MissionState.REPLANNING,
            evidence=evidence_for(kernel, repository, MissionState.REPLANNING),
        )
    discovery = DiscoveryAuthorization(
        "discovery", "evidence", "Validated specification change", "Impacted requirements reviewed"
    )
    kernel.transition(
        MissionState.SPEC_EVOLUTION,
        evidence=evidence_for(kernel, repository, MissionState.SPEC_EVOLUTION),
        authority_grant=grant(
            ActionKind.SPECIFICATION_EVOLUTION, discovery.record_digest, Authority.A2
        ),
        discovery=discovery,
    )
    kernel.transition(
        MissionState.REPLANNING, evidence=evidence_for(kernel, repository, MissionState.REPLANNING)
    )


def test_specification_evolution_requires_a2_and_discovery_record(repository):
    kernel = kernel_for(repository)
    for state in (
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
        MissionState.TESTING,
        MissionState.AUDITING,
        MissionState.DISCOVERY_REVIEW,
        MissionState.ACCEPTED,
    ):
        kernel.transition(state, evidence=evidence_for(kernel, repository, state))
    discovery = DiscoveryAuthorization(
        "discovery", "evidence", "Validated specification change", "Impacted requirements reviewed"
    )
    with pytest.raises(ForgeError, match="higher authority"):
        kernel.transition(
            MissionState.SPEC_EVOLUTION,
            evidence=evidence_for(kernel, repository, MissionState.SPEC_EVOLUTION),
            discovery=discovery,
            authority_grant=grant(
                ActionKind.SPECIFICATION_EVOLUTION, discovery.record_digest, Authority.A1
            ),
        )
    with pytest.raises(ForgeError, match="Discovery Record"):
        kernel.transition(
            MissionState.SPEC_EVOLUTION,
            evidence=evidence_for(kernel, repository, MissionState.SPEC_EVOLUTION),
            authority_grant=grant(
                ActionKind.SPECIFICATION_EVOLUTION, discovery.record_digest, Authority.A2
            ),
        )


def test_merging_requires_exact_independent_candidate_pass(repository):
    kernel = kernel_for(
        repository,
        auditor_verification_keys={"auditor": AUDITOR_KEY},
        trusted_builder_contexts=frozenset({"builder"}),
    )
    for state in (
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
        MissionState.TESTING,
        MissionState.AUDITING,
    ):
        kernel.transition(state, evidence=evidence_for(kernel, repository, state))
    candidate = CandidateIdentity(repository.digest, "abc", "tree", "FORGE-TK-001")
    with pytest.raises(ForgeError, match="exact candidate"):
        kernel.transition(
            MissionState.MERGING, evidence=evidence_for(kernel, repository, MissionState.MERGING)
        )
    self_review = CandidateValidation.issue(
        candidate.digest, "PASS", "evidence", "same", "same", signing_key=AUDITOR_KEY
    )
    with pytest.raises(ForgeError, match="independent PASS"):
        kernel.transition(
            MissionState.MERGING,
            evidence=evidence_for(kernel, repository, MissionState.MERGING),
            candidate=candidate,
            validation=self_review,
        )
    invented_auditor = CandidateValidation.issue(
        candidate.digest, "PASS", "evidence", "invented", "builder", signing_key=AUDITOR_KEY
    )
    with pytest.raises(ForgeError, match="independent PASS"):
        kernel.transition(
            MissionState.MERGING,
            evidence=evidence_for(kernel, repository, MissionState.MERGING),
            candidate=candidate,
            validation=invented_auditor,
        )
    forged_signature = CandidateValidation(
        candidate.digest, "PASS", "evidence", "auditor", "builder", "forged"
    )
    with pytest.raises(ForgeError, match="independent PASS"):
        kernel.transition(
            MissionState.MERGING,
            evidence=evidence_for(kernel, repository, MissionState.MERGING),
            candidate=candidate,
            validation=forged_signature,
        )


def test_merge_replay_rejects_candidate_without_repository_identity(repository):
    kernel = kernel_for(
        repository,
        auditor_verification_keys={"auditor": AUDITOR_KEY},
        trusted_builder_contexts=frozenset({"builder"}),
    )
    candidate = CandidateIdentity(repository.digest, "abc", "tree", "FORGE-TK-001")
    validation = CandidateValidation.issue(
        candidate.digest, "PASS", "evidence", "auditor", "builder", signing_key=AUDITOR_KEY
    )
    for state in (
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
        MissionState.TESTING,
        MissionState.AUDITING,
    ):
        kernel.transition(state, evidence=evidence_for(kernel, repository, state))
    kernel.transition(
        MissionState.MERGING,
        evidence=evidence_for(kernel, repository, MissionState.MERGING),
        candidate=candidate,
        validation=validation,
    )
    records = kernel.ledger.to_records()
    records[-1]["payload"]["candidate"]["repository_digest"] = "wrong"
    rebuilt = Receipt.create(
        records[-1]["sequence"],
        records[-1]["event"],
        records[-1]["state_before"],
        records[-1]["state_after"],
        records[-1]["payload"],
        records[-1]["previous_hash"],
    )
    records[-1]["receipt_hash"] = rebuilt.receipt_hash
    with pytest.raises(ForgeError, match="exact candidate-bound"):
        Ledger.from_records(records, checkpoint=checkpoint_for(records)).replay()


def test_kernel_state_is_read_only(repository):
    kernel = kernel_for(repository)
    with pytest.raises(AttributeError):
        kernel.state = MissionState.COMPLETE
    with pytest.raises(AttributeError):
        kernel.repository = dataclasses.replace(repository, remote="https://example.test/other")


def test_kernel_ledger_is_detached_and_read_only(repository):
    kernel = kernel_for(repository)
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    external = kernel.ledger
    forged = Receipt.create(
        2,
        "STATE_TRANSITION",
        "INITIALIZING",
        "UNDERSTANDING",
        transition_payload(repository, "forged-external"),
        external.receipts[-1].receipt_hash,
    )
    external.append(forged)
    assert kernel.state is MissionState.INITIALIZING
    assert len(kernel.ledger.receipts) == 1
    with pytest.raises(AttributeError):
        kernel.ledger = external


def test_unknown_mission_ledger_event_fails_closed(repository):
    receipt = Receipt.create(
        1,
        "STATE_TRANSITION_V2",
        None,
        "INITIALIZING",
        transition_payload(repository),
        None,
    )
    ledger = Ledger([receipt], stream_id=MISSION_ID)
    with pytest.raises(ForgeError, match="Unrecognized mission ledger event"):
        kernel_for(repository, ledger=ledger, ledger_checkpoint=ledger.checkpoint)


def test_persisted_mission_receipts_are_repository_bound(repository):
    kernel = kernel_for(repository)
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    other = dataclasses.replace(repository, remote="https://example.test/other")
    with pytest.raises(ForgeError, match="different repository"):
        kernel_for(other, ledger=kernel.ledger, ledger_checkpoint=kernel.ledger.checkpoint)


def test_ambiguous_restart_is_unknown(repository):
    kernel = kernel_for(repository)
    kernel.transition(
        MissionState.INITIALIZING,
        evidence=evidence_for(kernel, repository, MissionState.INITIALIZING),
    )
    ambiguous = ReconciliationEvidence.issue(
        EvidenceStatus.AMBIGUOUS,
        EffectDisposition.UNKNOWN,
        "effect-1",
        "ambiguous-observation",
        "validator",
        repository.digest,
        signing_key=EVIDENCE_KEY,
    )
    assert (
        kernel.reconcile_interrupted(effect_digest="effect-1", evidence=ambiguous)
        is ReconciliationStatus.UNKNOWN
    )
    assert len(kernel.ledger.receipts) == 1

    completed = ReconciliationEvidence.issue(
        EvidenceStatus.PRESENT,
        EffectDisposition.COMPLETED,
        "effect-1",
        "provider-confirmation",
        "validator",
        repository.digest,
        signing_key=EVIDENCE_KEY,
    )
    with pytest.raises(ForgeError, match="effect-bound"):
        kernel.reconcile_interrupted(effect_digest="effect-2", evidence=completed)
    assert (
        kernel.reconcile_interrupted(effect_digest="effect-1", evidence=completed)
        is ReconciliationStatus.EFFECT_COMPLETED
    )
    assert kernel.ledger.receipts[-1].event == "INTERRUPTED_EFFECT_RECONCILIATION"
    assert kernel.ledger.replay() is MissionState.INITIALIZING
    assert (
        kernel_for(
            repository, ledger=kernel.ledger, ledger_checkpoint=kernel.ledger.checkpoint
        ).state
        is MissionState.INITIALIZING
    )

    retryable = ReconciliationEvidence.issue(
        EvidenceStatus.PRESENT,
        EffectDisposition.NOT_STARTED,
        "effect-2",
        "provider-confirmation-2",
        "validator",
        repository.digest,
        signing_key=EVIDENCE_KEY,
    )
    assert (
        kernel.reconcile_interrupted(effect_digest="effect-2", evidence=retryable)
        is ReconciliationStatus.SAFE_TO_RETRY
    )

    forged = dataclasses.replace(completed, evidence_digest="forged")
    with pytest.raises(ForgeError, match="not authentic"):
        kernel.reconcile_interrupted(effect_digest="effect-1", evidence=forged)
