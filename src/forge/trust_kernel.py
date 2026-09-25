"""Small deterministic trust kernel for Forge Agent V0."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ForgeError(Exception):
    """Structured fail-closed error."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, "details": self.details}


class MissionState(StrEnum):
    INITIALIZING = "INITIALIZING"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    TASK_READY = "TASK_READY"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    REPAIRING = "REPAIRING"
    STUCK_RESOLUTION = "STUCK_RESOLUTION"
    AUDITING = "AUDITING"
    DISCOVERY_REVIEW = "DISCOVERY_REVIEW"
    ACCEPTED = "ACCEPTED"
    SPEC_EVOLUTION = "SPEC_EVOLUTION"
    REJECTED = "REJECTED"
    REPLANNING = "REPLANNING"
    MERGING = "MERGING"
    OUTCOME_EVALUATION = "OUTCOME_EVALUATION"
    LEARNING = "LEARNING"
    RECONCILING = "RECONCILING"
    FINISH_EVALUATION = "FINISH_EVALUATION"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


class Authority(StrEnum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


class EvidenceStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class ActionKind(StrEnum):
    ROUTINE = "ROUTINE"
    SPECIFICATION_EVOLUTION = "SPECIFICATION_EVOLUTION"
    PROTECTED = "PROTECTED"


class ReconciliationStatus(StrEnum):
    EFFECT_COMPLETED = "EFFECT_COMPLETED"
    SAFE_TO_RETRY = "SAFE_TO_RETRY"
    UNKNOWN = "UNKNOWN"


class EffectDisposition(StrEnum):
    COMPLETED = "COMPLETED"
    NOT_STARTED = "NOT_STARTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RepositoryIdentity:
    remote: str
    revision: str
    worktree: str
    branch: str

    def __post_init__(self) -> None:
        if not all((self.remote, self.revision, self.worktree, self.branch)):
            raise ForgeError(
                "INVALID_REPOSITORY_IDENTITY", "Repository identity fields are required"
            )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    repository_digest: str
    revision: str
    tree: str
    packet_id: str

    def __post_init__(self) -> None:
        if not all((self.repository_digest, self.revision, self.tree, self.packet_id)):
            raise ForgeError("INVALID_CANDIDATE_IDENTITY", "Candidate identity fields are required")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class CandidateValidation:
    candidate_digest: str
    result: str
    evidence_digest: str
    auditor_context_digest: str
    builder_context_digest: str
    issuer_signature: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.candidate_digest,
                self.result,
                self.evidence_digest,
                self.auditor_context_digest,
                self.builder_context_digest,
                self.issuer_signature,
            )
        ):
            raise ForgeError(
                "INVALID_CANDIDATE_VALIDATION",
                "Candidate validation identity, evidence, and signature are required",
            )

    def is_valid_for(self, candidate: CandidateIdentity) -> bool:
        return self.candidate_digest == candidate.digest

    @property
    def is_independent_pass(self) -> bool:
        return (
            self.result == "PASS"
            and bool(self.evidence_digest)
            and bool(self.auditor_context_digest)
            and bool(self.builder_context_digest)
            and self.auditor_context_digest != self.builder_context_digest
        )

    @classmethod
    def issue(
        cls,
        candidate_digest: str,
        result: str,
        evidence_digest: str,
        auditor_context_digest: str,
        builder_context_digest: str,
        *,
        signing_key: bytes,
    ) -> CandidateValidation:
        body = {
            "candidate_digest": candidate_digest,
            "result": result,
            "evidence_digest": evidence_digest,
            "auditor_context_digest": auditor_context_digest,
            "builder_context_digest": builder_context_digest,
        }
        return cls(**body, issuer_signature=_sign(body, signing_key))


@dataclass(frozen=True, slots=True)
class DiscoveryAuthorization:
    record_digest: str
    evidence_digest: str
    rationale: str
    impact_analysis: str

    def __post_init__(self) -> None:
        if not all(
            (self.record_digest, self.evidence_digest, self.rationale, self.impact_analysis)
        ):
            raise ForgeError(
                "INVALID_DISCOVERY_AUTHORIZATION",
                "Discovery Record, evidence, rationale, and impact analysis are required",
            )


