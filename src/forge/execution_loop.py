"""Deterministic contracts for one Architect → Builder → Auditor loop."""

from __future__ import annotations

import hashlib
import hmac
import json
import posixpath
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from .governor import Budget, BudgetDimension, BudgetLedger, SpendOutcome
from .paths import path_matches as _path_pattern_matches
from .policy import pattern_reaches_protected_surface, requires_owner_authority
from .product_brain import ProductBrain, RequirementStatus
from .trust_kernel import (
    Authority,
    CandidateIdentity,
    ForgeError,
    Ledger,
    Receipt,
    RepositoryIdentity,
)


class AgentRole(StrEnum):
    ARCHITECT = "ARCHITECT"
    BUILDER = "BUILDER"
    AUDITOR = "AUDITOR"
    GOVERNOR = "GOVERNOR"


class ImplementationVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class DiscoveryVerdict(StrEnum):
    NONE = "NONE"
    OBSERVATION = "OBSERVATION"
    MATERIAL_DISCOVERY = "MATERIAL_DISCOVERY"


class LoopState(StrEnum):
    EMPTY = "EMPTY"
    PACKET_READY = "PACKET_READY"
    CANDIDATE_READY = "CANDIDATE_READY"
    AUDITED = "AUDITED"
    MERGE_ELIGIBLE = "MERGE_ELIGIBLE"


@dataclass(frozen=True, slots=True)
class ContextIdentity:
    role: AgentRole
    digest: str
    action: str
    scope_digest: str
    payload_digest: str
    loop_id: str
    issuer_signature: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.digest,
                self.action,
                self.scope_digest,
                self.payload_digest,
                self.loop_id,
                self.issuer_signature,
            )
        ):
            raise ForgeError(
                "INVALID_CONTEXT_IDENTITY",
                "Signed context identity, action, payload, loop, and scope are required",
            )

    @classmethod
    def issue(
        cls,
        role: AgentRole,
        digest: str,
        action: str,
        scope_digest: str,
        payload_digest: str,
        loop_id: str,
        *,
        signing_key: bytes,
    ) -> ContextIdentity:
        body = {
            "role": role.value,
            "digest": digest,
            "action": action,
            "scope_digest": scope_digest,
            "payload_digest": payload_digest,
            "loop_id": loop_id,
        }
        return cls(
            role, digest, action, scope_digest, payload_digest, loop_id, _sign(body, signing_key)
        )


@dataclass(frozen=True, slots=True)
class BuildPacket:
    id: str
    objective: str
    requirements: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    acceptance: tuple[str, ...]
    evidence_required: tuple[str, ...]
    dependencies: tuple[str, ...]
    invariants: tuple[str, ...]
    risk: str
    authority: Authority
    retry_limit: int
    base_candidate: CandidateIdentity
    specification_hash: str

    def __post_init__(self) -> None:
        for field_name in (
            "requirements",
            "allowed_paths",
            "forbidden_paths",
            "acceptance",
            "evidence_required",
            "dependencies",
            "invariants",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not all(
            (
                self.id,
                self.objective,
                self.requirements,
                self.allowed_paths,
                self.acceptance,
                self.evidence_required,
                self.specification_hash,
            )
        ):
            raise ForgeError("INVALID_BUILD_PACKET", "Build Packet required fields cannot be empty")
        if self.retry_limit < 0:
            raise ForgeError("INVALID_BUILD_PACKET", "Retry limit cannot be negative")
        if self.risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ForgeError(
                "INVALID_BUILD_PACKET", "Build Packet risk must be LOW, MEDIUM, HIGH, or CRITICAL"
            )


@dataclass(frozen=True, slots=True)
class BuilderHandoff:
    packet_id: str
    candidate: CandidateIdentity
    context: ContextIdentity
    implementation_summary: str
    tests_attempted: tuple[str, ...]
    observations: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tests_attempted", tuple(self.tests_attempted))
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "blockers", tuple(self.blockers))


