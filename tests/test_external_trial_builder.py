from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from forge.ledger_store import LedgerStore
from scripts.external_trial_builder import (
    FORGE_ORIGIN,
    HALLAM_ORIGIN,
    HALLAM_PATHS,
    MAX_REQUEST_BYTES,
    PACKET_ID,
    HallamProposal,
    _diagnostic,
    _digest,
    _request_payload,
    _request_prompt,
    run_once,
    validate_scope,
)


def _init(root: Path, files: dict[str, str]) -> str:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "forge-tests@example.invalid"],
        ["git", "config", "user.name", "Forge Tests"],
        ["git", "add", "."],
        ["git", "commit", "-qm", "fixture"],
        ["git", "remote", "add", "origin", FORGE_ORIGIN],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repos(tmp_path, monkeypatch):
    forge = tmp_path / "forge"
    hallam = tmp_path / "hallam"
    forge.mkdir()
    hallam.mkdir()
    forge_sha = _init(
        forge, {".gitignore": ".env\n", ".env": "DEEPSEEK_API_KEY=local\n", "README.md": "forge\n"}
    )
    subprocess.run(["git", "remote", "set-url", "origin", FORGE_ORIGIN], cwd=forge, check=True)
    for name, content in {
        HALLAM_PATHS[0]: (
            "def opportunities(items, term):\n"
            '    html = """\n'
            "    const filtered = opportunities.filter(o => !ind||o.company.includes(q)||o.title.includes(q));\n"
            '    """\n'
            "    return html\n"
        ),
        HALLAM_PATHS[1]: "def test_opportunities():\n    pass\n",
    }.items():
        path = hallam / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "forge-tests@example.invalid"],
        ["git", "config", "user.name", "Forge Tests"],
        ["git", "add", "."],
        ["git", "commit", "-qm", "fixture"],
        ["git", "remote", "add", "origin", HALLAM_ORIGIN],
    ):
        subprocess.run(command, cwd=hallam, check=True, capture_output=True)
    target_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=hallam, check=True, capture_output=True, text=True
    ).stdout.strip()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("BUILDER_MODEL", "deepseek-flash")
    return forge, hallam, forge_sha, target_sha


def _body(proposal: dict, *, finish_reason="stop"):
    return {
        "choices": [{"message": {"content": json.dumps(proposal)}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 80},
    }


def _proposal():
    return {
        "edits": [
            {
                "path": HALLAM_PATHS[0],
                "old": "!ind||o.company.includes(q)||o.title.includes(q)",
                "new": "!ind||o.company.includes(q)||o.title.includes(q)||o.industry?.includes(q)",
            },
            {
                "path": HALLAM_PATHS[1],
                "old": "    pass",
                "new": "    industry_only_positive = True\n    unrelated_industry_negative = False\n    assert industry_only_positive\n    assert not unrelated_industry_negative",
            },
        ],
        "rationale": "Bounded Industry filter repair.",
    }


def test_valid_proposal_records_intent_before_request_and_never_edits(repos):
    forge, hallam, forge_sha, target_sha = repos
    before = (hallam / HALLAM_PATHS[0]).read_bytes()
    seen = {}

    def handler(request):
        seen["intent"] = [
            r.event for r in LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts
        ] == ["CALL_INTENT"]
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_body(_proposal()))

    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result.status == "SUCCEEDED" and seen["intent"]
    assert (hallam / HALLAM_PATHS[0]).read_bytes() == before
    ledger = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load()
    assert [r.event for r in ledger.receipts] == [
        "CALL_INTENT",
        "PROVIDER_DIAGNOSTIC",
        "CALL_OUTCOME",
    ]
    assert ledger.receipts[0].payload["wire_payload_digest"] == _digest(seen["payload"])
    assert seen["payload"]["thinking"] == {"type": "disabled"}
    assert "lesson_source" not in ledger.receipts[0].payload


def test_raw_secret_in_provider_diagnostics_is_refused_without_response_digest(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    monkeypatch.setenv("DEEPSEEK_API_KEY", "top-secret-value")
    body = _body(_proposal())
    body.update(
        {
            "id": "top-secret-value",
            "debug": {"credential": "top-secret-value", "nested": ["do-not-store"]},
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 80,
                "total_tokens": 120,
                "nested": {"credential": "top-secret-value"},
            },
        }
    )
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    ledger = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load()
    diagnostic = ledger.receipts[1].payload
    assert set(diagnostic) == {
        "packet_id",
        "request_id",
        "http_status",
        "response_digest",
        "latency_ms",
    }
    assert diagnostic["response_digest"] is None
    persisted = (forge / ".agent" / "ledger" / f"{PACKET_ID}.jsonl").read_text(encoding="utf-8")
    assert "top-secret-value" not in persisted
    assert "do-not-store" not in persisted


