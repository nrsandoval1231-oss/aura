"""Outcome and lesson engines: retained experience that can change later behaviour.

Built against the nine numbered evidence requirements in
`docs/self-improvement-acceptance.md`, which is explicit that storing lessons is not
the capability:

> The later Learning Engine cannot be accepted merely because it stores lessons.

So the types here are shaped by what has to be *provable* afterwards, not by what is
convenient to record. Each one carries the field that makes a later claim checkable:

  1. `OutcomeRecord`    — repository, candidate, packet, strategy, evidence, metric
  2. `CandidateLesson`  — context, diagnosis, intended change, negative knowledge
  3. `LessonDecision`   — an independent validate-or-reject with evidence and scope
  4. `LessonScope`      — repository-scoped in V0; global promotion is refused
  5. `RetrievalRecord`  — the lesson was available during later planning
  6. `ApplicationRecord`— whether the retrieved lesson changed the chosen strategy
  7. `Measurement`      — the named metric after application, UNKNOWN when unsound
  8. `LessonState`      — demotion and rollback when a lesson harms its own metric
  9. protected-surface refusal — self-modification never reaches governance

Three things this module refuses to do, because each is a way of appearing to learn
--------------------------------------------------------------------------------
**It will not validate a lesson on its author's word.** `validate` requires a
validator distinct from the author. A lesson that certifies itself is a stored
opinion.

**It will not let a lesson weaken what it was measured against.** A lesson whose
intended change touches a protected surface, or which proposes relaxing a
requirement or a gate, is refused outright — requirement 9, and the reason
`AGENT_RULES` says a lesson "may improve execution but may not weaken requirements
or governance". Getting green by lowering the bar is the failure mode that makes
self-improvement dangerous rather than merely useless.

**It will not report an improvement it cannot attribute.** `measure` returns UNKNOWN
when the baseline is missing, the metric is not the one the lesson named, or the
candidate differs. Requirement 7 asks for UNKNOWN in exactly these cases, and a
learning engine that reports improvement it cannot attribute is worse than one that
reports nothing, because it will be believed.

Retrieval is deterministic token similarity over failure signatures. FORGE-LRN-001
names full-text search as the eventual mechanism; Jaccard overlap is the honest
stand-in, and it is the whole of the ranking — no model is consulted, so the same
failure retrieves the same lessons on every run.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from forge.policy import requires_owner_authority

__all__ = [
    "ApplicationRecord",
    "CandidateLesson",
    "LearningError",
    "Lesson",
    "LessonDecision",
    "LessonScope",
    "LessonState",
    "LessonStore",
    "MeasurementVerdict",
    "Measurement",
    "Metric",
    "MetricDirection",
    "OutcomeRecord",
    "RetrievalRecord",
    "failure_signature",
    "similarity",
]


class LearningError(Exception):
    """Structured fail-closed error.

    Local rather than `trust_kernel.ForgeError` for the same reason `stuck` keeps its
    own: the learning engine is the part of the system that changes behaviour over
    time, and it must not be able to reach into transition validation.
    """

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, "details": self.details}


class MetricDirection(StrEnum):
    """Which way is better. A metric without a direction cannot show improvement."""

    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"


class LessonScope(StrEnum):
    #: The only scope V0 promotes to (requirement 4).
    REPOSITORY = "REPOSITORY"
    #: Named so that refusing it is explicit rather than an omission.
    GLOBAL = "GLOBAL"


class LessonState(StrEnum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    DEMOTED = "DEMOTED"
    ROLLED_BACK = "ROLLED_BACK"


class MeasurementVerdict(StrEnum):
    IMPROVED = "IMPROVED"
    UNCHANGED = "UNCHANGED"
    HARMED = "HARMED"
    #: Requirement 7: UNKNOWN when attribution or evidence is insufficient.
    UNKNOWN = "UNKNOWN"


#: Phrases that propose getting green by lowering the bar. Matched against a
#: lesson's intended change, because this is the one category of "improvement" that
#: must never be learnable (requirement 9, AGENT_RULES "Learning").
#: Up to three words may sit between the verb and its object, so "skip the failing
#: test" and "disable that flaky coverage gate" are caught alongside the bare forms.
#: Non-greedy, so the match reported is the shortest one and names the real phrase.
_GAP = r"(?:\s+\w+){0,3}?\s+(?:the\s+|that\s+|this\s+)?"


def _weakens(verb: str, *objects: str) -> str:
    return rf"\b{verb}(?:{_GAP}|\s+)(?:{'|'.join(objects)})\w*"


_WEAKENING_PHRASES = (
    _weakens(r"skip(?:ping)?", "test", "check", "gate", "audit", "validation", "assertion"),
    _weakens(r"disabl\w*", "test", "check", "gate", "audit", "validation", "guard"),
    _weakens(r"(?:remove|delete|drop)", "test", "check", "gate", "assertion", "audit", "guard"),
    _weakens(r"relax\w*", "requirement", "invariant", "gate", "threshold", "rule"),
    _weakens(r"lower\w*", "bar", "threshold", "coverage", "requirement"),
    _weakens(r"quarantin\w*", "test", "suite"),
    _weakens(r"bypass\w*", "gate", "audit", "authority", "guard", "check"),
    _weakens(r"widen\w*", "authority", "scope", "permission"),
    _weakens(r"loosen\w*", "check", "gate", "rule", "requirement", "invariant"),
    r"\bxfail\b",
    r"\bpytest\.mark\.skip\b",
    r"\bweaken\w*\b",
)
_WEAKENING = re.compile("|".join(_WEAKENING_PHRASES), re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Metric:
    """A named directional metric and its value."""

    name: str
    value: float
    direction: MetricDirection

    def __post_init__(self) -> None:
        object.__setattr__(self, "direction", MetricDirection(self.direction))
        if not self.name.strip():
            raise LearningError("INVALID_METRIC", "A metric must be named to be measurable")

    def improves_on(self, baseline: Metric) -> bool:
        if self.name != baseline.name:
            raise LearningError(
                "METRIC_MISMATCH",
                f"Cannot compare {self.name!r} against {baseline.name!r}",
            )
        if self.direction is MetricDirection.LOWER_IS_BETTER:
            return self.value < baseline.value
        return self.value > baseline.value

    def harms(self, baseline: Metric) -> bool:
        if self.name != baseline.name:
            raise LearningError(
                "METRIC_MISMATCH",
                f"Cannot compare {self.name!r} against {baseline.name!r}",
            )
        if self.direction is MetricDirection.LOWER_IS_BETTER:
            return self.value > baseline.value
        return self.value < baseline.value


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    """Requirement 1: attributable experience, down to the exact candidate."""

    packet_id: str
    repository_digest: str
    candidate_digest: str
    strategy_digest: str
    evidence_digest: str
    metric: Metric
    failing_checks: frozenset[str] = frozenset()
    succeeded: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "failing_checks", frozenset(self.failing_checks))
        missing = [
            name
            for name in (
                "packet_id",
                "repository_digest",
                "candidate_digest",
                "strategy_digest",
                "evidence_digest",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise LearningError(
                "UNATTRIBUTABLE_OUTCOME",
                f"An outcome record must identify {missing}; an outcome that cannot be "
                "attributed cannot support a lesson",
                details={"missing": missing},
            )

    @property
    def digest(self) -> str:
        return _digest(_plain(asdict(self)))


@dataclass(frozen=True, slots=True)
class CandidateLesson:
    """Requirement 2: context, diagnosis, intended change, and negative knowledge."""

    id: str
    author: str
    context: str
    diagnosis: str
    intended_change: str
    metric_name: str
    #: What was tried and did not work. Required: a lesson that records only the
    #: success discards the more reusable half of the experience.
    negative_knowledge: tuple[str, ...]
    #: Failure signatures this lesson is about, used for retrieval.
    failure_signatures: tuple[str, ...]
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("negative_knowledge", "failure_signatures", "derived_from"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ("id", "author", "context", "diagnosis", "intended_change", "metric_name"):
            if not str(getattr(self, name)).strip():
                raise LearningError(
                    "INCOMPLETE_LESSON",
                    f"A candidate lesson requires {name}; the acceptance contract names "
                    "context, diagnosis, intended behaviour change, and a metric",
                )
        if not self.negative_knowledge:
            raise LearningError(
                "INCOMPLETE_LESSON",
                "A candidate lesson requires negative knowledge — what was tried and "
                "failed. Recording only what worked discards the reusable half.",
            )
        if not self.derived_from:
            raise LearningError(
                "UNATTRIBUTABLE_LESSON",
                "A candidate lesson must cite the outcome records it came from",
            )

    @property
    def digest(self) -> str:
        return _digest(_plain(asdict(self)))


@dataclass(frozen=True, slots=True)
class LessonDecision:
    """Requirement 3: an independent validate-or-reject, with evidence and scope."""

    lesson_id: str
    validator: str
    validated: bool
    scope: LessonScope
    evidence_digest: str
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", LessonScope(self.scope))
        if not self.evidence_digest:
            raise LearningError(
                "UNEVIDENCED_DECISION", "A validation decision must cite its evidence"
            )
        if not self.validator.strip():
            raise LearningError("INVALID_DECISION", "A validation decision must name its validator")


@dataclass(frozen=True, slots=True)
class Lesson:
    """A candidate lesson plus the decision that moved it out of candidacy."""

    candidate: CandidateLesson
    state: LessonState
    scope: LessonScope | None = None
    decision: LessonDecision | None = None
    baseline: Metric | None = None

    @property
    def id(self) -> str:
        return self.candidate.id

    @property
    def is_applicable(self) -> bool:
        """Only a validated, repository-scoped lesson may influence later work."""
        return self.state is LessonState.VALIDATED and self.scope is LessonScope.REPOSITORY


@dataclass(frozen=True, slots=True)
class RetrievalRecord:
    """Requirement 5: proof the lesson was on the table during later planning."""

    packet_id: str
    query_signature: str
    retrieved: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "retrieved", tuple(self.retrieved))

    @property
    def lesson_ids(self) -> tuple[str, ...]:
        return tuple(lesson_id for lesson_id, _ in self.retrieved)

    @property
    def digest(self) -> str:
        return _digest({"packet_id": self.packet_id, "retrieved": list(self.retrieved)})


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    """Requirement 6: did the retrieved lesson actually change the chosen strategy?

    `changed_strategy` is derived from the two strategy digests rather than asserted,
    so "the lesson helped" cannot be recorded about a decision that was identical
    either way. That is the difference between a decision receipt and a claim.
    """

    packet_id: str
    lesson_id: str
    retrieval_digest: str
    candidate_digest: str
    strategy_without_lesson: str
    strategy_with_lesson: str

    def __post_init__(self) -> None:
        if not self.retrieval_digest:
            raise LearningError(
                "UNLINKED_APPLICATION",
                "An application record must cite the retrieval that made the lesson "
                "available; otherwise there is no evidence it was ever consulted",
            )
        if not self.candidate_digest:
            raise LearningError(
                "UNATTRIBUTABLE_APPLICATION",
                "An application record must identify the candidate whose strategy changed",
            )

    @property
    def changed_strategy(self) -> bool:
        return self.strategy_without_lesson != self.strategy_with_lesson

    @property
    def digest(self) -> str:
        return _digest(_plain(asdict(self)))


@dataclass(frozen=True, slots=True)
class Measurement:
    """Requirement 7: the named metric after application, or UNKNOWN."""

    lesson_id: str
    verdict: MeasurementVerdict
    baseline: Metric | None
    observed: Metric | None
    reason: str

    @property
    def digest(self) -> str:
        return _digest(_plain(asdict(self)))


_TOKEN = re.compile(r"[a-z0-9_]+")


def failure_signature(failing_checks: Iterable[str], error_text: str = "") -> str:
    """A stable, order-independent signature for one failure mode.

    Sorted, so the same failures in a different order produce the same signature —
    test runners do not guarantee order, and a signature that changed with it would
    make retrieval miss the lesson it needed most.
    """
    tokens = sorted({token for token in _TOKEN.findall(" ".join(failing_checks).casefold())})
    error_tokens = sorted({token for token in _TOKEN.findall(error_text.casefold())})
    return " ".join([*tokens, *error_tokens])


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of signature tokens, in [0, 1].

    Deterministic and explainable on purpose. FORGE-LRN-001 names full-text search as
    the eventual mechanism; what matters for V0 acceptance is that the same failure
    retrieves the same lessons every run, which a model-ranked retrieval would not
    guarantee.
    """
    left_tokens = set(_TOKEN.findall(left.casefold()))
    right_tokens = set(_TOKEN.findall(right.casefold()))
    if not left_tokens or not right_tokens:
        return 0.0
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union)


