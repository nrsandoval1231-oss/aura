import dataclasses

import pytest

from forge import (
    AgentRole,
    Assumption,
    AuditReport,
    Authority,
    BuilderHandoff,
    BuildPacket,
    CandidateIdentity,
    CandidateInspection,
    ContextIdentity,
    DiscoveryVerdict,
    EvidenceReceipt,
    ExecutionLoop,
    FinishContract,
    ForgeError,
    ImplementationVerdict,
    LoopState,
    NorthStar,
    OwnerAuthorization,
    ProductBrain,
    RepositoryIdentity,
    Requirement,
    RequirementStatus,
)
from forge.execution_loop import (
    _audit_report_payload_digest,
    _builder_handoff_payload_digest,
    _candidate_inspection_payload_digest,
    _digest,
)
from forge.trust_kernel import ActionKind, AuthorityGrant

ARCHITECT_KEY = b"a" * 32
BUILDER_KEY = b"b" * 32
AUDITOR_KEY = b"c" * 32
GOVERNOR_KEY = b"g" * 32
OWNER_KEY = b"product-owner-key"
LOOP_ID = "loop-instance-001"


def owner_grant(product: ProductBrain, event: str, data: dict) -> AuthorityGrant:
    scope = product.protected_scope_digest(event, data)
    return AuthorityGrant.issue(
        Authority.A3, ActionKind.PROTECTED, scope, "OWNER", signing_key=OWNER_KEY
    )


def initialize_product() -> ProductBrain:
    product = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    north_star = NorthStar("Build safely", "OWNER")
    product.ingest_north_star(
        north_star,
        authority=Authority.A3,
        authority_grant=owner_grant(product, "NORTH_STAR_INGESTED", dataclasses.asdict(north_star)),
    )
    contract = FinishContract(("verified candidate",))
    product.set_finish_contract(
        contract,
        authority=Authority.A3,
        authority_grant=owner_grant(product, "FINISH_CONTRACT_SET", dataclasses.asdict(contract)),
    )
    return product


@pytest.fixture
def repository():
    return RepositoryIdentity("https://example.test/repo", "base", "C:/repo", "main")


