"""Bounded, proposal-only Hallam recovery using the validated refusal lesson."""

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
from pydantic import BaseModel, Field, ValidationError

from forge import Ledger, LedgerStore
from forge.config import load_env
from forge.learning import (
    ApplicationRecord,
    CandidateLesson,
    LessonDecision,
    LessonScope,
    LessonStore,
    Metric,
    MetricDirection,
    OutcomeRecord,
)
from forge.providers import CallReceipt, Capability, SchemaInvalidError
from forge.providers.model_provider import PROVIDERS, DeepSeekAdapter, ProviderError
from forge.trust_kernel import Receipt

PACKET_ID = "FORGE-EXT-002"
MODEL = "deepseek-flash"
MAX_SPEND_USD = 0.46432
EXT001_CONSERVATIVE_MAX_USD = 0.23216
MAX_REQUEST_BYTES = 12_000
MAX_OUTPUT_TOKENS = 2_048
HALLAM_ORIGIN = "https://github.com/nrsandoval1231-oss/hallam.git"
FORGE_ORIGIN = "https://github.com/nrsandoval1231-oss/forge-agent.git"
HALLAM_BRANCH = "codex/forge-external-trial"
HALLAM_PATHS = ("apps/api/sabra_api/main.py", "tests/test_api.py")
FIELDS = frozenset({"company", "title", "industry", "location"})
CASES = frozenset({"industry_only", "unrelated_industry"})
LESSON_ID = "LESSON-EXPLAIN-EXTERNAL-REFUSAL"
LESSON_DIGEST = "ab743a3cbab9b74d56d102ac4c74a9a02c40444c8c1b0c6e26f2c28f683d6ea3"
REPOSITORY_DIGEST = "797f248d2e60d1cfc2f81e153c0f3c77922b17f5fa1bef5eff36696809b817df"
SOURCE_STRATEGY = (
    "external proposal call with generic ValueError outcome and no safe refusal-rule metadata"
)
SAFE_STRATEGY = (
    "external proposal call with audited safe refusal evidence, selection-only model authority, "
    "and deterministic two-file Hallam edits"
)
SOURCE_STRATEGY_DIGEST = "252e1e7d1866f715e877ffd40d5d2e9d1d54eb0995c7e7c53312289d7241529a"
FAILURE_SIGNATURE = (
    "unexplained_proposal_refusal a code proposal refused retained rule safe schema valid without"
)
THINKING = {"type": "disabled"}
MAX_USAGE_TOKENS = 1_000_000_000
ALLOWED_FINISH_REASONS = frozenset({"stop", "length", "content_filter", "tool_calls"})


class RecoverySelection(BaseModel):
    fields: list[Literal["company", "title", "industry", "location"]] = Field(
        min_length=1, max_length=4
    )
    positive_case: Literal["industry_only"]
    negative_case: Literal["unrelated_industry"]


class RefusalError(ValueError):
    CODES = frozenset(
        {
            "HTTP_STATUS_REFUSED",
            "SCHEMA_INVALID",
            "PROVIDER_USAGE_INVALID",
            "PROVIDER_ERROR",
            "SENSITIVE_OUTPUT_REFUSED",
            "SELECTION_INVALID",
            "SOURCE_INVALID",
            "IDENTITY_INVALID",
            "REQUEST_TOO_LARGE",
        }
    )

    def __init__(self, code: str, message: str):
        if code not in self.CODES:
            raise ValueError("unknown refusal code")
        super().__init__(message)
        self.reason_code = code


@dataclass(frozen=True)
class RunResult:
    status: Literal["SUCCEEDED", "REFUSED", "UNKNOWN"]
    selection: RecoverySelection | None
    receipt: CallReceipt | None
    error_type: str | None = None


