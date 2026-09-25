"""Deterministic Product Brain and Living Specification domain model."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from .trust_kernel import (
    ActionKind,
    Authority,
    AuthorityGrant,
    ForgeError,
    Ledger,
    LedgerCheckpoint,
    Receipt,
)


class RequirementStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    IMPLEMENTING = "IMPLEMENTING"
    EVIDENCED = "EVIDENCED"
    VERIFIED = "VERIFIED"
    SATISFIED = "SATISFIED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    OWNER_REQUIRED = "OWNER_REQUIRED"


class AssumptionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CHALLENGED = "CHALLENGED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class NorthStar:
    statement: str
    owner_ref: str
    version: int = 1

    def __post_init__(self) -> None:
        if (
            not isinstance(self.statement, str)
            or not isinstance(self.owner_ref, str)
            or not self.statement.strip()
            or not self.owner_ref.strip()
        ):
            raise ForgeError(
                "INVALID_NORTH_STAR", "North Star statement and owner reference cannot be blank"
            )


@dataclass(frozen=True, slots=True)
class FinishContract:
    criteria: tuple[str, ...]
    version: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "criteria", tuple(self.criteria))
        if not self.criteria or any(
            not isinstance(criterion, str) or not criterion.strip() for criterion in self.criteria
        ):
            raise ForgeError("EMPTY_FINISH_CONTRACT", "Finish Contract criteria cannot be blank")


@dataclass(frozen=True, slots=True)
class Requirement:
    id: str
    version: int
    statement: str
    origin: str
    status: RequirementStatus = RequirementStatus.PROPOSED
    authority: Authority = Authority.A2
    assumptions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    supersedes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "evidence_required", tuple(self.evidence_required))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.id, self.statement, self.origin)
        ):
            raise ForgeError(
                "INVALID_REQUIREMENT", "Requirement id, statement, and origin cannot be blank"
            )
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (*self.evidence_required, *self.evidence)
        ):
            raise ForgeError(
                "INVALID_REQUIREMENT_EVIDENCE",
                "Requirement evidence obligations and references cannot be blank",
            )

    @property
    def ref(self) -> str:
        return f"{self.id}:v{self.version}"


@dataclass(frozen=True, slots=True)
class Assumption:
    id: str
    statement: str
    source: str
    confidence: float
    status: AssumptionStatus = AssumptionStatus.UNKNOWN
    dependents: tuple[str, ...] = ()
    contradictory_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", AssumptionStatus(self.status))
        object.__setattr__(self, "dependents", tuple(self.dependents))
        object.__setattr__(self, "contradictory_evidence", tuple(self.contradictory_evidence))
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.id, self.statement, self.source)
        ):
            raise ForgeError(
                "INVALID_ASSUMPTION", "Assumption id, statement, and source cannot be blank"
            )
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, int | float)
            or not 0 <= self.confidence <= 1
        ):
            raise ForgeError(
                "INVALID_ASSUMPTION", "Assumption confidence must be a number between zero and one"
            )


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    id: str
    evidence: tuple[str, ...]
    rationale: str
    impact_analysis: str
    validated: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if not isinstance(self.validated, bool):
            raise ForgeError(
                "INVALID_DISCOVERY_RECORD", "Discovery validation status must be a boolean"
            )
        if not isinstance(self.id, str) or not self.id.strip():
            raise ForgeError("INVALID_DISCOVERY_RECORD", "Discovery id cannot be blank")
        if self.validated and (
            not self.evidence
            or any(not isinstance(item, str) or not item.strip() for item in self.evidence)
            or not isinstance(self.rationale, str)
            or not self.rationale.strip()
            or not isinstance(self.impact_analysis, str)
            or not self.impact_analysis.strip()
        ):
            raise ForgeError(
                "INVALID_DISCOVERY_RECORD",
                "Validated discovery requires nonblank evidence, rationale, and impact analysis",
            )


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    id: str
    question: str
    choice: str
    basis: tuple[str, ...]
    authority: Authority
    reversible: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "basis", tuple(self.basis))


@dataclass(frozen=True, slots=True)
class Invariant:
    id: str
    statement: str
    authority: str
    verification: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification", tuple(self.verification))
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (self.id, self.statement, self.authority)
        ):
            raise ForgeError(
                "INVALID_INVARIANT", "Invariant id, statement, and authority cannot be blank"
            )
        if not self.verification or any(
            not isinstance(item, str) or not item.strip() for item in self.verification
        ):
            raise ForgeError(
                "INVALID_INVARIANT", "Invariant requires nonblank verification references"
            )


@dataclass(frozen=True, slots=True)
class Contradiction:
    code: str
    subject: str
    detail: str


_REQUIREMENT_TRANSITIONS: dict[RequirementStatus, frozenset[RequirementStatus]] = {
    RequirementStatus.PROPOSED: frozenset(
        {
            RequirementStatus.ACTIVE,
            RequirementStatus.REJECTED,
            RequirementStatus.BLOCKED,
            RequirementStatus.OWNER_REQUIRED,
        }
    ),
    RequirementStatus.ACTIVE: frozenset(
        {
            RequirementStatus.IMPLEMENTING,
            RequirementStatus.BLOCKED,
            RequirementStatus.OWNER_REQUIRED,
            RequirementStatus.SUPERSEDED,
        }
    ),
    RequirementStatus.IMPLEMENTING: frozenset(
        {
            RequirementStatus.EVIDENCED,
            RequirementStatus.BLOCKED,
            RequirementStatus.OWNER_REQUIRED,
            RequirementStatus.SUPERSEDED,
        }
    ),
    RequirementStatus.EVIDENCED: frozenset(
        {
            RequirementStatus.VERIFIED,
            RequirementStatus.IMPLEMENTING,
            RequirementStatus.BLOCKED,
            RequirementStatus.SUPERSEDED,
        }
    ),
    RequirementStatus.VERIFIED: frozenset(
        {RequirementStatus.SATISFIED, RequirementStatus.IMPLEMENTING, RequirementStatus.SUPERSEDED}
    ),
    RequirementStatus.BLOCKED: frozenset(
        {
            RequirementStatus.ACTIVE,
            RequirementStatus.IMPLEMENTING,
            RequirementStatus.OWNER_REQUIRED,
            RequirementStatus.SUPERSEDED,
        }
    ),
    RequirementStatus.OWNER_REQUIRED: frozenset(
        {
            RequirementStatus.PROPOSED,
            RequirementStatus.ACTIVE,
            RequirementStatus.REJECTED,
            RequirementStatus.SUPERSEDED,
        }
    ),
    RequirementStatus.SATISFIED: frozenset({RequirementStatus.SUPERSEDED}),
    RequirementStatus.SUPERSEDED: frozenset(),
    RequirementStatus.REJECTED: frozenset(),
}

_EVENT_MINIMUM_AUTHORITY: dict[str, Authority] = {
    "NORTH_STAR_INGESTED": Authority.A3,
    "NORTH_STAR_REPLACED": Authority.A3,
    "FINISH_CONTRACT_SET": Authority.A3,
    "FINISH_CONTRACT_REPLACED": Authority.A3,
    "REQUIREMENT_ADDED": Authority.A2,
    "REQUIREMENT_VERSIONED": Authority.A2,
    "REQUIREMENT_TRANSITIONED": Authority.A2,
    "ASSUMPTION_ADDED": Authority.A2,
    "DECISION_RECORDED": Authority.A2,
    "INVARIANT_ADDED": Authority.A2,
}


class ProductBrain:
    """Structured, receipt-backed model of current product understanding."""

    def __init__(self, *, owner_verification_keys: Mapping[str, bytes] | None = None) -> None:
        self._north_star: NorthStar | None = None
        self._finish_contract: FinishContract | None = None
        self._requirements: dict[str, Requirement] = {}
        self._requirement_history: dict[str, list[Requirement]] = {}
        self._assumptions: dict[str, Assumption] = {}
        self._decisions: dict[str, DecisionRecord] = {}
        self._invariants: dict[str, Invariant] = {}
        self._ledger = Ledger()
        self._owner_verification_keys = dict(owner_verification_keys or {})

    @property
    def north_star(self) -> NorthStar | None:
        return self._north_star

    @property
    def finish_contract(self) -> FinishContract | None:
        return self._finish_contract

    @property
    def requirements(self) -> Mapping[str, Requirement]:
        return MappingProxyType(self._requirements)

    @property
    def requirement_history(self) -> Mapping[str, tuple[Requirement, ...]]:
        return MappingProxyType(
            {key: tuple(value) for key, value in self._requirement_history.items()}
        )

    @property
    def assumptions(self) -> Mapping[str, Assumption]:
        return MappingProxyType(self._assumptions)

    @property
    def decisions(self) -> Mapping[str, DecisionRecord]:
        return MappingProxyType(self._decisions)

    @property
    def invariants(self) -> Mapping[str, Invariant]:
        return MappingProxyType(self._invariants)

    @property
    def ledger(self) -> Ledger:
        return Ledger(self._ledger.receipts)

    @property
    def specification_hash(self) -> str:
        encoded = json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        return {
            "north_star": asdict(self._north_star) if self._north_star else None,
            "finish_contract": asdict(self._finish_contract) if self._finish_contract else None,
            "requirements": [asdict(self._requirements[key]) for key in sorted(self._requirements)],
            "requirement_history": {
                key: [asdict(item) for item in self._requirement_history[key]]
                for key in sorted(self._requirement_history)
            },
            "assumptions": [asdict(self._assumptions[key]) for key in sorted(self._assumptions)],
            "decisions": [asdict(self._decisions[key]) for key in sorted(self._decisions)],
            "invariants": [asdict(self._invariants[key]) for key in sorted(self._invariants)],
        }

    @staticmethod
    def protected_scope_digest(event: str, data: Mapping[str, Any]) -> str:
        return _digest({"event": event, "data": data})

    def ingest_north_star(
        self,
        north_star: NorthStar,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A3)
        self._validate_north_star("NORTH_STAR_INGESTED", north_star)
        self._mutate(
            "NORTH_STAR_INGESTED",
            asdict(north_star),
            lambda: setattr(self, "_north_star", north_star),
            authority,
            authority_grant,
        )

    def replace_north_star(
        self,
        north_star: NorthStar,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A3)
        self._validate_north_star("NORTH_STAR_REPLACED", north_star)
        self._mutate(
            "NORTH_STAR_REPLACED",
            asdict(north_star),
            lambda: setattr(self, "_north_star", north_star),
            authority,
            authority_grant,
        )

    def set_finish_contract(
        self,
        contract: FinishContract,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A3)
        event = (
            "FINISH_CONTRACT_SET" if self._finish_contract is None else "FINISH_CONTRACT_REPLACED"
        )
        self._validate_finish_contract(event, contract)
        self._mutate(
            event,
            asdict(contract),
            lambda: setattr(self, "_finish_contract", contract),
            authority,
            authority_grant,
        )

    def add_requirement(
        self,
        requirement: Requirement,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        self._validate_requirement_create(requirement)
        _require_authority(authority, requirement.authority)
        self._mutate(
            "REQUIREMENT_ADDED",
            asdict(requirement),
            lambda: self._store_requirement(requirement),
            authority,
            authority_grant,
        )

    def version_requirement(
        self,
        requirement: Requirement,
        *,
        discovery: DiscoveryRecord,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        current = self._requirements.get(requirement.id)
        if current is None:
            raise ForgeError("UNKNOWN_REQUIREMENT", "Cannot version a missing requirement")
        self._validate_requirement_version(current, requirement, discovery)
        _require_authority(authority, current.authority)
        _require_authority(authority, requirement.authority)

        def apply() -> None:
            superseded = replace(current, status=RequirementStatus.SUPERSEDED)
            self._requirement_history[current.id][-1] = superseded
            self._requirement_history[current.id].append(requirement)
            self._requirements[current.id] = requirement

        self._mutate(
            "REQUIREMENT_VERSIONED",
            {"requirement": asdict(requirement), "discovery": asdict(discovery)},
            apply,
            authority,
            authority_grant,
        )

    def transition_requirement(
        self,
        requirement_id: str,
        target: RequirementStatus,
        *,
        authority: Authority,
        evidence: tuple[str, ...] = (),
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        current = self._requirements.get(requirement_id)
        if current is None:
            raise ForgeError("UNKNOWN_REQUIREMENT", "Cannot transition a missing requirement")
        _require_authority(authority, current.authority)
        combined_evidence = tuple(sorted({*current.evidence, *evidence}))
        self._validate_requirement_transition(current, target, combined_evidence)
        updated = replace(current, status=target, evidence=combined_evidence)

        def apply() -> None:
            self._requirements[requirement_id] = updated
            self._requirement_history[requirement_id][-1] = updated

        self._mutate(
            "REQUIREMENT_TRANSITIONED",
            {"id": requirement_id, "target": target.value, "evidence": list(combined_evidence)},
            apply,
            authority,
            authority_grant,
        )

    def add_assumption(
        self,
        assumption: Assumption,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        self._add_unique(
            "ASSUMPTION_ADDED",
            assumption.id,
            assumption,
            self._assumptions,
            authority,
            authority_grant,
        )

    def add_decision(
        self,
        decision: DecisionRecord,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        _require_authority(authority, decision.authority)
        self._add_unique(
            "DECISION_RECORDED", decision.id, decision, self._decisions, authority, authority_grant
        )

    def add_invariant(
        self,
        invariant: Invariant,
        *,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        _require_authority(authority, Authority.A2)
        self._add_unique(
            "INVARIANT_ADDED", invariant.id, invariant, self._invariants, authority, authority_grant
        )

    def contradictions(self) -> tuple[Contradiction, ...]:
        findings: list[Contradiction] = []
        if self._north_star is None:
            findings.append(
                Contradiction(
                    "MISSING_NORTH_STAR", "product_brain", "Owner-controlled intent is absent"
                )
            )
        if self._finish_contract is None:
            findings.append(
                Contradiction(
                    "MISSING_FINISH_CONTRACT", "product_brain", "Completion criteria are absent"
                )
            )
        inactive = {RequirementStatus.SUPERSEDED, RequirementStatus.REJECTED}
        for requirement in self._requirements.values():
            if requirement.status in inactive:
                continue
            for dependency in requirement.dependencies:
                target = self._requirements.get(dependency)
                if target is None:
                    findings.append(
                        Contradiction("MISSING_REQUIREMENT_DEPENDENCY", requirement.id, dependency)
                    )
                elif target.status in inactive:
                    findings.append(
                        Contradiction("INACTIVE_REQUIREMENT_DEPENDENCY", requirement.id, dependency)
                    )
            for assumption in requirement.assumptions:
                record = self._assumptions.get(assumption)
                if record is None:
                    findings.append(Contradiction("MISSING_ASSUMPTION", requirement.id, assumption))
                else:
                    if record.status is AssumptionStatus.REJECTED:
                        findings.append(
                            Contradiction("REJECTED_ASSUMPTION", requirement.id, assumption)
                        )
                    if (
                        record.status in {AssumptionStatus.UNKNOWN, AssumptionStatus.CHALLENGED}
                        and not record.contradictory_evidence
                    ):
                        findings.append(
                            Contradiction("UNRESOLVED_ASSUMPTION", requirement.id, assumption)
                        )
                    if record.contradictory_evidence:
                        findings.append(
                            Contradiction("CONTRADICTED_ASSUMPTION", requirement.id, assumption)
                        )
        return tuple(sorted(findings, key=lambda item: (item.code, item.subject, item.detail)))

    @classmethod
    def from_records(
        cls,
        records: list[dict[str, Any]],
        *,
        checkpoint: LedgerCheckpoint,
        owner_verification_keys: Mapping[str, bytes] | None = None,
    ) -> ProductBrain:
        brain = cls(owner_verification_keys=owner_verification_keys)
        brain._ledger = Ledger.from_records(records, checkpoint=checkpoint)
        for receipt in brain._ledger.receipts:
            payload = receipt.payload
            if payload.get("specification_hash_before") != brain.specification_hash:
                raise ForgeError(
                    "SPECIFICATION_REPLAY_MISMATCH",
                    "Receipt before-hash does not match reconstructed specification",
                )
            try:
                authority = Authority(payload["authority"])
                if authority is Authority.A3:
                    brain._verify_authority_grant(
                        receipt.event, payload.get("data"), _authority_grant_from_payload(payload)
                    )
                brain._apply_event(receipt.event, payload.get("data"), authority)
            except ForgeError:
                raise
            except (KeyError, TypeError, ValueError) as exc:
                raise ForgeError(
                    "MALFORMED_SPECIFICATION_RECEIPT", "Specification receipt payload is invalid"
                ) from exc
            if payload.get("specification_hash_after") != brain.specification_hash:
                raise ForgeError(
                    "SPECIFICATION_REPLAY_MISMATCH",
                    "Receipt after-hash does not match reconstructed specification",
                )
        return brain

    def _mutate(
        self,
        event: str,
        data: dict[str, Any],
        apply: Any,
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        before = self.specification_hash
        if authority is Authority.A3:
            self._verify_authority_grant(event, data, authority_grant)
        prior_state = (
            self._north_star,
            self._finish_contract,
            dict(self._requirements),
            {key: list(value) for key, value in self._requirement_history.items()},
            dict(self._assumptions),
            dict(self._decisions),
            dict(self._invariants),
        )
        try:
            apply()
            after = self.specification_hash
            previous = self._ledger.receipts[-1].receipt_hash if self._ledger.receipts else None
            payload = {
                "data": data,
                "authority": authority.value,
                "specification_hash_before": before,
                "specification_hash_after": after,
            }
            if authority_grant is not None:
                payload["authority_grant"] = asdict(authority_grant)
            receipt = Receipt.create(
                len(self._ledger.receipts) + 1, event, None, None, payload, previous
            )
            self._ledger.append(receipt)
        except Exception:
            (
                self._north_star,
                self._finish_contract,
                self._requirements,
                self._requirement_history,
                self._assumptions,
                self._decisions,
                self._invariants,
            ) = prior_state
            raise

    def _verify_authority_grant(
        self, event: str, data: Mapping[str, Any] | None, grant: AuthorityGrant | None
    ) -> None:
        if grant is None or not isinstance(data, Mapping):
            raise ForgeError(
                "AUTHORITY_GRANT_REQUIRED",
                "Protected Product Brain mutation requires a signed owner grant",
            )
        scope_digest = self.protected_scope_digest(event, data)
        key = self._owner_verification_keys.get(grant.owner_ref)
        body = {
            "authority": grant.authority.value,
            "action": grant.action.value,
            "scope_digest": grant.scope_digest,
            "owner_ref": grant.owner_ref,
        }
        valid = key is not None and hmac.compare_digest(grant.issuer_signature, _sign(body, key))
        if (
            not valid
            or grant.authority is not Authority.A3
            or grant.action is not ActionKind.PROTECTED
            or grant.scope_digest != scope_digest
        ):
            raise ForgeError(
                "UNTRUSTED_AUTHORITY_GRANT",
                "Owner grant is not authentic or bound to this Product Brain mutation",
            )

    def _store_requirement(self, requirement: Requirement) -> None:
        self._requirements[requirement.id] = requirement
        self._requirement_history[requirement.id] = [requirement]

    def _validate_requirement_create(self, requirement: Requirement) -> None:
        if (
            requirement.id in self._requirements
            or requirement.version != 1
            or requirement.supersedes is not None
        ):
            raise ForgeError(
                "INVALID_REQUIREMENT_CREATE",
                "New requirement must have a unique id, version one, and no supersedes lineage",
            )
        if requirement.status is not RequirementStatus.PROPOSED or requirement.evidence:
            raise ForgeError(
                "INVALID_REQUIREMENT_CREATE", "New requirement must begin PROPOSED without evidence"
            )

    def _validate_north_star(self, event: str, north_star: NorthStar) -> None:
        if event == "NORTH_STAR_INGESTED":
            if self._north_star is not None:
                raise ForgeError(
                    "NORTH_STAR_EXISTS",
                    "Use owner-authorized replacement for an existing North Star",
                )
            if north_star.version != 1:
                raise ForgeError(
                    "INVALID_NORTH_STAR_VERSION", "Initial North Star must be version one"
                )
        elif self._north_star is None or north_star.version != self._north_star.version + 1:
            raise ForgeError(
                "INVALID_NORTH_STAR_VERSION",
                "North Star replacement must increment exactly one version",
            )

    def _validate_finish_contract(self, event: str, contract: FinishContract) -> None:
        if not contract.criteria:
            raise ForgeError(
                "EMPTY_FINISH_CONTRACT", "Finish Contract requires at least one criterion"
            )
        if event == "FINISH_CONTRACT_SET":
            if self._finish_contract is not None or contract.version != 1:
                raise ForgeError(
                    "INVALID_FINISH_CONTRACT_VERSION", "Initial Finish Contract must be version one"
                )
        elif self._finish_contract is None or contract.version != self._finish_contract.version + 1:
            raise ForgeError(
                "INVALID_FINISH_CONTRACT_VERSION",
                "Finish Contract replacement must increment exactly one version",
            )

    def _validate_requirement_version(
        self, current: Requirement, requirement: Requirement, discovery: DiscoveryRecord
    ) -> None:
        if requirement.version != current.version + 1 or requirement.supersedes != current.ref:
            raise ForgeError(
                "INVALID_REQUIREMENT_VERSION",
                "Requirement version and supersedes lineage must be exact",
            )
        if requirement.status is not RequirementStatus.PROPOSED or requirement.evidence:
            raise ForgeError(
                "INVALID_REQUIREMENT_VERSION",
                "New requirement version must begin PROPOSED without evidence",
            )
        if current.status in (RequirementStatus.SUPERSEDED, RequirementStatus.REJECTED):
            raise ForgeError("TERMINAL_REQUIREMENT", "Cannot version a terminal requirement")
        if int(requirement.authority.value[1]) < int(current.authority.value[1]):
            raise ForgeError(
                "AUTHORITY_DOWNGRADE", "Requirement version cannot lower declared authority"
            )
        if requirement.origin != discovery.id or not discovery.validated:
            raise ForgeError(
                "INVALID_DISCOVERY_RECORD",
                "Requirement evolution requires validated discovery evidence, rationale, and impact analysis",
            )

    @staticmethod
    def _validate_requirement_transition(
        current: Requirement, target: RequirementStatus, evidence: tuple[str, ...]
    ) -> None:
        if target not in _REQUIREMENT_TRANSITIONS[current.status]:
            raise ForgeError(
                "INVALID_REQUIREMENT_TRANSITION", f"{current.status} cannot transition to {target}"
            )
        if not set(current.evidence).issubset(evidence):
            raise ForgeError(
                "EVIDENCE_REGRESSION", "Requirement transition cannot discard accumulated evidence"
            )
        evidence_states = {
            RequirementStatus.EVIDENCED,
            RequirementStatus.VERIFIED,
            RequirementStatus.SATISFIED,
        }
        if target in evidence_states and (not current.evidence_required or not evidence):
            raise ForgeError(
                "MISSING_REQUIREMENT_EVIDENCE",
                "Evidence-backed requirement states require a nonempty evidence contract and proof",
            )
        missing_evidence = sorted(set(current.evidence_required) - set(evidence))
        if target in evidence_states and missing_evidence:
            raise ForgeError(
                "MISSING_REQUIREMENT_EVIDENCE",
                "Requirement evidence remains UNKNOWN",
                details={"missing": missing_evidence},
            )

    def _add_unique(
        self,
        event: str,
        item_id: str,
        item: Any,
        collection: dict[str, Any],
        authority: Authority,
        authority_grant: AuthorityGrant | None = None,
    ) -> None:
        if item_id in collection:
            raise ForgeError("DUPLICATE_PRODUCT_RECORD", f"Product record {item_id} already exists")
        self._mutate(
            event,
            asdict(item),
            lambda: collection.__setitem__(item_id, item),
            authority,
            authority_grant,
        )

    def _apply_event(
        self, event: str, data: Mapping[str, Any] | None, authority: Authority
    ) -> None:
        if not isinstance(data, Mapping):
            raise ForgeError(
                "MALFORMED_SPECIFICATION_RECEIPT", "Specification receipt data must be an object"
            )
        required_authority = _EVENT_MINIMUM_AUTHORITY.get(event)
        if required_authority is None:
            raise ForgeError("UNKNOWN_SPECIFICATION_EVENT", f"Cannot replay event {event}")
        _require_authority(authority, required_authority)
        if event in {"NORTH_STAR_INGESTED", "NORTH_STAR_REPLACED"}:
            item = NorthStar(**data)
            self._validate_north_star(event, item)
            self._north_star = item
        elif event in {"FINISH_CONTRACT_SET", "FINISH_CONTRACT_REPLACED"}:
            item = FinishContract(tuple(data["criteria"]), data["version"])
            self._validate_finish_contract(event, item)
            self._finish_contract = item
        elif event == "REQUIREMENT_ADDED":
            item = _requirement_from_data(data)
            _require_authority(authority, item.authority)
            self._validate_requirement_create(item)
            self._store_requirement(item)
        elif event == "REQUIREMENT_VERSIONED":
            item = _requirement_from_data(data["requirement"])
            discovery_data = data["discovery"]
            discovery = DiscoveryRecord(
                id=discovery_data["id"],
                evidence=tuple(discovery_data["evidence"]),
                rationale=discovery_data["rationale"],
                impact_analysis=discovery_data["impact_analysis"],
                validated=discovery_data["validated"],
            )
            current = self._requirements[item.id]
            _require_authority(authority, current.authority)
            _require_authority(authority, item.authority)
            self._validate_requirement_version(current, item, discovery)
            self._requirement_history[item.id][-1] = replace(
                current, status=RequirementStatus.SUPERSEDED
            )
            self._requirement_history[item.id].append(item)
            self._requirements[item.id] = item
        elif event == "REQUIREMENT_TRANSITIONED":
            current = self._requirements[data["id"]]
            _require_authority(authority, current.authority)
            target = RequirementStatus(data["target"])
            evidence = tuple(data.get("evidence", ()))
            self._validate_requirement_transition(current, target, evidence)
            updated = replace(current, status=target, evidence=evidence)
            self._requirements[current.id] = updated
            self._requirement_history[current.id][-1] = updated
        elif event == "ASSUMPTION_ADDED":
            item = Assumption(
                id=data["id"],
                statement=data["statement"],
                source=data["source"],
                confidence=data["confidence"],
                status=AssumptionStatus(data["status"]),
                dependents=tuple(data["dependents"]),
                contradictory_evidence=tuple(data["contradictory_evidence"]),
            )
            self._reject_duplicate_replay(item.id, self._assumptions)
            self._assumptions[item.id] = item
        elif event == "DECISION_RECORDED":
            item = DecisionRecord(
                data["id"],
                data["question"],
                data["choice"],
                tuple(data["basis"]),
                Authority(data["authority"]),
                data["reversible"],
            )
            _require_authority(authority, item.authority)
            self._reject_duplicate_replay(item.id, self._decisions)
            self._decisions[item.id] = item
        elif event == "INVARIANT_ADDED":
            item = Invariant(
                data["id"], data["statement"], data["authority"], tuple(data["verification"])
            )
            self._reject_duplicate_replay(item.id, self._invariants)
            self._invariants[item.id] = item
        else:
            raise ForgeError("UNKNOWN_SPECIFICATION_EVENT", f"Cannot replay event {event}")

    @staticmethod
    def _reject_duplicate_replay(item_id: str, collection: Mapping[str, Any]) -> None:
        if item_id in collection:
            raise ForgeError("DUPLICATE_PRODUCT_RECORD", f"Product record {item_id} already exists")


def _requirement_from_data(data: Mapping[str, Any]) -> Requirement:
    return Requirement(
        id=data["id"],
        version=data["version"],
        statement=data["statement"],
        origin=data["origin"],
        status=RequirementStatus(data["status"]),
        authority=Authority(data["authority"]),
        assumptions=tuple(data["assumptions"]),
        dependencies=tuple(data["dependencies"]),
        evidence_required=tuple(data["evidence_required"]),
        evidence=tuple(data.get("evidence", ())),
        supersedes=data.get("supersedes"),
    )


def _require_authority(provided: Authority, required: Authority) -> None:
    if int(provided.value[1]) < int(required.value[1]):
        raise ForgeError(
            "INSUFFICIENT_AUTHORITY",
            "Product mutation requires higher authority",
            details={"required": required.value, "provided": provided.value},
        )


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sign(value: Mapping[str, Any], key: bytes) -> str:
    encoded = json.dumps(
        _plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()


def _authority_grant_from_payload(payload: Mapping[str, Any]) -> AuthorityGrant:
    data = payload["authority_grant"]
    return AuthorityGrant(
        authority=Authority(data["authority"]),
        action=ActionKind(data["action"]),
        scope_digest=data["scope_digest"],
        owner_ref=data["owner_ref"],
        issuer_signature=data["issuer_signature"],
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value
