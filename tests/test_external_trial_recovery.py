from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from scripts import external_trial_finalize as finalize_runner
from scripts import external_trial_recovery as runner

FORGE_ROOT = Path(__file__).parents[1]
HALLAM_FIXTURE = FORGE_ROOT / "tests" / "fixtures" / "external_trial" / "hallam_pre_change"
FIXTURE_CANONICAL_SHA256 = {
    "apps/api/sabra_api/main.py": "f84d71e55fb81272c3aad96606a47528bdd60e51a965aa090b09affac51f93fc",
    "tests/test_api.py": "f9443f913f4d8ff3bf7ca623bc5bf7152c17e4629a5b11f8ceff6d7bbd3f7b59",
}
LESSON_ARTIFACT_CANONICAL_SHA256 = {
    "CANDIDATE.json": "11d0a682424fcece2a44b4c1d12e55fac7e9f3def2446b44676b78fc16165dda",
    "VALIDATED.json": "01bd1db99b1a18e20dbf0569019bdc34dde005a3e8f9bf488b0a8a7ce1d211ee",
}


def _canonical_fixture_digest(content: bytes) -> str:
    normalized = content.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sources() -> dict[str, str]:
    return {
        path: (HALLAM_FIXTURE / f"{path}.txt").read_text(encoding="utf-8")
        for path in runner.HALLAM_PATHS
    }


def _materialize_hallam(tmp_path: Path) -> Path:
    root = tmp_path / "hallam"
    for relative_path, content in sources().items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_pre_change_fixture_is_exact_and_modules_do_not_read_live_trial() -> None:
    for relative_path, expected_digest in FIXTURE_CANONICAL_SHA256.items():
        snapshot = HALLAM_FIXTURE / f"{relative_path}.txt"
        assert _canonical_fixture_digest(snapshot.read_bytes()) == expected_digest

    forbidden = "/".join(("AppData", "Local", "ForgeAgent", "external-trials")).lower()
    for module_name in ("test_external_trial_recovery.py", "test_external_trial_finalize.py"):
        module_text = (FORGE_ROOT / "tests" / module_name).read_text(encoding="utf-8")
        assert forbidden not in module_text.replace("\\", "/").lower()


def test_fixture_digest_accepts_checkout_line_endings_but_rejects_content_change() -> None:
    for relative_path, expected_digest in FIXTURE_CANONICAL_SHA256.items():
        snapshot = HALLAM_FIXTURE / f"{relative_path}.txt"
        lf_content = snapshot.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        crlf_content = lf_content.replace(b"\n", b"\r\n")

        assert _canonical_fixture_digest(lf_content) == expected_digest
        assert _canonical_fixture_digest(crlf_content) == expected_digest
        assert _canonical_fixture_digest(lf_content + b"# semantic change\n") != expected_digest


def test_validated_lesson_is_reconstructed_retrieved_and_applied() -> None:
    store, lesson, retrieval, candidate, application = runner._validated_lesson(FORGE_ROOT)
    assert lesson.is_applicable
    assert retrieval.lesson_ids == (runner.LESSON_ID,)
    assert candidate.digest == runner.LESSON_DIGEST
    assert application.changed_strategy
    assert application in store.applications


def test_reconstructed_decision_uses_full_accepted_evidence() -> None:
    store, lesson, _, _, _ = runner._validated_lesson(FORGE_ROOT)
    decision = lesson.decision
    assert decision is not None
    assert decision.evidence_digest == (
        "39658905d5528bf643c1d4218751b99fc047d25401f6c3163a780faa68d29ef2"
    )
    assert store.lessons[runner.LESSON_ID].is_applicable


def test_source_lesson_digest_mismatch_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(runner, "LESSON_DIGEST", "0" * 64)
    with pytest.raises(runner.RefusalError, match="authority|digest"):
        runner._validated_lesson(FORGE_ROOT)


def _lesson_artifact_root(tmp_path: Path) -> Path:
    root = tmp_path / "forge"
    target = root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001"
    target.mkdir(parents=True)
    for name in ("CANDIDATE.json", "VALIDATED.json"):
        (target / name).write_bytes(
            (FORGE_ROOT / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / name).read_bytes()
        )
    return root