@pytest.fixture
def brain():
    product = initialize_product()
    product.add_requirement(
        Requirement("R-001", 1, "Implement feature", "PRD"), authority=Authority.A2
    )
    product.transition_requirement("R-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    return product


def trusted_contexts():
    return {
        AgentRole.ARCHITECT: {"architect-context": ARCHITECT_KEY, "architect": ARCHITECT_KEY},
        AgentRole.BUILDER: {"builder-context": BUILDER_KEY},
        AgentRole.AUDITOR: {"auditor-context": AUDITOR_KEY},
        AgentRole.GOVERNOR: {"repository-inspector": GOVERNOR_KEY},
    }


def packet(repository, brain):
    base = CandidateIdentity(repository.digest, "base", "tree-base", "FORGE-LOOP-001")
    return BuildPacket(
        "FORGE-LOOP-001",
        "Implement one feature",
        ("R-001",),
        ("src/feature/feature.py", "tests/feature/test_feature.py"),
        ("src/governor/**",),
        ("behavioral test",),
        ("test_receipt", "diff_receipt"),
        (),
        (),
        "LOW",
        Authority.A2,
        2,
        base,
        brain.specification_hash,
    )


def packet_scope(build_packet):
    return OwnerAuthorization.create(
        build_packet, owner_ref="scope", evidence_digest="scope"
    ).scope_digest


def architect_context(build_packet, digest="architect-context"):
    payload_digest = packet_scope(build_packet)
    return ContextIdentity.issue(
        AgentRole.ARCHITECT,
        digest,
        "REGISTER_PACKET",
        payload_digest,
        payload_digest,
        LOOP_ID,
        signing_key=ARCHITECT_KEY,
    )


def handoff(repository):
    candidate = CandidateIdentity(
        repository.digest, "candidate", "tree-candidate", "FORGE-LOOP-001"
    )
    placeholder = ContextIdentity.issue(
        AgentRole.BUILDER,
        "builder-context",
        "BUILDER_HANDOFF",
        candidate.digest,
        "placeholder",
        LOOP_ID,
        signing_key=BUILDER_KEY,
    )
    claim = BuilderHandoff(
        "FORGE-LOOP-001", candidate, placeholder, "Implemented feature", ("pytest",), ("OBS-001",)
    )
    context = ContextIdentity.issue(
        AgentRole.BUILDER,
        "builder-context",
        "BUILDER_HANDOFF",
        candidate.digest,
        _builder_handoff_payload_digest(claim),
        LOOP_ID,
        signing_key=BUILDER_KEY,
    )
    return dataclasses.replace(claim, context=context)


def inspection(repository):
    candidate = CandidateIdentity(
        repository.digest, "candidate", "tree-candidate", "FORGE-LOOP-001"
    )
    base = CandidateIdentity(repository.digest, "base", "tree-base", "FORGE-LOOP-001")
    evidence = (
        EvidenceReceipt(
            "test_receipt", candidate.digest, ImplementationVerdict.PASS, "test-digest"
        ),
        EvidenceReceipt(
            "diff_receipt", candidate.digest, ImplementationVerdict.PASS, "diff-digest"
        ),
    )
    placeholder = ContextIdentity.issue(
        AgentRole.GOVERNOR,
        "repository-inspector",
        "CANDIDATE_INSPECTION",
        candidate.digest,
        "placeholder",
        LOOP_ID,
        signing_key=GOVERNOR_KEY,
    )
    claim = CandidateInspection(
        candidate.digest,
        base.digest,
        ("src/feature/feature.py", "tests/feature/test_feature.py"),
        evidence,
        placeholder,
    )
    context = ContextIdentity.issue(
        AgentRole.GOVERNOR,
        "repository-inspector",
        "CANDIDATE_INSPECTION",
        candidate.digest,
        _candidate_inspection_payload_digest(claim),
        LOOP_ID,
        signing_key=GOVERNOR_KEY,
    )
    return dataclasses.replace(claim, context=context)


def passing_audit(candidate, brain):
    placeholder = ContextIdentity.issue(
        AgentRole.AUDITOR,
        "auditor-context",
        "AUDIT",
        candidate.digest,
        "placeholder",
        LOOP_ID,
        signing_key=AUDITOR_KEY,
    )
    claim = AuditReport(
        candidate.digest,
        brain.specification_hash,
        placeholder,
        ImplementationVerdict.PASS,
        DiscoveryVerdict.OBSERVATION,
        (),
        (),
        (),
        ("OBS-001",),
        0.95,
    )
    context = ContextIdentity.issue(
        AgentRole.AUDITOR,
        "auditor-context",
        "AUDIT",
        candidate.digest,
        _audit_report_payload_digest(claim),
        LOOP_ID,
        signing_key=AUDITOR_KEY,
    )
    return dataclasses.replace(claim, context=context)


def governor_context(candidate, audit):
    payload_digest = _digest({"candidate_digest": candidate.digest, "audit_digest": audit.digest})
    return ContextIdentity.issue(
        AgentRole.GOVERNOR,
        "repository-inspector",
        "MERGE_ELIGIBILITY",
        candidate.digest,
        payload_digest,
        LOOP_ID,
        signing_key=GOVERNOR_KEY,
    )


def resign_handoff(claim: BuilderHandoff) -> BuilderHandoff:
    context = ContextIdentity.issue(
        AgentRole.BUILDER,
        "builder-context",
        "BUILDER_HANDOFF",
        claim.candidate.digest,
        _builder_handoff_payload_digest(claim),
        LOOP_ID,
        signing_key=BUILDER_KEY,
    )
    return dataclasses.replace(claim, context=context)


def resign_inspection(
    claim: CandidateInspection, *, scope_digest: str | None = None
) -> CandidateInspection:
    context = ContextIdentity.issue(
        AgentRole.GOVERNOR,
        "repository-inspector",
        "CANDIDATE_INSPECTION",
        scope_digest or claim.candidate_digest,
        _candidate_inspection_payload_digest(claim),
        LOOP_ID,
        signing_key=GOVERNOR_KEY,
    )
    return dataclasses.replace(claim, context=context)


def resign_audit(claim: AuditReport) -> AuditReport:
    context = ContextIdentity.issue(
        AgentRole.AUDITOR,
        "auditor-context",
        "AUDIT",
        claim.candidate_digest,
        _audit_report_payload_digest(claim),
        LOOP_ID,
        signing_key=AUDITOR_KEY,
    )
    return dataclasses.replace(claim, context=context)


def registered_loop(brain, repository):
    loop = ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts())
    build_packet = packet(repository, brain)
    loop.register_packet(build_packet, architect_context=architect_context(build_packet))
    return loop