class LessonStore:
    """Holds lessons and the records that make a behaviour-change claim checkable.

    Repository-scoped by construction: the store is created for one repository digest
    and refuses records from another. Requirement 4 disables global promotion in V0,
    and a store that silently accepted another repository's outcomes would be global
    promotion by accident.
    """

    #: Retrieval floor. Below this, an overlap is coincidence — two failures that
    #: merely both mention "test" should not put a lesson in front of a planner.
    MIN_SIMILARITY = 0.25

    def __init__(self, repository_digest: str):
        if not repository_digest:
            raise LearningError("INVALID_STORE", "A lesson store is scoped to a repository")
        self._repository_digest = repository_digest
        self._outcomes: dict[str, OutcomeRecord] = {}
        self._lessons: dict[str, Lesson] = {}
        self._retrievals: list[RetrievalRecord] = []
        self._applications: list[ApplicationRecord] = []
        self._measurements: list[Measurement] = []

    @property
    def repository_digest(self) -> str:
        return self._repository_digest

    @property
    def outcomes(self) -> Mapping[str, OutcomeRecord]:
        return dict(self._outcomes)

    @property
    def lessons(self) -> Mapping[str, Lesson]:
        return dict(self._lessons)

    @property
    def retrievals(self) -> tuple[RetrievalRecord, ...]:
        return tuple(self._retrievals)

    @property
    def applications(self) -> tuple[ApplicationRecord, ...]:
        return tuple(self._applications)

    @property
    def measurements(self) -> tuple[Measurement, ...]:
        return tuple(self._measurements)

    # -- requirement 1 ------------------------------------------------------

    def record_outcome(self, outcome: OutcomeRecord) -> None:
        if outcome.repository_digest != self._repository_digest:
            raise LearningError(
                "WRONG_REPOSITORY",
                "Outcome belongs to a different repository; V0 promotion is "
                "repository-scoped and cross-repository experience is not authorized",
            )
        self._outcomes[outcome.digest] = outcome

    # -- requirement 2, 9 ---------------------------------------------------

    def propose(self, candidate: CandidateLesson) -> Lesson:
        """Accept a candidate lesson, refusing the two kinds that must not exist."""
        unknown = [ref for ref in candidate.derived_from if ref not in self._outcomes]
        if unknown:
            raise LearningError(
                "UNATTRIBUTABLE_LESSON",
                "A lesson must derive from outcome records this store holds",
                details={"unknown_outcomes": unknown},
            )
        self._reject_weakening(candidate)
        self._reject_protected_self_modification(candidate)
        lesson = Lesson(candidate, LessonState.CANDIDATE)
        self._lessons[candidate.id] = lesson
        return lesson

    @staticmethod
    def _reject_weakening(candidate: CandidateLesson) -> None:
        match = _WEAKENING.search(candidate.intended_change)
        if match:
            raise LearningError(
                "LESSON_WEAKENS_GOVERNANCE",
                "This lesson proposes getting green by lowering the bar "
                f"({match.group(0)!r}). A lesson may improve execution but may not "
                "weaken requirements or governance (AGENT_RULES).",
                details={"matched": match.group(0)},
            )

    @staticmethod
    def _reject_protected_self_modification(candidate: CandidateLesson) -> None:
        """Requirement 9: never autonomously modify protected policy.

        The surfaces are read from `forge.policy`, the same registry the A3 authority
        check uses, so this cannot drift away from what the rest of the system treats
        as protected — which is exactly what audit F9 found happening to the last
        hand-maintained copy of a protection list.
        """
        reaching = sorted(
            {
                token
                for token in re.findall(
                    r"[\w./\\-]+\.(?:py|md|sh|json|toml)", candidate.intended_change
                )
                if requires_owner_authority(token)
            }
        )
        if reaching:
            raise LearningError(
                "LESSON_TOUCHES_PROTECTED_SURFACE",
                "A lesson may not propose autonomously modifying a protected surface: "
                f"{reaching}. Authority, audit independence, event integrity, and "
                "Finish Contract protections are outside self-modification in V0.",
                details={"protected": reaching},
            )

    # -- requirement 3, 4 ---------------------------------------------------

    def validate(self, decision: LessonDecision, *, baseline: Metric) -> Lesson:
        """Validate or reject a candidate lesson, independently and with a scope."""
        lesson = self._require_lesson(decision.lesson_id)
        if lesson.state is not LessonState.CANDIDATE:
            raise LearningError(
                "ALREADY_DECIDED",
                f"Lesson {lesson.id} is {lesson.state.value}, not a candidate",
            )
        if decision.validator == lesson.candidate.author:
            raise LearningError(
                "SELF_VALIDATED_LESSON",
                "A lesson cannot be validated by its own author. Without an "
                "independent decision, a retained lesson is a stored opinion.",
                details={"author": lesson.candidate.author},
            )
        if decision.validated and decision.scope is LessonScope.GLOBAL:
            raise LearningError(
                "GLOBAL_PROMOTION_DISABLED",
                "Automatic global promotion is disabled in V0; promote to REPOSITORY "
                "scope (self-improvement acceptance contract, requirement 4)",
            )
        if decision.validated and baseline.name != lesson.candidate.metric_name:
            raise LearningError(
                "METRIC_MISMATCH",
                f"Lesson {lesson.id} names metric {lesson.candidate.metric_name!r} but the "
                f"baseline measures {baseline.name!r}; an improvement claim needs the "
                "metric the lesson was about",
            )
        updated = Lesson(
            lesson.candidate,
            LessonState.VALIDATED if decision.validated else LessonState.REJECTED,
            decision.scope if decision.validated else None,
            decision,
            baseline if decision.validated else None,
        )
        self._lessons[lesson.id] = updated
        return updated

    # -- requirement 5 ------------------------------------------------------

    def retrieve(self, packet_id: str, query_signature: str, *, limit: int = 5) -> RetrievalRecord:
        """Rank applicable lessons against a failure signature, and record that we did.

        Recording happens whether or not anything is retrieved. An empty retrieval is
        evidence too: it distinguishes "no lesson applied because none was relevant"
        from "no lesson applied because nobody looked".
        """
        scored = [
            (
                lesson.id,
                max(
                    similarity(query_signature, sig) for sig in lesson.candidate.failure_signatures
                ),
            )
            for lesson in self._lessons.values()
            if lesson.is_applicable and lesson.candidate.failure_signatures
        ]
        ranked = sorted(
            ((lesson_id, score) for lesson_id, score in scored if score >= self.MIN_SIMILARITY),
            key=lambda pair: (-pair[1], pair[0]),
        )[:limit]
        record = RetrievalRecord(packet_id, query_signature, tuple(ranked))
        self._retrievals.append(record)
        return record

    # -- requirement 6 ------------------------------------------------------

    def record_application(self, application: ApplicationRecord) -> ApplicationRecord:
        lesson = self._require_lesson(application.lesson_id)
        if not lesson.is_applicable:
            raise LearningError(
                "LESSON_NOT_APPLICABLE",
                f"Lesson {lesson.id} is {lesson.state.value} and may not influence work",
            )
        retrieval = next(
            (
                record
                for record in self._retrievals
                if record.digest == application.retrieval_digest
            ),
            None,
        )
        if retrieval is None:
            raise LearningError(
                "UNLINKED_APPLICATION",
                "The cited retrieval is not one this store performed, so there is no "
                "evidence the lesson was available when the strategy was chosen",
            )
        if retrieval.packet_id != application.packet_id:
            raise LearningError(
                "MISMATCHED_APPLICATION",
                "The cited retrieval belongs to a different packet, so it cannot support "
                "this application",
            )
        if application.lesson_id not in retrieval.lesson_ids:
            raise LearningError(
                "MISMATCHED_APPLICATION",
                "The cited retrieval did not contain this lesson, so it cannot support "
                "the application",
            )
        self._applications.append(application)
        return application

    # -- requirement 7 ------------------------------------------------------

    def measure(self, lesson_id: str, observed: Metric, *, candidate_digest: str) -> Measurement:
        """Measure the named outcome after application. UNKNOWN when unattributable.

        Every UNKNOWN branch below is a case where a number exists and means nothing:
        no baseline to compare against, the wrong metric, or a lesson nobody applied
        to this candidate. Returning a verdict anyway is how a learning engine starts
        reporting improvements it did not cause.
        """
        lesson = self._require_lesson(lesson_id)
        if lesson.state is not LessonState.VALIDATED:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    f"Lesson is {lesson.state.value}; only a validated lesson has a "
                    "baseline to measure against.",
                )
            )
        if lesson.baseline is None:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    None,
                    observed,
                    "No baseline was captured at validation, so any change is unattributable.",
                )
            )
        if observed.name != lesson.baseline.name:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    f"Observed metric {observed.name!r} is not the metric the lesson "
                    f"named ({lesson.baseline.name!r}).",
                )
            )
        if observed.direction is not lesson.baseline.direction:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    f"Observed metric direction {observed.direction.value!r} does not "
                    f"match the baseline direction {lesson.baseline.direction.value!r}.",
                )
            )
        if not candidate_digest:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    "A measurement must be bound to the candidate it was taken on.",
                )
            )
        applied = [
            record
            for record in self._applications
            if record.lesson_id == lesson_id and record.changed_strategy
        ]
        if not applied:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    "No application record shows this lesson changing a strategy, so an "
                    "improvement cannot be attributed to it.",
                )
            )
        if candidate_digest not in {record.candidate_digest for record in applied}:
            return self._record_measurement(
                Measurement(
                    lesson_id,
                    MeasurementVerdict.UNKNOWN,
                    lesson.baseline,
                    observed,
                    "The application changed a different candidate, so this measurement "
                    "cannot be attributed to the lesson.",
                )
            )
        if observed.improves_on(lesson.baseline):
            verdict = MeasurementVerdict.IMPROVED
            reason = f"{observed.name} moved from {lesson.baseline.value} to {observed.value}."
        elif observed.harms(lesson.baseline):
            verdict = MeasurementVerdict.HARMED
            reason = f"{observed.name} worsened from {lesson.baseline.value} to {observed.value}."
        else:
            verdict = MeasurementVerdict.UNCHANGED
            reason = f"{observed.name} is unchanged at {observed.value}."
        return self._record_measurement(
            Measurement(lesson_id, verdict, lesson.baseline, observed, reason)
        )

    # -- requirement 8 ------------------------------------------------------

    def demote(self, lesson_id: str, *, reason: str, rollback: bool = False) -> Lesson:
        """Demote or roll back a lesson that harmed its own metric or conflicts.

        `rollback` is the stronger act: demotion stops a lesson influencing new work,
        rollback additionally declares the behaviour change should be undone. They are
        separate because they impose different obligations on the caller.
        """
        lesson = self._require_lesson(lesson_id)
        if not reason.strip():
            raise LearningError(
                "UNJUSTIFIED_DEMOTION", "Demotion must record why, or it cannot be reviewed"
            )
        updated = Lesson(
            lesson.candidate,
            LessonState.ROLLED_BACK if rollback else LessonState.DEMOTED,
            None,
            lesson.decision,
            lesson.baseline,
        )
        self._lessons[lesson_id] = updated
        return updated

    def demote_if_harmful(self, measurement: Measurement) -> Lesson | None:
        """Close the loop automatically for the one case that is unambiguous.

        Only HARMED triggers this. UNKNOWN must not: demoting on an unattributable
        measurement would discard sound lessons whenever evidence was merely thin,
        and the acceptance contract asks for UNKNOWN to be preserved, not acted on.
        """
        if measurement.verdict is not MeasurementVerdict.HARMED:
            return None
        return self.demote(
            measurement.lesson_id,
            reason=f"Harmed its own named metric: {measurement.reason}",
            rollback=True,
        )

    # -- helpers ------------------------------------------------------------

    def _require_lesson(self, lesson_id: str) -> Lesson:
        try:
            return self._lessons[lesson_id]
        except KeyError as exc:
            raise LearningError("UNKNOWN_LESSON", f"No lesson {lesson_id!r} in this store") from exc

    def _record_measurement(self, measurement: Measurement) -> Measurement:
        self._measurements.append(measurement)
        return measurement

    def episode_evidence(self, lesson_id: str) -> dict[str, Any]:
        """The full causal chain for one learning episode, as reviewable evidence.

        Shaped to be checked against the nine numbered requirements directly, so an
        auditor reads a chain rather than reassembling one from five collections.
        """
        lesson = self._require_lesson(lesson_id)
        retrievals = [r for r in self._retrievals if lesson_id in r.lesson_ids]
        applications = [a for a in self._applications if a.lesson_id == lesson_id]
        measurements = [m for m in self._measurements if m.lesson_id == lesson_id]
        return {
            "repository_digest": self._repository_digest,
            "lesson_id": lesson_id,
            "state": lesson.state.value,
            "scope": lesson.scope.value if lesson.scope else None,
            "outcomes": [self._outcomes[ref].digest for ref in lesson.candidate.derived_from],
            "candidate_lesson_digest": lesson.candidate.digest,
            "negative_knowledge": list(lesson.candidate.negative_knowledge),
            "decision": _plain(asdict(lesson.decision)) if lesson.decision else None,
            "baseline": _plain(asdict(lesson.baseline)) if lesson.baseline else None,
            "retrievals": [r.digest for r in retrievals],
            "applications": [
                {"digest": a.digest, "changed_strategy": a.changed_strategy} for a in applications
            ],
            "measurements": [
                {"verdict": m.verdict.value, "reason": m.reason} for m in measurements
            ],
            "changed_later_behaviour": any(a.changed_strategy for a in applications),
            "improved_named_outcome": any(
                m.verdict is MeasurementVerdict.IMPROVED for m in measurements
            ),
        }


def _plain(value: Any) -> Any:
    """JSON-ready form, with sets sorted so digests are stable."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, frozenset | set):
        return sorted(str(item) for item in value)
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value


def _digest(value: Mapping[str, Any] | Sequence[Any]) -> str:
    return hashlib.sha256(
        json.dumps(_plain(value), sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()