def _rewrite_artifact(root: Path, name: str, content: bytes) -> None:
    (root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / name).write_bytes(content)


@pytest.mark.parametrize("runner_module", [runner, finalize_runner])
@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"])
def test_lesson_artifacts_accept_only_lf_or_crlf_representations(
    tmp_path: Path, runner_module, line_ending: bytes
) -> None:
    root = _lesson_artifact_root(tmp_path)
    for name, expected_digest in LESSON_ARTIFACT_CANONICAL_SHA256.items():
        path = root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / name
        lf = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        content = lf if line_ending == b"\n" else lf.replace(b"\n", b"\r\n")
        _rewrite_artifact(root, name, content)
        assert runner_module._canonical_artifact_digest(content) == expected_digest

    assert runner_module._validated_lesson(root)[1].is_applicable


@pytest.mark.parametrize("runner_module", [runner, finalize_runner])
@pytest.mark.parametrize(
    "artifact, mutate",
    [
        (
            "CANDIDATE.json",
            lambda raw: raw.replace(b"FORGE-EXT-LESSON-001", b"FORGE-EXT-LESSON-099", 1),
        ),
        ("CANDIDATE.json", lambda raw: raw.replace(b"{", b"{ ", 1)),
        ("VALIDATED.json", lambda raw: json.dumps(json.loads(raw), sort_keys=True).encode("utf-8")),
        ("VALIDATED.json", lambda raw: raw.replace(b"39658905", b"00000000", 1)),
        ("CANDIDATE.json", lambda raw: b"\xff" + raw[1:]),
    ],
    ids=["value", "whitespace", "reordered-and-reformatted", "legacy-evidence", "invalid-utf8"],
)
def test_lesson_artifact_mutations_fail_closed(
    tmp_path: Path, runner_module, artifact: str, mutate
) -> None:
    root = _lesson_artifact_root(tmp_path)
    path = root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / artifact
    _rewrite_artifact(root, artifact, mutate(path.read_bytes()))

    with pytest.raises(runner_module.RefusalError, match="artifacts|artifact|canonical"):
        runner_module._validated_lesson(root)


@pytest.mark.parametrize("artifact", ["CANDIDATE.json", "VALIDATED.json"])
def test_missing_lesson_artifact_fails_before_any_claim_or_ledger(tmp_path, artifact) -> None:
    root = _lesson_artifact_root(tmp_path)
    (root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / artifact).unlink()
    with pytest.raises(runner.RefusalError, match="artifacts"):
        runner._validated_lesson(root)
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-002.claim.json").exists()
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-002.jsonl").exists()


@pytest.mark.parametrize("artifact", ["CANDIDATE.json", "VALIDATED.json"])
def test_mutated_lesson_artifact_fails_before_any_claim_or_ledger(tmp_path, artifact) -> None:
    root = _lesson_artifact_root(tmp_path)
    path = root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / artifact
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(runner.RefusalError, match="artifact"):
        runner._validated_lesson(root)
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-002.claim.json").exists()
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-002.jsonl").exists()


def test_retrieval_miss_fails_closed(monkeypatch) -> None:
    original = runner.LessonStore.retrieve
    monkeypatch.setattr(
        runner.LessonStore,
        "retrieve",
        lambda self, packet_id, query_signature: original(
            self, packet_id, "unrelated failure signature"
        ),
    )
    with pytest.raises(runner.RefusalError, match="not retrieved"):
        runner._validated_lesson(FORGE_ROOT)


def test_changed_strategy_is_derived_and_identical_strategy_is_rejected() -> None:
    _, _, retrieval, _, application = runner._validated_lesson(FORGE_ROOT)
    assert application.changed_strategy is True
    assert application.strategy_without_lesson != application.strategy_with_lesson
    assert application.retrieval_digest == retrieval.digest


