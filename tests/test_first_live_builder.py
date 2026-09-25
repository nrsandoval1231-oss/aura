from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import httpx
import pytest

from forge.ledger_store import LedgerStore
from scripts.first_live_builder import PACKET_ID, run_once, verify_repository_state

README = "# Forge\n\n## Credentials\n\nConfigure the builder.\n"


def _body(payload: dict, *, finish_reason: str = "stop") -> dict:
    return {
        "choices": [
            {
                "message": {"content": json.dumps(payload)},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 80},
    }


def _proposal() -> dict:
    return {
        "path": "README.md",
        "section": "Credentials",
        "replacement": "Set BUILDER_MODEL to a DeepSeek API model ID such as deepseek-flash.",
    }


@pytest.fixture(autouse=True)
def _credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("BUILDER_MODEL", "deepseek-flash")
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "forge-tests@example.invalid"],
        ["git", "config", "user.name", "Forge Tests"],
        ["git", "add", "README.md"],
        ["git", "commit", "-qm", "fixture"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True, capture_output=True)


def _base_sha(tmp_path):
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run(tmp_path, handler):
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    return run_once(
        tmp_path,
        base_sha=_base_sha(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_success_persists_intent_before_request_and_outcome_after(tmp_path):
    seen = {"requests": 0, "intent_was_durable": False}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["requests"] += 1
        store = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID)
        loaded = store.load()
        seen["intent_was_durable"] = [r.event for r in loaded.receipts] == ["CALL_INTENT"]
        return httpx.Response(200, json=_body(_proposal()))

    result = _run(tmp_path, handler)

    assert result.status == "SUCCEEDED"
    assert result.proposal is not None
    assert seen == {"requests": 1, "intent_was_durable": True}
    ledger = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID).load()
    assert [receipt.event for receipt in ledger.receipts] == ["CALL_INTENT", "CALL_OUTCOME"]
    assert ledger.receipts[1].payload["status"] == "SUCCEEDED"
    assert ledger.receipts[1].payload["effect"] == "PROPOSAL_ONLY"
    assert ledger.receipts[1].payload["proposal"] == _proposal()
    assert ledger.receipts[1].payload["proposal_digest"]


def test_existing_stream_refuses_second_invocation_without_new_request(tmp_path):
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    first = _run(tmp_path, handler)
    store = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID)
    before = store.receipts_path.read_bytes(), store.checkpoint_path.read_bytes()

    with pytest.raises(RuntimeError, match="already exists"):
        run_once(
            tmp_path,
            base_sha=_base_sha(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    assert first.status == "SUCCEEDED"
    assert requests == 1
    assert (store.receipts_path.read_bytes(), store.checkpoint_path.read_bytes()) == before


@pytest.mark.parametrize("partial", ["receipts", "checkpoint"])
def test_partial_ledger_sidecar_refuses_without_overwrite(tmp_path, partial):
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    store = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID)
    target = store.receipts_path if partial == "receipts" else store.checkpoint_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("preserve me", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        run_once(
            tmp_path,
            base_sha=_base_sha(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200))),
        )

    assert target.read_text(encoding="utf-8") == "preserve me"


def test_repository_identity_requires_exact_head_and_clean_state(tmp_path, monkeypatch):
    class Result:
        def __init__(self, stdout):
            self.stdout = stdout

    outputs = iter(["exact-head\n", ""])
    monkeypatch.setattr(
        "scripts.first_live_builder.subprocess.run",
        lambda *args, **kwargs: Result(next(outputs)),
    )
    verify_repository_state(tmp_path, "exact-head")


def test_malformed_structured_output_is_unknown_without_retry(tmp_path):
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body({"wrong": "shape"}))

    result = _run(tmp_path, handler)

    assert result.status == "UNKNOWN"
    assert result.error_type == "SchemaInvalidError"
    assert requests == 1
    ledger = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID).load()
    assert ledger.receipts[1].payload["status"] == "UNKNOWN"


def test_transport_failure_is_unknown_without_retry(tmp_path):
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ReadTimeout("simulated interruption")

    result = _run(tmp_path, handler)

    assert result.status == "UNKNOWN"
    assert result.error_type == "ProviderError"
    assert requests == 1
    ledger = LedgerStore(tmp_path / ".agent" / "ledger", PACKET_ID).load()
    assert ledger.receipts[1].payload["billing"] == "UNKNOWN"


def test_scope_violation_is_refused_and_never_applied(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_body(
                {
                    "path": "src/forge/trust_kernel.py",
                    "section": "Credentials",
                    "replacement": "BUILDER_MODEL=deepseek-flash",
                }
            ),
        )

    result = _run(tmp_path, handler)

    assert result.status == "REFUSED"
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == README


def test_oversized_prompt_refuses_before_intent_or_request(tmp_path):
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    with pytest.raises(RuntimeError, match="byte bound"):
        run_once(
            tmp_path,
            base_sha=_base_sha(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            prompt="x" * 7520,
        )

    assert requests == 0
    assert not (tmp_path / ".agent" / "ledger" / f"{PACKET_ID}.jsonl").exists()


def test_wrong_head_and_dirty_worktree_refuse_before_request(tmp_path):
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    with pytest.raises(RuntimeError, match="HEAD"):
        run_once(
            tmp_path,
            base_sha="wrong",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert requests == 0
    assert not (tmp_path / ".agent" / "ledger" / f"{PACKET_ID}.claim.json").exists()

    (tmp_path / "README.md").write_text(README + "dirty\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="clean"):
        run_once(
            tmp_path,
            base_sha=_base_sha(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert requests == 0


def test_interrupted_claim_refuses_retry(tmp_path):
    claim = tmp_path / ".agent" / "ledger" / f"{PACKET_ID}.claim.json"
    claim.parent.mkdir(parents=True)
    claim.write_text('{"status":"CLAIMED"}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="claim or ledger"):
        run_once(tmp_path, base_sha=_base_sha(tmp_path))


def test_interrupted_claim_fsync_remains_and_blocks_retry(tmp_path, monkeypatch):
    def interrupted_fsync(_descriptor):
        raise KeyboardInterrupt("simulated claim interruption")

    monkeypatch.setattr("scripts.first_live_builder.os.fsync", interrupted_fsync)
    with pytest.raises(KeyboardInterrupt):
        run_once(tmp_path, base_sha=_base_sha(tmp_path))

    claim = tmp_path / ".agent" / "ledger" / f"{PACKET_ID}.claim.json"
    assert claim.exists()

    monkeypatch.undo()
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    with pytest.raises(RuntimeError, match="claim or ledger"):
        run_once(
            tmp_path,
            base_sha=_base_sha(tmp_path),
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
    assert requests == 0


def test_concurrent_starts_have_at_most_one_handler_request(tmp_path):
    requests = 0
    lock = Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        with lock:
            requests += 1
        return httpx.Response(200, json=_body(_proposal()))

    def start():
        try:
            return run_once(
                tmp_path,
                base_sha=_base_sha(tmp_path),
                client=httpx.Client(transport=httpx.MockTransport(handler)),
            )
        except RuntimeError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: start(), range(2)))

    assert requests == 1
    assert [result.status for result in results if hasattr(result, "status")].count(
        "SUCCEEDED"
    ) == 1