def test_one_packet_reaches_governor_only_merge_eligibility(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    loop.submit_audit(passing_audit(builder_output.candidate, brain))
    eligibility = loop.mark_merge_eligible(
        governor_context=governor_context(builder_output.candidate, loop.audit),
        candidate=builder_output.candidate,
    )
    assert eligibility.authorized_by == governor_context(builder_output.candidate, loop.audit)
    assert loop.state is LoopState.MERGE_ELIGIBLE
    assert [item.event for item in loop.ledger.receipts] == [
        "BUILD_PACKET_REGISTERED",
        "CANDIDATE_REGISTERED",
        "AUDIT_RECORDED",
        "MERGE_ELIGIBILITY_GRANTED",
    ]
    assert loop.handoff.observations == ("OBS-001",)
    with pytest.raises(AttributeError):
        loop.state = LoopState.AUDITED
    with pytest.raises(AttributeError):
        loop.audit = passing_audit(builder_output.candidate, brain)


def test_packet_requires_known_active_requirement_and_clean_product_state(brain, repository):
    bad = dataclasses.replace(packet(repository, brain), requirements=("R-MISSING",))
    with pytest.raises(ForgeError, match="not active"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(bad, architect_context=architect_context(bad, "architect"))
    with pytest.raises(ForgeError, match="contradictory"):
        ExecutionLoop(
            ProductBrain(), repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            packet(repository, brain),
            architect_context=architect_context(packet(repository, brain), "architect"),
        )
    proposed = initialize_product()
    proposed.add_requirement(Requirement("R-001", 1, "Not active", "PRD"), authority=Authority.A2)
    with pytest.raises(ForgeError, match="not active"):
        ExecutionLoop(
            proposed, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            packet(repository, proposed),
            architect_context=architect_context(packet(repository, proposed), "architect"),
        )


def test_packet_requires_satisfied_requirement_dependencies(brain, repository):
    brain.add_requirement(Requirement("R-DEP", 1, "Dependency", "PRD"), authority=Authority.A2)
    brain.add_requirement(
        Requirement("R-CHILD", 1, "Child", "PRD", dependencies=("R-DEP",)), authority=Authority.A2
    )
    brain.transition_requirement("R-CHILD", RequirementStatus.ACTIVE, authority=Authority.A2)
    dependent_packet = dataclasses.replace(
        packet(repository, brain),
        requirements=("R-CHILD",),
        specification_hash=brain.specification_hash,
    )
    with pytest.raises(ForgeError, match="not satisfied"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            dependent_packet, architect_context=architect_context(dependent_packet, "architect")
        )


def test_packet_level_dependencies_and_invariants_must_be_ready(brain, repository):
    dependent = dataclasses.replace(packet(repository, brain), dependencies=("NODE-PREREQUISITE",))
    with pytest.raises(ForgeError, match="dependencies are not complete"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(dependent, architect_context=architect_context(dependent, "architect"))
    unknown_invariant = dataclasses.replace(packet(repository, brain), invariants=("INV-UNKNOWN",))
    with pytest.raises(ForgeError, match="unknown invariants"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            unknown_invariant, architect_context=architect_context(unknown_invariant, "architect")
        )


def test_packet_cannot_weaken_requirement_evidence_contract(repository):
    brain = initialize_product()
    brain.add_requirement(
        Requirement(
            "R-001", 1, "Implement feature", "PRD", evidence_required=("schema_validation",)
        ),
        authority=Authority.A2,
    )
    brain.transition_requirement("R-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    with pytest.raises(ForgeError, match="omits evidence"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            packet(repository, brain),
            architect_context=architect_context(packet(repository, brain), "architect"),
        )


def test_protected_packet_scope_requires_a3_at_registration(brain, repository):
    protected = dataclasses.replace(
        packet(repository, brain), allowed_paths=("AGENTS.md",), forbidden_paths=()
    )
    with pytest.raises(ForgeError, match="protected surfaces"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(protected, architect_context=architect_context(protected, "architect"))

    authorized = dataclasses.replace(protected, authority=Authority.A3)
    owner_authorization = OwnerAuthorization.create(
        authorized, owner_ref="OWNER-001", evidence_digest="approval-receipt"
    )
    loop = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        trusted_owner_authorizations=frozenset({owner_authorization.digest}),
    )
    loop.register_packet(
        authorized,
        architect_context=architect_context(authorized, "architect"),
        owner_authorization=owner_authorization,
    )
    assert loop.state is LoopState.PACKET_READY

    with pytest.raises(ForgeError, match="not authenticated"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            authorized,
            architect_context=architect_context(authorized, "architect"),
            owner_authorization=owner_authorization,
        )

    trust_kernel = dataclasses.replace(
        packet(repository, brain), allowed_paths=("src/forge/trust_kernel.py",), forbidden_paths=()
    )
    with pytest.raises(ForgeError, match="protected surfaces"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            trust_kernel, architect_context=architect_context(trust_kernel, "architect")
        )

    for path in (
        "src/forge/deployment.py",
        "src/forge/secrets.py",
        "src/forge/destructive_effects.py",
    ):
        owner_gated = dataclasses.replace(
            packet(repository, brain), allowed_paths=(path,), forbidden_paths=()
        )
        with pytest.raises(ForgeError, match="protected surfaces"):
            ExecutionLoop(
                brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
            ).register_packet(
                owner_gated, architect_context=architect_context(owner_gated, "architect")
            )

    for package in (
        "src/forge/deployment/**",
        "src/forge/secrets/**",
        "src/forge/destructive_effects/**",
    ):
        owner_gated = dataclasses.replace(
            packet(repository, brain), allowed_paths=(package,), forbidden_paths=()
        )
        with pytest.raises(ForgeError, match="protected surfaces"):
            ExecutionLoop(
                brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
            ).register_packet(
                owner_gated, architect_context=architect_context(owner_gated, "architect")
            )

    governor_module = dataclasses.replace(
        packet(repository, brain), allowed_paths=("src/forge/governor.py",), forbidden_paths=()
    )
    with pytest.raises(ForgeError, match="protected surfaces"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            governor_module, architect_context=architect_context(governor_module, "architect")
        )

    for top_level in ("src/policy.py", "src/authority.py", "src/evidence_ledger.py"):
        owner_gated = dataclasses.replace(
            packet(repository, brain), allowed_paths=(top_level,), forbidden_paths=()
        )
        with pytest.raises(ForgeError, match="protected surfaces"):
            ExecutionLoop(
                brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
            ).register_packet(
                owner_gated, architect_context=architect_context(owner_gated, "architect")
            )

    for governance_module in (
        "src/forge/execution_loop.py",
        "src/forge/product_brain.py",
        "src/acme/trust_kernel/core.py",
        "src/acme/north_star/model.py",
    ):
        owner_gated = dataclasses.replace(
            packet(repository, brain), allowed_paths=(governance_module,), forbidden_paths=()
        )
        with pytest.raises(ForgeError, match="protected surfaces"):
            ExecutionLoop(
                brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
            ).register_packet(
                owner_gated, architect_context=architect_context(owner_gated, "architect")
            )

    for north_star_path in ("NORTH_STAR.md", "north-star/intent.md"):
        owner_gated = dataclasses.replace(
            packet(repository, brain), allowed_paths=(north_star_path,), forbidden_paths=()
        )
        with pytest.raises(ForgeError, match="protected surfaces"):
            ExecutionLoop(
                brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
            ).register_packet(
                owner_gated, architect_context=architect_context(owner_gated, "architect")
            )

    wildcard = dataclasses.replace(
        packet(repository, brain),
        allowed_paths=("src/acme/**",),
        forbidden_paths=(),
        authority=Authority.A3,
    )
    with pytest.raises(ForgeError, match="owner authorization"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(wildcard, architect_context=architect_context(wildcard, "architect"))
    single_star = dataclasses.replace(
        packet(repository, brain),
        allowed_paths=("src/*/policy_config.json",),
        forbidden_paths=(),
        authority=Authority.A3,
    )
    with pytest.raises(ForgeError, match="owner authorization"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            single_star, architect_context=architect_context(single_star, "architect")
        )
    root_wildcard = dataclasses.replace(
        packet(repository, brain), allowed_paths=("*/core.py",), forbidden_paths=()
    )
    with pytest.raises(ForgeError, match="protected surfaces"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            root_wildcard, architect_context=architect_context(root_wildcard, "architect")
        )


def test_owner_authorization_binds_complete_packet_contract(brain, repository):
    protected = dataclasses.replace(
        packet(repository, brain),
        allowed_paths=("AGENTS.md",),
        forbidden_paths=(),
        authority=Authority.A3,
    )
    authorization = OwnerAuthorization.create(
        protected, owner_ref="OWNER-001", evidence_digest="approval-receipt"
    )
    changed_contract = dataclasses.replace(protected, objective="Different protected objective")
    loop = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        trusted_owner_authorizations=frozenset({authorization.digest}),
    )
    with pytest.raises(ForgeError, match="not bound"):
        loop.register_packet(
            changed_contract,
            architect_context=architect_context(changed_contract, "architect"),
            owner_authorization=authorization,
        )


def test_packet_authority_must_cover_declared_requirement_authority(repository):
    brain = initialize_product()
    protected_requirement = Requirement(
        "R-A3", 1, "Owner-gated work", "OWNER", authority=Authority.A3
    )
    brain.add_requirement(
        protected_requirement,
        authority=Authority.A3,
        authority_grant=owner_grant(
            brain, "REQUIREMENT_ADDED", dataclasses.asdict(protected_requirement)
        ),
    )
    transition_data = {"id": "R-A3", "target": RequirementStatus.ACTIVE.value, "evidence": []}
    brain.transition_requirement(
        "R-A3",
        RequirementStatus.ACTIVE,
        authority=Authority.A3,
        authority_grant=owner_grant(brain, "REQUIREMENT_TRANSITIONED", transition_data),
    )
    under_authorized = dataclasses.replace(
        packet(repository, brain),
        requirements=("R-A3",),
        specification_hash=brain.specification_hash,
    )
    with pytest.raises(ForgeError, match="below requirement"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            under_authorized, architect_context=architect_context(under_authorized, "architect")
        )


def test_builder_scope_and_evidence_fail_closed(brain, repository):
    loop = registered_loop(brain, repository)
    with pytest.raises(ForgeError, match="forbidden"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(
                    inspection(repository), changed_paths=("src/governor/policy.py",)
                )
            ),
        )
    with pytest.raises(ForgeError, match="missing required evidence"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(
                    inspection(repository), evidence=inspection(repository).evidence[:1]
                )
            ),
        )
    with pytest.raises(ForgeError, match="forbidden"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(
                    inspection(repository), changed_paths=("src/./governor/policy.py",)
                )
            ),
        )
    conflicting = (
        *inspection(repository).evidence,
        EvidenceReceipt(
            "test_receipt",
            handoff(repository).candidate.digest,
            ImplementationVerdict.FAIL,
            "failed-test-digest",
        ),
    )
    with pytest.raises(ForgeError, match="conflicting results"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(inspection(repository), evidence=conflicting)
            ),
        )