@dataclass(frozen=True, slots=True)
class TransitionEvidence:
    status: EvidenceStatus
    evidence_digest: str
    issuer_digest: str
    repository_digest: str
    state_before: str | None
    state_after: str
    issuer_signature: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", EvidenceStatus(self.status))
        if not all(
            (
                self.evidence_digest,
                self.issuer_digest,
                self.repository_digest,
                self.state_after,
                self.issuer_signature,
            )
        ):
            raise ForgeError(
                "INVALID_TRANSITION_EVIDENCE",
                "Transition evidence identity and digest are required",
            )

    @classmethod
    def issue(
        cls,
        evidence_digest: str,
        issuer_digest: str,
        repository_digest: str,
        state_before: str | None,
        state_after: str,
        *,
        signing_key: bytes,
    ) -> TransitionEvidence:
        if not all((evidence_digest, issuer_digest, repository_digest, state_after)):
            raise ForgeError(
                "INVALID_TRANSITION_EVIDENCE",
                "Transition evidence identity and digest are required",
            )
        body = {
            "status": EvidenceStatus.PRESENT.value,
            "evidence_digest": evidence_digest,
            "issuer_digest": issuer_digest,
            "repository_digest": repository_digest,
            "state_before": state_before,
            "state_after": state_after,
        }
        return cls(
            EvidenceStatus.PRESENT,
            evidence_digest,
            issuer_digest,
            repository_digest,
            state_before,
            state_after,
            _sign(body, signing_key),
        )


@dataclass(frozen=True, slots=True)
class ReconciliationEvidence:
    status: EvidenceStatus
    disposition: EffectDisposition
    effect_digest: str
    evidence_digest: str
    issuer_digest: str
    repository_digest: str
    issuer_signature: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", EvidenceStatus(self.status))
        object.__setattr__(self, "disposition", EffectDisposition(self.disposition))
        if not all(
            (
                self.effect_digest,
                self.evidence_digest,
                self.issuer_digest,
                self.repository_digest,
                self.issuer_signature,
            )
        ):
            raise ForgeError(
                "INVALID_RECONCILIATION_EVIDENCE",
                "Reconciliation evidence must identify the effect, evidence, issuer, and repository",
            )

    @classmethod
    def issue(
        cls,
        status: EvidenceStatus,
        disposition: EffectDisposition,
        effect_digest: str,
        evidence_digest: str,
        issuer_digest: str,
        repository_digest: str,
        *,
        signing_key: bytes,
    ) -> ReconciliationEvidence:
        body = {
            "status": status.value,
            "disposition": disposition.value,
            "effect_digest": effect_digest,
            "evidence_digest": evidence_digest,
            "issuer_digest": issuer_digest,
            "repository_digest": repository_digest,
        }
        return cls(
            status,
            disposition,
            effect_digest,
            evidence_digest,
            issuer_digest,
            repository_digest,
            _sign(body, signing_key),
        )


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    authority: Authority
    action: ActionKind
    scope_digest: str
    owner_ref: str
    issuer_signature: str

    @classmethod
    def issue(
        cls,
        authority: Authority,
        action: ActionKind,
        scope_digest: str,
        owner_ref: str,
        *,
        signing_key: bytes,
    ) -> AuthorityGrant:
        body = {
            "authority": authority.value,
            "action": action.value,
            "scope_digest": scope_digest,
            "owner_ref": owner_ref,
        }
        return cls(authority, action, scope_digest, owner_ref, _sign(body, signing_key))


@dataclass(frozen=True, slots=True)
class CompletionEvaluation:
    candidate_digest: str
    finish_contract_digest: str
    result: str
    evidence_digest: str
    auditor_context_digest: str
    issuer_signature: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.candidate_digest,
                self.finish_contract_digest,
                self.result,
                self.evidence_digest,
                self.auditor_context_digest,
                self.issuer_signature,
            )
        ):
            raise ForgeError(
                "INVALID_COMPLETION_EVALUATION",
                "Completion evaluation identity and evidence are required",
            )

    @classmethod
    def issue(
        cls,
        candidate_digest: str,
        finish_contract_digest: str,
        result: str,
        evidence_digest: str,
        auditor_context_digest: str,
        *,
        signing_key: bytes,
    ) -> CompletionEvaluation:
        body = {
            "candidate_digest": candidate_digest,
            "finish_contract_digest": finish_contract_digest,
            "result": result,
            "evidence_digest": evidence_digest,
            "auditor_context_digest": auditor_context_digest,
        }
        return cls(**body, issuer_signature=_sign(body, signing_key))


@dataclass(frozen=True, slots=True)
class Receipt:
    sequence: int
    event: str
    state_before: str | None
    state_after: str | None
    payload: Mapping[str, Any]
    previous_hash: str | None
    receipt_hash: str

    @classmethod
    def create(
        cls,
        sequence: int,
        event: str,
        state_before: str | None,
        state_after: str | None,
        payload: Mapping[str, Any],
        previous_hash: str | None,
    ) -> Receipt:
        frozen_payload = _freeze(dict(payload))
        body = {
            "sequence": sequence,
            "event": event,
            "state_before": state_before,
            "state_after": state_after,
            "payload": frozen_payload,
            "previous_hash": previous_hash,
        }
        return cls(**body, receipt_hash=_digest(body))


@dataclass(frozen=True, slots=True)
class LedgerCheckpoint:
    sequence: int
    head_hash: str | None
    stream_id: str | None = None

    def __post_init__(self) -> None:
        if self.sequence < 0 or (self.sequence == 0) != (self.head_hash is None):
            raise ForgeError(
                "INVALID_LEDGER_CHECKPOINT",
                "Ledger checkpoint sequence and head hash are inconsistent",
            )


