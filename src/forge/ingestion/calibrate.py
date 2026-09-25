"""CALIBRATE: one provider-neutral scoring call and deterministic interview selection."""

from __future__ import annotations

from pydantic import Field

from .calibration_contracts import (
    CalibrationClient,
    DecisionReceipt,
    ProbabilityAnswer,
    ProbabilityQuestion,
    Score,
    ScoreAnswer,
)
from .models import Ambiguity, AnswerFormat, BlastRadius, ReceiptLedger, StrictModel


class AmbiguityScore(StrictModel):
    ambiguity_id: str
    materially_changes: float = Field(ge=0, le=1)
    default_sufficient: float = Field(ge=0, le=1)
    default_confidence: float = Field(ge=0, le=1)


class InterviewQuestion(StrictModel):
    id: str
    ambiguity: str
    plain_language: str
    why_we_ask: str
    answer_format: AnswerFormat = AnswerFormat.FREE_TEXT
    voi_score: float = Field(ge=0, le=1)
    blast_radius: BlastRadius
    materially_changes: float = Field(gt=0.6, le=1)


class CalibrationResult(StrictModel):
    scores: list[AmbiguityScore]
    questions: list[InterviewQuestion] = Field(max_length=5)
    answered_ambiguities: list[str] = []
    owner_declined: bool = False


def calibrate(
    ambiguities: list[Ambiguity],
    client: CalibrationClient,
    *,
    ledger: ReceiptLedger | None = None,
    answers: dict[str, str] | None = None,
    owner_declined: bool = False,
    packet_id: str = "FORGE-ING-001",
) -> tuple[CalibrationResult, DecisionReceipt | None]:
    """Score every ambiguity in one call; answered questions are never asked again."""
    answers = answers or {}
    answered = set(answers)
    if ledger:
        answered.update(p["ambiguity_id"] for p in ledger.payloads("OWNER_ANSWERED"))
        owner_declined = owner_declined or bool(ledger.payloads("OWNER_DECLINED"))
    pending = [item for item in ambiguities if item.id not in answered]
    if not pending or owner_declined or len(answered) >= 5:
        result = CalibrationResult(
            scores=[],
            questions=[],
            answered_ambiguities=sorted(answered),
            owner_declined=owner_declined,
        )
        if ledger:
            ledger.append("CALIBRATE_COMPLETED", result.model_dump(mode="json"))
        return result, None

    questions = {}
    for ambiguity in pending:
        questions[f"{ambiguity.id}.materially_changes"] = ProbabilityQuestion(
            instructions="Would the true answer materially change the system architecture?"
        )
        questions[f"{ambiguity.id}.default_sufficient"] = ProbabilityQuestion(
            instructions="Can a reasonable default carry this to a useful first version?"
        )
        questions[f"{ambiguity.id}.default_confidence"] = Score(
            instructions="How confident are we in the stated default?",
            criteria=["low confidence", "medium confidence", "high confidence"],
        )
    raw, receipt = client.evaluate(
        state=[item.model_dump(mode="json") for item in pending],
        questions=questions,
        decision_fn="intent_calibration_v1",
        packet_id=packet_id,
    )
    scores: list[AmbiguityScore] = []
    by_id = {item.id: item for item in pending}
    for ambiguity in pending:
        material = raw[f"{ambiguity.id}.materially_changes"]
        sufficient = raw[f"{ambiguity.id}.default_sufficient"]
        confidence = raw[f"{ambiguity.id}.default_confidence"]
        if not isinstance(material, ProbabilityAnswer) or not isinstance(
            sufficient, ProbabilityAnswer
        ):
            raise TypeError(
                "Calibration provider returned the wrong answer type for a ProbabilityQuestion question"
            )
        if not isinstance(confidence, ScoreAnswer):
            raise TypeError(
                "Calibration provider returned the wrong answer type for a Score question"
            )
        scores.append(
            AmbiguityScore(
                ambiguity_id=ambiguity.id,
                materially_changes=material.probability,
                default_sufficient=sufficient.probability,
                default_confidence=_score_probability(confidence),
            )
        )
    radius_weight = {BlastRadius.LOW: 1, BlastRadius.MEDIUM: 2, BlastRadius.HIGH: 3}
    selected = [
        score
        for score in scores
        if score.materially_changes > 0.6 and score.default_sufficient <= 0.7
    ]
    selected.sort(
        key=lambda score: (
            radius_weight[by_id[score.ambiguity_id].blast_radius]
            * score.materially_changes
            * (1 - score.default_confidence),
            score.ambiguity_id,
        ),
        reverse=True,
    )
    interview = [
        InterviewQuestion(
            id=f"IQ-{index:03d}",
            ambiguity=score.ambiguity_id,
            plain_language=by_id[score.ambiguity_id].question_if_asked,
            why_we_ask=by_id[score.ambiguity_id].why_we_ask,
            voi_score=score.materially_changes * (1 - score.default_confidence),
            blast_radius=by_id[score.ambiguity_id].blast_radius,
            materially_changes=score.materially_changes,
        )
        for index, score in enumerate(selected[: max(0, 5 - len(answered))], 1)
    ]
    result = CalibrationResult(
        scores=scores, questions=interview, answered_ambiguities=sorted(answered)
    )
    if ledger:
        ledger.append(
            "INTENT_CALIBRATION",
            {
                "decision_receipt": receipt.model_dump(mode="json"),
                "scores": [score.model_dump() for score in scores],
            },
        )
        ledger.append("CALIBRATE_COMPLETED", result.model_dump(mode="json"))
    return result, receipt


def record_answer(ledger: ReceiptLedger, ambiguity_id: str, answer: str) -> None:
    if not ambiguity_id or not answer.strip():
        raise ValueError("answer and ambiguity id cannot be blank")
    ledger.append("OWNER_ANSWERED", {"ambiguity_id": ambiguity_id, "answer": answer})


def record_decline(ledger: ReceiptLedger, reason: str | None = None) -> None:
    ledger.append("OWNER_DECLINED", {"reason": reason})


def _score_probability(answer: ScoreAnswer) -> float:
    # Score(3) levels are ordinal. Confidence is the calibrated value safe for ranking.
    return answer.confidence
