"""Provider layer tests.

Every test here runs against an injected transport. No test in this repository
may make a live model call: the packet forbids it, and an audit gate that depends
on a third party being up is not a gate.

The cases below are written against the defects the 2026-09-21 audit found, so a
regression reintroduces a failing test rather than a silent 404 in production.
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from forge.providers import (
    PROVIDERS,
    ROUTING,
    BuildPlan,
    Capability,
    ModelProvider,
    ProviderError,
    SchemaInvalidError,
    independent_auditor,
)


class Echo(BaseModel):
    value: str


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    """Give every provider a key and a model so tests exercise transport, not config."""
    from forge.providers.model_provider import CAPABILITY_MODEL_ENV

    for spec in PROVIDERS.values():
        monkeypatch.setenv(spec.api_key_env, "test-key")
        # The provider's cross-family audit fallback model.
        monkeypatch.setenv(spec.model_env, f"audit-model-for-{spec.family}")
    # Primary routes read the capability's own variable, not the provider's (F11).
    for capability, model_env in CAPABILITY_MODEL_ENV.items():
        monkeypatch.setenv(model_env, f"test-model-for-{capability.value}")


def _transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _openai_body(payload: dict) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7},
    }


def _anthropic_body(payload: dict) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "usage": {"input_tokens": 11, "output_tokens": 7},
        "stop_reason": "end_turn",
    }


def test_anthropic_uses_the_messages_endpoint_and_key_header():
    """Regression for the audit's F3: Anthropic is not OpenAI-compatible."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_anthropic_body({"value": "ok"}))

    provider = ModelProvider(client=_transport(handler))
    result, receipt = provider.call(
        Capability.HIGH_REASONING, Echo, "sys", "prompt", caller_role="architect"
    )

    assert result.value == "ok"
    assert seen["url"].endswith("/v1/messages")
    assert "/chat/completions" not in seen["url"]
    assert seen["headers"]["x-api-key"] == "test-key"
    assert "authorization" not in seen["headers"]
    assert seen["headers"]["anthropic-version"]
    # Structured output is output_config.format, not response_format.
    assert "output_config" in seen["body"]
    assert "response_format" not in seen["body"]
    # system is a top-level field, not a message.
    assert seen["body"]["system"] == "sys"
    assert [m["role"] for m in seen["body"]["messages"]] == ["user"]
    assert receipt.family == "anthropic"
    assert receipt.input_tokens == 11


def test_deepseek_uses_json_output_and_schema_instruction():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_body({"value": "built"}))

    provider = ModelProvider(client=_transport(handler))
    result, receipt = provider.call(
        Capability.CODING, Echo, "sys", "prompt", caller_role="builder", packet_id="P-1"
    )

    assert result.value == "built"
    assert seen["url"].endswith("/chat/completions")
    assert seen["headers"]["authorization"] == "Bearer test-key"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["max_tokens"] == 4096
    assert (
        "Return only valid JSON matching this JSON Schema" in seen["body"]["messages"][0]["content"]
    )
    assert '"properties"' in seen["body"]["messages"][0]["content"]
    assert receipt.packet_id == "P-1"
    assert receipt.family == "deepseek"


def test_openai_keeps_json_schema_structured_output():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_openai_body({"value": "built"}))

    provider = ModelProvider(client=_transport(handler))
    result, receipt = provider.call(
        Capability.CODING,
        Echo,
        "sys",
        "prompt",
        caller_role="builder",
        provider_override="openai",
    )

    assert result.value == "built"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert "max_tokens" not in seen["body"]
    assert receipt.family == "openai"