class Ledger:
    """Append-only receipt chain with deterministic verification and replay."""

    def __init__(self, receipts: Iterable[Receipt] = (), *, stream_id: str | None = None):
        self._receipts: list[Receipt] = []
        self._stream_id = stream_id
        for receipt in receipts:
            self.append(receipt)

    @property
    def receipts(self) -> tuple[Receipt, ...]:
        return tuple(self._receipts)

    @property
    def checkpoint(self) -> LedgerCheckpoint:
        if not self._receipts:
            return LedgerCheckpoint(0, None, self._stream_id)
        return LedgerCheckpoint(
            len(self._receipts), self._receipts[-1].receipt_hash, self._stream_id
        )

    def to_records(self) -> list[dict[str, Any]]:
        return [
            {
                "sequence": receipt.sequence,
                "event": receipt.event,
                "state_before": receipt.state_before,
                "state_after": receipt.state_after,
                "payload": _plain(receipt.payload),
                "previous_hash": receipt.previous_hash,
                "receipt_hash": receipt.receipt_hash,
            }
            for receipt in self._receipts
        ]

    @classmethod
    def from_records(
        cls, records: Iterable[Mapping[str, Any]], *, checkpoint: LedgerCheckpoint
    ) -> Ledger:
        try:
            receipts = []
            for record in records:
                raw = dict(record)
                receipt = Receipt.create(
                    raw["sequence"],
                    raw["event"],
                    raw["state_before"],
                    raw["state_after"],
                    raw["payload"],
                    raw["previous_hash"],
                )
                if raw["receipt_hash"] != receipt.receipt_hash:
                    raise ForgeError(
                        "LEDGER_CORRUPT", "Persisted receipt hash does not match its content"
                    )
                receipts.append(receipt)
        except ForgeError:
            raise
        except (TypeError, KeyError, ValueError) as exc:
            raise ForgeError(
                "MALFORMED_RECEIPT", "Persisted record does not match the receipt schema"
            ) from exc
        ledger = cls(receipts, stream_id=checkpoint.stream_id)
        if ledger.checkpoint != checkpoint:
            raise ForgeError(
                "LEDGER_CHECKPOINT_MISMATCH",
                "Persisted ledger is truncated or differs from its independent checkpoint",
            )
        return ledger

    def append(self, receipt: Receipt) -> None:
        if not isinstance(receipt, Receipt):
            raise ForgeError("MALFORMED_RECEIPT", "Persisted record is not a Receipt")
        expected = Receipt.create(
            receipt.sequence,
            receipt.event,
            receipt.state_before,
            receipt.state_after,
            receipt.payload,
            receipt.previous_hash,
        )
        if receipt.receipt_hash != expected.receipt_hash:
            raise ForgeError("INVALID_RECEIPT", "Receipt hash does not match its content")
        if self._receipts:
            prior = self._receipts[-1]
            if (
                receipt.sequence != prior.sequence + 1
                or receipt.previous_hash != prior.receipt_hash
            ):
                raise ForgeError(
                    "LEDGER_APPEND_VIOLATION", "Receipt is not the next append-only record"
                )
        elif receipt.sequence != 1 or receipt.previous_hash is not None:
            raise ForgeError("LEDGER_APPEND_VIOLATION", "First receipt must start sequence one")
        self._receipts.append(expected)

    def verify(self) -> None:
        prior: Receipt | None = None
        for expected_sequence, receipt in enumerate(self._receipts, 1):
            if not isinstance(receipt, Receipt):
                raise ForgeError("MALFORMED_RECEIPT", "Persisted record is not a Receipt")
            expected = Receipt.create(
                receipt.sequence,
                receipt.event,
                receipt.state_before,
                receipt.state_after,
                receipt.payload,
                receipt.previous_hash,
            )
            if (
                receipt.sequence != expected_sequence
                or receipt.receipt_hash != expected.receipt_hash
            ):
                raise ForgeError("LEDGER_CORRUPT", "Ledger receipt content or sequence is invalid")
            if receipt.previous_hash != (prior.receipt_hash if prior else None):
                raise ForgeError("LEDGER_CORRUPT", "Ledger receipt chain is invalid")
            prior = receipt

    def replay(self) -> MissionState | None:
        self.verify()
        state: MissionState | None = None
        for receipt in self._receipts:
            if receipt.event == "INTERRUPTED_EFFECT_RECONCILIATION":
                if (
                    state is None
                    or receipt.state_before != state.value
                    or receipt.state_after != state.value
                ):
                    raise ForgeError(
                        "REPLAY_MISMATCH",
                        "Reconciliation receipt is not bound to the current mission state",
                    )
                try:
                    evidence = _reconciliation_evidence_from_payload(receipt.payload)
                except (KeyError, TypeError, ValueError, ForgeError) as exc:
                    raise ForgeError(
                        "REPLAY_MISMATCH", "Reconciliation evidence is malformed"
                    ) from exc
                if (
                    evidence.status is not EvidenceStatus.PRESENT
                    or evidence.repository_digest != receipt.payload.get("repository_digest")
                ):
                    raise ForgeError(
                        "REPLAY_MISMATCH",
                        "Reconciliation receipt does not prove a completed effect",
                    )
                continue
            if receipt.event != "STATE_TRANSITION":
                raise ForgeError(
                    "UNKNOWN_LEDGER_EVENT", f"Unrecognized mission ledger event: {receipt.event}"
                )
            try:
                evidence = _transition_evidence_from_payload(receipt.payload)
            except (KeyError, TypeError, ValueError, ForgeError) as exc:
                raise ForgeError(
                    "REPLAY_MISMATCH", "State transition evidence is malformed"
                ) from exc
            if (
                evidence.status is not EvidenceStatus.PRESENT
                or not all(
                    (
                        evidence.evidence_digest,
                        evidence.issuer_digest,
                        evidence.repository_digest,
                        evidence.state_after,
                        evidence.issuer_signature,
                    )
                )
                or evidence.repository_digest != receipt.payload.get("repository_digest")
                or evidence.state_before != receipt.state_before
                or evidence.state_after != receipt.state_after
            ):
                raise ForgeError(
                    "REPLAY_MISMATCH", "State transition evidence is absent or ambiguous"
                )
            if receipt.state_before != (state.value if state else None):
                raise ForgeError(
                    "REPLAY_MISMATCH", "Receipt state-before does not match replay state"
                )
            try:
                target = MissionState(receipt.state_after) if receipt.state_after else None
            except ValueError as exc:
                raise ForgeError(
                    "REPLAY_MISMATCH", "Receipt contains an unknown mission state"
                ) from exc
            if target is None:
                raise ForgeError(
                    "REPLAY_MISMATCH", "State transition receipt requires a target state"
                )
            if state is None and target is not MissionState.INITIALIZING:
                raise ForgeError(
                    "REPLAY_MISMATCH", "First replayed mission state must be INITIALIZING"
                )
            if state is not None and target not in _TRANSITIONS[state]:
                raise ForgeError(
                    "REPLAY_MISMATCH", f"Illegal replay transition: {state} to {target}"
                )
            _validate_replayed_transition_prerequisites(target, receipt.payload)
            state = target
        return state