def test_diagnostic_keeps_only_bounded_plain_integer_usage_and_safe_fields():
    response = httpx.Response(
        200,
        json={
            "id": "call_123:ok",
            "choices": [{"finish_reason": {"nested": "not-allowed"}}],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 7,
                "total_tokens": True,
                "negative": -1,
            },
        },
    )
    assert _diagnostic(response, latency_ms=12) == {
        "http_status": 200,
        "response_digest": _digest(response.content),
        "latency_ms": 12,
        "provider_response_id": "call_123:ok",
        "usage": {"prompt_tokens": 0, "completion_tokens": 7},
    }


def test_secret_in_schema_valid_proposal_is_refused_without_ledger_leak(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    secret = "top-secret-value"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    proposal = _proposal()
    proposal["rationale"] = f"Repair detail: {secret}"
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_body(proposal)))
        ),
    )
    assert result.status == "REFUSED"
    assert result.proposal is None
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    ledger_path = forge / ".agent" / "ledger" / f"{PACKET_ID}.jsonl"
    checkpoint_path = forge / ".agent" / "ledger" / f"{PACKET_ID}.checkpoint.json"
    assert secret not in ledger_path.read_text(encoding="utf-8")
    assert secret not in checkpoint_path.read_text(encoding="utf-8")
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    assert outcome["proposal"] is None
    assert outcome["error_type"] == "SENSITIVE_OUTPUT_REFUSED"
    assert outcome["refusal_reason"] == "SENSITIVE_OUTPUT_REFUSED"
    assert outcome["proposal_metadata"] is None
    assert outcome["output_digest"] is None
    assert outcome["diagnostic"]["response_digest"] is None
    assert outcome["diagnostic"].keys() == {"http_status", "response_digest", "latency_ms"}


def test_invalid_parsed_token_counts_are_refused_before_receipt_persistence(repos):
    forge, hallam, forge_sha, target_sha = repos
    body = _body(_proposal())
    body["usage"] = {"prompt_tokens": -9, "completion_tokens": True, "total_tokens": -8}
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.proposal is None and result.receipt is None
    assert result.error_type == "PROVIDER_USAGE_INVALID"
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    assert outcome["proposal"] is None
    assert outcome["provider_receipt"] is None
    receipts = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts
    diagnostic = receipts[1].payload
    assert "usage" not in diagnostic
    assert all(value not in diagnostic.values() for value in (-9, -8, True))


