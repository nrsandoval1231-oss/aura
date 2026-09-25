"""Offline controller tests. Review signatures are test fixtures, not real Astra audits."""

import hashlib
import hmac
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Barrier

import pytest

from forge.learning import CandidateLesson, Metric, MetricDirection
from forge.slice_learning import SliceLearning, _digest
from forge.stuck import Rung, Strategy, patch_hash

# Only the fake independent reviewer fixture owns this test key.
KEY = b"offline-test-reviewer"
BASE = Strategy(Rung.SAME_EDIT, "guess fixture order")
BETTER = Strategy(Rung.MECHANISM, "set environment before import")


def verifier(digest, proof):
    return hmac.compare_digest(hmac.new(KEY, digest.encode(), "sha256").hexdigest(), proof)


def engine(root, repo="repository-1", verify=verifier):
    return SliceLearning(root, repo, review_policy_id="fixture-review-v1", verify_review=verify)


def reviewed(e, identity, event, payload):
    proof = hmac.new(KEY, e.review_digest(event, payload).encode(), "sha256").hexdigest()
    return e.command(identity, event, payload, proof=proof)


def start(e, packet="S1", lane="deepseek", context="python-import:v1"):
    payload = dict(
        packet_id=packet,
        lane=lane,
        context_key=context,
        required_checks=["imports", "regression"],
        baseline_strategy=BASE.digest,
        query_signature="environment import fixture",
    )
    return e.command(f"start:{packet}", "slice_started", payload)


def attempt(
    e,
    packet="S1",
    number=1,
    strategy=BASE,
    failing=("imports",),
    ran=("imports", "regression"),
    patch=None,
):
    return e.command(
        f"attempt:{packet}:{number}",
        "attempt_recorded",
        {
            "packet_id": packet,
            "candidate_digest": f"candidate:{packet}:{number}",
            "patch_digest": patch or patch_hash(f"+{packet}:{number}"),
            "evidence_digest": f"checks:{packet}:{number}",
            "strategy": asdict(strategy),
            "checks_run": list(ran),
            "failing_checks": list(failing),
        },
    )


def finish(e, packet, attempts):
    return e.command(
        f"outcome:{packet}",
        "outcome_recorded",
        {
            "packet_id": packet,
            "metric": asdict(
                Metric("attempts_to_green", attempts, MetricDirection.LOWER_IS_BETTER)
            ),
        },
    )


def seed(e):
    start(e)
    attempt(e)
    attempt(e, number=2, strategy=BETTER, failing=())
    outcome = finish(e, "S1", 2)
    lesson = CandidateLesson(
        "L1",
        "deepseek",
        "environment import fixture",
        "import precedes env setup",
        "set environment before importing the module",
        "attempts_to_green",
        ("reordering unrelated assertions did not fix imports",),
        ("environment import fixture",),
        (outcome["outcome_digest"],),
    )
    e.command("propose:L1", "lesson_proposed", asdict(lesson))
    return lesson


def promote(e, lesson):
    payload = {
        "candidate_digest": lesson.digest,
        "baseline_digest": _digest(
            asdict(Metric("attempts_to_green", 2, MetricDirection.LOWER_IS_BETTER))
        ),
        "decision": {
            "lesson_id": "L1",
            "validator": "astra",
            "validated": True,
            "scope": "REPOSITORY",
            "evidence_digest": "independent-test-evidence",
            "rationale": "Scoped reproduction with unchanged required checks",
        },
    }
    return reviewed(e, "review:L1", "lesson_reviewed", payload)


def test_shared_lessons_only_after_review_and_pinned_per_slice(tmp_path):
    e = engine(tmp_path)
    lesson = seed(e)
    assert start(e, "S2", "luna")["snapshot"] == {}
    promote(e, lesson)
    assert "L1" in start(e, "S3")["snapshot"]
    assert e.inspect()["slices"]["S2"]["snapshot"] == {}
    # The historical start response remains stable after subsequent events.
    assert start(e, "S2", "luna")["attempts"] == []


def test_two_workers_record_without_losing_or_mixing_history(tmp_path):
    barrier = Barrier(2)

    def worker(lane):
        e = engine(tmp_path)
        start(e, lane, lane)
        barrier.wait(timeout=10)
        attempt(e, lane, failing=())
        return finish(e, lane, 1)

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(worker, ("deepseek", "luna")))
    assert all(r["succeeded"] for r in results)
    state = engine(tmp_path).inspect()
    assert all(len(s["attempts"]) == 1 for s in state["slices"].values())
    assert len(engine(tmp_path).store.load().receipts) == 6