_TRANSITIONS: dict[MissionState, frozenset[MissionState]] = {
    MissionState.INITIALIZING: frozenset({MissionState.UNDERSTANDING}),
    MissionState.UNDERSTANDING: frozenset({MissionState.PLANNING}),
    MissionState.PLANNING: frozenset({MissionState.TASK_READY}),
    MissionState.TASK_READY: frozenset({MissionState.IMPLEMENTING}),
    MissionState.IMPLEMENTING: frozenset({MissionState.TESTING}),
    MissionState.TESTING: frozenset({MissionState.REPAIRING, MissionState.AUDITING}),
    MissionState.REPAIRING: frozenset({MissionState.TESTING, MissionState.STUCK_RESOLUTION}),
    MissionState.STUCK_RESOLUTION: frozenset({MissionState.IMPLEMENTING, MissionState.PAUSED}),
    MissionState.AUDITING: frozenset(
        {MissionState.MERGING, MissionState.REPAIRING, MissionState.DISCOVERY_REVIEW}
    ),
    MissionState.DISCOVERY_REVIEW: frozenset({MissionState.ACCEPTED, MissionState.REJECTED}),
    MissionState.ACCEPTED: frozenset({MissionState.SPEC_EVOLUTION}),
    MissionState.SPEC_EVOLUTION: frozenset({MissionState.REPLANNING}),
    MissionState.REJECTED: frozenset({MissionState.REPLANNING}),
    MissionState.REPLANNING: frozenset({MissionState.PLANNING}),
    MissionState.MERGING: frozenset({MissionState.OUTCOME_EVALUATION}),
    MissionState.OUTCOME_EVALUATION: frozenset({MissionState.LEARNING}),
    MissionState.LEARNING: frozenset({MissionState.RECONCILING}),
    MissionState.RECONCILING: frozenset({MissionState.FINISH_EVALUATION}),
    MissionState.FINISH_EVALUATION: frozenset(
        {MissionState.PLANNING, MissionState.COMPLETE, MissionState.PAUSED}
    ),
    MissionState.PAUSED: frozenset({MissionState.RECONCILING, MissionState.PLANNING}),
    MissionState.COMPLETE: frozenset(),
}


