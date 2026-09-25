"""Context Engine tests.

Two of these matter more than the rest: a Builder must not be able to receive the
specification, and an Auditor must not be able to receive Builder reasoning. Both
are independence guarantees that a prompt cannot deliver, so they are tested as
assembly-time errors rather than as properties of generated text.
"""

from __future__ import annotations

import pytest

from forge.context_engine import (
    ROLE_POLICY,
    AssembledContext,
    ContextAssembler,
    ContextBudget,
    ContextItem,
    ContextProvenance,
    DropReason,
    SourceType,
)
from forge.execution_loop import AgentRole
from forge.trust_kernel import Authority, ForgeError


def provenance(source_type: SourceType, source_id: str = "S-1", **kwargs) -> ContextProvenance:
    return ContextProvenance(
        source_type=source_type,
        source_id=source_id,
        version=kwargs.get("version", 1),
        authority=kwargs.get("authority", Authority.A2),
        confidence=kwargs.get("confidence", 1.0),
    )


def item(item_id: str, source_type: SourceType, content: str = "content", **kwargs) -> ContextItem:
    return ContextItem(item_id, content, provenance(source_type, **kwargs))


@pytest.fixture
def assembler() -> ContextAssembler:
    return ContextAssembler()


def assemble(assembler: ContextAssembler, role: AgentRole, items) -> AssembledContext:
    return assembler.assemble(
        role, objective="implement the packet", packet_id="FORGE-T-001", items=items
    )


# ---------------------------------------------------------------------------
# Structural independence — the two guarantees a prompt cannot make
# ---------------------------------------------------------------------------


def test_auditor_cannot_receive_builder_reasoning(assembler):
    """The independence guarantee (Canonical S51).

    An auditor told how the builder got there is evaluating a narrative rather
    than a candidate, so this is refused at assembly rather than discouraged.
    """
    with pytest.raises(ForgeError) as excinfo:
        assemble(
            assembler,
            AgentRole.AUDITOR,
            [
                item("CTX-1", SourceType.DIFF),
                item("CTX-2", SourceType.BUILDER_REASONING, "I tried X then Y"),
            ],
        )

    assert excinfo.value.code == "FORBIDDEN_CONTEXT_SOURCE"
    assert "BUILDER_REASONING" in excinfo.value.message
    assert excinfo.value.details["role"] == "AUDITOR"


def test_builder_cannot_receive_the_specification(assembler):
    """A Builder given the North Star relitigates intent instead of building."""
    with pytest.raises(ForgeError) as excinfo:
        assemble(
            assembler,
            AgentRole.BUILDER,
            [item("CTX-1", SourceType.PACKET), item("CTX-2", SourceType.NORTH_STAR)],
        )

    assert excinfo.value.code == "FORBIDDEN_CONTEXT_SOURCE"
    assert excinfo.value.details["source_type"] == "NORTH_STAR"


def test_builder_cannot_receive_prior_reasoning(assembler):
    with pytest.raises(ForgeError):
        assemble(assembler, AgentRole.BUILDER, [item("CTX-1", SourceType.BUILDER_REASONING)])


def test_no_role_may_receive_builder_reasoning():
    """Nothing in the policy table hands this to anyone.

    Asserted against the table itself, not through one call per role, so adding
    a role later cannot quietly open the hole.
    """
    for role, policy in ROLE_POLICY.items():
        assert SourceType.BUILDER_REASONING not in policy, role


def test_every_role_has_a_policy():
    assert set(ROLE_POLICY) == set(AgentRole)


def test_architect_does_not_receive_repository_slices(assembler):
    """Planning against file contents is how an architect turns into a builder."""
    with pytest.raises(ForgeError):
        assemble(assembler, AgentRole.ARCHITECT, [item("CTX-1", SourceType.REPOSITORY_SLICE)])


def test_forbidden_source_is_refused_not_filtered(assembler):
    """Silent filtering would leave the caller believing something untrue."""
    with pytest.raises(ForgeError):
        assemble(
            assembler,
            AgentRole.BUILDER,
            [item("CTX-1", SourceType.PACKET), item("CTX-2", SourceType.DECISION)],
        )


# ---------------------------------------------------------------------------
# Provenance — Canonical S33
# ---------------------------------------------------------------------------


