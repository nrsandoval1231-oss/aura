from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import pytest

from forge.ledger_store import LedgerStore
from scripts.sentinel_builder import (
    PACKET_ID,
    PROMPT,
    SYSTEM_PROMPT,
    _digest,
    _request_prompt,
    run_once,
)


def _commit(root: Path, files: dict[str, str]) -> str:
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
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("BUILDER_MODEL", "deepseek-flash")


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path, str, str]:
    forge = tmp_path / "forge"
    target = tmp_path / "sentinal"
    forge.mkdir()
    target.mkdir()
    forge_sha = _commit(forge, {"README.md": "forge\n"})
    target_sha = _commit(
        target,
        {
            "scripts/ci_local.py": (
                "import subprocess\n\n"
                "def run_step(command, timeout=30):\n"
                "    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)\n"
                "    return completed.returncode, completed.stdout, completed.stderr\n"
            ),
            "tests/test_ci_local.py": (
                "def test_run_step_preserves_timeout():\n"
                "    assert run_step('echo ok') == 'echo ok'\n"
            ),
        },
    )
    return forge, target, forge_sha, target_sha


def _body(payload: dict, *, finish_reason: str = "stop") -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 80},
    }


def _proposal() -> dict:
    return {
        "path": "scripts/ci_local.py",
        "function": "run_step",
        "replacement": "def run_step(command):\n    return command\n",
        "rationale": "Use the first usable shell while preserving execution semantics.",
    }


