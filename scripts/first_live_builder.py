"""Run the single authorized DeepSeek Builder request without automatic retry.

The runner records intent before the external effect and records only a
sanitized outcome afterward. It returns a validated README proposal; applying
that proposal remains a separate, human-controlled effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from forge import Ledger, LedgerStore, ModelProvider
from forge.providers import CallReceipt, Capability
from forge.providers.model_provider import PROVIDERS, DeepSeekAdapter
from forge.trust_kernel import Receipt

PACKET_ID = "FORGE-LIVE-001"
MODEL = "deepseek-flash"
MAX_SPEND_USD = 15.0
MAX_REQUEST_BYTES = 8192
MAX_OUTPUT_TOKENS = 4096
# A conservative preflight ceiling. Actual billing comes from the provider and
# is recorded as UNKNOWN when the response does not include billing data.
INPUT_RATE_USD_PER_MILLION = 10.0
OUTPUT_RATE_USD_PER_MILLION = 20.0
PROMPT = (
    "Propose one small README.md edit. In the Credentials section, clarify that "
    "BUILDER_MODEL takes a DeepSeek API model ID such as deepseek-flash, not its "
    "display name. Return only the structured proposal."
)


class ReadmeEditProposal(BaseModel):
    path: str
    section: str
    replacement: str = Field(min_length=1, max_length=1000)


BuilderResponse = ReadmeEditProposal


@dataclass(frozen=True)
class RunResult:
    status: Literal["SUCCEEDED", "REFUSED", "UNKNOWN"]
    proposal: ReadmeEditProposal | None
    receipt: CallReceipt | None
    error_type: str | None = None


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append(
    store: LedgerStore, event: str, state_before: str, state_after: str, payload: dict
) -> None:
    ledger = store.load() if store.exists else Ledger(stream_id=store.stream_id)
    receipt = Receipt.create(
        len(ledger.receipts) + 1,
        event,
        state_before,
        state_after,
        payload,
        ledger.receipts[-1].receipt_hash if ledger.receipts else None,
    )
    ledger.append(receipt)
    store.write(ledger)


def _serialized_request_bytes(prompt: str) -> int:
    _, _, payload = DeepSeekAdapter().request(
        PROVIDERS["deepseek"],
        MODEL,
        "redacted",
        ReadmeEditProposal,
        "Return a bounded README edit proposal as structured JSON.",
        prompt,
    )
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _preflight(env: dict[str, str] | None = None, *, prompt: str = PROMPT) -> tuple[str, float]:
    values = os.environ if env is None else env
    if not values.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("Preflight refused: DEEPSEEK_API_KEY is missing")
    model = values.get("BUILDER_MODEL")
    if model != MODEL:
        raise RuntimeError(f"Preflight refused: BUILDER_MODEL must be {MODEL!r}")
    request_bytes = _serialized_request_bytes(prompt)
    if request_bytes > MAX_REQUEST_BYTES:
        raise RuntimeError("Preflight refused: serialized request exceeds byte bound")
    input_token_bound = MAX_REQUEST_BYTES + 1024
    estimate = (
        input_token_bound * INPUT_RATE_USD_PER_MILLION
        + MAX_OUTPUT_TOKENS * OUTPUT_RATE_USD_PER_MILLION
    ) / 1_000_000
    if estimate >= MAX_SPEND_USD:
        raise RuntimeError("Preflight refused: conservative request estimate exceeds grant")
    return model, estimate


def verify_repository_state(repository_root: Path, base_sha: str) -> None:
    """Require exact HEAD and no visible dirty state before a paid call."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Preflight refused: repository identity could not be verified") from exc
    if head != base_sha:
        raise RuntimeError("Preflight refused: repository HEAD does not match base SHA")
    if status:
        raise RuntimeError("Preflight refused: repository worktree is not clean")