def _digest(value: object) -> str:
    raw = (
        value
        if isinstance(value, bytes)
        else json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )
    return hashlib.sha256(raw).hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_artifact_digest(value: bytes) -> str:
    """Hash retained JSON after normalizing only physical line endings.

    The retained audit digests name the original CRLF byte streams.  This
    verifier instead pins the equivalent LF byte representation so a normal
    Git text checkout cannot change the evidence identity.  Decoding first
    keeps invalid UTF-8 outside the accepted representation.
    """
    value.decode("utf-8")
    canonical = value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _identity(root: Path, expected: str, label: str, origin: str) -> None:
    try:
        head = _git(root, "rev-parse", "HEAD")
        dirty = _git(root, "status", "--porcelain", "--untracked-files=all")
        actual_origin = _git(root, "remote", "get-url", "origin")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RefusalError("IDENTITY_INVALID", f"{label} identity could not be verified") from exc
    if (
        head != expected
        or dirty
        or actual_origin.rstrip("/").removesuffix(".git") != origin.rstrip("/").removesuffix(".git")
    ):
        raise RefusalError("IDENTITY_INVALID", f"{label} identity or clean state is invalid")


def _validated_lesson(
    forge_root: Path,
) -> tuple[LessonStore, object, object, object, ApplicationRecord]:
    candidate_path = forge_root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / "CANDIDATE.json"
    validated_path = forge_root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / "VALIDATED.json"
    try:
        candidate_raw = candidate_path.read_bytes()
        validated_raw = validated_path.read_bytes()
        candidate_artifact = json.loads(candidate_raw)
        validated_artifact = json.loads(validated_raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RefusalError(
            "SOURCE_INVALID", "validated lesson artifacts could not be read"
        ) from exc
    if (
        _canonical_artifact_digest(candidate_raw)
        != "11d0a682424fcece2a44b4c1d12e55fac7e9f3def2446b44676b78fc16165dda"
    ):
        raise RefusalError(
            "SOURCE_INVALID", "candidate lesson artifact does not match canonical audited evidence"
        )
    if (
        _canonical_artifact_digest(validated_raw)
        != "01bd1db99b1a18e20dbf0569019bdc34dde005a3e8f9bf488b0a8a7ce1d211ee"
    ):
        raise RefusalError(
            "SOURCE_INVALID", "validated lesson artifact does not match canonical audited evidence"
        )
    if not isinstance(candidate_artifact, dict) or not isinstance(validated_artifact, dict):
        raise RefusalError("SOURCE_INVALID", "lesson artifacts must be JSON objects")
    if candidate_artifact.get("state") != "CANDIDATE_AWAITING_INDEPENDENT_VALIDATION":
        raise RefusalError(
            "SOURCE_INVALID", "candidate lesson state is not the retained candidate state"
        )
    if (
        candidate_artifact.get("application") is not None
        or candidate_artifact.get("measurement") is not None
    ):
        raise RefusalError(
            "SOURCE_INVALID", "candidate artifact contains unauthorized application evidence"
        )
    if validated_artifact != {
        "application": None,
        "baseline": {
            "direction": "LOWER_IS_BETTER",
            "name": "unexplained_external_refusals",
            "value": 1.0,
        },
        "decision": {
            "evidence_digest": "39658905d5528bf643c1d4218751b99fc047d25401f6c3163a780faa68d29ef2",
            "lesson_id": LESSON_ID,
            "rationale": "Independent audit reproduced the outcome, lesson, failure signature, metric, strategy digest, and provenance. The change improves evidence without weakening requirements; ambiguity remains UNKNOWN.",
            "scope": "REPOSITORY",
            "validated": True,
            "validator": "astra",
        },
        "independent_audit_candidate": "3c9691a71f66db5d1cfd5f1b17151b03547fd1fa",
        "lesson_digest": LESSON_DIGEST,
        "lesson_id": LESSON_ID,
        "measurement": None,
        "packet_id": "FORGE-EXT-LESSON-001",
        "repository_digest": REPOSITORY_DIGEST,
        "scope": "REPOSITORY",
        "source_outcome_digest": "8f8f74e3722f9f3572edb696d85bc68c739887378f6a10cd816cbe7fe7d01c4a",
        "state": "VALIDATED",
    }:
        raise RefusalError(
            "SOURCE_INVALID", "validated lesson authority fields do not match audited evidence"
        )
    store = LessonStore(REPOSITORY_DIGEST)
    outcome = OutcomeRecord(
        "FORGE-EXT-001",
        REPOSITORY_DIGEST,
        "cd129121a1bbfb309a36598bbd8fd97d2d66acf0",
        SOURCE_STRATEGY_DIGEST,
        "ff73ef89c4c81c40eb9c899d2aebe870bcd8952a43428e39efaf4b5798f389d2",
        Metric("unexplained_external_refusals", 1.0, MetricDirection.LOWER_IS_BETTER),
        frozenset({"unexplained_proposal_refusal"}),
        False,
    )
    if outcome.digest != "8f8f74e3722f9f3572edb696d85bc68c739887378f6a10cd816cbe7fe7d01c4a":
        raise RefusalError(
            "SOURCE_INVALID", "validated lesson source outcome digest does not match"
        )
    store.record_outcome(outcome)
    candidate = CandidateLesson(
        LESSON_ID,
        "sol",
        "FORGE-EXT-001 made one paid proposal-only Hallam request. The schema-valid response was refused during scope validation, but the retained outcome named only ValueError and the failed rule could not be reconstructed.",
        "the execution strategy persisted too little safe refusal detail to attribute a post-schema rejection, so it blocked evidence-based recovery",
        "before a paid external Builder call, use independently audited allowlisted refusal reason codes and content-free hunk metadata, and scan credentials before any response-derived persistence",
        "unexplained_external_refusals",
        (
            "A generic exception type without the failed rule does not support attribution and must not justify blind retry.",
        ),
        (FAILURE_SIGNATURE,),
        (outcome.digest,),
    )
    if candidate.digest != LESSON_DIGEST:
        raise RefusalError("SOURCE_INVALID", "validated lesson digest does not match")
    store.propose(candidate)
    decision = LessonDecision(
        LESSON_ID,
        "astra",
        True,
        LessonScope.REPOSITORY,
        "39658905d5528bf643c1d4218751b99fc047d25401f6c3163a780faa68d29ef2",
        "accepted audited diagnostic repair",
    )
    if _text_digest(SOURCE_STRATEGY) != SOURCE_STRATEGY_DIGEST:
        raise RefusalError(
            "SOURCE_INVALID", "source strategy digest does not match retained outcome"
        )
    lesson = store.validate(
        decision,
        baseline=Metric("unexplained_external_refusals", 1.0, MetricDirection.LOWER_IS_BETTER),
    )
    retrieval = store.retrieve(PACKET_ID, FAILURE_SIGNATURE)
    if retrieval.lesson_ids != (LESSON_ID,):
        raise RefusalError(
            "SOURCE_INVALID", "validated lesson was not retrieved for the real failure signature"
        )
    candidate_digest = _digest(
        {"packet_id": PACKET_ID, "hallam_paths": HALLAM_PATHS, "strategy": SAFE_STRATEGY}
    )
    application = ApplicationRecord(
        PACKET_ID,
        LESSON_ID,
        retrieval.digest,
        candidate_digest,
        SOURCE_STRATEGY_DIGEST,
        _text_digest(SAFE_STRATEGY),
    )
    if not application.changed_strategy:
        raise RefusalError("SOURCE_INVALID", "lesson application did not change strategy")
    store.record_application(application)
    return store, lesson, retrieval, candidate, application


def _request(prompt: str) -> tuple[str, dict, dict]:
    return DeepSeekAdapter().request(
        PROVIDERS["deepseek"],
        MODEL,
        "redacted",
        RecoverySelection,
        "Return only the bounded selection JSON.",
        prompt,
    )


def _bound_payload(payload: dict) -> dict:
    """Apply this packet's output ceiling before the payload becomes evidence."""
    bounded = dict(payload)
    bounded["thinking"] = THINKING.copy()
    bounded["max_tokens"] = MAX_OUTPUT_TOKENS
    return bounded


def _conservative_estimate(output_token_bound: int) -> float:
    return ((MAX_REQUEST_BYTES + 1024) * 10 + output_token_bound * 20) / 1_000_000


def _prompt(target: Path) -> str:
    parts = [
        "Select only the fields needed to repair Hallam's Industry filter. Return fields plus positive_case=industry_only and negative_case=unrelated_industry. Do not provide file content."
    ]
    for rel in HALLAM_PATHS:
        path = target / rel
        if not path.is_file():
            raise RefusalError("SOURCE_INVALID", "required Hallam file is missing")
        text = path.read_text(encoding="utf-8")
        try:
            ast.parse(text)
        except SyntaxError as exc:
            raise RefusalError("SOURCE_INVALID", "Hallam source is invalid") from exc
        if rel.endswith("main.py"):
            if "o.company" not in text or "o.industry" in text:
                raise RefusalError(
                    "SOURCE_INVALID", "Hallam Industry defect precondition is absent"
                )
            marker = "(!ind||`${{o.company}} ${{o.title}}`.toLowerCase().includes(ind))"
            if marker not in text:
                raise RefusalError("SOURCE_INVALID", "Hallam filter shape is not the audited shape")
            parts.append(f"\n--- {rel} ---\n{marker}")
        else:
            parts.append(f"\n--- {rel} ---\n{text[-2500:]}")
    result = "".join(parts)
    if len(result.encode()) > 8_000:
        raise RefusalError("REQUEST_TOO_LARGE", "bounded request context is too large")
    return result


def _deterministic_edits(
    selection: RecoverySelection, sources: dict[str, str]
) -> list[dict[str, str]]:
    if set(selection.fields) != {"company", "title", "industry"} or len(selection.fields) != 3:
        raise RefusalError(
            "SELECTION_INVALID", "selection must contain the three audited search fields"
        )
    if (
        selection.positive_case not in CASES
        or selection.negative_case not in CASES
        or selection.positive_case == selection.negative_case
    ):
        raise RefusalError("SELECTION_INVALID", "behavior cases are not the audited pair")
    old_api = "(!ind||`${{o.company}} ${{o.title}}`.toLowerCase().includes(ind))"
    new_api = "(!ind||`${{o.company}} ${{o.title}} ${{o.industry}}`.toLowerCase().includes(ind))"
    if sources[HALLAM_PATHS[0]].count(old_api) != 1:
        raise RefusalError("SOURCE_INVALID", "audited Industry filter hunk is not unique")
    test_addition = """\n\ndef test_industry_only_and_unrelated_industry_boundaries() -> None:\n    response = TestClient(app).get("/opportunities")\n    assert "`${o.company} ${o.title} ${o.industry}`.toLowerCase().includes(ind)" in response.text\n    rows = [\n        {"company": "Acme", "title": "Operations", "industry": "Data Centers"},\n        {"company": "Acme", "title": "Operations", "industry": "Healthcare"},\n    ]\n    term = "data"\n    matches = [row for row in rows if term in f"{row['company']} {row['title']} {row['industry']}".lower()]\n    assert matches == [rows[0]]  # industry_only positive\n    assert rows[1] not in matches  # unrelated_industry negative\n"""
    old_test = '    assert response.json() == {"status": "ok"}\n'
    if sources[HALLAM_PATHS[1]].count(old_test) != 1:
        raise RefusalError("SOURCE_INVALID", "audited API test anchor is not unique")
    return [
        {"path": HALLAM_PATHS[0], "old": old_api, "new": new_api},
        {"path": HALLAM_PATHS[1], "old": old_test, "new": old_test + test_addition},
    ]


def _secrets() -> tuple[str, ...]:
    values = [os.environ.get(PROVIDERS["deepseek"].api_key_env, "")]
    values += [
        v
        for k, v in os.environ.items()
        if any(x in k.upper() for x in ("KEY", "TOKEN", "SECRET", "PASSWORD")) and len(v) >= 8
    ]
    return tuple(dict.fromkeys(v for v in values if v))


def _contains_secret(value: object, secrets: tuple[str, ...]) -> bool:
    if isinstance(value, str):
        decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)
        if any(s in value or s in decoded for s in secrets):
            return True
        try:
            nested = json.loads(value)
        except (ValueError, TypeError):
            nested = None
        return nested is not None and nested != value and _contains_secret(nested, secrets)
    if isinstance(value, dict):
        return any(
            _contains_secret(k, secrets) or _contains_secret(v, secrets) for k, v in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret(v, secrets) for v in value)
    return False


