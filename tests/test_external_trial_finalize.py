from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts import external_trial_finalize as runner

FORGE_ROOT = Path(__file__).parents[1]
HALLAM_FIXTURE = FORGE_ROOT / "tests" / "fixtures" / "external_trial" / "hallam_pre_change"
LESSON_ARTIFACT_CANONICAL_SHA256 = {
    "CANDIDATE.json": "11d0a682424fcece2a44b4c1d12e55fac7e9f3def2446b44676b78fc16165dda",
    "VALIDATED.json": "01bd1db99b1a18e20dbf0569019bdc34dde005a3e8f9bf488b0a8a7ce1d211ee",
}


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


def test_canonical_lesson_hashes_are_pinned_separately_from_legacy_evidence() -> None:
    artifact_root = FORGE_ROOT / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001"
    for name, expected_digest in LESSON_ARTIFACT_CANONICAL_SHA256.items():
        raw = (artifact_root / name).read_bytes()
        lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        assert runner._canonical_artifact_digest(lf) == expected_digest
        assert runner._canonical_artifact_digest(crlf) == expected_digest
    assert (
        json.loads((artifact_root / "VALIDATED.json").read_bytes())["decision"]["evidence_digest"]
        == "39658905d5528bf643c1d4218751b99fc047d25401f6c3163a780faa68d29ef2"
    )


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


@pytest.mark.parametrize("artifact", ["CANDIDATE.json", "VALIDATED.json"])
def test_missing_lesson_artifact_fails_before_any_claim_or_ledger(tmp_path, artifact) -> None:
    root = _lesson_artifact_root(tmp_path)
    (root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / artifact).unlink()
    with pytest.raises(runner.RefusalError, match="artifacts"):
        runner._validated_lesson(root)
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-003.claim.json").exists()
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-003.jsonl").exists()


@pytest.mark.parametrize("artifact", ["CANDIDATE.json", "VALIDATED.json"])
def test_mutated_lesson_artifact_fails_before_any_claim_or_ledger(tmp_path, artifact) -> None:
    root = _lesson_artifact_root(tmp_path)
    path = root / ".agent" / "artifacts" / "FORGE-EXT-LESSON-001" / artifact
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(runner.RefusalError, match="artifact"):
        runner._validated_lesson(root)
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-003.claim.json").exists()
    assert not (root / ".agent" / "ledger" / "FORGE-EXT-003.jsonl").exists()


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


def test_malicious_decision_is_refused() -> None:
    selection = runner.FinalizeSelection.model_construct(
        decision="exclude_industry",
        positive_case="industry_only",
        negative_case="unrelated_industry",
    )
    with pytest.raises(runner.RefusalError, match="selection"):
        runner._deterministic_edits(selection, sources())


def test_selection_rejects_unallowlisted_fields() -> None:
    with pytest.raises(runner.ValidationError):
        runner.FinalizeSelection.model_validate(
            {
                "decision": "include_industry",
                "positive_case": "industry_only",
                "negative_case": "unrelated_industry",
                "path": "apps/api/sabra_api/main.py",
            }
        )


def test_deterministic_edits_are_exactly_two_allowlisted_changes() -> None:
    selection = runner.FinalizeSelection(
        decision="include_industry",
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
    selection = runner.FinalizeSelection(
        decision="include_industry",
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


def test_run_once_identity_failure_precedes_claim(tmp_path, monkeypatch) -> None:
    forge_root = _lesson_artifact_root(tmp_path)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-0123456789")
    monkeypatch.setenv("BUILDER_MODEL", runner.MODEL)
    with pytest.raises(runner.RefusalError, match="identity"):
        runner.run_once(
            forge_root,
            HALLAM_FIXTURE,
            forge_sha="wrong",
            target_sha="hallam-test",
        )
    assert not (forge_root / ".agent" / "ledger" / "FORGE-EXT-003.claim.json").exists()


def test_run_once_budget_refusal_precedes_claim(monkeypatch, tmp_path) -> None:
    forge_root, target_root = _prepare_run(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "PACKET_ESTIMATE_CEILING_USD", runner.PRIOR_CUMULATIVE_ESTIMATE_USD)
    with pytest.raises(RuntimeError, match="spend"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
        )
    assert not (forge_root / ".agent" / "ledger" / "FORGE-EXT-003.claim.json").exists()


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
            assert intent["prior_cumulative_estimate_usd"] == 0.40336
            assert intent["prior_cumulative_max_usd"] == 0.46432
            assert intent["cumulative_conservative_estimate_usd"] == pytest.approx(0.47408)
            assert intent["cumulative_conservative_max_usd"] == pytest.approx(0.53504)
            assert intent["packet_estimate_ceiling_usd"] == 0.55408
            assert intent["cumulative_conservative_max_cap_usd"] == 0.69648
            assert intent["application_digest"] == runner._validated_lesson(forge_root)[4].digest
            assert intent["strategy_with_lesson"] == runner._text_digest(runner.SAFE_STRATEGY)
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
                                        "decision": "include_industry",
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
    claim = forge_root / ".agent" / "ledger" / "FORGE-EXT-003.claim.json"
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
        "decision": "include_industry",
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
    receipts_path = forge_root / ".agent" / "ledger" / "FORGE-EXT-003.jsonl"
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
        "decision": "include_industry",
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
    receipts_path = forge_root / ".agent" / "ledger" / "FORGE-EXT-003.jsonl"
    assert secret not in receipts_path.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="second run"):
        runner.run_once(
            forge_root,
            target_root,
            forge_sha="forge-test",
            target_sha="hallam-test",
            client=DuplicateKeyClient(),
        )