@pytest.mark.parametrize(
    "selection",
    [
        runner.RecoverySelection(
            fields=["company", "title"],
            positive_case="industry_only",
            negative_case="unrelated_industry",
        ),
        runner.RecoverySelection(
            fields=["company", "title", "industry", "location"],
            positive_case="industry_only",
            negative_case="unrelated_industry",
        ),
    ],
)
def test_malicious_or_unbounded_field_selection_is_refused(selection) -> None:
    with pytest.raises(runner.RefusalError, match="selection"):
        runner._deterministic_edits(selection, sources())


def test_deterministic_edits_are_exactly_two_allowlisted_changes() -> None:
    selection = runner.RecoverySelection(
        fields=["industry", "company", "title"],
        positive_case="industry_only",
        negative_case="unrelated_industry",
    )
    edits = runner._deterministic_edits(selection, sources())
    assert [item["path"] for item in edits] == list(runner.HALLAM_PATHS)
    assert "o.industry" in edits[0]["new"]
    assert "industry_only" in edits[1]["new"]
    assert "unrelated_industry" in edits[1]["new"]
    patched = sources()
    for edit in edits:
        assert patched[edit["path"]].count(edit["old"]) == 1
        patched[edit["path"]] = patched[edit["path"]].replace(edit["old"], edit["new"], 1)
    assert (
        "`${{o.company}} ${{o.title}} ${{o.industry}}`.toLowerCase().includes(ind)"
        in patched[runner.HALLAM_PATHS[0]]
    )
    assert "industry_only positive" in patched[runner.HALLAM_PATHS[1]]
    assert "unrelated_industry negative" in patched[runner.HALLAM_PATHS[1]]
    compile(patched[runner.HALLAM_PATHS[1]], "tests/test_api.py", "exec")


def test_deterministic_edits_refuse_duplicate_or_wrong_source() -> None:
    bad = sources()
    bad[runner.HALLAM_PATHS[0]] = bad[runner.HALLAM_PATHS[0]].replace(
        "`${{o.company}} ${{o.title}}`", "`${{o.industry}} ${{o.title}}`", 1
    )
    selection = runner.RecoverySelection(
        fields=["industry", "company", "title"],
        positive_case="industry_only",
        negative_case="unrelated_industry",
    )
    with pytest.raises(runner.RefusalError, match="hunk|shape"):
        runner._deterministic_edits(selection, bad)


@pytest.mark.parametrize(
    "value", ["secret-token-123456", {"nested": "secret-token-123456"}, ["secret-token-123456"]]
)
def test_secrets_are_detected_at_envelope_and_inner_levels(monkeypatch, value) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-token-123456")
    assert runner._contains_secret(value, runner._secrets())