def test_restart_recovers_progress_without_replaying_effects(tmp_path):
    e = engine(tmp_path)
    start(e)
    first = attempt(e)
    resumed = engine(tmp_path)
    assert attempt(resumed) == first
    assert len(resumed.inspect()["slices"]["S1"]["attempts"]) == 1
    assert resumed.recovery_plan("S1", BASE)["action"] == "ESCALATE"
    assert resumed.recovery_plan("S1", BETTER)["action"] == "REPAIR"
    with pytest.raises(ValueError, match="different content"):
        attempt(resumed, failing=())


def test_repeated_patch_and_missing_checks_are_not_success(tmp_path):
    e = engine(tmp_path)
    start(e)
    attempt(e, patch="same")
    result = attempt(e, number=2, strategy=BETTER, patch="same")
    assert result["assessment"]["reason"] == "REPEATED_PATCH"
    assert e.recovery_plan("S1", BETTER)["action"] == "ESCALATE"
    start(e, "S2", "luna")
    result = attempt(e, "S2", failing=(), ran=("imports",))
    assert result["assessment"]["verdict"] == "UNKNOWN"
    assert e.recovery_plan("S2", BETTER)["action"] == "RECONCILE"
    assert not finish(e, "S2", 1)["succeeded"]


def test_successful_same_strategy_repair_is_kept_as_evidence(tmp_path):
    e = engine(tmp_path)
    start(e)
    attempt(e)
    assert attempt(e, number=2, failing=())["assessment"]["verdict"] == "CHECKS_PASSED"
    assert e.recovery_plan("S1", BASE)["action"] == "AUDIT"


def test_authenticated_review_is_required_and_binds_candidate(tmp_path):
    e = engine(tmp_path)
    lesson = seed(e)
    with pytest.raises(ValueError, match="authenticated"):
        e.command("forged", "lesson_reviewed", {"decision": {"validator": "astra"}})
    forged = engine(tmp_path, verify=lambda digest, proof: False)
    with pytest.raises(ValueError, match="authenticated"):
        promote(forged, lesson)
    assert engine(tmp_path).inspect()["lessons"]["L1"]["state"] == "CANDIDATE"


def test_lesson_applied_then_harmful_result_rolls_back(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    start(e, "S2", "luna")
    attempt(e, "S2", strategy=BETTER, failing=("regression",))
    assert e.command("apply", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})[
        "changed_strategy"
    ]
    target = finish(e, "S2", 1)
    result = reviewed(
        e,
        "measure",
        "lesson_measured",
        {"lesson_id": "L1", "outcome_digest": target["outcome_digest"]},
    )
    assert result["verdict"] == "HARMED"  # Faster failure must not be rewarded.
    assert engine(tmp_path).inspect()["lessons"]["L1"]["state"] == "ROLLED_BACK"
    assert start(e, "S3")["snapshot"] == {}
    assert "L1" in e.inspect()["slices"]["S2"]["snapshot"]
    with pytest.raises(ValueError, match="already measured"):
        reviewed(
            e,
            "duplicate-measure",
            "lesson_measured",
            {"lesson_id": "L1", "outcome_digest": target["outcome_digest"]},
        )


def test_context_change_does_not_receive_lesson(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    assert not start(e, "S2", "luna", "different-protocol:v2")["snapshot"]
    attempt(e, "S2", strategy=BETTER, failing=())
    with pytest.raises(ValueError, match="pinned"):
        e.command("bad-application", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})


def test_missing_quality_evidence_is_unknown_without_demotion(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    start(e, "S2", "luna")
    attempt(e, "S2", strategy=BETTER, failing=(), ran=("imports",))
    e.command("apply", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})
    outcome = finish(e, "S2", 1)
    result = reviewed(
        e,
        "measure",
        "lesson_measured",
        {"lesson_id": "L1", "outcome_digest": outcome["outcome_digest"]},
    )
    assert result["verdict"] == result["attribution"]["verdict"] == "UNKNOWN"
    assert result["attribution"]["metric_evidence"] is None
    assert engine(tmp_path).inspect()["lessons"]["L1"]["state"] == "VALIDATED"


