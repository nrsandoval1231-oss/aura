"""
Jev (TypeSafe AI System One) integration — the decision layer for the
Forge/APEX merged runtime.

What Jev IS here:
  - Governor guardrail brain (tool-call risk classification)
  - Capability router (which model tier gets a packet)
  - Semantic stuck detector (is this attempt materially different?)
  - Confidence gate (autonomy thresholds with calibrated probabilities)
  - Escalation judge (does this need the owner?)
  - Failure-log retriever (relevance judgments without a vector DB)

What Jev is NOT:
  - Not a builder. It cannot generate text or code. Ever.
  - Not the Auditor. It pre-screens; the cross-family frontier model decides.
  - Not a calculator. Math, dates, and counting happen in code; Jev gets
    pre-digested inputs. (Documented jaggedness: arithmetic, dates, counting,
    double negatives, huge unfocused states.)

Operational rules (from TypeSafe's official docs):
  - ONE endpoint: POST https://api.typesafe.ai/v1/systemone. It is NOT the
    OpenAI chat-completions shape — state + questions only.
  - Official SDK: `pip install typesafe-sdk` (Python 3.10+). The client
    reads TYPESAFE_API_KEY from the environment, defaults to jev-latest,
    and handles 429/529 retry-with-backoff for us. We use the SDK rather
    than raw HTTP.
  - Rate limits (jev-1.13): 250,000 tokens/sec, 1,200 req/min — moving
    without notice while GPU capacity lands.
  - Request budget ~32k tokens total (state + questions). Keep states
    focused; irrelevant data in the state distracts the model.
  - PIN THE MODEL. jev-latest moves; thresholds tuned on one version can
    shift under you. We pin jev-1.13.0 and log the versioned ID from every
    response.
  - Ask every independent question in ONE call (speculative fan-out).
    Questions run in parallel against the same state; extra questions are
    nearly free (output tokens are unmetered).
  - Version model + questions + thresholds TOGETHER, and replay the canary
    benchmark when any of them change. (This is FORGE-VER-003 compatibility.)
  - Known jaggedness: no arithmetic, no date comparison, no counting, no
    hex/numeric encodings, avoid double negatives. Pre-digest all of that
    in code before building the state.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterable
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from forge.paths import paths_in_scope
from forge.providers.capability import ROUTABLE_TIERS, Capability

# ---------------------------------------------------------------------------
# Config — key lives in .env as TYPESAFE_API_KEY. Never in code, never in chat.
# ---------------------------------------------------------------------------

TYPESAFE_BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
JEV_MODEL_PINNED = os.environ.get("JEV_MODEL", "jev-1.13.0")  # pinned, not jev-latest


# ---------------------------------------------------------------------------
# Typed questions — the three primitives.
# ---------------------------------------------------------------------------


class Noul(BaseModel):
    """Yes/no question. Answer is P(true) in [0,1]."""

    type: Literal["noul"] = "noul"
    instructions: str
    criteria: dict[str, str] | None = None


class Choice(BaseModel):
    """One-of-N (up to 255 options)."""

    type: Literal["choice"] = "choice"
    instructions: str
    criteria: dict[str, str | None]


class Score(BaseModel):
    """Position on a 2–10 level ordered scale. Use for thresholds and
    ranking, NOT interpolation — levels are weakly calibrated numerically."""

    type: Literal["score"] = "score"
    instructions: str
    criteria: list[str]


Question = Noul | Choice | Score


# ---------------------------------------------------------------------------
# Typed answers + receipt (every decision is evidence — Forge S7/S18)
# ---------------------------------------------------------------------------


class NoulAnswer(BaseModel):
    type: Literal["noul"]
    noul: float = Field(ge=0.0, le=1.0)


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    confidence: float = Field(ge=0.0, le=1.0)
    probabilities: dict[str, float]


class ScoreAnswer(BaseModel):
    type: Literal["score"]
    score: float
    confidence: float = Field(ge=0.0, le=1.0)
    legend: dict[str, str]
    probabilities: dict[str, float]


Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer


class DecisionReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"DEC-{uuid.uuid4().hex[:8]}")
    model_reported: str  # versioned ID from the response — always log it
    model_requested: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    decision_fn: str  # which decision function made the call
    packet_id: str | None = None
    answers_summary: dict[str, Any]


class JevError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# The client. Uses the official SDK (pip install typesafe-sdk), which handles
# 429/529 retry-with-backoff natively. Model is pinned, never jev-latest.
# ---------------------------------------------------------------------------


class JevClient:
    def __init__(self, timeout_s: float = 10.0, *, client: Any | None = None):
        self._timeout = timeout_s
        if client is not None:
            # Injectable so tests and replays never reach the network.
            self._client = client
            return
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise JevError("Missing TYPESAFE_API_KEY. Put it in .env — never in code or chat.")
        try:
            from typesafe_sdk import TypeSafeClient  # official SDK
        except ImportError as e:
            raise JevError("pip install typesafe-sdk (requires Python 3.10+)") from e
        self._client = TypeSafeClient(model=JEV_MODEL_PINNED)

    def close(self) -> None:
        """Release the underlying HTTP client."""
        closer = getattr(self._client, "close", None)
        if callable(closer):
            closer()

    def __enter__(self) -> JevClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def evaluate(
        self,
        state: str | dict | list,
        questions: dict[str, Question],
        *,
        decision_fn: str,
        packet_id: str | None = None,
    ) -> tuple[dict[str, Answer], DecisionReceipt]:
        """One call, all questions in parallel. State may be a string, a
        JSON-shaped object, or an ordered array of events."""
        from typesafe_sdk import Choice as SDKChoice
        from typesafe_sdk import Noul as SDKNoul
        from typesafe_sdk import Score as SDKScore

        sdk_questions: dict[str, Any] = {}
        for name, q in questions.items():
            if isinstance(q, Noul):
                sdk_questions[name] = SDKNoul(
                    instructions=q.instructions,
                    criteria=q.criteria,  # optional {"true": "...", "false": "..."}
                )
            elif isinstance(q, Choice):
                sdk_questions[name] = SDKChoice(instructions=q.instructions, criteria=q.criteria)
            elif isinstance(q, Score):
                sdk_questions[name] = SDKScore(instructions=q.instructions, criteria=q.criteria)
            else:  # fail closed on unknown question shapes
                raise JevError(f"Unknown question type for '{name}'")

        started = time.monotonic()
        # The timeout must reach the SDK; a Governor guardrail that can hang
        # indefinitely is not a guardrail.
        response = self._client.system_one(
            state=state, questions=sdk_questions, timeout=self._timeout
        )
        latency_ms = int((time.monotonic() - started) * 1000)

        answers = self._parse_answers(response.answers)
        usage = getattr(response, "usage", None)
        receipt = DecisionReceipt(
            model_reported=getattr(response, "model", "unknown"),  # always log it
            model_requested=JEV_MODEL_PINNED,
            latency_ms=latency_ms,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            decision_fn=decision_fn,
            packet_id=packet_id,
            answers_summary={k: a.model_dump() for k, a in answers.items()},
        )
        return answers, receipt

    @staticmethod
    def _parse_answers(raw: dict[str, Any]) -> dict[str, Answer]:
        """Validate SDK answers into our Pydantic types. Schema-invalid
        answers raise here — fail closed, never parse loosely downstream."""
        out: dict[str, Answer] = {}
        for name, a in raw.items():
            if hasattr(a, "noul"):
                out[name] = NoulAnswer(type="noul", noul=a.noul)
            elif hasattr(a, "choice"):
                out[name] = ChoiceAnswer(
                    type="choice",
                    choice=a.choice,
                    confidence=a.confidence,
                    probabilities=dict(a.probabilities),
                )
            elif hasattr(a, "score"):
                out[name] = ScoreAnswer(
                    type="score",
                    score=a.score,
                    confidence=a.confidence,
                    legend=dict(a.legend),
                    probabilities=dict(a.probabilities),
                )
            else:
                raise JevError(f"Unknown answer shape for '{name}': {type(a)}")
        return out


# ---------------------------------------------------------------------------
# Decision functions — the actual integration points into Forge/APEX.
# Each one is a named, versioned, receipted judgment.
# Thresholds below are STARTING values; they are tuned against the canary
# benchmark (FORGE-VER-003) and versioned together with these questions.
# ---------------------------------------------------------------------------

#: Ordered merge-readiness levels. Index, not magnitude, is meaningful.
_MERGE_READINESS_LEVELS: tuple[str, ...] = (
    "Clearly unsafe or unverified",
    "Minor concerns; human spot-check advised",
    "Clean: verified, in-scope, evidence complete",
)


class RiskLevel(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


def classify_tool_call(
    client: JevClient,
    tool: str,
    args: dict,
    packet_scope: dict,
    *,
    touched_paths: Iterable[str],
) -> tuple[RiskLevel, bool, DecisionReceipt]:
    """Governor guardrail. Runs BEFORE every non-trivial tool call.

    Returns (risk_level, needs_human, receipt). Low confidence -> needs_human=True.
    Never trust the label alone.

    Scope is settled in code before Jev is asked anything; Jev judges only the risk
    class, which is a genuine semantic judgment.

    `touched_paths` is required, not optional. It defaulted to `()` once, and an
    empty path set reads as "in scope" to any `all()`-shaped check — so the
    callers least able to enumerate paths up front, `shell` above all, were the
    ones that silently lost the deterministic half of this guardrail. Pass the
    paths, or pass a sentinel the scope check will reject.
    """
    in_scope = paths_in_scope(touched_paths, packet_scope.get("allowed_paths", []))
    answers, receipt = client.evaluate(
        state={"tool": tool, "arguments": args},
        questions={
            "risk": Choice(
                instructions="What is the risk class of this tool call?",
                criteria={
                    "read_only": "Only reads data; no state changes",
                    "reversible": "Modifies state but fully undoable via version control",
                    "irreversible": "Deletes data, touches prod/secrets, or cannot be undone",
                },
            )
        },
        decision_fn="classify_tool_call",
    )
    risk = RiskLevel(answers["risk"].choice)  # type: ignore[union-attr]
    confidence = answers["risk"].confidence  # type: ignore[union-attr]
    needs_human = confidence < 0.6 or not in_scope or risk == RiskLevel.IRREVERSIBLE
    return risk, needs_human, receipt


def route_packet(
    client: JevClient, objective: str, files: list[str], context: str
) -> tuple[Capability, DecisionReceipt]:
    """Capability routing via calibrated decision. ~100ms, ~$0.0004."""
    descriptions = {
        Capability.FAST: "Renames, boilerplate, mechanical edits, simple classification",
        Capability.CODING: "Standard feature implementation, tests, bug fixes",
        Capability.HIGH_REASONING: ("Architecture, security-sensitive logic, cross-cutting design"),
    }
    answers, receipt = client.evaluate(
        state={"objective": objective, "files": files, "context": context[:8000]},
        questions={
            "tier": Choice(
                instructions="Choose the LEAST costly model tier that can complete this task.",
                criteria={tier.value: descriptions[tier] for tier in ROUTABLE_TIERS},
            )
        },
        decision_fn="route_packet",
    )
    chosen = Capability(answers["tier"].choice)  # type: ignore[union-attr]
    if chosen not in ROUTABLE_TIERS:
        raise JevError(f"Router returned a non-routable tier: {chosen}")
    return chosen, receipt


def is_materially_different_strategy(
    client: JevClient, prior_summary: str, new_summary: str, packet_id: str
) -> tuple[bool, DecisionReceipt]:
    """Forge S16 semantic stuck detection — the LLM-judge part, now ~100ms.
    Pair this with the deterministic patch-hash tripwire (FORGE-STK-001):
    hash catches identical retries; Jev catches 'same strategy, new costume'."""
    answers, receipt = client.evaluate(
        state={"prior_attempt": prior_summary, "new_attempt": new_summary},
        questions={
            "materially_different": Noul(
                instructions=(
                    "Does the new attempt use a genuinely different strategy or hypothesis "
                    "about the root cause — not merely rewording, reformatting, or tweaking "
                    "the same approach?"
                ),
                criteria={
                    "true": "Different root-cause hypothesis or different mechanism of attack",
                    "false": "Same underlying strategy with surface-level changes",
                },
            )
        },
        decision_fn="is_materially_different_strategy",
        packet_id=packet_id,
    )
    return answers["materially_different"].noul > 0.6, receipt  # type: ignore[union-attr]


def autonomy_gate(
    client: JevClient, candidate_summary: str, audit_verdict: str, packet_id: str
) -> tuple[str, DecisionReceipt]:
    """Confidence-gated autonomy implemented on calibrated probabilities.
    Returns 'merge' | 'flag_for_review' | 'human_gate'.
    NOTE: this ADVISES the Governor. It never grants merge eligibility —
    confidence does not confer authority. (Conflict register #4: Forge wins.)"""
    answers, receipt = client.evaluate(
        state={"candidate": candidate_summary, "audit_verdict": audit_verdict},
        questions={
            "merge_readiness": Score(
                instructions="How ready is this candidate to merge autonomously?",
                criteria=list(_MERGE_READINESS_LEVELS),
            ),
            "anomaly": Noul(
                instructions="Is there anything surprising or off-pattern about this candidate?"
            ),
        },
        decision_fn="autonomy_gate",
        packet_id=packet_id,
    )
    score_a: ScoreAnswer = answers["merge_readiness"]  # type: ignore[assignment]
    anomaly_p: float = answers["anomaly"].noul  # type: ignore[union-attr]
    if score_a.confidence < 0.6 or anomaly_p > 0.5:
        return "human_gate", receipt
    # Score levels are ordinal, not numeric — the module docstring says so, and a
    # midpoint threshold like `> 1.5` silently reinterprets a weakly calibrated
    # scale as a continuous one. Autonomy is the strictest thing this gate can
    # grant, so require the top level outright: anything short of it, including a
    # value that would round up to it, is a review, not a merge.
    top_level = len(_MERGE_READINESS_LEVELS) - 1
    if score_a.score >= top_level:
        return "merge", receipt
    return "flag_for_review", receipt


def needs_owner(
    client: JevClient, blocker_description: str, packet_id: str
) -> tuple[bool, DecisionReceipt]:
    """Protects the owner doctrine: don't interrupt the human for things
    Forge can determine from evidence; DO interrupt for genuine preference
    or protected-authority questions."""
    answers, receipt = client.evaluate(
        state={"blocker": blocker_description},
        questions={
            "owner_required": Noul(
                instructions=(
                    "Does this blocker genuinely require a human product/authority decision "
                    "(preference tradeoff, protected boundary, credentials, external action) — "
                    "rather than something resolvable by gathering more evidence or replanning?"
                )
            )
        },
        decision_fn="needs_owner",
        packet_id=packet_id,
    )
    return answers["owner_required"].noul > 0.7, receipt  # type: ignore[union-attr]


def relevant_failures(
    client: JevClient, task_description: str, failure_summaries: list[str]
) -> tuple[list[int], DecisionReceipt]:
    """Failure-log retrieval WITHOUT a vector DB (Forge S106 compliant).
    One Noul per past failure, all in a single parallel call — this is the
    documented pattern for counting/filtering by semantic condition."""
    if not failure_summaries:
        return [], DecisionReceipt(
            model_reported="none",
            model_requested=JEV_MODEL_PINNED,
            latency_ms=0,
            decision_fn="relevant_failures",
            answers_summary={},
        )
    questions = {
        f"rel_{i}": Noul(
            instructions=f"Is past failure #{i} relevant to avoiding a mistake in the current task?"
        )
        for i in range(len(failure_summaries))
    }
    state = {"current_task": task_description, "past_failures": failure_summaries}
    answers, receipt = client.evaluate(state, questions, decision_fn="relevant_failures")
    hits = [i for i in range(len(failure_summaries)) if answers[f"rel_{i}"].noul > 0.6]  # type: ignore[union-attr]
    return hits, receipt


if __name__ == "__main__":
    from forge.config import load_env

    load_env()

    jev = JevClient()
    risk, human, receipt = classify_tool_call(
        jev,
        tool="shell",
        args={"cmd": "rm -rf ./build"},
        packet_scope={"allowed_paths": ["src/**", "tests/**"]},
    )
    print(f"risk={risk} needs_human={human}")
    print(receipt.model_dump_json(indent=2))
