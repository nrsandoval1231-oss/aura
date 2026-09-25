"""Make one bounded, proposal-only DeepSeek request for the Sentinal trial.

The target repository is inspected and its exact clean commit is checked before
the external effect.  The returned proposal is never applied by this module.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from forge import Ledger, LedgerStore
from forge.config import load_env
from forge.providers import CallReceipt, Capability, SchemaInvalidError
from forge.providers.model_provider import PROVIDERS, DeepSeekAdapter, ProviderError
from forge.trust_kernel import Receipt

PACKET_ID = "FORGE-SENTINEL-002"
MODEL = "deepseek-flash"
MAX_SPEND_USD = 15.0
OWNER_REPORTED_PRIOR_SPEND_USD = 0.03
MAX_REQUEST_BYTES = 12_000
MAX_OUTPUT_TOKENS = 4_096
MAX_CONTEXT_CHARS = 9_000
INPUT_RATE_USD_PER_MILLION = 10.0
OUTPUT_RATE_USD_PER_MILLION = 20.0
TARGET_PATH = "scripts/ci_local.py"
TARGET_FUNCTION = "run_step"

SYSTEM_PROMPT = "Return only a bounded Sentinal run_step replacement as structured JSON."
THINKING = {"type": "disabled"}

PROMPT = """The Sentinal local Windows validation runner has six failing tests because
its run_step function selects a nonfunctional WindowsApps WSL bash launcher even
when Git Bash is installed. Propose a narrow replacement for only the
scripts/ci_local.py run_step function. It must preserve command arguments,
environment, return-code handling, timeout behavior, and output capture while
selecting a usable shell deterministically. Do not edit tests or product code.
Return only the structured proposal."""


class SentinelProposal(BaseModel):
    path: Literal["scripts/ci_local.py"]
    function: Literal["run_step"]
    replacement: str = Field(min_length=1, max_length=6000)
    rationale: str = Field(min_length=1, max_length=1000)


@dataclass(frozen=True)
class RunResult:
    status: Literal["SUCCEEDED", "REFUSED", "UNKNOWN"]
    proposal: SentinelProposal | None
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


def _require_clean(root: Path, expected_sha: str, label: str) -> None:
    try:
        head = _git(root, "rev-parse", "HEAD")
        status = _git(root, "status", "--porcelain", "--untracked-files=all")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"Preflight refused: {label} identity could not be verified") from exc
    if head != expected_sha:
        raise RuntimeError(f"Preflight refused: {label} HEAD does not match expected SHA")
    if status:
        raise RuntimeError(f"Preflight refused: {label} worktree is not clean")


def _wire_payload(prompt: str) -> dict:
    _, _, payload = DeepSeekAdapter().request(
        PROVIDERS["deepseek"],
        MODEL,
        "redacted",
        SentinelProposal,
        SYSTEM_PROMPT,
        prompt,
    )
    payload["thinking"] = THINKING.copy()
    return payload


def _request_metadata(prompt: str) -> tuple[int, str]:
    payload = _wire_payload(prompt)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return len(serialized), _digest(payload)


def _wire_request(prompt: str) -> tuple[str, dict[str, str], bytes, str]:
    """Build the exact bytes used by both preflight and the HTTP effect."""
    spec = PROVIDERS["deepseek"]
    api_key = os.environ.get(spec.api_key_env)
    if not api_key:
        raise RuntimeError("Preflight refused: DEEPSEEK_API_KEY is missing")
    url, _, _ = DeepSeekAdapter().request(
        spec, MODEL, api_key, SentinelProposal, SYSTEM_PROMPT, prompt
    )
    payload = _wire_payload(prompt)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return (
        url,
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        body,
        _digest(payload),
    )


def preflight(
    forge_root: Path,
    target_root: Path,
    *,
    forge_sha: str,
    target_sha: str,
    env: dict[str, str] | None = None,
    prompt: str = PROMPT,
) -> tuple[float, int, str]:
    """Verify identities, clean state, credentials, model, and spend bound."""
    _require_clean(forge_root, forge_sha, "Forge")
    _require_clean(target_root, target_sha, "Sentinal")
    values = os.environ if env is None else env
    if not values.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("Preflight refused: DEEPSEEK_API_KEY is missing")
    env_file = forge_root / ".env"
    if env_file.is_file():
        ignored = subprocess.run(["git", "check-ignore", "--quiet", "--", ".env"], cwd=forge_root)
        if ignored.returncode != 0:
            raise RuntimeError("Preflight refused: credential file is not git-ignored")
    if values.get("BUILDER_MODEL") != MODEL:
        raise RuntimeError(f"Preflight refused: BUILDER_MODEL must be {MODEL!r}")
    request_bytes, wire_digest = _request_metadata(prompt)
    if request_bytes > MAX_REQUEST_BYTES:
        raise RuntimeError("Preflight refused: serialized request exceeds byte bound")
    estimate = (
        (MAX_REQUEST_BYTES + 1024) * INPUT_RATE_USD_PER_MILLION
        + MAX_OUTPUT_TOKENS * OUTPUT_RATE_USD_PER_MILLION
    ) / 1_000_000
    remaining = MAX_SPEND_USD - OWNER_REPORTED_PRIOR_SPEND_USD
    if remaining <= 0 or estimate > remaining:
        raise RuntimeError("Preflight refused: cumulative conservative estimate exceeds grant")
    return estimate, request_bytes, wire_digest


def _claim(store: LedgerStore, base_sha: str, target_sha: str) -> str:
    request_id = f"REQ-{uuid.uuid4().hex}"
    path = store.receipts_path.with_suffix(".claim.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "forge_sha": base_sha,
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


def _safe_response_digest(response: httpx.Response) -> str | None:
    try:
        return hashlib.sha256(response.content).hexdigest()
    except (httpx.ResponseNotRead, RuntimeError):
        return None


def _diagnostic(response: httpx.Response) -> dict:
    """Return only non-secret transport facts; body content is never persisted."""
    body: dict = {
        "http_status": response.status_code,
        "response_digest": _safe_response_digest(response),
    }
    try:
        parsed = response.json()
    except (ValueError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        provider_id = parsed.get("id")
        if isinstance(provider_id, str) and len(provider_id) <= 200:
            body["provider_response_id"] = provider_id
        choices = parsed.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            body["finish_reason"] = choices[0].get("finish_reason")
        usage = parsed.get("usage")
        if isinstance(usage, dict):
            body["usage"] = {
                key: usage[key]
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if isinstance(usage.get(key), int)
            }
    return body


def validate_scope(proposal: SentinelProposal, source: str) -> None:
    if proposal.path != TARGET_PATH or proposal.function != TARGET_FUNCTION:
        raise ValueError("Proposal is outside scripts/ci_local.py run_step scope")
    if "def run_step" not in proposal.replacement:
        raise ValueError("Proposal does not replace run_step")
    if "tests/" in proposal.replacement or "src/" in proposal.replacement:
        raise ValueError("Proposal mentions an excluded source or test path")
    if TARGET_PATH in proposal.replacement:
        raise ValueError("Proposal may not rewrite files outside the function body")
    if not source.strip():
        raise ValueError("Target source is empty")
    try:
        module = ast.parse(proposal.replacement)
    except SyntaxError as exc:
        raise ValueError("Proposal replacement is not valid Python") from exc
    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        raise ValueError("Proposal must contain exactly one function definition")
    if module.body[0].name != TARGET_FUNCTION:
        raise ValueError("Proposal function name does not match run_step")


def _request_prompt(target_root: Path, prompt: str) -> str:
    """Give the model complete bounded implementation and failure context."""
    source_path = target_root / TARGET_PATH
    source = source_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == TARGET_FUNCTION
        ]
        if len(functions) != 1 or functions[0].end_lineno is None:
            raise ValueError("target run_step is missing or ambiguous")
        function = functions[0]
        source_lines = source.splitlines()
        segments: list[str] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node.end_lineno is not None:
                segments.extend(source_lines[node.lineno - 1 : node.end_lineno])
        segments.extend(source_lines[function.lineno - 1 : function.end_lineno])
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError("Preflight refused: target run_step context is unavailable") from exc
    implementation = "\n".join(segments)
    tests_path = target_root / "tests" / "test_ci_local.py"
    if not tests_path.is_file():
        raise RuntimeError("Preflight refused: affected test file is missing")
    tests = tests_path.read_text(encoding="utf-8")
    try:
        test_tree = ast.parse(tests)
        affected = []
        for node in test_tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = ast.get_source_segment(tests, node) or ""
            if "run_step" in segment:
                affected.append(node)
    except SyntaxError as exc:
        raise RuntimeError("Preflight refused: affected tests are unavailable") from exc
    if not affected:
        raise RuntimeError("Preflight refused: affected run_step tests are missing")
    test_lines = tests.splitlines()
    test_context = "\n".join(
        line
        for node in affected
        if node.end_lineno is not None
        for line in test_lines[node.lineno - 1 : node.end_lineno]
    )
    request = (
        f"{prompt}\n\nCurrent implementation:\n{implementation}\n\nAffected tests:\n{test_context}"
    )
    if len(request) > MAX_CONTEXT_CHARS:
        raise RuntimeError("Preflight refused: target context exceeds character bound")
    return request


def run_once(
    forge_root: Path,
    target_root: Path,
    *,
    forge_sha: str,
    target_sha: str,
    client: httpx.Client | None = None,
    prompt: str = PROMPT,
) -> RunResult:
    """Perform exactly one request after durable intent; never retry or apply."""
    store = LedgerStore(forge_root / ".agent" / "ledger", PACKET_ID)
    if (
        store.receipts_path.exists()
        or store.checkpoint_path.exists()
        or store.receipts_path.with_suffix(".claim.json").exists()
    ):
        raise RuntimeError(f"Refusing second run: claim or ledger for '{PACKET_ID}' already exists")
    _require_clean(forge_root, forge_sha, "Forge")
    _require_clean(target_root, target_sha, "Sentinal")
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
            "model": MODEL,
            "prompt_digest": _digest(request_prompt),
            "wire_payload_digest": wire_digest,
            "serialized_request_bytes": request_bytes,
            "request_byte_bound": MAX_REQUEST_BYTES,
            "output_token_bound": MAX_OUTPUT_TOKENS,
            "max_spend_usd": MAX_SPEND_USD,
            "owner_reported_prior_spend_usd": OWNER_REPORTED_PRIOR_SPEND_USD,
            "remaining_spend_usd": MAX_SPEND_USD - OWNER_REPORTED_PRIOR_SPEND_USD,
            "conservative_estimate_usd": estimate,
            "request_count": 1,
            "effect": "PROPOSAL_ONLY",
        },
    )
    # Reload the durable chain immediately before crossing the external boundary.
    LedgerStore(store.receipts_path.parent, PACKET_ID).load()
    url, headers, wire_bytes, actual_wire_digest = _wire_request(request_prompt)
    if actual_wire_digest != wire_digest:
        raise RuntimeError("Preflight refused: wire payload changed after digest")
    started = time.monotonic()
    receipt: CallReceipt | None = None
    diagnostic: dict = {"http_status": "UNKNOWN", "response_digest": None}
    diagnostic_state = "UNKNOWN"
    try:
        if client is None:
            response = httpx.post(url, headers=headers, content=wire_bytes, timeout=120.0)
        else:
            response = client.post(url, headers=headers, content=wire_bytes, timeout=120.0)
        diagnostic = _diagnostic(response)
        # Persist provider facts before attempting JSON/schema parsing.
        _append(
            store,
            "PROVIDER_DIAGNOSTIC",
            "CALLING",
            "RECEIVED",
            {"packet_id": PACKET_ID, "request_id": request_id, **diagnostic},
        )
        diagnostic_state = "RECEIVED"
        if response.status_code != 200:
            raise ValueError(f"HTTP refusal: status={response.status_code}")
        try:
            body = response.json()
            content, input_tokens, output_tokens = DeepSeekAdapter().parse(body)
        except (ValueError, KeyError, IndexError, TypeError, ProviderError) as exc:
            raise ProviderError("provider response could not be parsed") from exc
        receipt = CallReceipt(
            capability=Capability.CODING,
            provider="deepseek",
            model=MODEL,
            model_env="BUILDER_MODEL",
            family="deepseek",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            schema_valid=False,
            caller_role="builder",
            packet_id=PACKET_ID,
        )
        try:
            plan = SentinelProposal.model_validate_json(content)
        except Exception as exc:
            raise SchemaInvalidError("schema-invalid Sentinel proposal") from exc
        receipt = receipt.model_copy(update={"schema_valid": True})
        source = (target_root / TARGET_PATH).read_text(encoding="utf-8")
        validate_scope(plan, source)
        status: Literal["SUCCEEDED", "REFUSED"] = "SUCCEEDED"
        error_type = None
        proposal = plan
        output_digest = _digest(plan.model_dump())
    except ValueError as exc:
        status, error_type, proposal, output_digest = "REFUSED", type(exc).__name__, None, None
    except SchemaInvalidError as exc:
        status, error_type, proposal, output_digest = "REFUSED", type(exc).__name__, None, None
    except ProviderError as exc:
        status, error_type, proposal, output_digest = "REFUSED", type(exc).__name__, None, None
    except httpx.HTTPError as exc:
        status, error_type, proposal, output_digest = "UNKNOWN", type(exc).__name__, None, None
    except BaseException as exc:
        status, error_type, proposal, output_digest = "UNKNOWN", type(exc).__name__, None, None
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
            "output_digest": output_digest,
            "proposal": proposal.model_dump() if proposal else None,
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