def test_same_context_cannot_drop_required_checks(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    with pytest.raises(ValueError, match="required-check protocol"):
        e.command(
            "weaken",
            "slice_started",
            {
                "packet_id": "S2",
                "lane": "luna",
                "context_key": "python-import:v1",
                "required_checks": ["imports"],
                "baseline_strategy": BASE.digest,
                "query_signature": "environment import fixture",
            },
        )


def test_concurrent_rollback_preserves_pinned_historical_application(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    start(e, "S2", "luna")
    start(e, "S3", "deepseek")
    attempt(e, "S3", strategy=BETTER, failing=())
    attempt(e, "S2", strategy=BETTER, failing=("regression",))
    e.command("apply:S2", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})
    outcome = finish(e, "S2", 1)
    reviewed(
        e,
        "harm",
        "lesson_measured",
        {"lesson_id": "L1", "outcome_digest": outcome["outcome_digest"]},
    )
    assert e.command("apply:S3", "lesson_applied", {"packet_id": "S3", "lesson_id": "L1"})[
        "changed_strategy"
    ]
    assert engine(tmp_path).inspect()["lessons"]["L1"]["state"] == "ROLLED_BACK"
    assert not start(e, "S4", "luna")["snapshot"]


def test_application_can_follow_a_repair_candidate(tmp_path):
    e = engine(tmp_path)
    promote(e, seed(e))
    start(e, "S2", "luna")
    attempt(e, "S2", strategy=BETTER)
    e.command("apply:1", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})
    attempt(e, "S2", number=2, strategy=BETTER, failing=())
    e.command("apply:2", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})
    with pytest.raises(ValueError, match="this candidate"):
        e.command("duplicate", "lesson_applied", {"packet_id": "S2", "lesson_id": "L1"})
    outcome = finish(e, "S2", 2)
    result = reviewed(
        e,
        "measure",
        "lesson_measured",
        {"lesson_id": "L1", "outcome_digest": outcome["outcome_digest"]},
    )
    assert result["verdict"] == "UNCHANGED"


def test_no_review_no_automatic_promotion_and_no_overwrite(tmp_path):
    e = engine(tmp_path)
    lesson = seed(e)
    with pytest.raises(ValueError, match="immutable"):
        e.command("overwrite", "lesson_proposed", asdict(lesson))
    assert not start(e, "S2", "luna")["snapshot"]
    with pytest.raises(ValueError, match="another repository"):
        engine(tmp_path, "other-repo").inspect()


def test_incomplete_ledger_is_not_silently_reinitialized(tmp_path):
    e = engine(tmp_path)
    start(e)
    e.store.checkpoint_path.unlink()
    with pytest.raises(ValueError, match="Incomplete ledger"):
        e.inspect()


def test_thirty_slice_mechanism_uses_verified_lesson_in_later_real_process(tmp_path):
    """Thirty controlled episodes, not thirty live model builds or a policy study.

    Later fixture programs actually run in Python subprocesses. The test proves
    retrieval affects selected behavior and evidence persists across restarts.
    It makes no claim of statistical significance or generalized improvement.
    """
    root = tmp_path / "history"
    e = engine(root)
    promote(e, seed(e))
    for number in range(2, 31):
        packet = f"S{number}"
        e = engine(root)
        snapshot = start(e, packet, "luna" if number % 2 == 0 else "deepseek")
        strategy = BETTER if "L1" in snapshot["snapshot"] else BASE
        fixture = tmp_path / f"fixture_{number}.py"
        source = (
            "import os\nos.environ['FORGE_FIXTURE'] = 'ready'\nassert os.environ.get('FORGE_FIXTURE') == 'ready'\n"
            if strategy == BETTER
            else "import os\nassert os.environ.get('FORGE_FIXTURE') == 'ready'\n"
        )
        fixture.write_text(source)
        result = subprocess.run(
            [sys.executable, str(fixture)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0
        e.command(
            f"attempt:{packet}",
            "attempt_recorded",
            {
                "packet_id": packet,
                "candidate_digest": hashlib.sha256((packet + source).encode()).hexdigest(),
                "patch_digest": patch_hash("+" + source),
                "evidence_digest": hashlib.sha256(
                    (packet + str(result.returncode) + result.stdout + result.stderr).encode()
                ).hexdigest(),
                "strategy": asdict(strategy),
                "checks_run": ["imports", "regression"],
                "failing_checks": [],
            },
        )
        e.command(f"apply:{packet}", "lesson_applied", {"packet_id": packet, "lesson_id": "L1"})
        outcome = finish(e, packet, 1)
        measured = reviewed(
            e,
            f"measure:{packet}",
            "lesson_measured",
            {"lesson_id": "L1", "outcome_digest": outcome["outcome_digest"]},
        )
        assert measured["verdict"] == "IMPROVED"
        assert not measured["policy_promotion"]
    assert len(engine(root).inspect()["slices"]) == 30
    lines = (root / "slice-learning.jsonl").read_text().splitlines()
    assert all(json.loads(line)["receipt_hash"] for line in lines)