def test_short_provider_key_echo_is_omitted_from_diagnostic_and_ledger(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    secret = "short"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    body = _body(_proposal())
    body["id"] = secret
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    diagnostic = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert diagnostic["response_digest"] is None
    assert "provider_response_id" not in diagnostic
    assert secret not in (forge / ".agent" / "ledger" / f"{PACKET_ID}.jsonl").read_text(
        encoding="utf-8"
    )


def test_short_provider_key_in_proposal_is_refused_without_ledger_leak(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    secret = "short"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    proposal = _proposal()
    proposal["rationale"] = f"Repair detail: {secret}"
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_body(proposal)))
        ),
    )
    assert result.status == "REFUSED"
    assert result.proposal is None and result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    ledger_root = forge / ".agent" / "ledger"
    assert secret not in (ledger_root / f"{PACKET_ID}.jsonl").read_text(encoding="utf-8")
    assert secret not in (ledger_root / f"{PACKET_ID}.checkpoint.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("secret", ["short", "a-long-configured-secret-value-123456789"])
def test_raw_secret_in_ignored_extra_or_oversized_invalid_output_has_no_digest(
    repos, monkeypatch, secret
):
    forge, hallam, forge_sha, target_sha = repos
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    proposal = _proposal()
    body = _body(proposal)
    if secret == "short":
        body["ignored_extra"] = {"secret": secret}
    else:
        body["choices"][0]["message"]["content"] = secret + ("x" * 4_000)
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    ledger_root = forge / ".agent" / "ledger"
    ledger_text = (ledger_root / f"{PACKET_ID}.jsonl").read_text(encoding="utf-8")
    checkpoint_text = (ledger_root / f"{PACKET_ID}.checkpoint.json").read_text(encoding="utf-8")
    assert secret not in ledger_text and secret not in checkpoint_text
    outcome = LedgerStore(ledger_root, PACKET_ID).load().receipts[-1].payload
    assert outcome["diagnostic"]["response_digest"] is None
    assert outcome["output_digest"] is None
    assert outcome["proposal_metadata"] is None
    assert outcome["proposal"] is None


@pytest.mark.parametrize(
    ("secret", "placement"),
    [
        ("short", "valid"),
        ("long-configured-secret-value-123456789", "valid"),
        ("short", "ignored"),
        ("long-configured-secret-value-123456789", "oversized"),
    ],
)
def test_unicode_escaped_secret_is_suppressed_before_any_response_digest(
    repos, monkeypatch, secret, placement
):
    forge, hallam, forge_sha, target_sha = repos
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    escaped = "".join(f"\\u{ord(character):04x}" for character in secret)
    body = _body(_proposal())
    if placement == "valid":
        proposal = _proposal()
        proposal["rationale"] = escaped
        body = _body(proposal)
    elif placement == "ignored":
        body["ignored_extra"] = escaped
    else:
        body["choices"][0]["message"]["content"] = '{"rationale":"' + escaped + ("x" * 4_000)
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    ledger_root = forge / ".agent" / "ledger"
    ledger_text = (ledger_root / f"{PACKET_ID}.jsonl").read_text(encoding="utf-8")
    checkpoint_text = (ledger_root / f"{PACKET_ID}.checkpoint.json").read_text(encoding="utf-8")
    assert secret not in ledger_text and secret not in checkpoint_text
    outcome = LedgerStore(ledger_root, PACKET_ID).load().receipts[-1].payload
    assert outcome["diagnostic"]["response_digest"] is None
    assert outcome["output_digest"] is None
    assert outcome["proposal_metadata"] is None
    assert outcome["proposal"] is None


@pytest.mark.parametrize(
    "usage",
    [None, [], {"prompt_tokens": "40", "completion_tokens": 80}, {"prompt_tokens": 40}],
)
def test_malformed_usage_containers_are_provider_usage_refusals(repos, usage):
    forge, hallam, forge_sha, target_sha = repos
    body = _body(_proposal())
    body["usage"] = usage
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "PROVIDER_USAGE_INVALID"
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    assert outcome["refusal_reason"] == "PROVIDER_USAGE_INVALID"
    assert outcome["provider_receipt"] is None


def test_malformed_provider_structure_is_safe_provider_refusal(repos):
    forge, hallam, forge_sha, target_sha = repos
    body = {"usage": {"prompt_tokens": 40, "completion_tokens": 80}, "choices": [{}]}
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "PROVIDER_ERROR"
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    assert outcome["refusal_reason"] == "PROVIDER_ERROR"


def test_request_latency_is_measured_with_monotonic_clock(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    readings = iter((100.0, 100.123))
    monkeypatch.setattr("scripts.external_trial_builder.time.monotonic", lambda: next(readings))
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_body(_proposal())))
        ),
    )
    assert result.status == "SUCCEEDED"
    assert result.receipt is not None and result.receipt.latency_ms == 123
    diagnostic = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert diagnostic["latency_ms"] == 123


def test_hallam_context_and_serialized_request_fit_bounds(repos):
    _, hallam, _, _ = repos
    prompt = _request_prompt(hallam, "bounded")
    payload = _request_payload(prompt)
    assert len(prompt) <= 10_000
    assert "!ind||o.company" in prompt
    assert "o.industry" not in prompt
    assert (
        len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        <= MAX_REQUEST_BYTES
    )


def test_scope_requires_both_exact_paths_and_industry_boundary_cases(repos):
    _, hallam, _, _ = repos
    proposal = HallamProposal.model_validate(_proposal())
    sources = {path: (hallam / path).read_text(encoding="utf-8") for path in HALLAM_PATHS}
    validate_scope(proposal, sources)
    bad = _proposal()
    bad["edits"][1]["new"] = "    unrelated = True"
    with pytest.raises(ValueError, match="industry"):
        validate_scope(HallamProposal.model_validate(bad), sources)
    invalid = _proposal()
    invalid["edits"][0]["new"] = '"""'
    with pytest.raises(ValueError, match="invalid complete Python"):
        validate_scope(HallamProposal.model_validate(invalid), sources)


