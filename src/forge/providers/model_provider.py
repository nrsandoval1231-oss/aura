"""
Type-safe model provider layer for the Forge/APEX merged runtime.

Design rules (from the architecture):
- Agents request CAPABILITIES, not model names. (Forge S50)
- Every response is schema-validated. Invalid output is a runtime error,
  never something downstream guesses at. (Forge S52, S99)
- Model names live in config/env, never in code. The coding crown changes
  hands every few weeks; routing must survive that.
- Every call emits a receipt: who called, which capability, which model,
  tokens, latency, verdict-relevant metadata. (Forge S7, S18)

Two rules here came out of the 2026-09-21 audit (DEC-008):

1. **Each family brings its own adapter.** Anthropic is not OpenAI-compatible —
   it serves `/v1/messages`, authenticates with `x-api-key`, and takes
   `output_config.format` rather than `response_format`. Modelling it as a row in
   an OpenAI-shaped registry produced four simultaneous defects on the single
   most important route. Adding a provider means a `ProviderSpec` plus, if its
   wire format differs, an `Adapter`.
2. **No in-code default model ids.** They decay silently. A missing model
   environment variable fails closed.

Audit independence is enforced by passing the provider through the call, never by
mutating module state: the planned parallel scheduler would otherwise let
concurrent audits swap each other's routing out from under them.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from forge.providers.capability import Capability

__all__ = [
    "PROVIDERS",
    "ROUTING",
    "AuditVerdict",
    "BuildPlan",
    "CallReceipt",
    "Capability",
    "ModelProvider",
    "ProviderError",
    "ProviderSpec",
    "SchemaInvalidError",
]


class ProviderSpec(BaseModel):
    base_url: str
    api_key_env: str
    #: The model this provider serves when it is pulled in as a cross-family
    #: auditor for a capability it does not primarily route. Separate from the
    #: capability's own model env because a model id is only valid for one
    #: provider: `independent_auditor` can hand any capability to any family, and
    #: the capability's primary id would be meaningless there.
    model_env: str
    family: str  # used to enforce cross-family audit independence
    wire: str  # which Adapter speaks to it


PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec(
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_AUDIT_MODEL",
        family="anthropic",
        wire="anthropic",
    ),
    "openai": ProviderSpec(
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_AUDIT_MODEL",
        family="openai",
        wire="openai",
    ),
    "google": ProviderSpec(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        model_env="GEMINI_AUDIT_MODEL",
        family="google",
        wire="openai",
    ),
    "kimi": ProviderSpec(
        base_url="https://api.moonshot.ai/v1",
        api_key_env="KIMI_API_KEY",
        model_env="KIMI_AUDIT_MODEL",
        family="moonshot",
        wire="openai",
    ),
    "deepseek": ProviderSpec(
        base_url="https://api.deepseek.com/v1",  # OpenAI-compatible
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_AUDIT_MODEL",
        family="deepseek",
        wire="deepseek",
    ),
}

# Capability -> provider. This is the entire routing table; everything else is code.
# Economics: cheap builder + strong independent auditor. Builder output is an
# untrusted candidate by doctrine (Forge S97), so we buy cheap generation and
# spend the savings on verification.
ROUTING: dict[Capability, str] = {
    Capability.HIGH_REASONING: "anthropic",
    Capability.CODING: "deepseek",
    Capability.ROUTINE_AUDIT: "kimi",
    Capability.FAST: "google",
    Capability.EXEC_DEBUG: "kimi",
}

#: Capability -> the environment variable naming its model.
#:
#: Keyed on the capability, not the provider, because two capabilities may route
#: to the same provider and must still be able to use different models. Audit F11
#: found the previous provider-keyed arrangement collapsing ROUTINE_AUDIT and
#: EXEC_DEBUG onto `EXEC_MODEL` — both route to `kimi` — which left `AUDITOR_MODEL`
#: unreachable by any capability while `.env.example` documented it as the
#: per-packet review seat. A cheap-review setting that nothing reads is worse than
#: no setting, because it reads as configured.
CAPABILITY_MODEL_ENV: dict[Capability, str] = {
    Capability.HIGH_REASONING: "ARCHITECT_MODEL",
    Capability.CODING: "BUILDER_MODEL",
    Capability.ROUTINE_AUDIT: "AUDITOR_MODEL",
    Capability.FAST: "FAST_MODEL",
    Capability.EXEC_DEBUG: "EXEC_MODEL",
}


def model_env_for(capability: Capability, provider_name: str) -> str:
    """Name the environment variable holding the model id for this exact route.

    On the capability's primary provider that is the capability's own variable. On
    any other provider — which only happens when `independent_auditor` routes an
    audit away from the family that produced the candidate — it is that provider's
    audit model, because the primary id names a model the other family does not
    serve. Returning a name rather than a value keeps the "no in-code default"
    rule intact: resolution still fails closed on the missing variable, and the
    error can say which one it wanted.
    """
    if ROUTING.get(capability) == provider_name:
        return CAPABILITY_MODEL_ENV[capability]
    return PROVIDERS[provider_name].model_env


class CallReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"CALL-{uuid.uuid4().hex[:8]}")
    capability: Capability
    provider: str
    model: str
    #: Which variable the model id came from. Recorded because a cross-family
    #: audit reroute changes it, and F11 found that escalation happening with
    #: nothing in the evidence to show it had.
    model_env: str
    family: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    schema_valid: bool
    caller_role: str  # architect | builder | auditor | ...
    packet_id: str | None = None


T = TypeVar("T", bound=BaseModel)


class SchemaInvalidError(RuntimeError):
    """Model output failed validation. Fail closed; never parse loosely."""


class ProviderError(RuntimeError):
    pass


class Adapter(Protocol):
    """Translates one request into a provider's wire format and back.

    `parse` returns (content, input_tokens, output_tokens).
    """

    def request(
        self,
        spec: ProviderSpec,
        model: str,
        api_key: str,
        schema: type[BaseModel],
        system: str,
        prompt: str,
    ) -> tuple[str, dict[str, str], dict[str, object]]: ...

    def parse(self, body: dict) -> tuple[str, int | None, int | None]: ...


class OpenAIAdapter:
    """`/chat/completions` with JSON-schema structured outputs.

    Used by OpenAI itself and by providers that deliberately mirror its shape
    (Moonshot and Gemini's compatibility endpoint).
    """

    def request(self, spec, model, api_key, schema, system, prompt):
        return (
            f"{spec.base_url}/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": schema.model_json_schema(),
                        "strict": True,
                    },
                },
            },
        )

    def parse(self, body):
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected OpenAI-shaped response: {str(body)[:500]}") from exc
        usage = body.get("usage") or {}
        return content, usage.get("prompt_tokens"), usage.get("completion_tokens")


class DeepSeekAdapter(OpenAIAdapter):
    """DeepSeek Chat Completions JSON Output adapter."""

    MAX_TOKENS = 4096

    def request(self, spec, model, api_key, schema, system, prompt):
        schema_text = json.dumps(schema.model_json_schema(), sort_keys=True)
        schema_instruction = (
            "Return only valid JSON matching this JSON Schema. Do not include "
            f"markdown fences or explanatory text.\n{schema_text}"
        )
        return (
            f"{spec.base_url}/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": f"{system}\n\n{schema_instruction}"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": self.MAX_TOKENS,
                "response_format": {"type": "json_object"},
            },
        )

    def parse(self, body):
        try:
            choice = body["choices"][0]
            finish_reason = choice["finish_reason"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected DeepSeek response: {str(body)[:500]}") from exc
        if finish_reason != "stop":
            raise ProviderError(
                f"DeepSeek completion did not stop cleanly: finish_reason={finish_reason!r}"
            )
        try:
            content = choice["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError(f"Unexpected DeepSeek response: {str(body)[:500]}") from exc
        usage = body.get("usage") or {}
        return content, usage.get("prompt_tokens"), usage.get("completion_tokens")


class AnthropicAdapter:
    """`/v1/messages` with `output_config.format`.

    Anthropic is not OpenAI-compatible. Different path, different auth header, a
    required version header, `system` as a top-level field rather than a message,
    and structured output configured through `output_config`, not `response_format`.
    """

    API_VERSION = "2023-06-01"
    MAX_TOKENS = 16000

    def request(self, spec, model, api_key, schema, system, prompt):
        return (
            f"{spec.base_url}/messages",
            {
                "x-api-key": api_key,
                "anthropic-version": self.API_VERSION,
                "content-type": "application/json",
            },
            {
                "model": model,
                "max_tokens": self.MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "name": schema.__name__,
                        "schema": schema.model_json_schema(),
                    }
                },
            },
        )

    def parse(self, body):
        # A refusal is a real outcome, not a transport failure — surface it as one
        # rather than letting schema validation report it as malformed output.
        if body.get("stop_reason") == "refusal":
            details = body.get("stop_details") or {}
            raise ProviderError(f"Anthropic declined the request: {details.get('category')}")
        try:
            content = next(
                block["text"] for block in body["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError, StopIteration) as exc:
            raise ProviderError(f"Unexpected Anthropic response: {str(body)[:500]}") from exc
        usage = body.get("usage") or {}
        return content, usage.get("input_tokens"), usage.get("output_tokens")


ADAPTERS: dict[str, Adapter] = {
    "openai": OpenAIAdapter(),
    "anthropic": AnthropicAdapter(),
    "deepseek": DeepSeekAdapter(),
}


class ModelProvider:
    def __init__(self, timeout_s: float = 120.0, *, client: httpx.Client | None = None):
        self._timeout = timeout_s
        self._client = client  # injectable so tests never touch the network
        self.receipts: list[CallReceipt] = []  # in-memory; Forge persists to ledger

    def _resolve(
        self, provider_name: str, capability: Capability
    ) -> tuple[ProviderSpec, str, str, str]:
        try:
            spec = PROVIDERS[provider_name]
        except KeyError as exc:
            raise ProviderError(f"Unknown provider '{provider_name}'") from exc
        api_key = os.environ.get(spec.api_key_env)
        if not api_key:
            raise ProviderError(
                f"Missing {spec.api_key_env}. Put it in .env — never in code or chat."
            )
        model_env = model_env_for(capability, provider_name)
        model = os.environ.get(model_env)
        if not model:
            # No in-code fallback: a stale hardcoded id is worse than a clear stop.
            raise ProviderError(f"Missing {model_env}. Model ids are configuration, not code.")
        return spec, model, api_key, model_env

    def call(
        self,
        capability: Capability,
        schema: type[T],
        system: str,
        prompt: str,
        *,
        caller_role: str,
        packet_id: str | None = None,
        provider_override: str | None = None,
    ) -> tuple[T, CallReceipt]:
        """Structured, type-safe call. Returns (validated_object, receipt).

        `provider_override` exists so audit independence can be enforced per call
        instead of by mutating the shared routing table.
        """
        provider_name = provider_override or ROUTING[capability]
        spec, model, api_key, model_env = self._resolve(provider_name, capability)
        adapter = ADAPTERS[spec.wire]
        url, headers, payload = adapter.request(spec, model, api_key, schema, system, prompt)

        started = time.monotonic()
        try:
            if self._client is not None:
                resp = self._client.post(url, headers=headers, json=payload, timeout=self._timeout)
            else:
                resp = httpx.post(url, headers=headers, json=payload, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ProviderError(f"{provider_name} transport error: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if resp.status_code != 200:
            raise ProviderError(f"{provider_name} HTTP {resp.status_code}: {resp.text[:500]}")

        content, input_tokens, output_tokens = adapter.parse(resp.json())

        # Type safety is enforced HERE, at the boundary. No try/except-pass
        # anywhere downstream is allowed to rescue malformed output.
        schema_valid = False
        try:
            result = schema.model_validate_json(content)
            schema_valid = True
        except ValidationError as exc:
            raise SchemaInvalidError(
                f"{model} returned schema-invalid output for {schema.__name__}: {exc}"
            ) from exc
        finally:
            receipt = CallReceipt(
                capability=capability,
                provider=provider_name,
                model=model,
                model_env=model_env,
                family=spec.family,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                schema_valid=schema_valid,
                caller_role=caller_role,
                packet_id=packet_id,
            )
            self.receipts.append(receipt)

        return result, receipt

    def audit_call(
        self,
        schema: type[T],
        system: str,
        prompt: str,
        *,
        produced_by_family: str,
        final_gate: bool = False,
        packet_id: str | None = None,
    ) -> tuple[T, CallReceipt]:
        """Audit calls enforce cross-family independence.

        final_gate=True upgrades to the strongest reasoning model.
        """
        cap = Capability.HIGH_REASONING if final_gate else Capability.ROUTINE_AUDIT
        provider_name = independent_auditor(cap, produced_by_family)
        return self.call(
            cap,
            schema,
            system,
            prompt,
            caller_role="auditor",
            packet_id=packet_id,
            provider_override=provider_name,
        )


def independent_auditor(capability: Capability, produced_by_family: str) -> str:
    """Pick an auditing provider from a different family than the candidate's.

    Independence is architectural, not prompt-based (Forge S28, S51-amended), so
    this is a pure function of the routing table — safe to call concurrently.
    """
    preferred = ROUTING[capability]
    if PROVIDERS[preferred].family != produced_by_family:
        return preferred
    # Sorted, not insertion-ordered. F11 found the previous `next(...)` over
    # `PROVIDERS.items()` returning whichever provider happened to be declared
    # first, which made the audit seat depend on the literal order of a dict
    # literal — reordering the registry for readability would have silently moved
    # every fallback audit to a different family and price.
    fallback = next(
        (
            name
            for name in sorted(PROVIDERS)
            if PROVIDERS[name].family != produced_by_family and name != preferred
        ),
        None,
    )
    if fallback is None:
        # Fail closed: an audit by the family that wrote the candidate is not an
        # audit, and silently proceeding would forfeit the guarantee.
        raise ProviderError(
            f"No provider outside family '{produced_by_family}' is available to audit"
        )
    return fallback


# ---------------------------------------------------------------------------
# Example contracts — the shape agents must return. (Forge S52)
# ---------------------------------------------------------------------------


class BuildPlan(BaseModel):
    objective: str
    steps: list[str]
    files_to_touch: list[str]
    acceptance_criteria: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class AuditVerdict(BaseModel):
    verdict: str = Field(pattern=r"^(PASS|FAIL|UNKNOWN)$")  # UNKNOWN is real
    findings: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