class TrustKernel:
    def __init__(
        self,
        repository: RepositoryIdentity,
        *,
        mission_id: str,
        ledger: Ledger | None = None,
        ledger_checkpoint: LedgerCheckpoint | None = None,
        auditor_verification_keys: Mapping[str, bytes] | None = None,
        evidence_verification_keys: Mapping[str, bytes] | None = None,
        owner_verification_keys: Mapping[str, bytes] | None = None,
        trusted_builder_contexts: frozenset[str] = frozenset(),
        protected_candidate_digests: frozenset[str] = frozenset(),
        finish_contract_digest: str | None = None,
    ):
        if not mission_id:
            raise ForgeError("INVALID_MISSION_ID", "Mission identity is required")
        self._mission_id = mission_id
        self._repository = repository
        self._auditor_verification_keys = dict(auditor_verification_keys or {})
        self._evidence_verification_keys = dict(evidence_verification_keys or {})
        self._owner_verification_keys = dict(owner_verification_keys or {})
        self._trusted_builder_contexts = frozenset(trusted_builder_contexts)
        self._protected_candidate_digests = frozenset(protected_candidate_digests)
        self._protection_policy_digest = _digest(
            {"protected_candidate_digests": sorted(self._protected_candidate_digests)}
        )
        self._finish_contract_digest = finish_contract_digest
        if self._auditor_verification_keys.keys() & self._trusted_builder_contexts:
            raise ForgeError(
                "CONTEXT_AUTHORITY_CONFLICT", "Builder and Auditor contexts must be disjoint"
            )
        restoring = ledger is not None
        source_ledger = ledger if ledger is not None else Ledger()
        if restoring and ledger_checkpoint is None:
            raise ForgeError(
                "LEDGER_CHECKPOINT_REQUIRED",
                "Restoring a persisted mission requires an independent ledger checkpoint",
            )
        if ledger_checkpoint is not None and source_ledger.checkpoint != ledger_checkpoint:
            raise ForgeError(
                "LEDGER_CHECKPOINT_MISMATCH",
                "Persisted mission ledger is truncated or differs from its checkpoint",
            )
        if (
            restoring
            and ledger_checkpoint is not None
            and ledger_checkpoint.stream_id != mission_id
        ):
            raise ForgeError(
                "MISSION_IDENTITY_MISMATCH",
                "Persisted ledger checkpoint belongs to a different mission",
            )
        self._ledger = Ledger(source_ledger.receipts, stream_id=mission_id)
        for receipt in self._ledger.receipts:
            if receipt.payload.get("repository_digest") != repository.digest:
                raise ForgeError(
                    "WRONG_REPOSITORY",
                    "Persisted mission receipt belongs to a different repository",
                )
            if receipt.payload.get("mission_id") != mission_id:
                raise ForgeError(
                    "MISSION_IDENTITY_MISMATCH", "Persisted receipt belongs to a different mission"
                )
        self._state = self._ledger.replay() if self._ledger.receipts else None
        self._merged_candidate_digest = self._validate_governed_receipts()

    @property
    def state(self) -> MissionState | None:
        return self._state

    @property
    def repository(self) -> RepositoryIdentity:
        return self._repository

    @property
    def ledger(self) -> Ledger:
        """Return a detached immutable-history view of the kernel ledger."""
        return Ledger(self._ledger.receipts, stream_id=self._mission_id)

    def transition(
        self,
        target: MissionState,
        *,
        evidence: TransitionEvidence | None = None,
        authority_grant: AuthorityGrant | None = None,
        discovery: DiscoveryAuthorization | None = None,
        candidate: CandidateIdentity | None = None,
        validation: CandidateValidation | None = None,
        completion: CompletionEvaluation | None = None,
    ) -> Receipt:
        expected_before = self._state.value if self._state else None
        if (
            evidence is None
            or evidence.status is not EvidenceStatus.PRESENT
            or not self._transition_evidence_is_valid(evidence, expected_before, target.value)
        ):
            status = evidence.status.value if evidence else EvidenceStatus.UNKNOWN.value
            raise ForgeError(
                "UNKNOWN_EVIDENCE",
                "Transition requires signed, present, unambiguous evidence",
                details={"status": status},
            )
        if self._state is None:
            if target is not MissionState.INITIALIZING:
                raise ForgeError(
                    "INVALID_INITIAL_STATE", "First mission state must be INITIALIZING"
                )
        elif target not in _TRANSITIONS[self._state]:
            raise ForgeError("INVALID_TRANSITION", f"{self._state} cannot transition to {target}")
        payload: dict[str, Any] = {
            "repository_digest": self._repository.digest,
            "mission_id": self._mission_id,
            "evidence": asdict(evidence),
        }
        if target is MissionState.SPEC_EVOLUTION:
            if discovery is None:
                raise ForgeError(
                    "DISCOVERY_AUTHORIZATION_REQUIRED",
                    "Specification evolution requires a Discovery Record, evidence, and rationale",
                )
            self.authorize(
                ActionKind.SPECIFICATION_EVOLUTION,
                authority_grant,
                scope_digest=discovery.record_digest,
            )
            payload["discovery"] = asdict(discovery)
            payload["authority_grant"] = asdict(authority_grant)
        if target is MissionState.MERGING:
            if candidate is None or validation is None:
                raise ForgeError(
                    "CANDIDATE_VALIDATION_REQUIRED",
                    "Merging requires an exact candidate and independent PASS validation",
                )
            self.bind_candidate(candidate, self._repository)
            if not validation.is_valid_for(candidate) or not self._validation_is_trusted(
                validation
            ):
                raise ForgeError(
                    "CANDIDATE_VALIDATION_REQUIRED",
                    "Merging requires an exact candidate-bound independent PASS",
                )
            candidate_is_protected = candidate.digest in self._protected_candidate_digests
            payload["protection_policy_digest"] = self._protection_policy_digest
            payload["candidate_is_protected"] = candidate_is_protected
            if candidate_is_protected:
                self.authorize(ActionKind.PROTECTED, authority_grant, scope_digest=candidate.digest)
                payload["authority_grant"] = asdict(authority_grant)
            payload["candidate"] = asdict(candidate)
            payload["validation"] = asdict(validation)
        if target is MissionState.COMPLETE:
            if completion is None or completion.result != "PASS":
                raise ForgeError(
                    "FINISH_CONTRACT_EVALUATION_REQUIRED",
                    "Completion requires a PASS Finish Contract evaluation",
                )
            if (
                completion.candidate_digest != self._merged_candidate_digest
                or completion.finish_contract_digest != self._finish_contract_digest
            ):
                raise ForgeError(
                    "FINISH_CONTRACT_EVALUATION_REQUIRED",
                    "Completion evaluation is not bound to the merged candidate",
                )
            if not self._auditor_receipt_is_valid(completion):
                raise ForgeError(
                    "UNTRUSTED_COMPLETION_AUDIT",
                    "Completion evaluation must carry a valid trusted Auditor signature",
                )
            payload["completion"] = asdict(completion)
        before = expected_before
        previous = self._ledger.receipts[-1].receipt_hash if self._ledger.receipts else None
        receipt = Receipt.create(
            len(self._ledger.receipts) + 1,
            "STATE_TRANSITION",
            before,
            target.value,
            payload,
            previous,
        )
        self._ledger.append(receipt)
        self._state = target
        if target is MissionState.MERGING and candidate is not None:
            self._merged_candidate_digest = candidate.digest
        return receipt

    def _validation_is_trusted(self, validation: CandidateValidation) -> bool:
        return (
            validation.is_independent_pass
            and validation.builder_context_digest in self._trusted_builder_contexts
            and self._auditor_receipt_is_valid(validation)
        )

    def _transition_evidence_is_valid(
        self, evidence: TransitionEvidence, state_before: str | None, state_after: str
    ) -> bool:
        key = self._evidence_verification_keys.get(evidence.issuer_digest)
        if key is None:
            return False
        if (
            evidence.repository_digest != self._repository.digest
            or evidence.state_before != state_before
            or evidence.state_after != state_after
        ):
            return False
        body = {
            "status": evidence.status.value,
            "evidence_digest": evidence.evidence_digest,
            "issuer_digest": evidence.issuer_digest,
            "repository_digest": evidence.repository_digest,
            "state_before": evidence.state_before,
            "state_after": evidence.state_after,
        }
        return hmac.compare_digest(evidence.issuer_signature, _sign(body, key))

    def _auditor_receipt_is_valid(
        self, receipt: CandidateValidation | CompletionEvaluation
    ) -> bool:
        key = self._auditor_verification_keys.get(receipt.auditor_context_digest)
        if key is None:
            return False
        body = asdict(receipt)
        signature = body.pop("issuer_signature")
        return hmac.compare_digest(signature, _sign(body, key))

    def _validate_governed_receipts(self) -> str | None:
        merged_candidate_digest: str | None = None
        for receipt in self._ledger.receipts:
            if receipt.event == "INTERRUPTED_EFFECT_RECONCILIATION":
                evidence = _reconciliation_evidence_from_payload(receipt.payload)
                if (
                    not self._reconciliation_evidence_is_valid(evidence)
                    or evidence.status is not EvidenceStatus.PRESENT
                ):
                    raise ForgeError(
                        "UNTRUSTED_RECONCILIATION_EVIDENCE",
                        "Interrupted-effect reconciliation is not backed by trusted evidence",
                    )
                continue
            if receipt.event != "STATE_TRANSITION":
                continue
            target = MissionState(receipt.state_after)
            evidence = _transition_evidence_from_payload(receipt.payload)
            if not self._transition_evidence_is_valid(
                evidence, receipt.state_before, receipt.state_after or ""
            ):
                raise ForgeError(
                    "UNTRUSTED_TRANSITION_EVIDENCE",
                    "Transition receipt evidence signature is not trusted",
                )
            if target is MissionState.SPEC_EVOLUTION:
                discovery = DiscoveryAuthorization(**receipt.payload["discovery"])
                grant = _authority_grant_from_payload(receipt.payload)
                self.authorize(
                    ActionKind.SPECIFICATION_EVOLUTION, grant, scope_digest=discovery.record_digest
                )
            if target is MissionState.MERGING:
                candidate = CandidateIdentity(**receipt.payload["candidate"])
                validation = CandidateValidation(**receipt.payload["validation"])
                if (
                    receipt.payload.get("protection_policy_digest")
                    != self._protection_policy_digest
                ):
                    raise ForgeError(
                        "PROTECTION_POLICY_MISMATCH",
                        "Merge receipt protection policy is absent or differs from the configured policy",
                    )
                candidate_is_protected = candidate.digest in self._protected_candidate_digests
                if receipt.payload.get("candidate_is_protected") is not candidate_is_protected:
                    raise ForgeError(
                        "PROTECTION_POLICY_MISMATCH",
                        "Merge receipt candidate protection classification is inconsistent",
                    )
                if not self._validation_is_trusted(validation):
                    raise ForgeError(
                        "UNTRUSTED_AUDIT_CONTEXT",
                        "Merge receipt is not backed by trusted independent execution identities",
                    )
                if candidate_is_protected:
                    self.authorize(
                        ActionKind.PROTECTED,
                        _authority_grant_from_payload(receipt.payload),
                        scope_digest=candidate.digest,
                    )
                merged_candidate_digest = candidate.digest
            if target is MissionState.COMPLETE:
                completion = CompletionEvaluation(**receipt.payload["completion"])
                if (
                    completion.result != "PASS"
                    or completion.candidate_digest != merged_candidate_digest
                    or completion.finish_contract_digest != self._finish_contract_digest
                ):
                    raise ForgeError(
                        "REPLAY_MISMATCH",
                        "Completion receipt is not bound to the merged candidate and Finish Contract PASS",
                    )
                if not self._auditor_receipt_is_valid(completion):
                    raise ForgeError(
                        "UNTRUSTED_COMPLETION_AUDIT",
                        "Completion receipt lacks a valid trusted Auditor signature",
                    )
        return merged_candidate_digest

    def authorize(
        self, action: ActionKind, grant: AuthorityGrant | None, *, scope_digest: str
    ) -> None:
        required = {
            ActionKind.ROUTINE: Authority.A1,
            ActionKind.SPECIFICATION_EVOLUTION: Authority.A2,
            ActionKind.PROTECTED: Authority.A3,
        }[action]
        if grant is None:
            raise ForgeError("AUTHORITY_GRANT_REQUIRED", "Action requires a signed authority grant")
        key = self._owner_verification_keys.get(grant.owner_ref)
        body = {
            "authority": grant.authority.value,
            "action": grant.action.value,
            "scope_digest": grant.scope_digest,
            "owner_ref": grant.owner_ref,
        }
        signature_valid = key is not None and hmac.compare_digest(
            grant.issuer_signature, _sign(body, key)
        )
        if not signature_valid or grant.action is not action or grant.scope_digest != scope_digest:
            raise ForgeError(
                "UNTRUSTED_AUTHORITY_GRANT", "Authority grant is not authentic or scope-bound"
            )
        if int(grant.authority.value[1]) < int(required.value[1]):
            raise ForgeError(
                "INSUFFICIENT_AUTHORITY",
                "Action requires higher authority",
                details={"required": required.value, "provided": grant.authority.value},
            )

    def bind_candidate(self, candidate: CandidateIdentity, repository: RepositoryIdentity) -> None:
        if (
            repository.digest != self._repository.digest
            or candidate.repository_digest != self._repository.digest
        ):
            raise ForgeError("WRONG_REPOSITORY", "Candidate belongs to a different repository")

    def _reconciliation_evidence_is_valid(self, evidence: ReconciliationEvidence) -> bool:
        key = self._evidence_verification_keys.get(evidence.issuer_digest)
        if key is None or evidence.repository_digest != self._repository.digest:
            return False
        body = asdict(evidence)
        signature = body.pop("issuer_signature")
        return hmac.compare_digest(signature, _sign(body, key))

    def reconcile_interrupted(
        self, *, effect_digest: str, evidence: ReconciliationEvidence | None
    ) -> ReconciliationStatus:
        if evidence is None or evidence.status in (
            EvidenceStatus.ABSENT,
            EvidenceStatus.AMBIGUOUS,
            EvidenceStatus.UNKNOWN,
        ):
            return ReconciliationStatus.UNKNOWN
        if evidence.effect_digest != effect_digest or not self._reconciliation_evidence_is_valid(
            evidence
        ):
            raise ForgeError(
                "UNTRUSTED_RECONCILIATION_EVIDENCE",
                "Reconciliation evidence is not authentic and effect-bound",
            )
        if self._state is None:
            raise ForgeError(
                "RECONCILIATION_STATE_REQUIRED",
                "Interrupted-effect reconciliation requires an initialized mission",
            )
        previous = self._ledger.receipts[-1].receipt_hash
        payload = {
            "repository_digest": self._repository.digest,
            "mission_id": self._mission_id,
            "evidence": asdict(evidence),
        }
        receipt = Receipt.create(
            len(self._ledger.receipts) + 1,
            "INTERRUPTED_EFFECT_RECONCILIATION",
            self._state.value,
            self._state.value,
            payload,
            previous,
        )
        self._ledger.append(receipt)
        if evidence.disposition is EffectDisposition.COMPLETED:
            return ReconciliationStatus.EFFECT_COMPLETED
        if evidence.disposition is EffectDisposition.NOT_STARTED:
            return ReconciliationStatus.SAFE_TO_RETRY
        return ReconciliationStatus.UNKNOWN


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


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def _validate_replayed_transition_prerequisites(
    target: MissionState, payload: Mapping[str, Any]
) -> None:
    if target is MissionState.SPEC_EVOLUTION:
        try:
            discovery = DiscoveryAuthorization(**payload["discovery"])
            grant = _authority_grant_from_payload(payload)
        except (KeyError, TypeError, ValueError, ForgeError) as exc:
            raise ForgeError(
                "REPLAY_MISMATCH",
                "Specification evolution receipt lacks governed discovery authorization",
            ) from exc
        if (
            int(grant.authority.value[1]) < int(Authority.A2.value[1])
            or grant.action is not ActionKind.SPECIFICATION_EVOLUTION
            or grant.scope_digest != discovery.record_digest
        ):
            raise ForgeError(
                "REPLAY_MISMATCH", "Specification evolution receipt lacks A2 authority"
            )
    if target is MissionState.MERGING:
        try:
            candidate = CandidateIdentity(**payload["candidate"])
            validation = CandidateValidation(**payload["validation"])
            repository_digest = payload["repository_digest"]
            protection_policy_digest = payload["protection_policy_digest"]
            candidate_is_protected = payload["candidate_is_protected"]
        except (KeyError, TypeError, ForgeError) as exc:
            raise ForgeError(
                "REPLAY_MISMATCH", "Merge receipt lacks candidate-bound validation"
            ) from exc
        if (
            not isinstance(protection_policy_digest, str)
            or not protection_policy_digest
            or not isinstance(candidate_is_protected, bool)
        ):
            raise ForgeError(
                "REPLAY_MISMATCH", "Merge receipt lacks a governed protection policy classification"
            )
        if (
            candidate.repository_digest != repository_digest
            or not validation.is_valid_for(candidate)
            or not validation.is_independent_pass
        ):
            raise ForgeError(
                "REPLAY_MISMATCH", "Merge receipt lacks an exact candidate-bound independent PASS"
            )
    if target is MissionState.COMPLETE:
        try:
            completion = CompletionEvaluation(**payload["completion"])
        except (KeyError, TypeError, ForgeError) as exc:
            raise ForgeError(
                "REPLAY_MISMATCH", "Completion receipt lacks Finish Contract evaluation evidence"
            ) from exc
        if completion.result != "PASS":
            raise ForgeError("REPLAY_MISMATCH", "Completion receipt lacks a Finish Contract PASS")