def _contains_secret_bytes(value: bytes, secrets: tuple[str, ...]) -> bool:
    if any(secret.encode("utf-8") in value for secret in secrets):
        return True
    return _contains_secret(value.decode("utf-8", "replace"), secrets)


def _contains_secret_lossless(value: object, secrets: tuple[str, ...]) -> bool:
    """Scan JSON objects as their full sequence of key/value pairs."""
    if isinstance(value, str):
        decoded = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), value)
        if any(secret in value or secret in decoded for secret in secrets):
            return True
        try:
            nested = json.loads(value, object_pairs_hook=tuple)
        except (ValueError, TypeError):
            nested = None
        return nested is not None and nested != value and _contains_secret_lossless(nested, secrets)
    if isinstance(value, dict):
        return any(
            _contains_secret_lossless(key, secrets) or _contains_secret_lossless(item, secrets)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_lossless(item, secrets) for item in value)
    return False


def _parsed_safe_response(content: bytes, secrets: tuple[str, ...]) -> dict:
    """Scan raw and duplicate-preserving JSON before retaining a response digest."""
    if _contains_secret_bytes(content, secrets):
        raise RefusalError("SENSITIVE_OUTPUT_REFUSED", "configured secret detected")
    try:
        lossless = json.loads(content, object_pairs_hook=tuple)
        parsed = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RefusalError("SCHEMA_INVALID", "provider response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise RefusalError("SCHEMA_INVALID", "provider response must be a JSON object")
    if _contains_secret_lossless(lossless, secrets):
        raise RefusalError("SENSITIVE_OUTPUT_REFUSED", "configured secret detected")
    return parsed


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
    ).encode()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("Refusing second run: retained claim blocks retry") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    return request_id


