"""The Context Engine — governed, provenanced, budgeted context assembly.

Canonical Sections 32 and 33. Forge does not dump the repository and the PRD into
every prompt: context is a governed resource, different roles receive different
context, and every item knows where it came from.

Two guarantees here are structural, not prompted, because a prompt cannot make
either of them true:

- **A Builder never receives the specification.** It gets its packet, the file
  slices it is allowed to touch, and the requirements and lessons that bear on
  them. Handing it the North Star invites it to relitigate intent instead of
  implementing the packet.
- **An Auditor never receives Builder reasoning.** This is the independence
  guarantee (Canonical S51). An auditor told how the builder got there is
  evaluating a narrative, not a candidate.

Both are enforced by `ROLE_POLICY`, an allow-list checked at assembly time.
Supplying a forbidden source raises rather than silently filtering, because a
caller that tried is a caller with a bug, and dropping it quietly would hide that.

Budget is measured in characters rather than tokens, deliberately. Tokens are the
quantity that costs money, but every tokenizer is model-specific and would make
assembly non-deterministic across a provider swap — and determinism is what lets
an audit replay a context. Characters are a stable, documented proxy; the receipt
records both the measure and the unit so a later routing model (FORGE-LRN-002) can
recalibrate without re-reading this file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from forge.execution_loop import AgentRole
from forge.trust_kernel import Authority, ForgeError

__all__ = [
    "ROLE_POLICY",
    "AssembledContext",
    "ContextAssembler",
    "ContextBudget",
    "ContextItem",
    "ContextProvenance",
    "DropReason",
    "DroppedItem",
    "SourceType",
]


class SourceType(StrEnum):
    """Where a context item came from.

    `BUILDER_REASONING` exists so the auditor exclusion is a named rule with a
    test, rather than an absence nobody notices when a new source is added.
    """

    NORTH_STAR = "NORTH_STAR"
    REQUIREMENT = "REQUIREMENT"
    ASSUMPTION = "ASSUMPTION"
    DECISION = "DECISION"
    INVARIANT = "INVARIANT"
    LESSON = "LESSON"
    REPOSITORY_SLICE = "REPOSITORY_SLICE"
    EVIDENCE = "EVIDENCE"
    PACKET = "PACKET"
    DIFF = "DIFF"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    BUILDER_REASONING = "BUILDER_REASONING"


#: Which source types each role may receive. An allow-list, not a deny-list: a
#: source type added to `SourceType` later reaches no role until someone decides
#: it should, which is the safe direction to fail.
ROLE_POLICY: Mapping[AgentRole, frozenset[SourceType]] = {
    # The Architect plans, so it sees intent. It does not see repository slices:
    # planning against file contents is how an architect turns into a builder.
    AgentRole.ARCHITECT: frozenset(
        {
            SourceType.NORTH_STAR,
            SourceType.REQUIREMENT,
            SourceType.ASSUMPTION,
            SourceType.DECISION,
            SourceType.INVARIANT,
            SourceType.LESSON,
            SourceType.EVIDENCE,
            SourceType.PACKET,
        }
    ),
    # The Builder implements a bounded packet. No North Star, no decision records,
    # no prior reasoning — just the work and what bears on it.
    AgentRole.BUILDER: frozenset(
        {
            SourceType.PACKET,
            SourceType.REPOSITORY_SLICE,
            SourceType.REQUIREMENT,
            SourceType.INVARIANT,
            SourceType.LESSON,
        }
    ),
    # The Auditor evaluates a frozen candidate against stated criteria. Never
    # BUILDER_REASONING: that is the whole independence guarantee.
    AgentRole.AUDITOR: frozenset(
        {
            SourceType.DIFF,
            SourceType.ACCEPTANCE_CRITERION,
            SourceType.EVIDENCE,
            SourceType.REQUIREMENT,
            SourceType.INVARIANT,
            SourceType.PACKET,
        }
    ),
    # The Governor is deterministic code. It reads evidence, never prose.
    AgentRole.GOVERNOR: frozenset(
        {
            SourceType.EVIDENCE,
            SourceType.PACKET,
            SourceType.DIFF,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class ContextProvenance:
    """Where an item came from, and how much it should be trusted. (S33)"""

    source_type: SourceType
    source_id: str
    version: int
    authority: Authority
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", SourceType(self.source_type))
        object.__setattr__(self, "authority", Authority(self.authority))
        if not self.source_id:
            raise ForgeError("INVALID_PROVENANCE", "Context provenance requires a source id")
        if self.version < 0:
            raise ForgeError(
                "INVALID_PROVENANCE", "Context provenance version must not be negative"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ForgeError(
                "INVALID_PROVENANCE", "Context provenance confidence must be between zero and one"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "version": self.version,
            "authority": self.authority.value,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One piece of assembled context, inseparable from its provenance.

    Provenance is a required constructor argument rather than an optional
    decoration: an item without it is exactly the retrieved text that S33 exists
    to stop from becoming indistinguishable from canonical truth.
    """

    id: str
    content: str
    provenance: ContextProvenance

    def __post_init__(self) -> None:
        if not self.id:
            raise ForgeError("INVALID_CONTEXT_ITEM", "Context item requires an id")
        if not isinstance(self.provenance, ContextProvenance):
            raise ForgeError("INVALID_CONTEXT_ITEM", f"Context item {self.id} requires provenance")

    @property
    def size(self) -> int:
        """Budget cost, in characters. See the module docstring on the unit."""
        return len(self.content)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "size": self.size,
            "provenance": self.provenance.as_dict(),
        }