def test_wrong_repository_and_packet_identity_fail_closed(brain, repository):
    loop = registered_loop(brain, repository)
    wrong = dataclasses.replace(handoff(repository).candidate, repository_digest="wrong")
    wrong_claim = dataclasses.replace(handoff(repository), candidate=wrong)
    wrong_context = ContextIdentity.issue(
        AgentRole.BUILDER,
        "builder-context",
        "BUILDER_HANDOFF",
        wrong.digest,
        _builder_handoff_payload_digest(wrong_claim),
        LOOP_ID,
        signing_key=BUILDER_KEY,
    )
    with pytest.raises(ForgeError, match="different repository"):
        loop.receive_builder_handoff(
            dataclasses.replace(handoff(repository), candidate=wrong, context=wrong_context),
            inspection=inspection(repository),
        )
    with pytest.raises(ForgeError, match="not bound"):
        loop.receive_builder_handoff(
            resign_handoff(dataclasses.replace(handoff(repository), packet_id="OTHER")),
            inspection=inspection(repository),
        )
    with pytest.raises(ForgeError, match="packet base"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(inspection(repository), base_candidate_digest="wrong")
            ),
        )
    stale_evidence = dataclasses.replace(
        inspection(repository).evidence[0], candidate_digest="stale"
    )
    with pytest.raises(ForgeError, match="exact candidate"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(
                    inspection(repository),
                    evidence=(stale_evidence, *inspection(repository).evidence[1:]),
                )
            ),
        )
    with pytest.raises(ForgeError, match="not bound"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(inspection(repository), candidate_digest="wrong"),
                scope_digest=handoff(repository).candidate.digest,
            ),
        )
    forged_context = ContextIdentity.issue(
        AgentRole.GOVERNOR,
        "forged-inspector",
        "CANDIDATE_INSPECTION",
        handoff(repository).candidate.digest,
        _candidate_inspection_payload_digest(inspection(repository)),
        LOOP_ID,
        signing_key=GOVERNOR_KEY,
    )
    forged_inspector = dataclasses.replace(inspection(repository), context=forged_context)
    with pytest.raises(ForgeError, match="not authorized"):
        loop.receive_builder_handoff(handoff(repository), inspection=forged_inspector)


