"""Provider-neutral intent calibration contract; no service or transport is selected."""

from __future__ import annotations

import uuid
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class ProbabilityQuestion(BaseModel):
    type: Literal["probability"] = "probability"
    instructions: str
    criteria: dict[str, str] | None = None


class Score(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    criteria: list[str]


class ProbabilityAnswer(BaseModel):
    type: Literal["probability"]
    probability: float = Field(ge=0, le=1)


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float
    confidence: float = Field(ge=0, le=1)
    legend: dict[str, str]
    probabilities: dict[str, float]


class DecisionReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:8]}")
    model_reported: str
    model_requested: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    decision_fn: str
    packet_id: str | None = None
    answers_summary: dict[str, Any]


class CalibrationClient(Protocol):
    def evaluate(
        self,
        state: list[dict[str, Any]],
        questions: dict[str, ProbabilityQuestion | Score],
        *,
        decision_fn: str,
        packet_id: str,
    ) -> tuple[dict[str, ProbabilityAnswer | ScoreAnswer], DecisionReceipt]: ...
