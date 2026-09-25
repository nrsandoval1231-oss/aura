"""Shared validated records for intent ingestion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from forge.ledger_store import LedgerStore
from forge.trust_kernel import ForgeError, Ledger, Receipt


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConfidenceLabel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BlastRadius(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequirementSeed(StrictModel):
    id: str
    statement: str
    source_quote: str | None = None
    inferred: bool = False

    @model_validator(mode="after")
    def traced_or_inferred(self) -> RequirementSeed:
        if not self.source_quote and not self.inferred:
            raise ValueError("a requirement needs source text or inferred=True")
        return self


class Ambiguity(StrictModel):
    id: str
    dimension: str
    question_if_asked: str
    why_we_ask: str
    current_assumption: str
    assumption_confidence: float = Field(ge=0, le=1)
    blast_radius: BlastRadius
    resolvable_by_default: bool


class KnownUnknown(StrictModel):
    id: str
    plain: str
    source_ambiguity: str | None = None


class StageReceipt(StrictModel):
    event: str
    payload: dict[str, Any]
    recorded_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    previous_hash: str | None = None
    receipt_hash: str = ""


class ReceiptLedger:
    """Ingestion view of the core append-only ledger and durable checkpoint."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.receipts: list[StageReceipt] = []
        self._store = LedgerStore(self.path.parent, self.path.stem) if self.path else None
        self._failed = False
        if self._store:
            if self.path.suffix != ".jsonl":
                raise ValueError("ingestion receipt path must end in .jsonl")
            if self.path.exists() != self._store.checkpoint_path.exists():
                raise ValueError("ingestion stream or checkpoint is missing")
            if self._store.exists:
                try:
                    self._preflight_persisted(has_receipts=True)
                    self._ledger = self._store.load()
                except ForgeError as exc:
                    raise ValueError(
                        f"ingestion stream checkpoint or receipt mismatch: {exc}"
                    ) from exc
            else:
                self._ledger = Ledger(stream_id=self.path.stem)
        else:
            self._ledger = Ledger()
        self.receipts = [self._stage(item) for item in self._ledger.receipts]

    def _reject_invalid_framing(self) -> None:
        """Reject framing that the core reader intentionally treats as ignorable."""
        assert self.path is not None
        raw = self.path.read_bytes()
        if not raw or not raw.endswith(b"\n"):
            raise ValueError("ingestion stream has an incomplete final record")
        lines = raw.splitlines(keepends=True)
        if any(not line.strip() for line in lines):
            raise ValueError("ingestion stream contains a blank record")

    def _preflight_persisted(self, *, has_receipts: bool) -> None:
        """Check existence, framing, and stream identity before core reload."""
        assert self.path is not None and self._store is not None
        stream_exists = self.path.exists()
        checkpoint_exists = self._store.checkpoint_path.exists()
        if not stream_exists or not checkpoint_exists:
            if not has_receipts and not stream_exists and not checkpoint_exists:
                return
            raise ValueError("ingestion stream or checkpoint is missing")
        self._reject_invalid_framing()
        try:
            checkpoint = json.loads(self._store.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("ingestion checkpoint is malformed") from exc
        if checkpoint.get("stream_id") != self.path.stem:
            raise ValueError("ingestion checkpoint stream identity mismatch")

    @staticmethod
    def _stage(item: Receipt) -> StageReceipt:
        return StageReceipt(
            event=item.event,
            payload=dict(item.payload["data"]),
            recorded_at=item.payload["recorded_at"],
            previous_hash=item.previous_hash,
            receipt_hash=item.receipt_hash,
        )

    def append(self, event: str, payload: dict[str, Any]) -> StageReceipt:
        if self._failed:
            raise ValueError("ingestion append state is ambiguous; reload required")
        if self._store:
            try:
                self._preflight_persisted(has_receipts=bool(self._ledger.receipts))
                if not self._store.exists:
                    # An empty, genuinely fresh ledger may create its first files.
                    if self._ledger.receipts:
                        raise ValueError("ingestion stream or checkpoint is missing")
                else:
                    if self._store.load().checkpoint != self._ledger.checkpoint:
                        raise ValueError("ingestion stream changed since last append")
            except ForgeError as exc:
                raise ValueError(f"ingestion stream checkpoint or receipt mismatch: {exc}") from exc
        item = Receipt.create(
            len(self._ledger.receipts) + 1,
            event,
            None,
            None,
            {"data": payload, "recorded_at": datetime.now(UTC).isoformat()},
            self._ledger.checkpoint.head_hash,
        )
        self._ledger.append(item)
        try:
            if self._store:
                self._store.append(item, self._ledger)
        except BaseException:
            self._failed = True
            raise
        receipt = self._stage(item)
        self.receipts.append(receipt)
        return receipt

    def payloads(self, event: str) -> list[dict[str, Any]]:
        return [item.payload for item in self.receipts if item.event == event]

    def verify(self) -> None:
        self._ledger.verify()
        if self.receipts != [self._stage(item) for item in self._ledger.receipts]:
            raise ValueError("ingestion receipt view differs from verified ledger")
        if self._failed:
            raise ValueError("ingestion append state is ambiguous")
        if self._store:
            try:
                self._preflight_persisted(has_receipts=bool(self._ledger.receipts))
                persisted = self._store.load()
            except ForgeError as exc:
                raise ValueError(f"ingestion stream checkpoint or receipt mismatch: {exc}") from exc
            if persisted.to_records() != self._ledger.to_records():
                raise ValueError("ingestion stream differs from loaded receipts")


class PipelineStage(StrEnum):
    DECOMPOSE = "DECOMPOSE"
    CALIBRATE = "CALIBRATE"
    REFINE = "REFINE"
    HANDOFF = "HANDOFF"


class Provisional(StrEnum):
    PROVISIONAL = "PROVISIONAL"


class AnswerFormat(StrEnum):
    FREE_TEXT = "free_text"


class SignatureKind(StrEnum):
    OWNER = "owner"


class ContractStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class DeclineReason(StrictModel):
    declined: Literal[True] = True
    reason: str | None = None