def _run(repos, handler):
    forge, target, forge_sha, target_sha = repos
    return run_once(
        forge,
        target,
        forge_sha=forge_sha,
        target_sha=target_sha,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_valid_call_persists_intent_before_request_and_never_mutates_target(repos):
    seen = {"requests": 0, "intent": False}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["requests"] += 1
        ledger = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load()
        seen["intent"] = [item.event for item in ledger.receipts] == ["CALL_INTENT"]
        return httpx.Response(200, json=_body(_proposal()))

    before = (repos[1] / "scripts" / "ci_local.py").read_bytes()
    result = _run(repos, handler)
    assert result.status == "SUCCEEDED"
    assert result.proposal is not None
    assert seen == {"requests": 1, "intent": True}
    assert (repos[1] / "scripts" / "ci_local.py").read_bytes() == before
    assert [
        r.event for r in LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts
    ] == ["CALL_INTENT", "PROVIDER_DIAGNOSTIC", "CALL_OUTCOME"]
    receipts = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts
    assert [(item.state_before, item.state_after) for item in receipts] == [
        ("INITIALIZING", "CALLING"),
        ("CALLING", "RECEIVED"),
        ("RECEIVED", "PROPOSED"),
    ]


def test_prompt_contains_complete_function_and_intent_binds_exact_wire_payload(repos):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=_body(_proposal()))

    _run(repos, handler)
    prompt = _request_prompt(repos[1], PROMPT)
    assert "timeout=timeout" in prompt
    assert "completed.stderr" in prompt
    ledger = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load()
    intent = ledger.receipts[0].payload
    assert intent["prompt_digest"] == _digest(prompt)
    assert intent["wire_payload_digest"] == _digest(seen["payload"])
    assert intent["serialized_request_bytes"] == len(
        json.dumps(seen["payload"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    assert seen["payload"]["messages"][1]["content"] == prompt
    assert seen["payload"]["messages"][0]["content"].startswith(SYSTEM_PROMPT)
    assert seen["payload"]["thinking"] == {"type": "disabled"}


def test_duplicate_claim_and_reload_state_block_second_call(repos):
    _run(repos, lambda _: httpx.Response(200, json=_body(_proposal())))
    with pytest.raises(RuntimeError, match="second run"):
        _run(repos, lambda _: httpx.Response(200, json=_body(_proposal())))


@pytest.mark.parametrize("which", ["forge", "target"])
def test_identity_or_dirty_state_refuses_before_request(repos, which):
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    forge, target, forge_sha, target_sha = repos
    if which == "forge":
        (forge / "README.md").write_text("dirty\n", encoding="utf-8")
        expected = forge_sha
    else:
        (target / "scripts" / "ci_local.py").write_text("dirty\n", encoding="utf-8")
        expected = target_sha
    with pytest.raises(RuntimeError, match="not clean"):
        run_once(
            forge,
            target,
            forge_sha=expected if which == "forge" else forge_sha,
            target_sha=expected if which == "target" else target_sha,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert requests == 0


def test_scope_refusal_is_recorded_and_target_unchanged(repos):
    before = (repos[1] / "scripts" / "ci_local.py").read_bytes()
    result = _run(
        repos,
        lambda _: httpx.Response(
            200,
            json=_body(
                {
                    **_proposal(),
                    "replacement": "def run_step(command):\n    return tests/ci_local.py\n",
                }
            ),
        ),
    )
    assert result.status == "REFUSED"
    assert result.error_type == "ValueError"
    assert (repos[1] / "scripts" / "ci_local.py").read_bytes() == before
    assert (
        LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts[-1].payload["status"]
        == "REFUSED"
    )


def test_malformed_model_output_is_unknown_and_not_retried(repos):
    result = _run(repos, lambda _: httpx.Response(200, json=_body({"wrong": "shape"})))
    assert result.status == "REFUSED"
    assert result.error_type == "SchemaInvalidError"


def test_transport_interruption_is_unknown_and_not_retried(repos):
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("interrupted")

    result = _run(repos, handler)
    assert result.status == "UNKNOWN"
    assert result.error_type == "ReadTimeout"
    assert (
        LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID)
        .load()
        .receipts[-1]
        .payload["billing"]
        == "UNKNOWN"
    )
    receipts = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts
    assert [(item.state_before, item.state_after) for item in receipts] == [
        ("INITIALIZING", "CALLING"),
        ("CALLING", "UNKNOWN"),
        ("UNKNOWN", "UNKNOWN"),
    ]


def test_non_stop_finish_and_usage_are_durable_before_refusal(repos):
    result = _run(
        repos, lambda _: httpx.Response(200, json=_body(_proposal(), finish_reason="length"))
    )
    assert result.status == "REFUSED"
    diagnostic = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert diagnostic["http_status"] == 200
    assert diagnostic["finish_reason"] == "length"
    assert diagnostic["usage"] == {"prompt_tokens": 40, "completion_tokens": 80}
    assert "test-key" not in str(diagnostic)


def test_provider_response_id_is_whitelisted_without_copying_body_fields(repos):
    payload = _body(_proposal())
    payload.update({"id": "chatcmpl-safe-123", "secret": "must-not-persist"})
    result = _run(repos, lambda _: httpx.Response(200, json=payload))
    assert result.status == "SUCCEEDED"
    diagnostic = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert diagnostic["provider_response_id"] == "chatcmpl-safe-123"
    assert "secret" not in diagnostic
    assert "must-not-persist" not in str(diagnostic)


def test_http_refusal_records_status_and_body_digest_without_secret(repos):
    response = httpx.Response(429, content=b'{"error":"rate limited"}')
    result = _run(repos, lambda _: response)
    assert result.status == "REFUSED"
    diagnostic = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts[1].payload
    assert diagnostic["http_status"] == 429
    assert diagnostic["response_digest"] == _digest(b'{"error":"rate limited"}')
    assert "rate limited" not in str(diagnostic)
    receipts = LedgerStore(repos[0] / ".agent" / "ledger", PACKET_ID).load().receipts
    assert [(item.state_before, item.state_after) for item in receipts] == [
        ("INITIALIZING", "CALLING"),
        ("CALLING", "RECEIVED"),
        ("RECEIVED", "REFUSED"),
    ]


def test_prior_reported_spend_counts_against_cumulative_cap_before_claim(repos, monkeypatch):
    monkeypatch.setattr("scripts.sentinel_builder.OWNER_REPORTED_PRIOR_SPEND_USD", 14.99)
    with pytest.raises(RuntimeError, match="cumulative"):
        _run(repos, lambda _: httpx.Response(200, json=_body(_proposal())))
    assert not (repos[0] / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


def test_request_bound_refuses_before_claim_or_request(repos):
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    with pytest.raises(RuntimeError, match="context exceeds"):
        run_once(
            repos[0],
            repos[1],
            forge_sha=repos[2],
            target_sha=repos[3],
            prompt="x" * 12000,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert requests == 0
    assert not (repos[0] / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


def test_missing_credential_refuses_before_claim_or_request(repos, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    with pytest.raises(RuntimeError, match="missing"):
        _run(repos, lambda _: httpx.Response(200, json=_body(_proposal())))
    assert not (repos[0] / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()


def test_spend_bound_refuses_when_conservative_estimate_is_too_high(repos, monkeypatch):
    monkeypatch.setattr("scripts.sentinel_builder.MAX_OUTPUT_TOKENS", 2_000_000)
    with pytest.raises(RuntimeError, match="cumulative"):
        run_once(
            repos[0],
            repos[1],
            forge_sha=repos[2],
            target_sha=repos[3],
            client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
        )
