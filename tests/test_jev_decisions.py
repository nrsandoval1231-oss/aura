"""Decision layer tests.

Jev is injected as a fake throughout. The point of these tests is the Forge side
of the boundary — how answers are turned into gates — not the vendor's model.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from forge.decisions import jev_decisions as jd
from forge.decisions.jev_decisions import (
    Capability,
    JevClient,
    JevError,
    RiskLevel,
    autonomy_gate,
    classify_tool_call,
    is_materially_different_strategy,
    needs_owner,
    relevant_failures,
    route_packet,
)
from forge.paths import paths_in_scope


class FakeSDK:
    """Stands in for `TypeSafeClient`, returning answers in the SDK's own shape."""

    def __init__(self, answers: dict, *, usage=None, model="jev-1.13.0"):
        self._answers = answers
        self._usage = usage or SimpleNamespace(input_tokens=5, output_tokens=2)
        self._model = model
        self.calls: list[dict] = []
        self.closed = False

    def system_one(self, state, questions, **kwargs):
        self.calls.append({"state": state, "questions": questions, **kwargs})
        return SimpleNamespace(answers=self._answers, usage=self._usage, model=self._model)

    def close(self):
        self.closed = True


def _noul(p: float):
    return SimpleNamespace(noul=p)


def _choice(value: str, confidence: float):
    return SimpleNamespace(choice=value, confidence=confidence, probabilities={value: confidence})


def _score(value: float, confidence: float, levels: int = 3):
    return SimpleNamespace(
        score=value,
        confidence=confidence,
        legend={str(i): f"level {i}" for i in range(levels)},
        probabilities={str(i): 1.0 / levels for i in range(levels)},
    )


def _client(answers: dict, **kwargs) -> tuple[JevClient, FakeSDK]:
    sdk = FakeSDK(answers, **kwargs)
    return JevClient(client=sdk), sdk


# ---------------------------------------------------------------------------
# Client mechanics — the audit's F6
# ---------------------------------------------------------------------------


def test_timeout_reaches_the_sdk():
    """A Governor guardrail that can hang forever is not a guardrail."""
    client, sdk = _client({"q": _noul(0.9)})
    client._timeout = 3.5
    client.evaluate("state", {"q": jd.Noul(instructions="?")}, decision_fn="t")

    assert sdk.calls[0]["timeout"] == 3.5


def test_client_closes_its_transport():
    client, sdk = _client({})
    with client:
        pass
    assert sdk.closed is True


def test_receipt_records_the_versioned_model():
    client, _ = _client({"q": _noul(0.5)}, model="jev-1.13.0-20260901")
    _, receipt = client.evaluate("s", {"q": jd.Noul(instructions="?")}, decision_fn="t")

    assert receipt.model_reported == "jev-1.13.0-20260901"
    assert receipt.model_requested == jd.JEV_MODEL_PINNED
    assert receipt.input_tokens == 5


def test_unknown_question_type_fails_closed():
    client, _ = _client({})
    with pytest.raises(JevError, match="Unknown question type"):
        client.evaluate("s", {"q": object()}, decision_fn="t")


def test_unknown_answer_shape_fails_closed():
    client, _ = _client({"q": SimpleNamespace(surprise=1)})
    with pytest.raises(JevError, match="Unknown answer shape"):
        client.evaluate("s", {"q": jd.Noul(instructions="?")}, decision_fn="t")


# ---------------------------------------------------------------------------
# Scope is decided in code, not by the model — the audit's F6
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paths", "allowed", "expected"),
    [
        (["src/forge/a.py"], ["src/**"], True),
        (["src/forge/a.py", "tests/b.py"], ["src/**", "tests/**"], True),
        (["docs/secret.md"], ["src/**"], False),
        # Traversal must not launder a protected path into scope.
        (["src/../AGENTS.md"], ["src/**"], False),
        (["src/forge/../../.agent/DECISIONS.md"], ["src/**"], False),
        (["src/forge/../../AGENTS.md"], ["src/forge/**"], False),
        (["/etc/passwd"], ["src/**"], False),
        (["C:/Windows/system32"], ["**"], False),
        # `*` must not cross a separator.
        (["src/forge/deep/a.py"], ["src/*"], False),
        # Every empty edge fails closed.
        ([], ["src/**"], False),
        (["src/a.py"], [], False),
        ([], [], False),
    ],
)
def test_paths_in_scope_is_deterministic_and_fails_closed(paths, allowed, expected):
    assert paths_in_scope(paths, allowed) is expected


def test_classify_tool_call_requires_touched_paths():
    """An omitted path set used to read as in-scope, disabling half the guardrail."""
    client, _ = _client({"risk": _choice("reversible", 0.9)})
    with pytest.raises(TypeError):
        classify_tool_call(
            client,
            tool="shell",
            args={"cmd": "rm -rf ./build"},
            packet_scope={"allowed_paths": ["src/**"]},
        )


def test_traversal_write_still_needs_a_human():
    """The concrete attack: escape the packet scope with `..` on a reversible write."""
    client, _ = _client({"risk": _choice("reversible", 0.95)})
    _, needs_human, _ = classify_tool_call(
        client,
        tool="write",
        args={"path": "src/forge/../../AGENTS.md"},
        packet_scope={"allowed_paths": ["src/forge/**"]},
        touched_paths=["src/forge/../../AGENTS.md"],
    )
    assert needs_human is True