def run_once(
    forge_root: Path,
    target_root: Path,
    *,
    forge_sha: str,
    target_sha: str,
    client: httpx.Client | None = None,
) -> RunResult:
    store = LedgerStore(forge_root / ".agent" / "ledger", PACKET_ID)
    if (
        store.receipts_path.exists()
        or store.checkpoint_path.exists()
        or store.receipts_path.with_suffix(".claim.json").exists()
    ):
        raise RuntimeError("Refusing second run: claim or ledger already exists")
    _identity(forge_root, forge_sha, "Forge", FORGE_ORIGIN)
    _identity(target_root, target_sha, "Hallam", HALLAM_ORIGIN)
    if not os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("BUILDER_MODEL") != MODEL:
        raise RuntimeError(
            "Preflight refused: configured Builder credentials/model are unavailable"
        )
    env_file = forge_root / ".env"
    if (
        env_file.is_file()
        and subprocess.run(
            ["git", "check-ignore", "--quiet", "--", ".env"], cwd=forge_root
        ).returncode
        != 0
    ):
        raise RuntimeError("Preflight refused: credential file is not ignored")
    store_learning, _, retrieval, _, application = _validated_lesson(forge_root)
    prompt = _prompt(target_root)
    _, _, payload = _request(prompt)
    payload = _bound_payload(payload)
    wire = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(wire) > MAX_REQUEST_BYTES:
        raise RuntimeError("Preflight refused: request exceeds byte bound")
    estimate = _conservative_estimate(payload["max_tokens"])
    cumulative_estimate = EXT001_CONSERVATIVE_MAX_USD + estimate
    if cumulative_estimate > MAX_SPEND_USD:
        raise RuntimeError("Preflight refused: conservative spend exceeds packet cap")
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
            "strategy_without_lesson": SOURCE_STRATEGY_DIGEST,
            "strategy_with_lesson": _text_digest(SAFE_STRATEGY),
            "lesson_id": LESSON_ID,
            "lesson_digest": LESSON_DIGEST,
            "retrieval_digest": retrieval.digest,
            "application_digest": application.digest,
            "changed_strategy": application.changed_strategy,
            "wire_payload_digest": _digest(payload),
            "serialized_request_bytes": len(wire),
            "request_byte_bound": MAX_REQUEST_BYTES,
            "output_token_bound": payload["max_tokens"],
            "max_spend_usd": MAX_SPEND_USD,
            "prior_packet_conservative_max_usd": EXT001_CONSERVATIVE_MAX_USD,
            "conservative_estimate_usd": estimate,
            "cumulative_conservative_estimate_usd": cumulative_estimate,
            "cumulative_conservative_max_usd": MAX_SPEND_USD,
            "request_count": 1,
            "effect": "PROPOSAL_ONLY",
        },
    )
    LedgerStore(store.receipts_path.parent, PACKET_ID).load()
    spec = PROVIDERS["deepseek"]
    url, headers, provider_payload = DeepSeekAdapter().request(
        spec,
        MODEL,
        os.environ[spec.api_key_env],
        RecoverySelection,
        "Return only the bounded selection JSON.",
        prompt,
    )
    provider_payload = _bound_payload(provider_payload)
    if _digest(provider_payload) != _digest(payload):
        raise RuntimeError("Preflight refused: wire payload changed after intent")
    status: Literal["SUCCEEDED", "REFUSED", "UNKNOWN"] = "UNKNOWN"
    error: str | None = None
    selection: RecoverySelection | None = None
    receipt: CallReceipt | None = None
    diagnostic: dict[str, object] = {
        "http_status": None,
        "latency_ms": None,
        "response_digest": None,
    }
    started = time.monotonic()
    try:
        response = (client or httpx.Client()).post(
            url,
            headers={**headers, "Content-Type": "application/json"},
            content=wire,
            timeout=120.0,
        )
        content = response.content
        secrets = _secrets()
        try:
            parsed = _parsed_safe_response(content, secrets)
        except RefusalError:
            diagnostic = {
                "http_status": response.status_code,
                "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
                "response_digest": None,
            }
            raise
        diagnostic = {
            "http_status": response.status_code,
            "latency_ms": max(0, int((time.monotonic() - started) * 1000)),
            "response_digest": _digest(content),
        }
        if response.status_code != 200:
            raise RefusalError("HTTP_STATUS_REFUSED", "HTTP status was not accepted")
        usage = parsed.get("usage") if isinstance(parsed, dict) else None
        if not isinstance(usage, dict) or not all(
            isinstance(usage.get(k), int)
            and not isinstance(usage.get(k), bool)
            and 0 <= usage[k] <= MAX_USAGE_TOKENS
            for k in ("prompt_tokens", "completion_tokens")
        ):
            raise RefusalError("PROVIDER_USAGE_INVALID", "provider usage is invalid")
        message, input_tokens, output_tokens = DeepSeekAdapter().parse(parsed)
        try:
            selection = RecoverySelection.model_validate_json(message)
        except ValidationError as exc:
            raise RefusalError("SCHEMA_INVALID", "selection schema is invalid") from exc
        if _contains_secret(selection.model_dump(), secrets):
            raise RefusalError("SENSITIVE_OUTPUT_REFUSED", "configured secret detected")
        sources = {p: (target_root / p).read_text(encoding="utf-8") for p in HALLAM_PATHS}
        _deterministic_edits(selection, sources)
        receipt = CallReceipt(
            capability=Capability.CODING,
            provider="deepseek",
            model=MODEL,
            model_env="BUILDER_MODEL",
            family="deepseek",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=diagnostic["latency_ms"],
            schema_valid=True,
            caller_role="builder",
            packet_id=PACKET_ID,
        )
        status = "SUCCEEDED"
    except RefusalError as exc:
        error = exc.reason_code
        status = "REFUSED"
    except (SchemaInvalidError, ProviderError, ValueError, TypeError, json.JSONDecodeError):
        error = "SCHEMA_INVALID"
        status = "REFUSED"
    except BaseException:
        error = "TRANSPORT_UNKNOWN"
        status = "UNKNOWN"
    _append(
        store,
        "PROVIDER_DIAGNOSTIC",
        "CALLING",
        "RECEIVED" if diagnostic["http_status"] is not None else "UNKNOWN",
        {"packet_id": PACKET_ID, "request_id": request_id, **diagnostic},
    )
    _append(
        store,
        "CALL_OUTCOME",
        "RECEIVED" if diagnostic["http_status"] is not None else "UNKNOWN",
        "PROPOSED" if status == "SUCCEEDED" else status,
        {
            "packet_id": PACKET_ID,
            "request_id": request_id,
            "status": status,
            "error_type": error,
            "selection": selection.model_dump() if selection else None,
            "provider_receipt": receipt.model_dump() if receipt else None,
            "diagnostic": diagnostic,
            "billing": "UNKNOWN",
            "effect": "PROPOSAL_ONLY",
        },
    )
    return RunResult(status, selection, receipt, error)


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