def test_schema_valid_scope_refusal_persists_only_bounded_hunk_metadata(repos):
    forge, hallam, forge_sha, target_sha = repos
    proposal = _proposal()
    proposal["rationale"] = "do not persist this rationale"
    proposal["edits"][1]["new"] = "    unrelated = True"
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=_body(proposal)))
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "TEST_INDUSTRY_REQUIREMENT_MISSING"
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    metadata = outcome["proposal_metadata"]
    assert outcome["refusal_reason"] == "TEST_INDUSTRY_REQUIREMENT_MISSING"
    assert outcome["proposal"] is None and outcome["output_digest"] is None
    assert [item["path"] for item in metadata] == list(HALLAM_PATHS)
    assert all(
        set(item) == {"path", "old_length", "old_sha256", "new_length", "new_sha256"}
        and isinstance(item["old_length"], int)
        and isinstance(item["new_length"], int)
        and len(item["old_sha256"]) == 64
        and len(item["new_sha256"]) == 64
        for item in metadata
    )
    persisted = (forge / ".agent" / "ledger" / f"{PACKET_ID}.jsonl").read_text(encoding="utf-8")
    assert "do not persist this rationale" not in persisted
    assert proposal["edits"][0]["old"] not in persisted
    assert proposal["edits"][0]["new"] not in persisted


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("context", "SCOPE_CONTEXT_INVALID"),
        ("cross_path", "SCOPE_CROSS_PATH_REWRITE"),
        ("api_invariant", "API_FILTER_INVARIANT_REMOVED"),
        ("api_requirement", "API_FILTER_REQUIREMENT_MISSING"),
        ("test_requirement", "TEST_INDUSTRY_REQUIREMENT_MISSING"),
    ],
)
def test_every_scope_validation_rule_has_an_allowlisted_reason_code(repos, mutation, reason):
    _, hallam, _, _ = repos
    proposal = _proposal()
    sources = {path: (hallam / path).read_text(encoding="utf-8") for path in HALLAM_PATHS}
    if mutation == "context":
        sources.pop(HALLAM_PATHS[1])
    elif mutation == "cross_path":
        proposal["edits"][0]["old"] = "apps/other.py"
    elif mutation == "api_invariant":
        proposal["edits"][0]["new"] = "!ind||o.industry?.includes(q)"
    elif mutation == "api_requirement":
        proposal["edits"][0]["new"] = "!ind||o.company.includes(q)||o.title.includes(q)"
    else:
        proposal["edits"][1]["new"] = "    unrelated = True"
    with pytest.raises(ValueError) as raised:
        validate_scope(HallamProposal.model_validate(proposal), sources)
    assert raised.value.reason_code == reason


def test_http_refusal_has_distinct_allowlisted_code_without_proposal_metadata(repos):
    forge, hallam, forge_sha, target_sha = repos
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(429, json={"secret": "do-not-store"})
            )
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "HTTP_STATUS_REFUSED"
    outcome = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload
    assert outcome["refusal_reason"] == "HTTP_STATUS_REFUSED"
    assert outcome["proposal_metadata"] is None
    assert "do-not-store" not in (forge / ".agent" / "ledger" / f"{PACKET_ID}.jsonl").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("which", ["forge", "hallam"])
def test_dirty_or_wrong_identity_refuses_before_request(repos, which):
    forge, hallam, forge_sha, target_sha = repos
    root, expected = (forge, forge_sha) if which == "forge" else (hallam, target_sha)
    (root / ("README.md" if which == "forge" else HALLAM_PATHS[0])).write_text(
        "dirty\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="not clean"):
        run_once(
            forge,
            hallam,
            forge_sha=expected if which == "forge" else forge_sha,
            target_sha=expected if which == "hallam" else target_sha,
            client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
        )


def test_malformed_output_and_interruption_are_fail_closed_without_retry(repos):
    forge, hallam, forge_sha, target_sha = repos
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_body({"wrong": "shape"}))
            )
        ),
    )
    assert result.status == "REFUSED"
    assert (
        LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload["billing"]
        == "UNKNOWN"
    )