def test_builder_cannot_audit_and_auditor_context_must_be_independent(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    builder_audit = dataclasses.replace(
        passing_audit(builder_output.candidate, brain), context=builder_output.context
    )
    with pytest.raises(ForgeError, match="Only Auditor"):
        loop.submit_audit(builder_audit)
    forged_context = ContextIdentity.issue(
        AgentRole.AUDITOR,
        "forged-auditor",
        "AUDIT",
        builder_output.candidate.digest,
        _audit_report_payload_digest(passing_audit(builder_output.candidate, brain)),
        LOOP_ID,
        signing_key=AUDITOR_KEY,
    )
    forged = dataclasses.replace(
        passing_audit(builder_output.candidate, brain), context=forged_context
    )
    with pytest.raises(ForgeError, match="not authorized"):
        loop.submit_audit(forged)


def test_signed_context_cannot_authorize_modified_audit_payload(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    signed = passing_audit(builder_output.candidate, brain)
    tampered = dataclasses.replace(signed, evidence_gaps=("removed after signing",))
    with pytest.raises(ForgeError, match="not authorized"):
        loop.submit_audit(tampered)


def test_trusted_builder_and_auditor_contexts_must_be_disjoint(brain, repository):
    conflicting = trusted_contexts()
    conflicting[AgentRole.AUDITOR] = {"builder-context": AUDITOR_KEY}
    with pytest.raises(ForgeError, match="must be disjoint"):
        ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=conflicting)

    architect_conflict = trusted_contexts()
    architect_conflict[AgentRole.ARCHITECT] = {"builder-context": ARCHITECT_KEY}
    with pytest.raises(ForgeError, match="must be disjoint"):
        ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=architect_conflict)

    auditor_governor_conflict = trusted_contexts()
    auditor_governor_conflict[AgentRole.GOVERNOR] = {"auditor-context": GOVERNOR_KEY}
    with pytest.raises(ForgeError, match="Auditor and Governor"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=auditor_governor_conflict
        )

    architect_auditor_conflict = trusted_contexts()
    architect_auditor_conflict[AgentRole.ARCHITECT] = {"auditor-context": ARCHITECT_KEY}
    with pytest.raises(ForgeError, match="Architect and Auditor"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=architect_auditor_conflict
        )

    shared_key = trusted_contexts()
    shared_key[AgentRole.AUDITOR] = {"auditor-context": BUILDER_KEY}
    with pytest.raises(ForgeError, match="share signing keys"):
        ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=shared_key)

    hmac_equivalent_short_keys = trusted_contexts()
    hmac_equivalent_short_keys[AgentRole.BUILDER] = {"builder-context": b"x"}
    hmac_equivalent_short_keys[AgentRole.AUDITOR] = {"auditor-context": b"x\0"}
    with pytest.raises(ForgeError, match="exactly 32 bytes"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=hmac_equivalent_short_keys
        )