class DropReason(StrEnum):
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    OVERSIZED_ITEM = "OVERSIZED_ITEM"


@dataclass(frozen=True, slots=True)
class DroppedItem:
    """An item the role did not receive, and why.

    Recorded rather than discarded: what the Builder could not see is part of the
    record of why the candidate looks the way it does, and an auditor reading the
    manifest should not have to infer it.
    """

    id: str
    source_type: SourceType
    size: int
    reason: DropReason

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type.value,
            "size": self.size,
            "reason": self.reason.value,
        }


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """A hard per-role ceiling."""

    max_characters: int

    def __post_init__(self) -> None:
        if self.max_characters <= 0:
            raise ForgeError("INVALID_CONTEXT_BUDGET", "Context budget must be positive")


#: Starting budgets. The Builder gets the most because it carries file slices; the
#: Governor gets least because it reads evidence, not prose. These are tuned
#: against real traces by FORGE-LRN-002, not guessed at twice.
DEFAULT_BUDGETS: Mapping[AgentRole, ContextBudget] = {
    AgentRole.ARCHITECT: ContextBudget(60_000),
    AgentRole.BUILDER: ContextBudget(120_000),
    AgentRole.AUDITOR: ContextBudget(80_000),
    AgentRole.GOVERNOR: ContextBudget(20_000),
}


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """The result: what the role receives, what it did not, and what that cost."""

    role: AgentRole
    objective: str
    packet_id: str
    items: tuple[ContextItem, ...] = field(default_factory=tuple)
    dropped: tuple[DroppedItem, ...] = field(default_factory=tuple)
    budget: ContextBudget = ContextBudget(1)

    @property
    def size(self) -> int:
        return sum(item.size for item in self.items)

    @property
    def headroom(self) -> int:
        return self.budget.max_characters - self.size

    @property
    def digest(self) -> str:
        """Stable across runs, processes, and machines, so a context is replayable."""
        return _digest(
            {
                "role": self.role.value,
                "objective": self.objective,
                "packet_id": self.packet_id,
                "items": [item.as_dict() for item in self.items],
                "dropped": [drop.as_dict() for drop in self.dropped],
                "budget": self.budget.max_characters,
            }
        )

    def manifest(self) -> dict[str, Any]:
        """Every supplied item accounted for, as included or dropped."""
        return {
            "role": self.role.value,
            "packet_id": self.packet_id,
            "objective": self.objective,
            "digest": self.digest,
            "included": [item.as_dict() for item in self.items],
            "dropped": [drop.as_dict() for drop in self.dropped],
        }

    def size_receipt(self) -> dict[str, Any]:
        """Ledger-shaped measurement. This is what FORGE-LRN-002 consumes."""
        by_source: dict[str, int] = {}
        for item in self.items:
            key = item.provenance.source_type.value
            by_source[key] = by_source.get(key, 0) + item.size
        return {
            "packet_id": self.packet_id,
            "role": self.role.value,
            "unit": "characters",
            "budget": self.budget.max_characters,
            "used": self.size,
            "headroom": self.headroom,
            "items_included": len(self.items),
            "items_dropped": len(self.dropped),
            "by_source_type": dict(sorted(by_source.items())),
            "context_digest": self.digest,
        }

    def render(self) -> str:
        """The assembled context as text, in the canonical S32 order it was given."""
        blocks = [f"ROLE: {self.role.value}", f"OBJECTIVE: {self.objective}"]
        for item in self.items:
            provenance = item.provenance
            blocks.append(
                f"[{item.id} | {provenance.source_type.value} "
                f"{provenance.source_id} v{provenance.version} "
                f"| authority {provenance.authority.value} "
                f"| confidence {provenance.confidence}]\n{item.content}"
            )
        return "\n\n".join(blocks)


