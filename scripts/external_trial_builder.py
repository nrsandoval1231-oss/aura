"""Run the single bounded Hallam external-trial Builder request.

The runner is proposal-only: it may inspect Hallam and call the configured
Builder once, but it never edits or pushes the external repository.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError, model_validator

from forge import Ledger, LedgerStore
from forge.config import load_env
from forge.providers import CallReceipt, Capability, SchemaInvalidError
from forge.providers.model_provider import PROVIDERS, DeepSeekAdapter, ProviderError
from forge.trust_kernel import Receipt

PACKET_ID = "FORGE-EXT-001"
MODEL = "deepseek-flash"
MAX_SPEND_USD = 15.0
MAX_REQUEST_BYTES = 14_000
MAX_OUTPUT_TOKENS = 4_096
INPUT_RATE_USD_PER_MILLION = 10.0
OUTPUT_RATE_USD_PER_MILLION = 20.0
FORGE_ORIGIN = "https://github.com/nrsandoval1231-oss/forge-agent.git"
HALLAM_ORIGIN = "https://github.com/nrsandoval1231-oss/hallam.git"
HALLAM_BRANCH = "codex/forge-external-trial"
HALLAM_PATHS = ("apps/api/sabra_api/main.py", "tests/test_api.py")
THINKING = {"type": "disabled"}
MAX_DIAGNOSTIC_ID_LENGTH = 200
MAX_USAGE_TOKENS = 1_000_000_000
ALLOWED_FINISH_REASONS = frozenset({"stop", "length", "content_filter", "tool_calls"})
REFUSAL_REASON_CODES = frozenset(
    {
        "HTTP_STATUS_REFUSED",
        "SCHEMA_INVALID",
        "PROVIDER_USAGE_INVALID",
        "PROVIDER_ERROR",
        "SENSITIVE_OUTPUT_REFUSED",
        "SCOPE_CONTEXT_INVALID",
        "SCOPE_PATH_INVALID",
        "SCOPE_CROSS_PATH_REWRITE",
        "HUNK_NOT_UNIQUE",
        "INVALID_RECONSTRUCTED_SOURCE",
        "API_FILTER_INVARIANT_REMOVED",
        "API_FILTER_REQUIREMENT_MISSING",
        "TEST_INDUSTRY_REQUIREMENT_MISSING",
    }
)

SYSTEM_PROMPT = (
    "Return only a bounded Hallam Industry-filter proposal as structured JSON. "
    "The proposal is never applied by this runner."
)
PROMPT = """Hallam's Opportunities page has an Industry input and the API returns an
industry field, but the browser filter currently searches only company and title.
Propose the smallest safe repair. Your proposal may change only:
1. apps/api/sabra_api/main.py
2. tests/test_api.py
The repair must preserve existing behavior and add tests proving both an
industry-only positive match and an unrelated-industry negative non-match.
Return only structured JSON.
"""


class HallamEdit(BaseModel):
    path: Literal["apps/api/sabra_api/main.py", "tests/test_api.py"]
    old: str = Field(min_length=1, max_length=3_000)
    new: str = Field(min_length=1, max_length=3_000)


class HallamProposal(BaseModel):
    edits: list[HallamEdit] = Field(min_length=2, max_length=2)
    rationale: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def exact_paths(self) -> HallamProposal:
        paths = [edit.path for edit in self.edits]
        if sorted(paths) != sorted(HALLAM_PATHS):
            raise ValueError("proposal must contain exactly the two allowed Hallam paths")
        if len(set(paths)) != 2:
            raise ValueError("proposal must contain one edit for each allowed Hallam path")
        return self


class RefusalError(ValueError):
    """A safe, allowlisted refusal that carries no untrusted detail."""

    def __init__(self, reason_code: str, message: str):
        if reason_code not in REFUSAL_REASON_CODES:
            raise ValueError("unknown refusal reason code")
        super().__init__(message)
        self.reason_code = reason_code


class SensitiveProposalError(RefusalError):
    """Raised without exposing secret-bearing provider output."""

    def __init__(self):
        super().__init__("SENSITIVE_OUTPUT_REFUSED", "configured secret detected")


class InvalidProviderUsageError(RefusalError):
    """Raised when untrusted provider token counts cannot enter evidence."""

    def __init__(self):
        super().__init__("PROVIDER_USAGE_INVALID", "provider token counts are invalid")


class ScopeRefusal(RefusalError):
    """Raised when a schema-valid proposal violates a bounded scope rule."""


@dataclass(frozen=True)
class RunResult:
    status: Literal["SUCCEEDED", "REFUSED", "UNKNOWN"]
    proposal: HallamProposal | None
    receipt: CallReceipt | None
    error_type: str | None = None


def _digest(value: object) -> str:
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _require_clean(root: Path, expected_sha: str, label: str, expected_origin: str) -> None:
    try:
        head = _git(root, "rev-parse", "HEAD")
        status = _git(root, "status", "--porcelain", "--untracked-files=all")
        origin = _git(root, "remote", "get-url", "origin")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Preflight refused: {label} identity could not be verified") from exc
    if head != expected_sha:
        raise RuntimeError(f"Preflight refused: {label} HEAD does not match expected SHA")
    if status:
        raise RuntimeError(f"Preflight refused: {label} worktree is not clean")
    normalized_origin = origin.rstrip("/").removesuffix(".git")
    normalized_expected = expected_origin.rstrip("/").removesuffix(".git")
    if normalized_origin != normalized_expected:
        raise RuntimeError(f"Preflight refused: {label} origin does not match expected repository")


def _request_payload(prompt: str) -> dict:
    _, _, payload = DeepSeekAdapter().request(
        PROVIDERS["deepseek"], MODEL, "redacted", HallamProposal, SYSTEM_PROMPT, prompt
    )
    payload["thinking"] = THINKING.copy()
    return payload


def _request_prompt(target_root: Path, prompt: str) -> str:
    parts = [prompt]
    for relative in HALLAM_PATHS:
        path = target_root / relative
        if not path.is_file():
            raise RuntimeError(f"Preflight refused: required Hallam file is missing: {relative}")
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            raise RuntimeError(f"Preflight refused: Hallam source is invalid: {relative}") from exc
        if relative.endswith("main.py"):
            lowered = text.casefold()
            marker = next((item for item in ("!ind||", "o.company") if item in lowered), None)
            if marker is None:
                raise RuntimeError(
                    "Preflight refused: Hallam Industry filter defect marker is absent"
                )
            marker_index = lowered.index(marker)
            context = text[max(0, marker_index - 2_000) : min(len(text), marker_index + 4_000)]
            if "o.company" not in context.casefold() or "o.industry" in context.casefold():
                raise RuntimeError(
                    "Preflight refused: bounded Hallam context does not expose the unfiltered Industry defect"
                )
            parts.append(f"\n--- {relative} ---\n{context}")
        else:
            candidates = []
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                segment = ast.get_source_segment(text, node) or ""
                marker = segment.casefold()
                if "industry" in marker or "opportunit" in marker or "filter" in marker:
                    candidates.append(segment)
            parts.append(f"\n--- {relative} ---\n" + "\n\n".join(candidates)[:4_000])
    result = "".join(parts)
    if len(result) > 10_000:
        raise RuntimeError("Preflight refused: target context exceeds character bound")
    return result


def preflight(
    forge_root: Path,
    target_root: Path,
    *,
    forge_sha: str,
    target_sha: str,
    env: dict[str, str] | None = None,
    prompt: str,
) -> tuple[float, int, str]:
    _require_clean(forge_root, forge_sha, "Forge", FORGE_ORIGIN)
    _require_clean(target_root, target_sha, "Hallam", HALLAM_ORIGIN)
    values = os.environ if env is None else env
    if not values.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("Preflight refused: DEEPSEEK_API_KEY is missing")
    env_file = forge_root / ".env"
    if (
        env_file.is_file()
        and subprocess.run(
            ["git", "check-ignore", "--quiet", "--", ".env"], cwd=forge_root
        ).returncode
        != 0
    ):
        raise RuntimeError("Preflight refused: credential file is not git-ignored")
    if values.get("BUILDER_MODEL") != MODEL:
        raise RuntimeError(f"Preflight refused: BUILDER_MODEL must be {MODEL!r}")
    payload = _request_payload(prompt)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request_bytes = len(serialized)
    if request_bytes > MAX_REQUEST_BYTES:
        raise RuntimeError("Preflight refused: serialized request exceeds byte bound")
    estimate = (
        (MAX_REQUEST_BYTES + 1024) * INPUT_RATE_USD_PER_MILLION
        + MAX_OUTPUT_TOKENS * OUTPUT_RATE_USD_PER_MILLION
    ) / 1_000_000
    if estimate > MAX_SPEND_USD:
        raise RuntimeError("Preflight refused: conservative request estimate exceeds grant")
    return estimate, request_bytes, _digest(payload)


def _claim(store: LedgerStore, forge_sha: str, target_sha: str) -> str:
    request_id = f"REQ-{uuid.uuid4().hex}"
    path = store.receipts_path.with_suffix(".claim.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "forge_sha": forge_sha,
            "target_sha": target_sha,
            "status": "CLAIMED",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Refusing second run: claim for '{PACKET_ID}' already exists") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    return request_id


def _append(store: LedgerStore, event: str, before: str, after: str, payload: dict) -> None:
    ledger = store.load() if store.exists else Ledger(stream_id=store.stream_id)
    receipt = Receipt.create(
        len(ledger.receipts) + 1,
        event,
        before,
        after,
        payload,
        ledger.receipts[-1].receipt_hash if ledger.receipts else None,
    )
    ledger.append(receipt)
    store.write(ledger)


def _configured_secrets() -> tuple[str, ...]:
    """Return configured secret values solely to reject them from diagnostics."""
    provider_key = os.environ.get(PROVIDERS["deepseek"].api_key_env)
    generic_secrets = (
        value
        for name, value in os.environ.items()
        if len(value) >= 8
        and any(marker in name.upper() for marker in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
    )
    return tuple(dict.fromkeys(value for value in (provider_key, *generic_secrets) if value))


def _safe_response_id(value: object, secrets: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or not value or len(value) > MAX_DIAGNOSTIC_ID_LENGTH:
        return None
    if any(secret in value for secret in secrets):
        return None
    if not all(
        character.isascii() and (character.isalnum() or character in "._:-") for character in value
    ):
        return None
    return value


def _safe_usage(value: object) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    usage = {
        key: tokens
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance((tokens := value.get(key)), int)
        and not isinstance(tokens, bool)
        and 0 <= tokens <= MAX_USAGE_TOKENS
    }
    return usage or None


def _valid_token_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_USAGE_TOKENS


def _contains_configured_secret(value: object, secrets: tuple[str, ...]) -> bool:
    if isinstance(value, str):
        if any(secret in value for secret in secrets):
            return True
        decoded = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(int(match.group(1), 16)),
            value,
        )
        if decoded != value and any(secret in decoded for secret in secrets):
            return True
        try:
            nested = json.loads(value)
        except (UnicodeDecodeError, ValueError, TypeError):
            nested = None
        if nested is not None and nested != value:
            return _contains_configured_secret(nested, secrets)
        return False
    if isinstance(value, dict):
        return any(
            _contains_configured_secret(key, secrets) or _contains_configured_secret(item, secrets)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_configured_secret(item, secrets) for item in value)
    return False


def _response_content(response: httpx.Response) -> bytes:
    try:
        content = response.content
    except (httpx.ResponseNotRead, RuntimeError) as exc:
        raise RuntimeError("provider response content could not be observed") from exc
    if not isinstance(content, bytes):
        raise RuntimeError("provider response content has an invalid type")
    return content


def _response_contains_secret(content: bytes, secrets: tuple[str, ...]) -> bool:
    if any(secret.encode("utf-8") in content for secret in secrets):
        return True
    try:
        parsed = json.loads(content)
    except (UnicodeDecodeError, ValueError, TypeError):
        return False
    return _contains_configured_secret(parsed, secrets)


def _validated_response_json(content: bytes) -> dict:
    try:
        parsed = json.loads(content)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise RefusalError("SCHEMA_INVALID", "provider response JSON is invalid") from exc
    if not isinstance(parsed, dict):
        raise RefusalError("SCHEMA_INVALID", "provider response object is invalid")
    usage = parsed.get("usage")
    if not isinstance(usage, dict):
        raise InvalidProviderUsageError()
    if not _valid_token_count(usage.get("prompt_tokens")) or not _valid_token_count(
        usage.get("completion_tokens")
    ):
        raise InvalidProviderUsageError()
    return parsed


def _proposal_metadata(proposal: HallamProposal) -> list[dict[str, int | str]]:
    """Return bounded hunk metadata without retaining proposal text or rationale."""
    return [
        {
            "path": edit.path,
            "old_length": len(edit.old),
            "old_sha256": _digest(edit.old),
            "new_length": len(edit.new),
            "new_sha256": _digest(edit.new),
        }
        for edit in proposal.edits
    ]


def _diagnostic(
    response: httpx.Response,
    *,
    latency_ms: int | None = None,
    response_content: bytes | None = None,
    include_response_digest: bool = True,
    suppress_response_fields: bool = False,
) -> dict:
    """Persist only a flat, allowlisted provider diagnostic schema."""
    if response_content is None:
        try:
            response_content = response.content
        except (httpx.ResponseNotRead, RuntimeError):
            response_content = None
    response_digest = (
        _digest(response_content)
        if include_response_digest and response_content is not None
        else None
    )
    status = response.status_code
    diagnostic: dict[str, int | str | None | dict[str, int]] = {
        "http_status": status if isinstance(status, int) and not isinstance(status, bool) else None,
        "response_digest": response_digest,
        "latency_ms": latency_ms
        if isinstance(latency_ms, int) and not isinstance(latency_ms, bool) and latency_ms >= 0
        else None,
    }
    if suppress_response_fields:
        return diagnostic
    try:
        parsed = json.loads(response_content) if response_content is not None else None
    except (UnicodeDecodeError, ValueError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        response_id = _safe_response_id(parsed.get("id"), _configured_secrets())
        if response_id is not None:
            diagnostic["provider_response_id"] = response_id
        choices = parsed.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = choices[0].get("finish_reason")
            if isinstance(finish_reason, str) and finish_reason in ALLOWED_FINISH_REASONS:
                diagnostic["finish_reason"] = finish_reason
        usage = _safe_usage(parsed.get("usage"))
        if usage is not None:
            diagnostic["usage"] = usage
    return diagnostic


def validate_scope(proposal: HallamProposal, sources: dict[str, str]) -> None:
    if set(sources) != set(HALLAM_PATHS):
        raise ScopeRefusal(
            "SCOPE_CONTEXT_INVALID", "proposal source context is outside Hallam scope"
        )
    for edit in proposal.edits:
        if edit.path not in HALLAM_PATHS:
            raise ScopeRefusal("SCOPE_PATH_INVALID", "proposal names a path outside Hallam scope")
        if (
            "apps/" in edit.old
            or "tests/" in edit.old
            or "apps/" in edit.new
            or "tests/" in edit.new
        ):
            raise ScopeRefusal(
                "SCOPE_CROSS_PATH_REWRITE", "replacement may not rewrite another path"
            )
        source = sources[edit.path]
        if source.count(edit.old) != 1:
            raise ScopeRefusal("HUNK_NOT_UNIQUE", "each hunk old value must occur exactly once")
        candidate = source.replace(edit.old, edit.new, 1)
        try:
            ast.parse(candidate)
        except SyntaxError as exc:
            raise ScopeRefusal(
                "INVALID_RECONSTRUCTED_SOURCE", "hunk produces an invalid complete Python file"
            ) from exc
        if edit.path.endswith("main.py"):
            current_lower = source.casefold()
            candidate_lower = candidate.casefold()
            for invariant in ("o.company", "o.title", "!ind||"):
                if invariant in current_lower and invariant not in candidate_lower:
                    raise ScopeRefusal(
                        "API_FILTER_INVARIANT_REMOVED", "API filter invariant removed"
                    )
            if "o.industry" not in candidate_lower or "||" not in candidate:
                raise ScopeRefusal(
                    "API_FILTER_REQUIREMENT_MISSING", "API Industry predicate requirement missing"
                )
        else:
            marker = edit.new.casefold()
            if "industry" not in marker:
                raise ScopeRefusal(
                    "TEST_INDUSTRY_REQUIREMENT_MISSING", "test industry requirement missing"
                )
            if "industry_only" not in marker and "industry-only" not in marker:
                raise ScopeRefusal(
                    "TEST_INDUSTRY_REQUIREMENT_MISSING", "positive industry test missing"
                )
            if "unrelated_industry" not in marker and "unrelated-industry" not in marker:
                raise ScopeRefusal(
                    "TEST_INDUSTRY_REQUIREMENT_MISSING", "negative industry test missing"
                )


def run_once(
    forge_root: Path,
    target_root: Path,
    *,
    forge_sha: str,
    target_sha: str,
    client: httpx.Client | None = None,
    prompt: str = PROMPT,
) -> RunResult:
    """Perform exactly one proposal-only request after durable intent."""
    store = LedgerStore(forge_root / ".agent" / "ledger", PACKET_ID)
    if (
        store.receipts_path.exists()
        or store.checkpoint_path.exists()
        or store.receipts_path.with_suffix(".claim.json").exists()
    ):
        raise RuntimeError(f"Refusing second run: claim or ledger for '{PACKET_ID}' already exists")
    _require_clean(forge_root, forge_sha, "Forge", FORGE_ORIGIN)
    _require_clean(target_root, target_sha, "Hallam", HALLAM_ORIGIN)
    request_prompt = _request_prompt(target_root, prompt)
    estimate, request_bytes, wire_digest = preflight(
        forge_root, target_root, forge_sha=forge_sha, target_sha=target_sha, prompt=request_prompt
    )
    request_id = _claim(store, forge_sha, target_sha)
    _append(
        store,
        "CALL_INTENT",
        "INITIALIZING",
        "CALLING",
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "forge_sha": forge_sha,
            "target_sha": target_sha,
            "target_branch": HALLAM_BRANCH,
            "model": MODEL,
            "prompt_digest": _digest(request_prompt),
            "wire_payload_digest": wire_digest,
            "serialized_request_bytes": request_bytes,
            "request_byte_bound": MAX_REQUEST_BYTES,
            "output_token_bound": MAX_OUTPUT_TOKENS,
            "max_spend_usd": MAX_SPEND_USD,
            "conservative_estimate_usd": estimate,
            "request_count": 1,
            "effect": "PROPOSAL_ONLY",
        },
    )
    LedgerStore(store.receipts_path.parent, PACKET_ID).load()
    spec = PROVIDERS["deepseek"]
    api_key = os.environ.get(spec.api_key_env)
    url, headers, payload = DeepSeekAdapter().request(
        spec, MODEL, api_key or "", HallamProposal, SYSTEM_PROMPT, request_prompt
    )
    payload["thinking"] = THINKING.copy()
    wire_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_wire_digest = _digest(payload)
    if actual_wire_digest != wire_digest:
        raise RuntimeError("Preflight refused: wire payload changed after digest")
    receipt: CallReceipt | None = None
    diagnostic = {"http_status": None, "response_digest": None, "latency_ms": None}
    diagnostic_state = "UNKNOWN"
    latency_ms: int | None = None
    refusal_reason: str | None = None
    proposal_metadata: list[dict[str, int | str]] | None = None
    proposal: HallamProposal | None = None
    try:
        started_at = time.monotonic()
        try:
            response = (client or httpx.Client()).post(
                url,
                headers={**headers, "Content-Type": "application/json"},
                content=wire_bytes,
                timeout=120.0,
            )
        finally:
            latency_ms = max(0, int((time.monotonic() - started_at) * 1_000))
        response_content = _response_content(response)
        secrets = _configured_secrets()
        if _response_contains_secret(response_content, secrets):
            diagnostic = _diagnostic(
                response,
                latency_ms=latency_ms,
                response_content=response_content,
                include_response_digest=False,
                suppress_response_fields=True,
            )
            _append(
                store,
                "PROVIDER_DIAGNOSTIC",
                "CALLING",
                "RECEIVED",
                {"packet_id": PACKET_ID, "request_id": request_id, **diagnostic},
            )
            diagnostic_state = "RECEIVED"
            raise SensitiveProposalError()
        diagnostic = _diagnostic(response, latency_ms=latency_ms, response_content=response_content)
        _append(
            store,
            "PROVIDER_DIAGNOSTIC",
            "CALLING",
            "RECEIVED",
            {"packet_id": PACKET_ID, "request_id": request_id, **diagnostic},
        )
        diagnostic_state = "RECEIVED"
        if response.status_code != 200:
            raise RefusalError("HTTP_STATUS_REFUSED", "HTTP status was not accepted")
        response_json = _validated_response_json(response_content)
        content, input_tokens, output_tokens = DeepSeekAdapter().parse(response_json)
        if not _valid_token_count(input_tokens) or not _valid_token_count(output_tokens):
            raise InvalidProviderUsageError()
        receipt = CallReceipt(
            capability=Capability.CODING,
            provider="deepseek",
            model=MODEL,
            model_env="BUILDER_MODEL",
            family="deepseek",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            schema_valid=False,
            caller_role="builder",
            packet_id=PACKET_ID,
        )
        try:
            proposal = HallamProposal.model_validate_json(content)
        except ValidationError as exc:
            raise RefusalError("SCHEMA_INVALID", "proposal schema is invalid") from exc
        if _contains_configured_secret(proposal.model_dump(), _configured_secrets()):
            raise SensitiveProposalError()
        receipt = receipt.model_copy(update={"schema_valid": True})
        sources = {path: (target_root / path).read_text(encoding="utf-8") for path in HALLAM_PATHS}
        validate_scope(proposal, sources)
        status, error_type, output_digest = "SUCCEEDED", None, _digest(proposal.model_dump())
    except RefusalError as exc:
        refused_proposal = proposal
        status, error_type, proposal, output_digest = "REFUSED", exc.reason_code, None, None
        refusal_reason = exc.reason_code
        if refusal_reason != "SENSITIVE_OUTPUT_REFUSED" and refused_proposal is not None:
            proposal_metadata = _proposal_metadata(refused_proposal)
    except (SchemaInvalidError, ProviderError) as exc:
        code = "SCHEMA_INVALID" if isinstance(exc, SchemaInvalidError) else "PROVIDER_ERROR"
        status, error_type, proposal, output_digest = "REFUSED", code, None, None
        refusal_reason = code
    except (ValueError, TypeError, json.JSONDecodeError):
        status, error_type, proposal, output_digest = "REFUSED", "SCHEMA_INVALID", None, None
        refusal_reason = "SCHEMA_INVALID"
    except BaseException:
        status, error_type, proposal, output_digest = "UNKNOWN", "TRANSPORT_UNKNOWN", None, None
    if not any(item.event == "PROVIDER_DIAGNOSTIC" for item in store.load().receipts):
        _append(
            store,
            "PROVIDER_DIAGNOSTIC",
            "CALLING",
            "UNKNOWN",
            {"packet_id": PACKET_ID, "request_id": request_id, **diagnostic},
        )
    _append(
        store,
        "CALL_OUTCOME",
        diagnostic_state,
        {"SUCCEEDED": "PROPOSED", "REFUSED": "REFUSED"}.get(status, "UNKNOWN"),
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "status": status,
            "error_type": error_type,
            "refusal_reason": refusal_reason,
            "output_digest": output_digest,
            "proposal": proposal.model_dump() if proposal else None,
            "proposal_metadata": proposal_metadata,
            "provider_receipt": receipt.model_dump() if receipt else None,
            "diagnostic": diagnostic,
            "wire_payload_digest": actual_wire_digest,
            "billing": "UNKNOWN",
            "effect": "PROPOSAL_ONLY",
        },
    )
    return RunResult(status, proposal, receipt, error_type)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forge-root", type=Path, default=Path.cwd())
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--forge-sha", required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    load_env(args.env_file or (args.forge_root / ".env"))
    result = run_once(
        args.forge_root, args.target_root, forge_sha=args.forge_sha, target_sha=args.target_sha
    )
    print(json.dumps({"status": result.status, "error_type": result.error_type}, sort_keys=True))
    return 0 if result.status == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