@dataclass(frozen=True, slots=True)
class AuditReport:
    candidate_digest: str
    specification_hash: str
    context: ContextIdentity
    implementation_verdict: ImplementationVerdict
    discovery_verdict: DiscoveryVerdict
    findings: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    invariant_findings: tuple[str, ...]
    discovery_candidates: tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "implementation_verdict", ImplementationVerdict(self.implementation_verdict)
        )
        object.__setattr__(self, "discovery_verdict", DiscoveryVerdict(self.discovery_verdict))
        for field_name in (
            "findings",
            "evidence_gaps",
            "invariant_findings",
            "discovery_candidates",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if not self.specification_hash:
            raise ForgeError("INVALID_AUDIT_REPORT", "Audit specification hash is required")
        if not 0 <= self.confidence <= 1:
            raise ForgeError(
                "INVALID_AUDIT_REPORT", "Audit confidence must be between zero and one"
            )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class MergeEligibility:
    candidate_digest: str
    audit_digest: str
    authorized_by: ContextIdentity


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    kind: str
    candidate_digest: str
    result: ImplementationVerdict
    evidence_digest: str

    def __post_init__(self) -> None:
        if not all((self.kind, self.candidate_digest, self.evidence_digest)):
            raise ForgeError(
                "INVALID_EVIDENCE_RECEIPT", "Evidence receipt identity fields are required"
            )


@dataclass(frozen=True, slots=True)
class CandidateInspection:
    candidate_digest: str
    base_candidate_digest: str
    changed_paths: tuple[str, ...]
    evidence: tuple[EvidenceReceipt, ...]
    context: ContextIdentity

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed_paths", tuple(self.changed_paths))
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True, slots=True)
class OwnerAuthorization:
    packet_id: str
    scope_digest: str
    owner_ref: str
    evidence_digest: str

    def __post_init__(self) -> None:
        if not all((self.packet_id, self.scope_digest, self.owner_ref, self.evidence_digest)):
            raise ForgeError(
                "INVALID_OWNER_AUTHORIZATION",
                "Owner authorization identity and evidence are required",
            )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    @classmethod
    def create(
        cls, packet: BuildPacket, *, owner_ref: str, evidence_digest: str
    ) -> OwnerAuthorization:
        return cls(packet.id, _packet_scope_digest(packet), owner_ref, evidence_digest)