def test_loop_trust_configuration_is_read_only(brain, repository):
    contexts = trusted_contexts()
    loop = ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=contexts)
    contexts[AgentRole.BUILDER] = {"forged-builder": b"forged"}

    with pytest.raises(AttributeError):
        _ = loop.trusted_contexts
    with pytest.raises(AttributeError):
        loop.trusted_owner_authorizations = frozenset({"forged-authorization"})
    with pytest.raises(AttributeError):
        loop.product_brain = ProductBrain()


def test_context_credentials_are_action_and_scope_bound(brain, repository):
    original = packet(repository, brain)
    changed = dataclasses.replace(original, objective="Different packet")
    loop = ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts())
    with pytest.raises(ForgeError, match="not authorized"):
        loop.register_packet(changed, architect_context=architect_context(original))


def test_path_patterns_do_not_cross_directory_separators(brain, repository):
    scoped = dataclasses.replace(
        packet(repository, brain), allowed_paths=("safe/*.txt",), forbidden_paths=()
    )
    loop = ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts())
    loop.register_packet(scoped, architect_context=architect_context(scoped))
    with pytest.raises(ForgeError, match="outside packet scope"):
        loop.receive_builder_handoff(
            handoff(repository),
            inspection=resign_inspection(
                dataclasses.replace(
                    inspection(repository), changed_paths=("safe/private/data.txt",)
                )
            ),
        )


def test_repository_root_governance_packages_require_a3(brain, repository):
    protected = dataclasses.replace(
        packet(repository, brain), allowed_paths=("governor/core.py",), forbidden_paths=()
    )
    with pytest.raises(ForgeError, match="protected surfaces"):
        ExecutionLoop(
            brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts()
        ).register_packet(
            protected,
            architect_context=architect_context(protected),
        )