def test_classify_tool_call_does_not_ask_the_model_about_scope():
    client, sdk = _client({"risk": _choice("reversible", 0.9)})
    risk, needs_human, _ = classify_tool_call(
        client,
        tool="write",
        args={"path": "docs/secret.md"},
        packet_scope={"allowed_paths": ["src/**"]},
        touched_paths=["docs/secret.md"],
    )

    assert risk is RiskLevel.REVERSIBLE
    # Out of scope, decided in code, so a human is required.
    assert needs_human is True
    assert "in_scope" not in sdk.calls[0]["questions"]
    assert "packet_allowed_paths" not in sdk.calls[0]["state"]


def test_in_scope_reversible_call_proceeds():
    client, _ = _client({"risk": _choice("reversible", 0.95)})
    _, needs_human, _ = classify_tool_call(
        client,
        tool="write",
        args={"path": "src/forge/a.py"},
        packet_scope={"allowed_paths": ["src/**"]},
        touched_paths=["src/forge/a.py"],
    )
    assert needs_human is False


def test_irreversible_always_needs_a_human():
    client, _ = _client({"risk": _choice("irreversible", 0.99)})
    _, needs_human, _ = classify_tool_call(
        client,
        tool="rm",
        args={},
        packet_scope={"allowed_paths": ["**"]},
        touched_paths=["build/artifact"],
    )
    assert needs_human is True


def test_low_confidence_needs_a_human():
    client, _ = _client({"risk": _choice("read_only", 0.4)})
    _, needs_human, _ = classify_tool_call(
        client,
        tool="cat",
        args={},
        packet_scope={"allowed_paths": ["**"]},
        touched_paths=["src/forge/a.py"],
    )
    assert needs_human is True


# ---------------------------------------------------------------------------
# Routing shares one capability vocabulary — the audit's F6
# ---------------------------------------------------------------------------


def test_route_packet_returns_the_shared_capability():
    from forge.providers import ROUTING
    from forge.providers import Capability as ProviderCapability

    client, _ = _client({"tier": _choice("coding", 0.9)})
    tier, _ = route_packet(client, "objective", ["a.py"], "context")

    assert tier is Capability.CODING
    assert tier is ProviderCapability.CODING
    # The whole point: a routed tier can index the provider table.
    assert ROUTING[tier] == "deepseek"


def test_route_packet_rejects_a_non_routable_tier():
    client, _ = _client({"tier": _choice("routine_audit", 0.9)})
    with pytest.raises(JevError, match="non-routable tier"):
        route_packet(client, "o", [], "c")


# ---------------------------------------------------------------------------
# Autonomy gate treats score levels as ordinal — the audit's F6
# ---------------------------------------------------------------------------


def test_top_level_score_merges():
    client, _ = _client({"merge_readiness": _score(2.0, 0.9), "anomaly": _noul(0.1)})
    verdict, _ = autonomy_gate(client, "candidate", "PASS", "P-1")
    assert verdict == "merge"


def test_middle_level_score_does_not_merge():
    """`> 1.5` used to read a midpoint off a weakly calibrated ordinal scale."""
    client, _ = _client({"merge_readiness": _score(1.6, 0.9), "anomaly": _noul(0.1)})
    verdict, _ = autonomy_gate(client, "candidate", "PASS", "P-1")
    assert verdict == "flag_for_review"


def test_anomaly_forces_a_human_gate():
    client, _ = _client({"merge_readiness": _score(2.0, 0.99), "anomaly": _noul(0.8)})
    verdict, _ = autonomy_gate(client, "candidate", "PASS", "P-1")
    assert verdict == "human_gate"


def test_low_confidence_forces_a_human_gate():
    client, _ = _client({"merge_readiness": _score(2.0, 0.3), "anomaly": _noul(0.0)})
    verdict, _ = autonomy_gate(client, "candidate", "PASS", "P-1")
    assert verdict == "human_gate"


# ---------------------------------------------------------------------------
# Remaining decision functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("p", "expected"), [(0.9, True), (0.5, False)])
def test_materially_different_strategy(p, expected):
    client, _ = _client({"materially_different": _noul(p)})
    result, _ = is_materially_different_strategy(client, "prior", "new", "P-1")
    assert result is expected


@pytest.mark.parametrize(("p", "expected"), [(0.8, True), (0.6, False)])
def test_needs_owner(p, expected):
    client, _ = _client({"owner_required": _noul(p)})
    result, _ = needs_owner(client, "blocker", "P-1")
    assert result is expected


def test_relevant_failures_selects_by_index():
    client, _ = _client({"rel_0": _noul(0.9), "rel_1": _noul(0.2), "rel_2": _noul(0.7)})
    hits, _ = relevant_failures(client, "task", ["a", "b", "c"])
    assert hits == [0, 2]


def test_relevant_failures_short_circuits_on_empty_history():
    client, sdk = _client({})
    hits, receipt = relevant_failures(client, "task", [])
    assert hits == []
    assert sdk.calls == []  # no call, no spend
    assert receipt.model_reported == "none"
