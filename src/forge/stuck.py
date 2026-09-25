"""Stuck detection and bounded recovery.

The Finish Contract requires that "stuck resolution requires materially different
strategies", and `.agent/AGENT_RULES.md` bounds it: *allow at most two materially
different bounded repairs; if evidence does not improve, return to canonical intent
and relevant ADRs, identify the real constraint, and issue a revised packet.*

Nothing implemented either sentence before this module. `BuildPacket.retry_limit`
counted attempts, which is a different and weaker thing: three attempts at the same
idea satisfy a retry budget and satisfy nothing about recovery.

Three properties, all decided deterministically
-----------------------------------------------
**Repetition is measured on the patch, not on the narrative.** An agent asked
whether it is repeating itself will say no. `patch_hash` normalises a diff — drops
hunk headers, line numbers, and trailing whitespace, keeps the added and removed
content — so the same edit reached by a different explanation hashes the same.

**Material difference is measured on declared strategy, not on prose distance.** A
`Strategy` names its rung on the abstraction ladder, the mechanism it changes, and
the surfaces it touches. Two strategies are materially different when they differ
in rung or mechanism; touching different files with the same mechanism at the same
rung is the same idea applied twice, which is exactly what the rule exists to stop.

**Improvement is measured on failing checks, not on confidence.** An attempt
improved matters if the set of failing checks strictly shrank. A model's belief that
things are going better is not evidence, and "evidence does not improve" has to mean
something a gate can evaluate without asking anyone.

Escalation only ever moves up the ladder. Re-entering a rung already tried is how a
loop looks from inside, so it is refused rather than counted.

This module decides and records. It never repairs anything itself, and it cannot
grant authority: a verdict of `OWNER` is a stop, not a permission.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

__all__ = [
    "AttemptRecord",
    "Rung",
    "StuckDetector",
    "StuckReason",
    "StuckVerdict",
    "Strategy",
    "StuckError",
    "materially_different",
    "patch_hash",
]


class StuckError(Exception):
    """Structured fail-closed error, mirroring `trust_kernel.ForgeError`.

    Kept local rather than importing the kernel's: `trust_kernel` is a protected
    surface and stuck detection is not part of it. A recovery bug must not be able
    to reach into transition validation.
    """

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, "details": self.details}


class Rung(IntEnum):
    """The abstraction ladder (FORGE-STK-003).

    Ordered, because escalation is defined as moving up it. An `IntEnum` rather than
    a `StrEnum` so that ordering is a property of the type rather than a convention
    every comparison has to remember.
    """

    SAME_EDIT = 0  # fix the same code the same way
    MECHANISM = 1  # same interface, different mechanism
    INTERFACE = 2  # change the contract between the parts
    DESIGN = 3  # change which parts exist
    INTENT = 4  # the requirement itself is the constraint


class StuckReason(StrEnum):
    NOT_STUCK = "NOT_STUCK"
    REPEATED_PATCH = "REPEATED_PATCH"
    NOT_MATERIALLY_DIFFERENT = "NOT_MATERIALLY_DIFFERENT"
    RUNG_ALREADY_TRIED = "RUNG_ALREADY_TRIED"
    NO_IMPROVEMENT = "NO_IMPROVEMENT"
    REPAIR_BUDGET_EXHAUSTED = "REPAIR_BUDGET_EXHAUSTED"
    LADDER_EXHAUSTED = "LADDER_EXHAUSTED"


class StuckVerdict(StrEnum):
    CONTINUE = "CONTINUE"  # this attempt is a legitimate next try
    ESCALATE = "ESCALATE"  # go up the ladder; a bounded repair remains
    RETURN_TO_INTENT = "RETURN_TO_INTENT"  # re-derive from canonical intent and ADRs
    OWNER = "OWNER"  # a human decides; never a permission to proceed


#: `.agent/AGENT_RULES.md`: at most two materially different bounded repairs.
MAX_MATERIAL_REPAIRS = 2

_HUNK_HEADER = re.compile(r"^@@.*?@@.*$", re.MULTILINE)
_DIFF_METADATA = re.compile(r"^(?:index |diff --git |--- |\+\+\+ |similarity |rename )", re.M)


def patch_hash(diff: str) -> str:
    """Hash the *content* of a change, so cosmetic differences do not hide a repeat.

    Normalises away what moves when the same edit is re-derived: hunk headers and
    line numbers, git metadata lines, trailing whitespace, and blank context. What
    remains is the added and removed lines in order. Two attempts that produce the
    same edit hash the same even when the diff is framed differently, which is the
    only way loop detection survives an agent that re-explains itself each round.
    """
    kept: list[str] = []
    for raw in diff.splitlines():
        if _HUNK_HEADER.match(raw) or _DIFF_METADATA.match(raw):
            continue
        if raw[:1] not in {"+", "-"}:
            continue  # context lines shift with unrelated edits; they are not the change
        body = raw[1:].rstrip()
        if not body:
            continue
        kept.append(f"{raw[0]}{body}")
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Strategy:
    """A declared approach, in the terms material difference is judged on."""

    rung: Rung
    #: What is being changed in kind — "retry", "replace-algorithm", "invert-
    #: dependency". Free text, but it is the field that decides difference, so a
    #: strategy that reuses a mechanism label is declaring it is the same idea.
    mechanism: str
    #: Surfaces the approach touches. Recorded for evidence and for explaining a
    #: verdict; deliberately *not* part of the difference test.
    surfaces: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "surfaces", tuple(self.surfaces))
        object.__setattr__(self, "rung", Rung(self.rung))
        if not self.mechanism.strip():
            raise StuckError(
                "INVALID_STRATEGY",
                "A strategy must name its mechanism; an unnamed approach cannot be "
                "shown to differ from the last one",
            )

    @property
    def digest(self) -> str:
        return _digest({"rung": int(self.rung), "mechanism": _normalize_mechanism(self.mechanism)})


def _normalize_mechanism(mechanism: str) -> str:
    """Casing, punctuation and word order must not manufacture a difference."""
    words = sorted(re.findall(r"[a-z0-9]+", mechanism.casefold()))
    return "-".join(words)


def materially_different(first: Strategy, second: Strategy) -> bool:
    """True when `second` is a materially different approach from `first`.

    Rung or mechanism must differ. Touching different files with the same mechanism
    at the same rung is the same idea pointed somewhere else — the case the rule is
    written against, and the one a naive diff-the-file-list check would wave
    through.
    """
    return first.digest != second.digest


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """One bounded attempt and what it actually achieved."""

    packet_id: str
    attempt: int
    patch_digest: str
    strategy: Strategy
    #: Checks that failed after this attempt. Empty means the attempt succeeded.
    failing_checks: frozenset[str]
    evidence_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "failing_checks", frozenset(self.failing_checks))
        if not self.packet_id or not self.evidence_digest:
            raise StuckError(
                "INVALID_ATTEMPT", "An attempt must name its packet and carry evidence"
            )
        if self.attempt < 1:
            raise StuckError("INVALID_ATTEMPT", "Attempts are numbered from one")

    @property
    def succeeded(self) -> bool:
        return not self.failing_checks


@dataclass(frozen=True, slots=True)
class StuckAssessment:
    """The verdict, why, and enough detail to act on it without guessing."""

    verdict: StuckVerdict
    reason: StuckReason
    message: str
    next_rung: Rung | None
    material_repairs_used: int
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason.value,
            "message": self.message,
            "next_rung": int(self.next_rung) if self.next_rung is not None else None,
            "material_repairs_used": self.material_repairs_used,
            "details": dict(self.details),
        }

    @property
    def digest(self) -> str:
        return _digest(self.as_dict())


class StuckDetector:
    """Records attempts for one packet and decides whether it is stuck.

    Deliberately per-packet and in-memory. It holds no authority and grants none;
    the Governor reads its assessment and the owner decides anything it escalates.
    """

    def __init__(self, packet_id: str, *, max_material_repairs: int = MAX_MATERIAL_REPAIRS):
        if not packet_id:
            raise StuckError("INVALID_PACKET", "Stuck detection is scoped to a packet")
        if max_material_repairs < 1:
            raise StuckError("INVALID_BUDGET", "A recovery budget of zero cannot permit any repair")
        self._packet_id = packet_id
        self._max_material_repairs = max_material_repairs
        self._attempts: list[AttemptRecord] = []

    @property
    def attempts(self) -> tuple[AttemptRecord, ...]:
        return tuple(self._attempts)

    @property
    def material_repairs_used(self) -> int:
        """Distinct strategies tried after the first attempt.

        The first attempt is the work, not a repair. Counting it would spend a third
        of a two-repair budget before anything had gone wrong.
        """
        if len(self._attempts) <= 1:
            return 0
        seen = {self._attempts[0].strategy.digest}
        used = 0
        for record in self._attempts[1:]:
            if record.strategy.digest not in seen:
                seen.add(record.strategy.digest)
                used += 1
        return used

    @property
    def rungs_tried(self) -> frozenset[Rung]:
        return frozenset(record.strategy.rung for record in self._attempts)

    def assess(
        self,
        *,
        patch_digest: str,
        strategy: Strategy,
        failing_checks: Iterable[str],
    ) -> StuckAssessment:
        """Judge a *proposed* attempt without recording it.

        Separate from `record` so the loop can ask before spending an attempt. A
        detector that only reports after the fact cannot prevent the third identical
        patch, it can only annotate it.
        """
        failing = frozenset(failing_checks)
        if not self._attempts:
            return StuckAssessment(
                StuckVerdict.CONTINUE,
                StuckReason.NOT_STUCK,
                "First attempt for this packet.",
                strategy.rung,
                0,
            )

        previous = self._attempts[-1]

        if patch_digest in {record.patch_digest for record in self._attempts}:
            return self._blocked(
                StuckReason.REPEATED_PATCH,
                "This patch is byte-identical in content to one already tried, so it "
                "will fail the same way. Repetition is the loop, not the fix.",
                strategy,
                details={"patch_digest": patch_digest},
            )

        if not materially_different(previous.strategy, strategy):
            return self._blocked(
                StuckReason.NOT_MATERIALLY_DIFFERENT,
                f"Strategy is not materially different from attempt {previous.attempt}: "
                f"same rung ({previous.strategy.rung.name}) and same mechanism. "
                "AGENT_RULES requires materially different repairs.",
                strategy,
                details={
                    "previous_mechanism": previous.strategy.mechanism,
                    "proposed_mechanism": strategy.mechanism,
                    "rung": previous.strategy.rung.name,
                },
            )

        if strategy.rung in self.rungs_tried and strategy.rung <= previous.strategy.rung:
            return self._blocked(
                StuckReason.RUNG_ALREADY_TRIED,
                f"Rung {strategy.rung.name} has already been tried and this is not an "
                "escalation. Recovery moves up the ladder; re-entering a rung is how a "
                "loop looks from the inside.",
                strategy,
                details={"rungs_tried": sorted(rung.name for rung in self.rungs_tried)},
            )

        used = self.material_repairs_used
        if used >= self._max_material_repairs:
            return StuckAssessment(
                StuckVerdict.RETURN_TO_INTENT,
                StuckReason.REPAIR_BUDGET_EXHAUSTED,
                f"{used} materially different repairs have been tried, which is the "
                "budget. Return to canonical intent and the relevant ADRs, identify the "
                "real constraint, and issue a revised packet.",
                None,
                used,
                {"max_material_repairs": self._max_material_repairs},
            )

        if not self._evidence_improved(previous.failing_checks, failing):
            return StuckAssessment(
                StuckVerdict.RETURN_TO_INTENT,
                StuckReason.NO_IMPROVEMENT,
                "The failing-check set did not shrink across attempts, so the evidence "
                "is not improving. Another bounded repair spends budget on the same wall.",
                None,
                used,
                {
                    "previous_failing": sorted(previous.failing_checks),
                    "proposed_failing": sorted(failing),
                },
            )

        return StuckAssessment(
            StuckVerdict.CONTINUE,
            StuckReason.NOT_STUCK,
            f"Materially different repair at rung {strategy.rung.name}; "
            f"{self._max_material_repairs - used} remaining in budget.",
            strategy.rung,
            used,
        )

    def record(self, record: AttemptRecord) -> None:
        """Append an attempt that actually happened.

        Records history rather than judging it: an attempt made against a blocking
        assessment is still a fact, and losing it would make the next assessment
        weaker. The Governor is responsible for not making it.
        """
        if record.packet_id != self._packet_id:
            raise StuckError(
                "PACKET_MISMATCH",
                f"Attempt belongs to {record.packet_id}, not {self._packet_id}",
            )
        expected = len(self._attempts) + 1
        if record.attempt != expected:
            raise StuckError(
                "ATTEMPT_OUT_OF_ORDER",
                f"Expected attempt {expected}, got {record.attempt}",
                details={"expected": expected, "received": record.attempt},
            )
        self._attempts.append(record)

    def _blocked(
        self,
        reason: StuckReason,
        message: str,
        strategy: Strategy,
        *,
        details: Mapping[str, Any],
    ) -> StuckAssessment:
        """A blocked attempt escalates if the ladder has room, else it stops.

        Escalating past INTENT is not a thing: at that rung the requirement itself is
        the constraint, and only the owner can change a requirement.
        """
        used = self.material_repairs_used
        next_rung = _next_rung(max(self.rungs_tried | {strategy.rung}))
        if next_rung is None:
            return StuckAssessment(
                StuckVerdict.OWNER,
                StuckReason.LADDER_EXHAUSTED,
                f"{message} The abstraction ladder is exhausted: at INTENT the "
                "requirement is the constraint, and only the owner may change one.",
                None,
                used,
                dict(details),
            )
        return StuckAssessment(
            StuckVerdict.ESCALATE, reason, message, next_rung, used, dict(details)
        )

    @staticmethod
    def _evidence_improved(before: frozenset[str], after: frozenset[str]) -> bool:
        """Improvement is a strictly smaller failing set.

        Not "different": swapping one failure for another is motion, not progress,
        and a rule that accepted it would let two attempts trade failures forever
        inside budget. A newly empty set improves trivially.
        """
        if not after:
            return True
        return after < before


def _next_rung(current: Rung) -> Rung | None:
    return None if current >= Rung.INTENT else Rung(int(current) + 1)


def _digest(value: Mapping[str, Any] | Sequence[Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    ).hexdigest()