def test_packet_and_audit_collections_are_canonicalized(brain, repository):
    requirements = ["R-001"]
    allowed_paths = ["src/feature/feature.py"]
    mutable_packet = BuildPacket(
        "FORGE-LOOP-001",
        "Implement one feature",
        requirements,
        allowed_paths,
        [],
        ["behavioral test"],
        ["test_receipt"],
        [],
        [],
        "LOW",
        Authority.A2,
        2,
        CandidateIdentity(repository.digest, "base", "tree-base", "FORGE-LOOP-001"),
        brain.specification_hash,
    )
    requirements.append("R-FORGED")
    allowed_paths.append("src/forge/governor.py")
    assert mutable_packet.requirements == ("R-001",)
    assert mutable_packet.allowed_paths == ("src/feature/feature.py",)

    evidence_gaps = ["missing proof"]
    mutable_audit = AuditReport(
        "candidate",
        brain.specification_hash,
        ContextIdentity.issue(
            AgentRole.AUDITOR,
            "auditor-context",
            "AUDIT",
            "candidate",
            "placeholder",
            LOOP_ID,
            signing_key=AUDITOR_KEY,
        ),
        ImplementationVerdict.PASS,
        DiscoveryVerdict.NONE,
        [],
        evidence_gaps,
        [],
        [],
        0.9,
    )
    evidence_gaps.clear()
    assert mutable_audit.evidence_gaps == ("missing proof",)


def test_candidate_mutation_invalidates_audit(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    loop.submit_audit(passing_audit(builder_output.candidate, brain))
    changed = dataclasses.replace(builder_output.candidate, revision="changed")
    assert not loop.audit_is_current(changed)
    with pytest.raises(ForgeError, match="changed after audit"):
        loop.mark_merge_eligible(
            governor_context=governor_context(changed, loop.audit), candidate=changed
        )


def test_only_governor_can_mark_merge_eligible(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    loop.submit_audit(passing_audit(builder_output.candidate, brain))
    with pytest.raises(ForgeError, match="Only Governor"):
        loop.mark_merge_eligible(
            governor_context=passing_audit(builder_output.candidate, brain).context,
            candidate=builder_output.candidate,
        )
    with pytest.raises(ForgeError, match="not authorized"):
        loop.mark_merge_eligible(
            governor_context=ContextIdentity.issue(
                AgentRole.GOVERNOR,
                "forged-governor",
                "MERGE_ELIGIBILITY",
                builder_output.candidate.digest,
                _digest(
                    {
                        "candidate_digest": builder_output.candidate.digest,
                        "audit_digest": loop.audit.digest,
                    }
                ),
                LOOP_ID,
                signing_key=GOVERNOR_KEY,
            ),
            candidate=builder_output.candidate,
        )


def test_material_discovery_requires_review_before_merge_eligibility(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    material = resign_audit(
        dataclasses.replace(
            passing_audit(builder_output.candidate, brain), discovery_verdict="MATERIAL_DISCOVERY"
        )
    )
    loop.submit_audit(material)
    with pytest.raises(ForgeError, match="Material discovery"):
        loop.mark_merge_eligible(
            governor_context=governor_context(builder_output.candidate, loop.audit),
            candidate=builder_output.candidate,
        )


def test_product_state_change_invalidates_audit(brain, repository):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    loop.submit_audit(passing_audit(builder_output.candidate, brain))
    brain.add_assumption(
        Assumption("A-NEW", "Changed after audit", "OBS", 0.5), authority=Authority.A2
    )
    assert not loop.audit_is_current(builder_output.candidate)
    with pytest.raises(ForgeError, match="specification changed"):
        loop.mark_merge_eligible(
            governor_context=governor_context(builder_output.candidate, loop.audit),
            candidate=builder_output.candidate,
        )


@pytest.mark.parametrize("verdict", [ImplementationVerdict.FAIL, ImplementationVerdict.UNKNOWN])
def test_fail_or_unknown_audit_blocks_merge_eligibility(brain, repository, verdict):
    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    loop.submit_audit(
        resign_audit(
            dataclasses.replace(
                passing_audit(builder_output.candidate, brain), implementation_verdict=verdict
            )
        )
    )
    with pytest.raises(ForgeError, match="cannot become merge eligible"):
        loop.mark_merge_eligible(
            governor_context=governor_context(builder_output.candidate, loop.audit),
            candidate=builder_output.candidate,
        )


# ---------------------------------------------------------------------------
# Budget enforcement (FORGE-GOV-001).
#
# The Finish Contract names budgets among what the Governor enforces. Until this,
# `BuildPacket.retry_limit` was declared by every packet and read by nothing, so a
# packet could declare two retries and take twenty.
# ---------------------------------------------------------------------------


def test_the_attempt_budget_refuses_a_candidate_once_it_is_spent(brain, repository):
    """A retry is a new loop, so the Governor's ledger is what spans the attempts.

    A budget owned by a single loop could never be exhausted: `register_packet`
    refuses a second packet and nothing returns the state to PACKET_READY, so one
    loop accepts at most one candidate. That is why the Finish Contract puts budgets
    on the Governor.
    """
    from forge.governor import Budget, BudgetDimension, BudgetLedger

    build_packet = packet(repository, brain)
    governor_budget = BudgetLedger(build_packet.id, Budget(attempts=1))

    first = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        budget_ledger=governor_budget,
    )
    first.register_packet(build_packet, architect_context=architect_context(build_packet))
    first.receive_builder_handoff(handoff(repository), inspection=inspection(repository))
    assert governor_budget.spent(BudgetDimension.ATTEMPTS) == 1

    # Same loop_id, because the test helpers sign contexts against it; what is being
    # exercised is the ledger spanning two loop instances, not loop identity.
    retry = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        budget_ledger=governor_budget,
    )
    retry.register_packet(build_packet, architect_context=architect_context(build_packet))
    with pytest.raises(ForgeError, match="budget exhausted"):
        retry.receive_builder_handoff(handoff(repository), inspection=inspection(repository))
    assert governor_budget.spent(BudgetDimension.ATTEMPTS) == 1


def test_a_budget_and_a_ledger_together_are_refused(brain, repository):
    """Two sources of one limit is how a limit stops being one."""
    from forge.governor import Budget, BudgetLedger

    with pytest.raises(ForgeError, match="not both"):
        ExecutionLoop(
            brain,
            repository,
            loop_id=LOOP_ID,
            trusted_contexts=trusted_contexts(),
            budget=Budget(attempts=2),
            budget_ledger=BudgetLedger("FORGE-LOOP-001", Budget(attempts=5)),
        )


def test_another_packets_budget_cannot_be_charged(brain, repository):
    from forge.governor import Budget, BudgetLedger

    loop = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        budget_ledger=BudgetLedger("FORGE-OTHER-001", Budget(attempts=5)),
    )
    build_packet = packet(repository, brain)
    loop.register_packet(build_packet, architect_context=architect_context(build_packet))
    with pytest.raises(ForgeError, match="BUDGET_PACKET_MISMATCH|belongs to"):
        loop.receive_builder_handoff(handoff(repository), inspection=inspection(repository))