def test_deepseek_length_finish_fails_closed_before_schema_acceptance():
    """A truncated JSON document must not pass merely because it validates."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps({"value": "complete"})},
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 4096},
            },
        )

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(ProviderError, match="finish_reason='length'"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


def test_missing_model_env_fails_closed(monkeypatch):
    """Regression for the audit's F3: no in-code default model ids."""
    from forge.providers.model_provider import CAPABILITY_MODEL_ENV

    monkeypatch.delenv(CAPABILITY_MODEL_ENV[Capability.CODING])
    provider = ModelProvider(client=_transport(lambda r: httpx.Response(200, json={})))

    with pytest.raises(ProviderError, match="Model ids are configuration"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


def test_missing_api_key_fails_closed(monkeypatch):
    monkeypatch.delenv(PROVIDERS["deepseek"].api_key_env)
    provider = ModelProvider(client=_transport(lambda r: httpx.Response(200, json={})))

    with pytest.raises(ProviderError, match="Missing DEEPSEEK_API_KEY"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


def test_schema_invalid_output_raises_and_still_records_a_receipt():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_body({"wrong_field": 1}))

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(SchemaInvalidError):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")

    # The failed call is still evidence (Forge S7/S18).
    assert len(provider.receipts) == 1
    assert provider.receipts[0].schema_valid is False


def test_non_200_is_a_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="no such model")

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(ProviderError, match="HTTP 404"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


def test_transport_failure_is_a_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(ProviderError, match="transport error"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


def test_anthropic_refusal_is_reported_as_a_refusal():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"stop_reason": "refusal", "stop_details": {"category": "cyber"}}
        )

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(ProviderError, match="declined"):
        provider.call(Capability.HIGH_REASONING, Echo, "s", "p", caller_role="architect")


def test_malformed_provider_response_fails_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    provider = ModelProvider(client=_transport(handler))
    with pytest.raises(ProviderError, match="Unexpected"):
        provider.call(Capability.CODING, Echo, "s", "p", caller_role="builder")


# ---------------------------------------------------------------------------
# Audit independence — the audit's F4
# ---------------------------------------------------------------------------


def test_auditor_avoids_the_family_that_produced_the_candidate():
    routine_family = PROVIDERS[ROUTING[Capability.ROUTINE_AUDIT]].family
    chosen = independent_auditor(Capability.ROUTINE_AUDIT, routine_family)
    assert PROVIDERS[chosen].family != routine_family


def test_auditor_keeps_the_routed_provider_when_families_already_differ():
    chosen = independent_auditor(Capability.ROUTINE_AUDIT, "a-family-nobody-has")
    assert chosen == ROUTING[Capability.ROUTINE_AUDIT]


def test_independent_auditor_does_not_mutate_the_routing_table():
    """Regression for F4: independence must not be implemented by global mutation.

    The planned parallel scheduler would otherwise let concurrent audits swap
    each other's routing out from under them.
    """
    before = dict(ROUTING)
    for family in {spec.family for spec in PROVIDERS.values()}:
        independent_auditor(Capability.ROUTINE_AUDIT, family)
        independent_auditor(Capability.HIGH_REASONING, family)
    assert ROUTING == before


def test_concurrent_audits_each_get_an_independent_family():
    """Two audits of differently-sourced candidates must not cross-contaminate."""
    import concurrent.futures

    families = [spec.family for spec in PROVIDERS.values()] * 8
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        chosen = list(
            pool.map(lambda f: independent_auditor(Capability.ROUTINE_AUDIT, f), families)
        )

    for family, provider_name in zip(families, chosen, strict=True):
        assert PROVIDERS[provider_name].family != family
    assert ROUTING[Capability.ROUTINE_AUDIT] == "kimi"


def test_audit_call_routes_away_from_the_producing_family():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        # The auditor may land on any family, so answer in that family's shape.
        payload = {"value": "audited"}
        body = (
            _anthropic_body(payload)
            if request.url.path.endswith("/messages")
            else _openai_body(payload)
        )
        return httpx.Response(200, json=body)

    provider = ModelProvider(client=_transport(handler))
    producing = PROVIDERS[ROUTING[Capability.ROUTINE_AUDIT]].family
    _, receipt = provider.audit_call(
        Echo, "sys", "prompt", produced_by_family=producing, packet_id="P-2"
    )

    assert receipt.family != producing
    assert receipt.caller_role == "auditor"


