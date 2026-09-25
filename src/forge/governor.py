"""Budget enforcement for the Governor.

The Finish Contract requires that "the Governor enforces state, scope, authority,
budgets, and valid transitions". Four of the five had homes: state and transitions in
`trust_kernel`, scope and authority in `execution_loop` and `policy`. Budgets had
none. `BuildPacket.retry_limit` was the closest thing and nothing read it.

A budget is only a budget if exhausting it stops the work
---------------------------------------------------------
So every consumption goes through `spend`, which refuses once a limit is reached and
returns a receipt either way. A counter that callers are trusted to check is
documentation.

Budgets are consumed before the work, not after
-----------------------------------------------
`spend` is called with the cost *before* the attempt, and a refusal means the attempt
does not happen. Charging afterwards makes every limit off by one attempt, and the
attempt that overruns is exactly the expensive one you wanted to prevent — the
runaway that motivated a wall-clock budget in the first place.

An unset budget is unlimited, and saying so is the point
--------------------------------------------------------
`None` means no limit, and `Budget.declared` reports which dimensions are actually
bounded. V0 does not know what a sensible token ceiling is, and inventing one would
be a fabricated control. What must not happen is a system that looks budgeted because
a `BudgetLedger` exists while every dimension is `None`, so the ledger reports its own
coverage and `tests/test_governor.py` asserts the wall-clock and attempt dimensions
are bounded for any packet the loop runs.

This module holds no authority. Exhausting a budget produces `EXHAUSTED`, which is a
stop — never a grant, and never something a caller can overspend by asking twice.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

__all__ = [
    "Budget",
    "BudgetDimension",
    "BudgetLedger",
    "GovernorError",
    "SpendOutcome",
    "SpendReceipt",
]


class GovernorError(Exception):
    """Structured fail-closed error."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, "details": self.details}


class BudgetDimension(StrEnum):
    """What a packet can run out of.

    Attempts and wall clock are the two that bound a runaway regardless of provider:
    a loop that never calls a model can still spin, and a loop that calls a free model
    can still spin forever. Tokens and currency bound cost, and are unset in V0
    because no live call has been made and no real figure exists to set them from.
    """

    ATTEMPTS = "ATTEMPTS"
    WALL_CLOCK_SECONDS = "WALL_CLOCK_SECONDS"
    MODEL_CALLS = "MODEL_CALLS"
    INPUT_TOKENS = "INPUT_TOKENS"
    OUTPUT_TOKENS = "OUTPUT_TOKENS"


class SpendOutcome(StrEnum):
    ALLOWED = "ALLOWED"
    #: The spend was refused because it would exceed the limit. The work must not
    #: happen. Not a warning.
    EXHAUSTED = "EXHAUSTED"


@dataclass(frozen=True, slots=True)
class Budget:
    """Per-packet limits. `None` on a dimension means unlimited, deliberately."""

    attempts: int | None = None
    wall_clock_seconds: float | None = None
    model_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for dimension, limit in self.as_mapping().items():
            if limit is None:
                continue
            if limit <= 0:
                raise GovernorError(
                    "INVALID_BUDGET",
                    f"{dimension.value} limit of {limit} permits no work at all; use None "
                    "for unlimited rather than zero for blocked",
                    details={"dimension": dimension.value, "limit": limit},
                )

    def as_mapping(self) -> dict[BudgetDimension, int | float | None]:
        return {
            BudgetDimension.ATTEMPTS: self.attempts,
            BudgetDimension.WALL_CLOCK_SECONDS: self.wall_clock_seconds,
            BudgetDimension.MODEL_CALLS: self.model_calls,
            BudgetDimension.INPUT_TOKENS: self.input_tokens,
            BudgetDimension.OUTPUT_TOKENS: self.output_tokens,
        }

    def limit_for(self, dimension: BudgetDimension) -> int | float | None:
        return self.as_mapping()[dimension]

    @property
    def declared(self) -> frozenset[BudgetDimension]:
        """Dimensions that are actually bounded.

        Exists so "is this packet budgeted?" has an answer that does not depend on
        reading five fields and noticing they are all None.
        """
        return frozenset(
            dimension for dimension, limit in self.as_mapping().items() if limit is not None
        )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True, slots=True)
class SpendReceipt:
    """Evidence for one spend decision, allowed or refused."""

    packet_id: str
    dimension: BudgetDimension
    amount: int | float
    spent_before: int | float
    spent_after: int | float
    limit: int | float | None
    outcome: SpendOutcome
    reason: str

    @property
    def digest(self) -> str:
        return _digest(_plain(asdict(self)))

    def as_dict(self) -> dict[str, Any]:
        return _plain(asdict(self))