class ExecutionLoop:
    """Governor-controlled state for a single bounded Build Packet."""

    def __init__(
        self,
        product_brain: ProductBrain,
        repository: RepositoryIdentity,
        *,
        loop_id: str,
        trusted_contexts: Mapping[AgentRole, Mapping[str, bytes]],
        trusted_owner_authorizations: frozenset[str] = frozenset(),
        completed_packet_dependencies: frozenset[str] = frozenset(),
        known_invariants: frozenset[str] = frozenset(),
        budget: Budget | None = None,
        budget_ledger: BudgetLedger | None = None,
    ):
        if not loop_id:
            raise ForgeError("INVALID_LOOP_ID", "Execution loop identity is required")
        if any(
            not isinstance(key, bytes) or len(key) != 32
            for contexts in trusted_contexts.values()
            for key in contexts.values()
        ):
            raise ForgeError(
                "INVALID_CONTEXT_KEY", "Trusted context signing keys must be exactly 32 bytes"
            )
        self._loop_id = loop_id
        self._product_brain = product_brain
        self._repository = repository
        self._context_verification_keys = {
            role: dict(keys) for role, keys in trusted_contexts.items()
        }
        self._trusted_owner_authorizations = frozenset(trusted_owner_authorizations)
        if budget is not None and budget_ledger is not None:
            raise ForgeError(
                "AMBIGUOUS_BUDGET",
                "Pass either a Budget or an existing BudgetLedger, not both: two "
                "sources of a limit is how a limit stops being one",
            )
        self._budget = budget
        # A loop handles exactly one candidate — `register_packet` refuses a second
        # packet and nothing returns the state to PACKET_READY — so a retry is a new
        # loop. A ledger owned by one loop could therefore never be exhausted, which
        # is why the Governor may pass its own and keep it across attempts. That is
        # also why the Finish Contract puts budgets on the Governor rather than here.
        self._budget_ledger: BudgetLedger | None = budget_ledger
        self._completed_packet_dependencies = frozenset(completed_packet_dependencies)
        self._known_invariants = frozenset(known_invariants) | frozenset(product_brain.invariants)
        builder_contexts = frozenset(self._context_verification_keys.get(AgentRole.BUILDER, {}))
        auditor_contexts = frozenset(self._context_verification_keys.get(AgentRole.AUDITOR, {}))
        governor_contexts = frozenset(self._context_verification_keys.get(AgentRole.GOVERNOR, {}))
        privileged_contexts = (
            frozenset(self._context_verification_keys.get(AgentRole.ARCHITECT, {}))
            | auditor_contexts
            | governor_contexts
        )
        if builder_contexts & privileged_contexts:
            raise ForgeError(
                "CONTEXT_AUTHORITY_CONFLICT",
                "Builder trusted contexts must be disjoint from Architect, Auditor, and Governor contexts",
            )
        if auditor_contexts & governor_contexts:
            raise ForgeError(
                "CONTEXT_AUTHORITY_CONFLICT",
                "Auditor and Governor trusted contexts must be disjoint",
            )
        if auditor_contexts & frozenset(
            self._context_verification_keys.get(AgentRole.ARCHITECT, {})
        ):
            raise ForgeError(
                "CONTEXT_AUTHORITY_CONFLICT",
                "Architect and Auditor trusted contexts must be disjoint",
            )
        role_keys = {
            role: set(keys.values()) for role, keys in self._context_verification_keys.items()
        }
        roles = tuple(role_keys)
        if any(
            role_keys[roles[left]] & role_keys[roles[right]]
            for left in range(len(roles))
            for right in range(left + 1, len(roles))
        ):
            raise ForgeError(
                "CONTEXT_AUTHORITY_CONFLICT", "Independent roles must not share signing keys"
            )
        self._state = LoopState.EMPTY
        self._packet: BuildPacket | None = None
        self._architect_context: ContextIdentity | None = None
        self._handoff: BuilderHandoff | None = None
        self._audit: AuditReport | None = None
        self._eligibility: MergeEligibility | None = None
        self._ledger = Ledger()

    @property
    def state(self) -> LoopState:
        return self._state

    @property
    def product_brain(self) -> ProductBrain:
        return self._product_brain

    @property
    def repository(self) -> RepositoryIdentity:
        return self._repository

    @property
    def packet(self) -> BuildPacket | None:
        return self._packet

    @property
    def architect_context(self) -> ContextIdentity | None:
        return self._architect_context

    @property
    def handoff(self) -> BuilderHandoff | None:
        return self._handoff

    @property
    def audit(self) -> AuditReport | None:
        return self._audit

    @property
    def eligibility(self) -> MergeEligibility | None:
        return self._eligibility

    @property
    def ledger(self) -> Ledger:
        return Ledger(self._ledger.receipts)

    @property
    def trusted_owner_authorizations(self) -> frozenset[str]:
        return self._trusted_owner_authorizations

    @property
    def completed_packet_dependencies(self) -> frozenset[str]:
        return self._completed_packet_dependencies

    @property
    def known_invariants(self) -> frozenset[str]:
        return self._known_invariants

    def register_packet(
        self,
        packet: BuildPacket,
        *,
        architect_context: ContextIdentity,
        owner_authorization: OwnerAuthorization | None = None,
    ) -> None:
        if self._state is not LoopState.EMPTY:
            raise ForgeError("LOOP_ALREADY_STARTED", "This loop already has a Build Packet")
        if architect_context.role is not AgentRole.ARCHITECT:
            raise ForgeError(
                "INVALID_ARCHITECT_CONTEXT", "Build Packet must originate from Architect context"
            )
        packet_digest = _packet_scope_digest(packet)
        self._require_trusted_context(
            architect_context,
            action="REGISTER_PACKET",
            scope_digest=packet_digest,
            payload_digest=packet_digest,
        )
        if packet.base_candidate.repository_digest != self._repository.digest:
            raise ForgeError(
                "WRONG_REPOSITORY", "Build Packet base belongs to a different repository"
            )
        missing_dependencies = sorted(
            set(packet.dependencies) - self._completed_packet_dependencies
        )
        if missing_dependencies:
            raise ForgeError(
                "UNREADY_PACKET_DEPENDENCY",
                "Build Packet dependencies are not complete",
                details={"missing": missing_dependencies},
            )
        unknown_invariants = sorted(set(packet.invariants) - self._known_invariants)
        if unknown_invariants:
            raise ForgeError(
                "UNKNOWN_PACKET_INVARIANT",
                "Build Packet references unknown invariants",
                details={"unknown": unknown_invariants},
            )
        self._validate_packet_authority(packet)
        requires_owner = _packet_scope_requires_a3(packet)
        contradictions = self._product_brain.contradictions()
        if contradictions:
            raise ForgeError(
                "PRODUCT_BRAIN_CONTRADICTION",
                "Build Packet cannot start from contradictory product state",
                details={"codes": [item.code for item in contradictions]},
            )
        if packet.specification_hash != self._product_brain.specification_hash:
            raise ForgeError(
                "SPECIFICATION_IDENTITY_MISMATCH",
                "Build Packet is not bound to the current specification",
            )
        work_eligible = {RequirementStatus.ACTIVE, RequirementStatus.IMPLEMENTING}
        for requirement_id in packet.requirements:
            requirement = self._product_brain.requirements.get(requirement_id)
            if requirement is None or requirement.status not in work_eligible:
                raise ForgeError(
                    "INVALID_PACKET_REQUIREMENT",
                    f"Requirement {requirement_id} is not active for work",
                )
            if int(packet.authority.value[1]) < int(requirement.authority.value[1]):
                raise ForgeError(
                    "INSUFFICIENT_AUTHORITY",
                    f"Build Packet authority is below requirement {requirement_id} authority",
                )
            missing_requirement_evidence = sorted(
                set(requirement.evidence_required) - set(packet.evidence_required)
            )
            if missing_requirement_evidence:
                raise ForgeError(
                    "WEAKENED_EVIDENCE_CONTRACT",
                    f"Build Packet omits evidence required by {requirement_id}",
                    details={"missing": missing_requirement_evidence},
                )
            requires_owner = requires_owner or requirement.authority is Authority.A3
            self._validate_requirement_dependencies(requirement_id)
        if requires_owner:
            self._validate_owner_authorization(packet, owner_authorization)
        self._packet = packet
        self._architect_context = architect_context
        self._state = LoopState.PACKET_READY
        self._record(
            "BUILD_PACKET_REGISTERED",
            {
                "packet": asdict(packet),
                "architect_context": asdict(architect_context),
                "owner_authorization": asdict(owner_authorization) if owner_authorization else None,
            },
        )

    def receive_builder_handoff(
        self, handoff: BuilderHandoff, *, inspection: CandidateInspection
    ) -> None:
        packet = self._require_packet()
        if self._state is not LoopState.PACKET_READY:
            raise ForgeError("INVALID_LOOP_STATE", "Builder handoff is not currently accepted")
        if handoff.context.role is not AgentRole.BUILDER:
            raise ForgeError(
                "INVALID_BUILDER_CONTEXT", "Candidate must originate from Builder context"
            )
        self._require_trusted_context(
            handoff.context,
            action="BUILDER_HANDOFF",
            scope_digest=handoff.candidate.digest,
            payload_digest=_builder_handoff_payload_digest(handoff),
        )
        if handoff.packet_id != packet.id or handoff.candidate.packet_id != packet.id:
            raise ForgeError(
                "PACKET_IDENTITY_MISMATCH", "Builder candidate is not bound to this packet"
            )
        if handoff.candidate.repository_digest != self._repository.digest:
            raise ForgeError(
                "WRONG_REPOSITORY", "Builder candidate belongs to a different repository"
            )
        if handoff.candidate.digest == packet.base_candidate.digest:
            raise ForgeError(
                "UNCHANGED_CANDIDATE", "Builder candidate must differ from the packet base"
            )
        if inspection.context.role is not AgentRole.GOVERNOR:
            raise ForgeError(
                "UNTRUSTED_CANDIDATE_INSPECTION", "Candidate inspection requires Governor context"
            )
        self._require_trusted_context(
            inspection.context,
            action="CANDIDATE_INSPECTION",
            scope_digest=handoff.candidate.digest,
            payload_digest=_candidate_inspection_payload_digest(inspection),
        )
        if inspection.candidate_digest != handoff.candidate.digest:
            raise ForgeError(
                "CANDIDATE_INSPECTION_MISMATCH",
                "Repository inspection is not bound to the Builder candidate",
            )
        if inspection.base_candidate_digest != packet.base_candidate.digest:
            raise ForgeError(
                "BASE_CANDIDATE_MISMATCH",
                "Trusted repository inspection does not confirm the packet base",
            )
        self._validate_paths(inspection.changed_paths, packet)
        if (
            any(_path_requires_a3(path) for path in inspection.changed_paths)
            and packet.authority is not Authority.A3
        ):
            raise ForgeError(
                "INSUFFICIENT_AUTHORITY", "Protected changed path requires A3 authority"
            )
        if any(item.candidate_digest != handoff.candidate.digest for item in inspection.evidence):
            raise ForgeError(
                "EVIDENCE_CANDIDATE_MISMATCH",
                "Inspected evidence is not bound to the exact candidate",
            )
        for kind in packet.evidence_required:
            results = {item.result for item in inspection.evidence if item.kind == kind}
            if ImplementationVerdict.PASS in results and results - {ImplementationVerdict.PASS}:
                raise ForgeError(
                    "CONTRADICTORY_EVIDENCE", f"Evidence for {kind} contains conflicting results"
                )
        valid_evidence = {
            item.kind for item in inspection.evidence if item.result is ImplementationVerdict.PASS
        }
        missing = sorted(set(packet.evidence_required) - valid_evidence)
        if missing:
            raise ForgeError(
                "MISSING_BUILDER_EVIDENCE",
                "Builder handoff is missing required evidence",
                details={"missing": missing},
            )
        # Charged here, once the candidate is accepted, rather than on arrival. A
        # handoff refused for a forged context, the wrong repository or an
        # out-of-scope path is a protocol error, not a try at the work: those never
        # register a candidate, so they cannot loop the loop forward, and charging
        # them would let a malformed client burn a packet's retries without ever
        # attempting the work. `retry_limit` is the packet contract's *retry
        # budget*, which counts candidate attempts.
        self._spend_attempt()
        self._handoff = handoff
        self._audit = None
        self._eligibility = None
        self._state = LoopState.CANDIDATE_READY
        self._record(
            "CANDIDATE_REGISTERED", {"handoff": asdict(handoff), "inspection": asdict(inspection)}
        )

    def submit_audit(self, report: AuditReport) -> None:
        if self._state is not LoopState.CANDIDATE_READY or self._handoff is None:
            raise ForgeError("INVALID_LOOP_STATE", "Audit requires a registered candidate")
        if report.context.role is not AgentRole.AUDITOR:
            raise ForgeError(
                "AUDITOR_INDEPENDENCE_VIOLATION", "Only Auditor context may submit an audit"
            )
        self._require_trusted_context(
            report.context,
            action="AUDIT",
            scope_digest=report.candidate_digest,
            payload_digest=_audit_report_payload_digest(report),
        )
        if report.context.digest == self._handoff.context.digest:
            raise ForgeError(
                "AUDITOR_INDEPENDENCE_VIOLATION", "Auditor context must differ from Builder context"
            )
        if report.candidate_digest != self._handoff.candidate.digest:
            raise ForgeError(
                "AUDIT_CANDIDATE_MISMATCH", "Audit is not bound to the exact candidate"
            )
        if (
            self._packet is None
            or report.specification_hash != self._packet.specification_hash
            or report.specification_hash != self._product_brain.specification_hash
        ):
            raise ForgeError(
                "AUDIT_SPECIFICATION_MISMATCH", "Audit is not bound to the current specification"
            )
        self._audit = report
        self._eligibility = None
        self._state = LoopState.AUDITED
        self._record("AUDIT_RECORDED", asdict(report))

    def mark_merge_eligible(
        self, *, governor_context: ContextIdentity, candidate: CandidateIdentity
    ) -> MergeEligibility:
        if governor_context.role is not AgentRole.GOVERNOR:
            raise ForgeError(
                "GOVERNOR_AUTHORITY_REQUIRED", "Only Governor may mark merge eligibility"
            )
        if self._state is not LoopState.AUDITED or self._audit is None or self._handoff is None:
            raise ForgeError("INVALID_LOOP_STATE", "Merge eligibility requires an audit")
        eligibility_payload = _digest(
            {"candidate_digest": candidate.digest, "audit_digest": self._audit.digest}
        )
        self._require_trusted_context(
            governor_context,
            action="MERGE_ELIGIBILITY",
            scope_digest=candidate.digest,
            payload_digest=eligibility_payload,
        )
        if (
            candidate.digest != self._handoff.candidate.digest
            or self._audit.candidate_digest != candidate.digest
        ):
            raise ForgeError("AUDIT_INVALIDATED", "Candidate changed after audit")
        if (
            self._packet is None
            or self._product_brain.specification_hash != self._packet.specification_hash
        ):
            raise ForgeError(
                "AUDIT_INVALIDATED", "Product specification changed after packet registration"
            )
        if self._product_brain.contradictions():
            raise ForgeError("AUDIT_INVALIDATED", "Product state became contradictory after audit")
        for requirement_id in self._packet.requirements:
            requirement = self._product_brain.requirements.get(requirement_id)
            if requirement is None or requirement.status not in {
                RequirementStatus.ACTIVE,
                RequirementStatus.IMPLEMENTING,
            }:
                raise ForgeError(
                    "AUDIT_INVALIDATED", "Packet requirement is no longer active for work"
                )
            self._validate_requirement_dependencies(requirement_id, error_code="AUDIT_INVALIDATED")
        if self._audit.implementation_verdict is not ImplementationVerdict.PASS:
            raise ForgeError("AUDIT_NOT_PASS", "FAIL or UNKNOWN audit cannot become merge eligible")
        if self._audit.discovery_verdict is DiscoveryVerdict.MATERIAL_DISCOVERY:
            raise ForgeError(
                "DISCOVERY_REVIEW_REQUIRED",
                "Material discovery must be resolved before merge eligibility",
            )
        if self._audit.evidence_gaps or self._audit.invariant_findings:
            raise ForgeError(
                "AUDIT_GAPS_REMAIN", "Audit gaps or invariant findings block merge eligibility"
            )
        eligibility = MergeEligibility(candidate.digest, self._audit.digest, governor_context)
        self._eligibility = eligibility
        self._state = LoopState.MERGE_ELIGIBLE
        self._record("MERGE_ELIGIBILITY_GRANTED", asdict(eligibility))
        return eligibility

    def audit_is_current(self, candidate: CandidateIdentity) -> bool:
        return (
            self._audit is not None
            and self._packet is not None
            and self._audit.candidate_digest == candidate.digest
            and self._audit.specification_hash
            == self._product_brain.specification_hash
            == self._packet.specification_hash
        )

    @property
    def budget_ledger(self) -> BudgetLedger | None:
        """The packet's budget record, or `None` when no budget was declared."""
        return self._budget_ledger

    def _spend_attempt(self) -> None:
        """Charge one attempt, refusing the handoff when the budget is spent.

        A packet's `retry_limit` is a declaration; this is the thing that enforces
        it. When the packet declares a retry limit and no explicit `Budget` was
        passed, the limit becomes the attempts budget — `retry_limit` had no reader
        at all before, so a packet could declare two retries and take twenty.
        """
        packet = self._require_packet()
        if self._budget_ledger is not None and self._budget_ledger.packet_id != packet.id:
            raise ForgeError(
                "BUDGET_PACKET_MISMATCH",
                f"Budget ledger belongs to {self._budget_ledger.packet_id}, not {packet.id}; "
                "one packet's attempts must not be charged to another's budget",
            )
        if self._budget_ledger is None:
            budget = self._budget
            if budget is None and packet.retry_limit:
                # retry_limit is retries, so the first attempt is not one of them.
                budget = Budget(attempts=packet.retry_limit + 1)
            if budget is None:
                return
            self._budget_ledger = BudgetLedger(packet.id, budget)
        receipt = self._budget_ledger.spend(BudgetDimension.ATTEMPTS)
        if receipt.outcome is SpendOutcome.EXHAUSTED:
            self._record("BUDGET_EXHAUSTED", receipt.as_dict())
            raise ForgeError(
                "BUDGET_EXHAUSTED",
                f"Attempt budget exhausted for {packet.id}: {receipt.reason}",
                details=receipt.as_dict(),
            )

    def _require_packet(self) -> BuildPacket:
        if self._packet is None:
            raise ForgeError("MISSING_BUILD_PACKET", "No Build Packet is registered")
        return self._packet

    def _validate_paths(self, paths: tuple[str, ...], packet: BuildPacket) -> None:
        if not paths:
            raise ForgeError(
                "EMPTY_CANDIDATE_DIFF", "Builder candidate must identify changed paths"
            )
        for raw_path in paths:
            portable = raw_path.replace("\\", "/")
            path = posixpath.normpath(portable)
            if (
                portable.startswith("/")
                or path in {".", ".."}
                or path.startswith("../")
                or ":" in path.split("/", 1)[0]
            ):
                raise ForgeError("INVALID_CHANGED_PATH", f"Unsafe changed path: {raw_path}")
            if any(
                _path_pattern_matches(path, posixpath.normpath(pattern.replace("\\", "/")))
                for pattern in packet.forbidden_paths
            ):
                raise ForgeError("FORBIDDEN_PATH_CHANGE", f"Changed path is forbidden: {raw_path}")
            if not any(
                _path_pattern_matches(path, posixpath.normpath(pattern.replace("\\", "/")))
                for pattern in packet.allowed_paths
            ):
                raise ForgeError(
                    "OUT_OF_SCOPE_PATH", f"Changed path is outside packet scope: {raw_path}"
                )

    def _validate_packet_authority(self, packet: BuildPacket) -> None:
        normalized_patterns = tuple(
            posixpath.normpath(item.replace("\\", "/")) for item in packet.allowed_paths
        )
        if packet.authority is not Authority.A3 and any(
            pattern_reaches_protected_surface(pattern) for pattern in normalized_patterns
        ):
            raise ForgeError(
                "INSUFFICIENT_AUTHORITY",
                "Build Packet scope includes protected surfaces requiring A3",
            )

    def _validate_owner_authorization(
        self, packet: BuildPacket, authorization: OwnerAuthorization | None
    ) -> None:
        if authorization is None:
            raise ForgeError(
                "OWNER_AUTHORIZATION_REQUIRED",
                "A3 work requires separately authenticated owner authorization",
            )
        if (
            authorization.packet_id != packet.id
            or authorization.scope_digest != _packet_scope_digest(packet)
        ):
            raise ForgeError(
                "OWNER_AUTHORIZATION_MISMATCH",
                "Owner authorization is not bound to this packet scope",
            )
        if authorization.digest not in self._trusted_owner_authorizations:
            raise ForgeError(
                "UNTRUSTED_OWNER_AUTHORIZATION", "Owner authorization evidence is not authenticated"
            )

    def _validate_requirement_dependencies(
        self, requirement_id: str, *, error_code: str = "UNREADY_REQUIREMENT_DEPENDENCY"
    ) -> None:
        requirement = self._product_brain.requirements[requirement_id]
        for dependency_id in requirement.dependencies:
            dependency = self._product_brain.requirements.get(dependency_id)
            if dependency is None or dependency.status is not RequirementStatus.SATISFIED:
                raise ForgeError(
                    error_code,
                    f"Requirement {requirement_id} dependency {dependency_id} is not satisfied",
                )

    def _require_trusted_context(
        self, context: ContextIdentity, *, action: str, scope_digest: str, payload_digest: str
    ) -> None:
        key = self._context_verification_keys.get(context.role, {}).get(context.digest)
        body = {
            "role": context.role.value,
            "digest": context.digest,
            "action": context.action,
            "scope_digest": context.scope_digest,
            "payload_digest": context.payload_digest,
            "loop_id": context.loop_id,
        }
        if (
            key is None
            or context.action != action
            or context.scope_digest != scope_digest
            or context.payload_digest != payload_digest
            or context.loop_id != self._loop_id
            or not hmac.compare_digest(context.issuer_signature, _sign(body, key))
        ):
            raise ForgeError(
                "UNTRUSTED_CONTEXT", f"Context is not authorized for role {context.role}"
            )

    def _record(self, event: str, data: dict[str, Any]) -> None:
        previous = self._ledger.receipts[-1].receipt_hash if self._ledger.receipts else None
        receipt = Receipt.create(len(self._ledger.receipts) + 1, event, None, None, data, previous)
        self._ledger.append(receipt)


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _builder_handoff_payload_digest(handoff: BuilderHandoff) -> str:
    return _digest(
        {
            "packet_id": handoff.packet_id,
            "candidate": asdict(handoff.candidate),
            "implementation_summary": handoff.implementation_summary,
            "tests_attempted": handoff.tests_attempted,
            "observations": handoff.observations,
            "blockers": handoff.blockers,
        }
    )