def _claim(store: LedgerStore, request_id: str, base_sha: str) -> None:
    claim_path = store.receipts_path.with_suffix(".claim.json")
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "base_sha": base_sha,
            "status": "CLAIMED",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        descriptor = os.open(
            claim_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )
    except FileExistsError as exc:
        raise RuntimeError(f"Refusing second run: claim for '{PACKET_ID}' already exists") from exc
    # Once O_EXCL succeeds, the claim is permanent evidence of ownership. An
    # interrupted write leaves it in place so a later invocation cannot retry.
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _validate_scope(proposal: ReadmeEditProposal, readme: str) -> None:
    if proposal.path != "README.md" or proposal.section != "Credentials":
        raise ValueError("Proposal is outside the README Credentials scope")
    if "## Credentials" not in readme:
        raise ValueError("README Credentials section is missing")
    if "BUILDER_MODEL" not in proposal.replacement:
        raise ValueError("Proposal does not address BUILDER_MODEL")
    if "deepseek-flash" not in proposal.replacement:
        raise ValueError("Proposal does not identify the DeepSeek API model id")
    if "## " in proposal.replacement:
        raise ValueError("Proposal may not add or alter another README section")


def run_once(
    repository_root: Path,
    *,
    base_sha: str,
    client: httpx.Client | None = None,
    readme_text: str | None = None,
    prompt: str = PROMPT,
) -> RunResult:
    """Make exactly one request after durable intent; never retry on failure."""
    store = LedgerStore(repository_root / ".agent" / "ledger", PACKET_ID)
    if (
        store.receipts_path.exists()
        or store.checkpoint_path.exists()
        or store.receipts_path.with_suffix(".claim.json").exists()
    ):
        raise RuntimeError(f"Refusing second run: claim or ledger for '{PACKET_ID}' already exists")
    verify_repository_state(repository_root, base_sha)
    model, estimate = _preflight(prompt=prompt)
    request_id = f"REQ-{uuid.uuid4().hex}"
    _claim(store, request_id, base_sha)
    _append(
        store,
        "CALL_INTENT",
        "INITIALIZING",
        "CALLING",
        {
            "packet_id": PACKET_ID,
            "base_sha": base_sha,
            "request_id": request_id,
            "model": model,
            "prompt_digest": _digest(prompt),
            "output_token_bound": MAX_OUTPUT_TOKENS,
            "request_byte_bound": MAX_REQUEST_BYTES,
            "input_token_estimate_bound": MAX_REQUEST_BYTES + 1024,
            "spend_authority": "owner-grant-2026-09-22",
            "max_spend_usd": MAX_SPEND_USD,
            "conservative_estimate_usd": estimate,
            "request_count": 1,
        },
    )
    # Rebuild the persisted chain before crossing the external effect boundary.
    LedgerStore(store.receipts_path.parent, PACKET_ID).load()

    provider = ModelProvider(client=client)
    try:
        plan, receipt = provider.call(
            Capability.CODING,
            BuilderResponse,
            "Return a bounded README edit proposal as structured JSON.",
            prompt,
            caller_role="builder",
            packet_id=PACKET_ID,
        )
        proposal = ReadmeEditProposal.model_validate(plan.model_dump())
        _validate_scope(proposal, readme_text or (repository_root / "README.md").read_text())
        status: Literal["SUCCEEDED", "REFUSED"] = "SUCCEEDED"
        error_type = None
        output_digest = _digest(proposal.model_dump())
    except ValueError as exc:
        receipt = provider.receipts[-1] if provider.receipts else None
        proposal = None
        status = "REFUSED"
        error_type = type(exc).__name__
        output_digest = None
    except BaseException as exc:
        receipt = provider.receipts[-1] if provider.receipts else None
        proposal = None
        status = "UNKNOWN"
        error_type = type(exc).__name__
        output_digest = None

    _append(
        store,
        "CALL_OUTCOME",
        "CALLING",
        {"SUCCEEDED": "PROPOSED", "REFUSED": "REFUSED"}.get(status, "UNKNOWN"),
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "status": status,
            "error_type": error_type,
            "output_digest": output_digest,
            "proposal": proposal.model_dump() if proposal else None,
            "proposal_digest": output_digest,
            "provider_receipt": receipt.model_dump() if receipt else None,
            "billing": "UNKNOWN",
            "effect": "PROPOSAL_ONLY",
        },
    )
    return RunResult(status, proposal, receipt, error_type)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    from forge.config import load_env

    verify_repository_state(args.root, args.base_sha)
    load_env(args.env_file or (args.root / ".env"))
    result = run_once(args.root, base_sha=args.base_sha)
    print(json.dumps({"status": result.status, "error_type": result.error_type}, sort_keys=True))
    return 0 if result.status == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