def test_secret_scan_detects_unicode_escaped_inner_value(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-token-123456")
    encoded = json.dumps("secret-token-123456").replace("-", "\\u002d")
    assert runner._contains_secret(encoded, runner._secrets())


def test_raw_secret_bytes_are_rejected_before_digesting(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-token-123456")
    assert runner._contains_secret_bytes(
        b'{"ignored_field":"secret-token-123456"}', runner._secrets()
    )
    assert not runner._contains_secret_bytes(b'{"safe":"value"}', runner._secrets())


def test_parsed_response_scans_utf16_and_utf32_json_representations(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-token-123456")
    body = json.dumps({"nested": {"credential": "secret-token-123456"}})
    for encoding in ("utf-16", "utf-32"):
        with pytest.raises(runner.RefusalError, match="configured secret"):
            runner._parsed_safe_response(body.encode(encoding), runner._secrets())


def test_lossless_response_scan_preserves_duplicate_key_values(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-token-123456")
    body = b'{"credential":"secret-token-123456","credential":"safe"}'
    with pytest.raises(runner.RefusalError, match="configured secret"):
        runner._parsed_safe_response(body, runner._secrets())


def test_provider_usage_and_malformed_response_fail_closed() -> None:
    assert runner.RefusalError.CODES
    with pytest.raises(runner.RefusalError):
        raise runner.RefusalError("PROVIDER_USAGE_INVALID", "invalid")


def test_prompt_and_request_bounds_are_bounded(tmp_path) -> None:
    prompt = runner._prompt(_materialize_hallam(tmp_path))
    assert len(prompt.encode()) <= 8_000
    assert len(prompt.encode()) < runner.MAX_REQUEST_BYTES


def test_wrong_identity_is_refused(tmp_path) -> None:
    with pytest.raises(runner.RefusalError, match="identity"):
        runner._identity(tmp_path, "wrong", "Forge", runner.FORGE_ORIGIN)


def _run_roots(tmp_path: Path) -> tuple[Path, Path]:
    forge_root = _lesson_artifact_root(tmp_path)
    target_root = _materialize_hallam(tmp_path)
    return forge_root, target_root


def _prepare_run(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    forge_root, target_root = _run_roots(tmp_path)
    monkeypatch.setattr(runner, "_identity", lambda *args: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-0123456789")
    monkeypatch.setenv("BUILDER_MODEL", runner.MODEL)
    return forge_root, target_root


def _intent_payload(forge_root: Path) -> dict:
    ledger = runner.LedgerStore(forge_root / ".agent" / "ledger", runner.PACKET_ID).load()
    return next(receipt.payload for receipt in ledger.receipts if receipt.event == "CALL_INTENT")


def test_run_once_success_persists_intent_before_dispatch_and_binds_transmitted_bound(
    monkeypatch, tmp_path
) -> None:
    forge_root, target_root = _prepare_run(monkeypatch, tmp_path)
    dispatched: list[dict] = []

    class SuccessfulClient:
        def post(self, *args, **kwargs):
            intent = _intent_payload(forge_root)
            assert intent["output_token_bound"] == runner.MAX_OUTPUT_TOKENS
            assert intent["conservative_estimate_usd"] == runner._conservative_estimate(
                runner.MAX_OUTPUT_TOKENS
            )
            payload = json.loads(kwargs["content"])
            assert payload["max_tokens"] == intent["output_token_bound"]
            dispatched.append(payload)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "fields": ["company", "title", "industry"],
                                        "positive_case": "industry_only",
                                        "negative_case": "unrelated_industry",
                                    }
                                )
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 17, "completion_tokens": 13},
                },
            )

    result = runner.run_once(
        forge_root,
        target_root,
        forge_sha="forge-test",
        target_sha="hallam-test",
        client=SuccessfulClient(),
    )

    assert result.status == "SUCCEEDED"
    assert result.receipt is not None
    assert result.receipt.input_tokens == 17
    assert result.receipt.output_tokens == 13
    assert len(dispatched) == 1
    ledger = runner.LedgerStore(forge_root / ".agent" / "ledger", runner.PACKET_ID).load()
    assert [receipt.event for receipt in ledger.receipts] == [
        "CALL_INTENT",
        "PROVIDER_DIAGNOSTIC",
        "CALL_OUTCOME",
    ]
    outcome = ledger.receipts[-1].payload
    assert outcome["status"] == "SUCCEEDED"
    assert outcome["provider_receipt"]["model"] == runner.MODEL
    with pytest.raises(RuntimeError, match="second run"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
            client=SuccessfulClient(),
        )


def test_run_once_transport_interruption_is_unknown_with_durable_claim_and_retry_block(
    monkeypatch, tmp_path
) -> None:
    forge_root, target_root = _prepare_run(monkeypatch, tmp_path)

    class BrokenClient:
        def post(self, *args, **kwargs):
            assert _intent_payload(forge_root)["output_token_bound"] == runner.MAX_OUTPUT_TOKENS
            raise httpx.ReadTimeout("interrupted")

    result = runner.run_once(
        forge_root,
        target_root,
        forge_sha="forge-test",
        target_sha="hallam-test",
        client=BrokenClient(),
    )

    assert result.status == "UNKNOWN"
    assert result.error_type == "TRANSPORT_UNKNOWN"
    claim = forge_root / ".agent" / "ledger" / "FORGE-EXT-002.claim.json"
    assert claim.is_file()
    ledger = runner.LedgerStore(forge_root / ".agent" / "ledger", runner.PACKET_ID).load()
    assert ledger.receipts[-1].event == "CALL_OUTCOME"
    assert ledger.receipts[-1].payload["status"] == "UNKNOWN"
    with pytest.raises(RuntimeError, match="second run"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
            client=BrokenClient(),
        )


def _credential_bearing_response(secret: str, location: str) -> dict:
    selection = {
        "fields": ["company", "title", "industry"],
        "positive_case": "industry_only",
        "negative_case": "unrelated_industry",
    }
    if location == "schema_valid_extra":
        selection["credential"] = secret
    body: dict = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps(selection)},
            }
        ],
        "usage": {"prompt_tokens": 17, "completion_tokens": 13},
    }
    if location == "ignored_extra":
        body["credential"] = secret
    if location == "nested_encoded":
        body["metadata"] = {"encoded_credential": secret.replace("-", "\\u002d")}
    return body


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
@pytest.mark.parametrize("location", ["schema_valid_extra", "ignored_extra", "nested_encoded"])
def test_run_once_rejects_encoded_credential_before_digest_or_persistence(
    monkeypatch, tmp_path, encoding, location
) -> None:
    forge_root, target_root = _prepare_run(monkeypatch, tmp_path)
    secret = "test-key-0123456789"

    class CredentialClient:
        def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                content=json.dumps(_credential_bearing_response(secret, location)).encode(encoding),
            )

    result = runner.run_once(
        forge_root,
        target_root,
        forge_sha="forge-test",
        target_sha="hallam-test",
        client=CredentialClient(),
    )

    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    assert result.selection is None
    assert result.receipt is None
    ledger = runner.LedgerStore(forge_root / ".agent" / "ledger", runner.PACKET_ID).load()
    outcome = ledger.receipts[-1].payload
    assert outcome["status"] == "REFUSED"
    assert outcome["diagnostic"]["response_digest"] is None
    receipts_path = forge_root / ".agent" / "ledger" / "FORGE-EXT-002.jsonl"
    assert secret not in receipts_path.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="second run"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
            client=CredentialClient(),
        )