class BudgetLedger:
    """Tracks and enforces one packet's budget.

    Every spend is recorded, including refused ones. A refused spend is the most
    interesting entry in the record — it is the moment a limit did something — and
    dropping it would leave a ledger that only ever shows budgets being respected.
    """

    def __init__(self, packet_id: str, budget: Budget):
        if not packet_id:
            raise GovernorError("INVALID_PACKET", "A budget is scoped to a packet")
        self._packet_id = packet_id
        self._budget = budget
        self._spent: dict[BudgetDimension, int | float] = dict.fromkeys(BudgetDimension, 0)
        self._receipts: list[SpendReceipt] = []

    @property
    def packet_id(self) -> str:
        return self._packet_id

    @property
    def budget(self) -> Budget:
        return self._budget

    @property
    def receipts(self) -> tuple[SpendReceipt, ...]:
        return tuple(self._receipts)

    def spent(self, dimension: BudgetDimension) -> int | float:
        return self._spent[dimension]

    def remaining(self, dimension: BudgetDimension) -> int | float | None:
        """`None` when the dimension is unlimited — not zero, and not infinity.

        Returning a number for an unbounded dimension would let a caller compare it
        and conclude something false. `None` forces the question.
        """
        limit = self._budget.limit_for(dimension)
        if limit is None:
            return None
        return max(0, limit - self._spent[dimension])

    def is_exhausted(self, dimension: BudgetDimension) -> bool:
        remaining = self.remaining(dimension)
        return remaining is not None and remaining <= 0

    @property
    def exhausted_dimensions(self) -> frozenset[BudgetDimension]:
        return frozenset(d for d in BudgetDimension if self.is_exhausted(d))

    def spend(self, dimension: BudgetDimension, amount: int | float = 1) -> SpendReceipt:
        """Charge `amount` before doing the work. A refusal means do not do it.

        Refusing rather than raising is deliberate: exhaustion is an expected
        outcome the Governor routes on, not an exceptional one, and an exception
        would tempt callers to wrap it in a `try` that continues anyway. The receipt
        is the thing they have to look at.
        """
        if amount <= 0:
            raise GovernorError(
                "INVALID_SPEND",
                f"Spend of {amount} on {dimension.value} is not a cost; a zero or "
                "negative charge would let unlimited work through a bounded dimension",
                details={"dimension": dimension.value, "amount": amount},
            )
        limit = self._budget.limit_for(dimension)
        before = self._spent[dimension]

        if limit is None:
            self._spent[dimension] = before + amount
            return self._record(
                dimension,
                amount,
                before,
                self._spent[dimension],
                limit,
                SpendOutcome.ALLOWED,
                f"{dimension.value} is unlimited for this packet.",
            )

        if before + amount > limit:
            # Nothing is consumed on a refusal, so the ledger keeps saying exactly
            # what was used. A refused spend that still charged would make the
            # remaining figure drift away from reality every time a limit bit.
            return self._record(
                dimension,
                amount,
                before,
                before,
                limit,
                SpendOutcome.EXHAUSTED,
                f"{dimension.value} budget exhausted: {before} of {limit} used, "
                f"{amount} requested. The work must not proceed.",
            )

        self._spent[dimension] = before + amount
        return self._record(
            dimension,
            amount,
            before,
            self._spent[dimension],
            limit,
            SpendOutcome.ALLOWED,
            f"{dimension.value}: {self._spent[dimension]} of {limit} used.",
        )

    def _record(
        self,
        dimension: BudgetDimension,
        amount: int | float,
        before: int | float,
        after: int | float,
        limit: int | float | None,
        outcome: SpendOutcome,
        reason: str,
    ) -> SpendReceipt:
        receipt = SpendReceipt(
            self._packet_id, dimension, amount, before, after, limit, outcome, reason
        )
        self._receipts.append(receipt)
        return receipt

    def evidence(self) -> dict[str, Any]:
        """The budget record for this packet, as reviewable evidence."""
        return {
            "packet_id": self._packet_id,
            "budget_digest": self._budget.digest,
            "declared_dimensions": sorted(d.value for d in self._budget.declared),
            "unbounded_dimensions": sorted(
                d.value for d in BudgetDimension if d not in self._budget.declared
            ),
            "spent": {d.value: self._spent[d] for d in BudgetDimension},
            "limits": {d.value: self._budget.limit_for(d) for d in BudgetDimension},
            "exhausted": sorted(d.value for d in self.exhausted_dimensions),
            "refusals": [
                r.as_dict() for r in self._receipts if r.outcome is SpendOutcome.EXHAUSTED
            ],
            "spend_count": len(self._receipts),
        }


def _plain(value: Any) -> Any:
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
