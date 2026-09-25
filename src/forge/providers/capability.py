"""The single capability vocabulary.

Roles ask for a capability; model names are an implementation detail (Forge S50).

This lives in its own module because both the provider layer and the decision
layer need it. They previously each defined their own `Capability` with different
members, so a tier chosen by the router could not index the provider's routing
table at all. One enum, one meaning.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Capability", "ROUTABLE_TIERS"]


class Capability(StrEnum):
    HIGH_REASONING = "high_reasoning"  # Architect, final-gate audit, stuck resolution
    CODING = "coding"  # Builder / workers
    ROUTINE_AUDIT = "routine_audit"  # per-packet review (cheaper than final gate)
    FAST = "fast"  # scoping, classification, routing
    EXEC_DEBUG = "exec_debug"  # sandbox execution / test-fix loop


#: The tiers the packet router is allowed to choose between. Audit and exec-debug
#: seats are assigned by the Governor from the packet's role, not proposed by a
#: decision model, so they are deliberately not offered here.
ROUTABLE_TIERS: tuple[Capability, ...] = (
    Capability.FAST,
    Capability.CODING,
    Capability.HIGH_REASONING,
)