def _candidate_inspection_payload_digest(inspection: CandidateInspection) -> str:
    return _digest(
        {
            "candidate_digest": inspection.candidate_digest,
            "base_candidate_digest": inspection.base_candidate_digest,
            "changed_paths": inspection.changed_paths,
            "evidence": [asdict(item) for item in inspection.evidence],
        }
    )


def _audit_report_payload_digest(report: AuditReport) -> str:
    return _digest(
        {
            "candidate_digest": report.candidate_digest,
            "specification_hash": report.specification_hash,
            "implementation_verdict": report.implementation_verdict,
            "discovery_verdict": report.discovery_verdict,
            "findings": report.findings,
            "evidence_gaps": report.evidence_gaps,
            "invariant_findings": report.invariant_findings,
            "discovery_candidates": report.discovery_candidates,
            "confidence": report.confidence,
        }
    )


def _sign(value: Mapping[str, Any], key: bytes) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()


def _path_requires_a3(raw_path: str) -> bool:
    """Delegate to the protected-surface registry.

    Kept as a thin alias rather than inlined at the call sites, so there is still
    one name to grep for when asking what needs the owner. The list itself lives
    in `forge.policy`. Audit F9 measured what happens when a second copy drifts:
    this one had been written against `governor.py`, `authority.py`,
    `evidence_ledger.py` and `secrets.py`, none of which were ever created, and it
    protected two of twelve real surfaces as a result.
    """
    return requires_owner_authority(raw_path)


def _packet_scope_requires_a3(packet: BuildPacket) -> bool:
    return any(
        pattern_reaches_protected_surface(posixpath.normpath(item.replace("\\", "/")))
        for item in packet.allowed_paths
    )


def _packet_scope_digest(packet: BuildPacket) -> str:
    return _digest(asdict(packet))