def test_no_independent_family_fails_closed(monkeypatch):
    """An audit by the family that wrote the candidate is not an audit."""
    only = {"kimi": PROVIDERS["kimi"]}
    monkeypatch.setattr("forge.providers.model_provider.PROVIDERS", only)
    with pytest.raises(ProviderError, match="No provider outside family"):
        independent_auditor(Capability.ROUTINE_AUDIT, "moonshot")


def test_build_plan_contract_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        BuildPlan(
            objective="o",
            steps=[],
            files_to_touch=[],
            acceptance_criteria=[],
            confidence=1.5,
        )


# ---------------------------------------------------------------------------
# F11: model ids were keyed on the provider, so two capabilities sharing a
# provider collapsed onto one model and AUDITOR_MODEL was unreachable.
# ---------------------------------------------------------------------------


def test_capabilities_sharing_a_provider_read_different_models():
    """ROUTINE_AUDIT and EXEC_DEBUG both route to Moonshot and must stay distinct."""
    from forge.providers.model_provider import ROUTING, model_env_for

    assert ROUTING[Capability.ROUTINE_AUDIT] == ROUTING[Capability.EXEC_DEBUG]
    routine = model_env_for(Capability.ROUTINE_AUDIT, ROUTING[Capability.ROUTINE_AUDIT])
    exec_debug = model_env_for(Capability.EXEC_DEBUG, ROUTING[Capability.EXEC_DEBUG])
    assert routine == "AUDITOR_MODEL"
    assert exec_debug == "EXEC_MODEL"
    assert routine != exec_debug


def test_every_capability_model_variable_is_reachable():
    """A documented seat that no route reads is worse than no seat at all."""
    from forge.providers.model_provider import CAPABILITY_MODEL_ENV, ROUTING, model_env_for

    reachable = {model_env_for(capability, ROUTING[capability]) for capability in ROUTING}
    assert reachable == set(CAPABILITY_MODEL_ENV.values())


def test_routine_audit_reroute_does_not_borrow_the_architect_model():
    """The F11 escalation: a cheap review silently running on the final-gate model."""
    from forge.providers.model_provider import CAPABILITY_MODEL_ENV, model_env_for

    rerouted = independent_auditor(Capability.ROUTINE_AUDIT, "moonshot")
    assert PROVIDERS[rerouted].family != "moonshot"
    resolved = model_env_for(Capability.ROUTINE_AUDIT, rerouted)
    assert resolved != CAPABILITY_MODEL_ENV[Capability.HIGH_REASONING]
    assert resolved == PROVIDERS[rerouted].model_env


def test_receipt_records_which_variable_supplied_the_model():
    """Escalation has to be visible in evidence, not just in behaviour."""
    provider = ModelProvider(
        client=_transport(lambda request: httpx.Response(200, json=_openai_body({"value": "ok"})))
    )
    _, receipt = provider.call(Capability.CODING, Echo, "sys", "prompt", caller_role="builder")
    assert receipt.model_env == "BUILDER_MODEL"
    assert receipt.model == "test-model-for-coding"


def test_fallback_auditor_choice_does_not_depend_on_dict_order(monkeypatch):
    """F11: the seat was decided by the literal order of the PROVIDERS dict."""
    import forge.providers.model_provider as mp

    baseline = independent_auditor(Capability.ROUTINE_AUDIT, "moonshot")
    reordered = {name: mp.PROVIDERS[name] for name in reversed(list(mp.PROVIDERS))}
    monkeypatch.setattr(mp, "PROVIDERS", reordered)
    assert mp.independent_auditor(Capability.ROUTINE_AUDIT, "moonshot") == baseline