def test_assembled_items_carry_full_provenance(assembler):
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [item("CTX-1", SourceType.REQUIREMENT, source_id="R-014", version=3)],
    )

    recorded = context.items[0].provenance.as_dict()
    assert recorded == {
        "source_type": "REQUIREMENT",
        "source_id": "R-014",
        "version": 3,
        "authority": "A2",
        "confidence": 1.0,
    }


def test_item_without_provenance_is_refused():
    with pytest.raises(ForgeError) as excinfo:
        ContextItem("CTX-1", "content", provenance=None)  # type: ignore[arg-type]
    assert excinfo.value.code == "INVALID_CONTEXT_ITEM"


@pytest.mark.parametrize(
    ("field", "value"),
    [("source_id", ""), ("version", -1), ("confidence", 1.5), ("confidence", -0.1)],
)
def test_invalid_provenance_is_refused(field, value):
    kwargs = {
        "source_type": SourceType.REQUIREMENT,
        "source_id": "R-1",
        "version": 1,
        "authority": Authority.A2,
        "confidence": 1.0,
    }
    kwargs[field] = value
    with pytest.raises(ForgeError) as excinfo:
        ContextProvenance(**kwargs)
    assert excinfo.value.code == "INVALID_PROVENANCE"


def test_rendered_context_shows_provenance_inline(assembler):
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [item("CTX-1", SourceType.REQUIREMENT, "A is one-to-many with B", source_id="R-014")],
    )

    rendered = context.render()
    assert "ROLE: BUILDER" in rendered
    assert "CTX-1" in rendered and "REQUIREMENT" in rendered and "R-014" in rendered
    assert "A is one-to-many with B" in rendered


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_items_within_budget_are_all_included():
    assembler = ContextAssembler({role: ContextBudget(100) for role in AgentRole})
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [item("CTX-1", SourceType.PACKET, "a" * 40), item("CTX-2", SourceType.PACKET, "b" * 40)],
    )

    assert [i.id for i in context.items] == ["CTX-1", "CTX-2"]
    assert context.dropped == ()
    assert context.size == 80
    assert context.headroom == 20


def test_overflow_drops_in_order_and_records_the_reason():
    assembler = ContextAssembler({role: ContextBudget(100) for role in AgentRole})
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [
            item("CTX-1", SourceType.PACKET, "a" * 60),
            item("CTX-2", SourceType.REQUIREMENT, "b" * 60),
            item("CTX-3", SourceType.LESSON, "c" * 30),
        ],
    )

    assert [i.id for i in context.items] == ["CTX-1", "CTX-3"]
    assert [(d.id, d.reason) for d in context.dropped] == [("CTX-2", DropReason.BUDGET_EXCEEDED)]
    assert context.size == 90


def test_an_item_larger_than_the_whole_budget_is_distinguished():
    """A sizing problem and a crowding problem want different fixes."""
    assembler = ContextAssembler({role: ContextBudget(50) for role in AgentRole})
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [item("CTX-BIG", SourceType.REPOSITORY_SLICE, "x" * 500)],
    )

    assert context.items == ()
    assert context.dropped[0].reason is DropReason.OVERSIZED_ITEM


def test_one_oversized_item_does_not_starve_what_follows():
    assembler = ContextAssembler({role: ContextBudget(100) for role in AgentRole})
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [
            item("CTX-BIG", SourceType.REPOSITORY_SLICE, "x" * 500),
            item("CTX-SMALL", SourceType.LESSON, "y" * 10),
        ],
    )

    assert [i.id for i in context.items] == ["CTX-SMALL"]


def test_manifest_accounts_for_every_supplied_item():
    """Context the role did not receive is evidence, not litter."""
    assembler = ContextAssembler({role: ContextBudget(100) for role in AgentRole})
    supplied = [
        item("CTX-1", SourceType.PACKET, "a" * 60),
        item("CTX-2", SourceType.REQUIREMENT, "b" * 60),
        item("CTX-3", SourceType.LESSON, "c" * 30),
    ]
    context = assemble(assembler, AgentRole.BUILDER, supplied)

    manifest = context.manifest()
    accounted = {entry["id"] for entry in manifest["included"]} | {
        entry["id"] for entry in manifest["dropped"]
    }
    assert accounted == {i.id for i in supplied}