class ContextAssembler:
    """Assembles role-specific context under policy and budget.

    Pure and deterministic: it holds budgets and nothing else, so two assemblers
    configured alike produce byte-identical results.
    """

    def __init__(self, budgets: Mapping[AgentRole, ContextBudget] | None = None):
        self._budgets = dict(budgets if budgets is not None else DEFAULT_BUDGETS)
        missing = [role for role in AgentRole if role not in self._budgets]
        if missing:
            raise ForgeError(
                "MISSING_CONTEXT_BUDGET",
                "No context budget for: " + ", ".join(role.value for role in missing),
            )

    def budget_for(self, role: AgentRole) -> ContextBudget:
        return self._budgets[role]

    def assemble(
        self,
        role: AgentRole,
        *,
        objective: str,
        packet_id: str,
        items: Iterable[ContextItem],
    ) -> AssembledContext:
        """Assemble context for one role.

        `items` is consumed in the order given, and that order is the priority:
        the caller knows what matters most for this packet, and a greedy
        in-order fill is the only budgeting rule that is obvious to a reader and
        reproducible by a replay. An item that cannot fit is dropped and recorded;
        later smaller items still fit, so one oversized slice does not starve
        everything behind it.
        """
        if not objective:
            raise ForgeError("INVALID_CONTEXT_REQUEST", "Context assembly requires an objective")
        if not packet_id:
            raise ForgeError("INVALID_CONTEXT_REQUEST", "Context assembly requires a packet id")

        policy = ROLE_POLICY.get(role)
        if policy is None:
            raise ForgeError("UNKNOWN_CONTEXT_ROLE", f"No context policy for role {role.value}")

        budget = self._budgets[role]
        supplied = list(items)
        self._enforce_policy(role, policy, supplied)
        self._reject_duplicates(supplied)

        included: list[ContextItem] = []
        dropped: list[DroppedItem] = []
        used = 0
        for item in supplied:
            if item.size > budget.max_characters:
                # Distinguished from a plain overflow: an item that could never
                # fit in an empty budget is a sizing problem, not a crowding one,
                # and the two want different fixes.
                dropped.append(
                    DroppedItem(
                        item.id, item.provenance.source_type, item.size, DropReason.OVERSIZED_ITEM
                    )
                )
                continue
            if used + item.size > budget.max_characters:
                dropped.append(
                    DroppedItem(
                        item.id, item.provenance.source_type, item.size, DropReason.BUDGET_EXCEEDED
                    )
                )
                continue
            included.append(item)
            used += item.size

        return AssembledContext(
            role=role,
            objective=objective,
            packet_id=packet_id,
            items=tuple(included),
            dropped=tuple(dropped),
            budget=budget,
        )

    @staticmethod
    def _enforce_policy(
        role: AgentRole, policy: frozenset[SourceType], items: Sequence[ContextItem]
    ) -> None:
        """Refuse forbidden sources loudly.

        Filtering them out silently would let a caller believe the Auditor saw
        the Builder's reasoning and consider the audit informed, or believe it
        did not and consider a leak impossible. Raising makes the caller's
        mistake visible at the point it was made.
        """
        for item in items:
            source_type = item.provenance.source_type
            if source_type not in policy:
                raise ForgeError(
                    "FORBIDDEN_CONTEXT_SOURCE",
                    f"Role {role.value} may not receive {source_type.value} "
                    f"(context item {item.id})",
                    details={
                        "role": role.value,
                        "source_type": source_type.value,
                        "item_id": item.id,
                        "allowed": sorted(source.value for source in policy),
                    },
                )

    @staticmethod
    def _reject_duplicates(items: Sequence[ContextItem]) -> None:
        seen: set[str] = set()
        for item in items:
            if item.id in seen:
                raise ForgeError(
                    "DUPLICATE_CONTEXT_ITEM",
                    f"Context item {item.id} supplied more than once",
                )
            seen.add(item.id)


def _digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()
