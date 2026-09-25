"""DECOMPOSE: structured provisional understanding from raw owner intent."""

from __future__ import annotations

from pydantic import Field, model_validator

from forge.providers.model_provider import CallReceipt, Capability, ModelProvider

from .models import (
    Ambiguity,
    ConfidenceLabel,
    KnownUnknown,
    Provisional,
    ReceiptLedger,
    RequirementSeed,
    StrictModel,
)


class Decomposition(StrictModel):
    status: Provisional = Provisional.PROVISIONAL
    confidence: ConfidenceLabel
    north_star_plain: str = Field(max_length=800)
    requirements: list[RequirementSeed] = Field(max_length=12)
    ambiguities: list[Ambiguity]
    known_unknowns: list[KnownUnknown]

    @model_validator(mode="after")
    def validate_traceability(self) -> Decomposition:
        for requirement in self.requirements:
            if not requirement.source_quote and not requirement.inferred:
                raise ValueError("requirements must be traced or explicitly inferred")
        return self


SYSTEM = """You turn an owner's raw product idea into a cautious PROVISIONAL outline.
Return only the requested structure. Never invent scope silently: quote the owner's text for
each directly supported requirement and mark every other requirement inferred. For a broad
category idea, identify at least eight genuine ambiguities. Use plain non-technical language."""


def decompose(
    raw_intent: str,
    provider: ModelProvider,
    *,
    ledger: ReceiptLedger | None = None,
    packet_id: str = "FORGE-ING-001",
) -> tuple[Decomposition, CallReceipt]:
    """Call HIGH_REASONING once and validate the provisional result."""
    if not isinstance(raw_intent, str) or not raw_intent.strip():
        raise ValueError("raw intent cannot be blank")
    result, receipt = provider.call(
        Capability.HIGH_REASONING,
        Decomposition,
        SYSTEM,
        f"Owner intent, verbatim:\n{raw_intent}",
        caller_role="architect",
        packet_id=packet_id,
    )
    if _is_broad(raw_intent) and len(result.ambiguities) < 8:
        raise ValueError("broad intent requires at least eight ambiguities")
    if ledger:
        ledger.append(
            "DECOMPOSE_COMPLETED",
            {"raw_intent": raw_intent, "result": result.model_dump(mode="json")},
        )
    return result, receipt


def _is_broad(intent: str) -> bool:
    words = intent.lower().split()
    category_words = {"erp", "platform", "marketplace", "system", "app", "business"}
    return len(words) < 30 or bool(category_words.intersection(words))