def test_the_packet_retry_limit_becomes_the_attempt_budget(brain, repository):
    """A declared retry budget now bounds something without extra configuration."""
    from forge.governor import BudgetDimension

    loop = registered_loop(brain, repository)
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))

    ledger = loop.budget_ledger
    assert ledger is not None
    # retry_limit counts retries, so the budget is the first attempt plus the retries.
    assert ledger.budget.attempts == packet(repository, brain).retry_limit + 1
    assert ledger.spent(BudgetDimension.ATTEMPTS) == 1


def test_a_refused_handoff_does_not_consume_a_retry(brain, repository):
    """A forged context is a protocol error, not a try at the work.

    Charging it would let a malformed client burn a packet's retries without ever
    attempting the work, and would make every validation path budget-sensitive.
    """
    from forge.governor import Budget, BudgetDimension

    loop = ExecutionLoop(
        brain,
        repository,
        loop_id=LOOP_ID,
        trusted_contexts=trusted_contexts(),
        budget=Budget(attempts=1),
    )
    build_packet = packet(repository, brain)
    loop.register_packet(build_packet, architect_context=architect_context(build_packet))

    forged = dataclasses.replace(
        handoff(repository),
        context=dataclasses.replace(handoff(repository).context, issuer_signature="forged"),
    )
    with pytest.raises(ForgeError):
        loop.receive_builder_handoff(forged, inspection=inspection(repository))

    # The budget is untouched, so the real attempt still fits.
    builder_output = handoff(repository)
    loop.receive_builder_handoff(builder_output, inspection=inspection(repository))
    assert loop.budget_ledger.spent(BudgetDimension.ATTEMPTS) == 1


def test_a_loop_without_a_budget_or_retry_limit_has_no_ledger(brain, repository):
    """Unlimited stays explicit: no budget means no ledger, not a zeroed one."""
    loop = ExecutionLoop(brain, repository, loop_id=LOOP_ID, trusted_contexts=trusted_contexts())
    build_packet = dataclasses.replace(packet(repository, brain), retry_limit=0)
    loop.register_packet(build_packet, architect_context=architect_context(build_packet))
    loop.receive_builder_handoff(handoff(repository), inspection=inspection(repository))
    assert loop.budget_ledger is None