@pytest.mark.parametrize("size", [0, -1])
def test_non_positive_budget_is_refused(size):
    with pytest.raises(ForgeError) as excinfo:
        ContextBudget(size)
    assert excinfo.value.code == "INVALID_CONTEXT_BUDGET"


def test_missing_budget_for_a_role_is_refused():
    with pytest.raises(ForgeError) as excinfo:
        ContextAssembler({AgentRole.BUILDER: ContextBudget(10)})
    assert excinfo.value.code == "MISSING_CONTEXT_BUDGET"


# ---------------------------------------------------------------------------
# Determinism and measurement
# ---------------------------------------------------------------------------


def test_identical_inputs_produce_an_identical_digest(assembler):
    def build():
        return assemble(
            assembler,
            AgentRole.BUILDER,
            [
                item("CTX-1", SourceType.PACKET, "objective"),
                item("CTX-2", SourceType.REQUIREMENT, "requirement"),
            ],
        )

    assert build().digest == build().digest


def test_digest_changes_with_content(assembler):
    first = assemble(assembler, AgentRole.BUILDER, [item("CTX-1", SourceType.PACKET, "one")])
    second = assemble(assembler, AgentRole.BUILDER, [item("CTX-1", SourceType.PACKET, "two")])
    assert first.digest != second.digest


def test_digest_changes_with_order(assembler):
    a = item("CTX-1", SourceType.PACKET, "one")
    b = item("CTX-2", SourceType.PACKET, "two")
    assert (
        assemble(assembler, AgentRole.BUILDER, [a, b]).digest
        != assemble(assembler, AgentRole.BUILDER, [b, a]).digest
    )


def test_digest_reflects_dropped_items():
    """Two contexts with the same content but different drops are not the same."""
    roomy = ContextAssembler({role: ContextBudget(1000) for role in AgentRole})
    tight = ContextAssembler({role: ContextBudget(20) for role in AgentRole})
    items = [item("CTX-1", SourceType.PACKET, "a" * 15), item("CTX-2", SourceType.LESSON, "b" * 15)]

    assert (
        assemble(roomy, AgentRole.BUILDER, items).digest
        != assemble(tight, AgentRole.BUILDER, items).digest
    )


def test_size_receipt_is_ledger_shaped():
    """This is the measurement FORGE-LRN-002 consumes."""
    assembler = ContextAssembler({role: ContextBudget(100) for role in AgentRole})
    context = assemble(
        assembler,
        AgentRole.BUILDER,
        [
            item("CTX-1", SourceType.PACKET, "a" * 20),
            item("CTX-2", SourceType.REQUIREMENT, "b" * 30),
            item("CTX-3", SourceType.LESSON, "c" * 90),
        ],
    )

    receipt = context.size_receipt()
    assert receipt["role"] == "BUILDER"
    assert receipt["packet_id"] == "FORGE-T-001"
    assert receipt["unit"] == "characters"
    assert receipt["budget"] == 100
    assert receipt["used"] == 50
    assert receipt["headroom"] == 50
    assert receipt["items_included"] == 2
    assert receipt["items_dropped"] == 1
    assert receipt["by_source_type"] == {"PACKET": 20, "REQUIREMENT": 30}
    assert receipt["context_digest"] == context.digest


def test_duplicate_item_ids_are_refused(assembler):
    """Two items sharing an id make the manifest ambiguous about what was sent."""
    with pytest.raises(ForgeError) as excinfo:
        assemble(
            assembler,
            AgentRole.BUILDER,
            [item("CTX-1", SourceType.PACKET), item("CTX-1", SourceType.LESSON)],
        )
    assert excinfo.value.code == "DUPLICATE_CONTEXT_ITEM"


@pytest.mark.parametrize(("objective", "packet_id"), [("", "P-1"), ("obj", "")])
def test_assembly_requires_objective_and_packet(assembler, objective, packet_id):
    with pytest.raises(ForgeError) as excinfo:
        assembler.assemble(AgentRole.BUILDER, objective=objective, packet_id=packet_id, items=[])
    assert excinfo.value.code == "INVALID_CONTEXT_REQUEST"


def test_empty_context_is_valid_and_measured(assembler):
    """A role can legitimately need nothing; that is a zero, not an error."""
    context = assemble(assembler, AgentRole.GOVERNOR, [])
    assert context.items == ()
    assert context.size == 0
    assert context.size_receipt()["items_included"] == 0