def _transition_evidence_from_payload(payload: Mapping[str, Any]) -> TransitionEvidence:
    data = payload["evidence"]
    return TransitionEvidence(
        status=EvidenceStatus(data["status"]),
        evidence_digest=data["evidence_digest"],
        issuer_digest=data["issuer_digest"],
        repository_digest=data["repository_digest"],
        state_before=data["state_before"],
        state_after=data["state_after"],
        issuer_signature=data["issuer_signature"],
    )


def _reconciliation_evidence_from_payload(payload: Mapping[str, Any]) -> ReconciliationEvidence:
    data = payload["evidence"]
    return ReconciliationEvidence(
        status=EvidenceStatus(data["status"]),
        disposition=EffectDisposition(data["disposition"]),
        effect_digest=data["effect_digest"],
        evidence_digest=data["evidence_digest"],
        issuer_digest=data["issuer_digest"],
        repository_digest=data["repository_digest"],
        issuer_signature=data["issuer_signature"],
    )


def _authority_grant_from_payload(payload: Mapping[str, Any]) -> AuthorityGrant:
    data = payload["authority_grant"]
    return AuthorityGrant(
        authority=Authority(data["authority"]),
        action=ActionKind(data["action"]),
        scope_digest=data["scope_digest"],
        owner_ref=data["owner_ref"],
        issuer_signature=data["issuer_signature"],
    )