def test_interrupted_append_claim_blocks_retry(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    monkeypatch.setattr(
        "scripts.external_trial_builder.os.fsync",
        lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    with pytest.raises(KeyboardInterrupt):
        run_once(
            forge,
            hallam,
            forge_sha=forge_sha,
            target_sha=target_sha,
            client=httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json=_body(_proposal()))
                )
            ),
        )
    assert (forge / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


def test_wrong_origin_refuses_before_request(repos):
    forge, hallam, forge_sha, target_sha = repos
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://example.invalid/wrong.git"],
        cwd=hallam,
        check=True,
    )
    with pytest.raises(RuntimeError, match="origin"):
        run_once(forge, hallam, forge_sha=forge_sha, target_sha=target_sha)


@pytest.mark.parametrize(
    "name,value,message",
    [("DEEPSEEK_API_KEY", None, "missing"), ("BUILDER_MODEL", "other-model", "BUILDER_MODEL")],
)
def test_missing_key_or_wrong_model_refuses_before_claim(repos, monkeypatch, name, value, message):
    forge, hallam, forge_sha, target_sha = repos
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=message):
        run_once(forge, hallam, forge_sha=forge_sha, target_sha=target_sha)
    assert not (forge / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


def test_oversized_request_refuses_before_claim(repos, monkeypatch):
    forge, hallam, forge_sha, target_sha = repos
    monkeypatch.setattr("scripts.external_trial_builder.MAX_REQUEST_BYTES", 100)
    with pytest.raises(RuntimeError, match="serialized request"):
        run_once(forge, hallam, forge_sha=forge_sha, target_sha=target_sha)
    assert not (forge / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


@pytest.mark.parametrize("kind", ["claim", "ledger"])
def test_preexisting_claim_or_ledger_blocks_retry(repos, kind):
    forge, hallam, forge_sha, target_sha = repos
    store = LedgerStore(forge / ".agent" / "ledger", PACKET_ID)
    store.receipts_path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "claim":
        store.receipts_path.with_suffix(".claim.json").write_text("{}", encoding="utf-8")
    else:
        store.receipts_path.write_text("partial", encoding="utf-8")
    with pytest.raises(RuntimeError, match="second run"):
        run_once(forge, hallam, forge_sha=forge_sha, target_sha=target_sha)


def test_hunks_must_be_unique_and_exact(repos):
    forge, hallam, *_ = repos
    proposal = HallamProposal.model_validate(_proposal())
    sources = {path: (hallam / path).read_text(encoding="utf-8") for path in HALLAM_PATHS}
    validate_scope(proposal, sources)
    missing = _proposal()
    missing["edits"][0]["old"] = "not present"
    with pytest.raises(ValueError, match="exactly once"):
        validate_scope(HallamProposal.model_validate(missing), sources)
    duplicated = _proposal()
    duplicated["edits"][1]["path"] = HALLAM_PATHS[0]
    with pytest.raises(ValueError, match="exactly the two"):
        HallamProposal.model_validate(duplicated)


def test_transport_interruption_is_unknown_once_and_keeps_durable_chain(repos):
    forge, hallam, forge_sha, target_sha = repos
    requests = 0

    def handler(_):
        nonlocal requests
        requests += 1
        raise httpx.ReadTimeout("interrupted")

    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert result.status in {"REFUSED", "UNKNOWN"}
    assert requests == 1
    store = LedgerStore(forge / ".agent" / "ledger", PACKET_ID)
    assert store.load().receipts[-1].payload["billing"] == "UNKNOWN"
    with pytest.raises(RuntimeError, match="second run"):
        run_once(forge, hallam, forge_sha=forge_sha, target_sha=target_sha)


def test_unread_response_digest_fails_closed_without_persisting_body(repos):
    forge, hallam, forge_sha, target_sha = repos
    response = httpx.Response(200, stream=httpx.ByteStream(b"hidden"))
    result = run_once(
        forge,
        hallam,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(transport=httpx.MockTransport(lambda _: response)),
    )
    assert result.status in {"REFUSED", "UNKNOWN"}
    diagnostic = LedgerStore(forge / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert isinstance(diagnostic["response_digest"], str)


def test_unread_response_digest_is_none_and_does_not_raise():
    class UnreadResponse:
        status_code = 200

        @property
        def content(self):
            raise httpx.ResponseNotRead

        def json(self):
            raise httpx.ResponseNotRead

    assert _diagnostic(UnreadResponse()) == {
        "http_status": 200,
        "response_digest": None,
        "latency_ms": None,
    }