def _duplicate_key_credential_response(secret: str, location: str) -> str:
    selection = {
        "fields": ["company", "title", "industry"],
        "positive_case": "industry_only",
        "negative_case": "unrelated_industry",
    }
    if location == "envelope":
        return (
            '{"credential":"'
            + secret
            + '","credential":"safe","choices":[{"finish_reason":"stop","message":{"content":'
            + json.dumps(json.dumps(selection))
            + '}}],"usage":{"prompt_tokens":17,"completion_tokens":13}}'
        )
    nested_selection = '{"credential":"' + secret + '","credential":"safe",'
    nested_selection += json.dumps(selection, separators=(",", ":"))[1:]
    body = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": nested_selection},
            }
        ],
        "usage": {"prompt_tokens": 17, "completion_tokens": 13},
    }
    return json.dumps(body)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
@pytest.mark.parametrize("location", ["envelope", "nested_proposal"])
def test_run_once_rejects_earlier_duplicate_key_secret_before_persistence(
    monkeypatch, tmp_path, encoding, location
) -> None:
    forge_root, target_root = _prepare_run(monkeypatch, tmp_path)
    secret = "test-key-0123456789"

    class DuplicateKeyClient:
        def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                content=_duplicate_key_credential_response(secret, location).encode(encoding),
            )

    result = runner.run_once(
        forge_root,
        target_root,
        forge_sha="forge-test",
        target_sha="hallam-test",
        client=DuplicateKeyClient(),
    )

    assert result.status == "REFUSED"
    assert result.error_type == "SENSITIVE_OUTPUT_REFUSED"
    assert result.selection is None
    assert result.receipt is None
    ledger = runner.LedgerStore(forge_root / ".agent" / "ledger", runner.PACKET_ID).load()
    outcome = ledger.receipts[-1].payload
    assert outcome["status"] == "REFUSED"
    assert outcome["diagnostic"]["response_digest"] is None
    receipts_path = forge_root / ".agent" / "ledger" / "FORGE-EXT-002.jsonl"
    assert secret not in receipts_path.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="second run"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
            client=DuplicateKeyClient(),
        )
