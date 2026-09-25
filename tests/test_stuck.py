"""Stuck detection and bounded recovery.

The Finish Contract requires "stuck resolution requires materially different
strategies" and AGENT_RULES bounds it at two such repairs. These tests are written
against the ways an agent gets past that rule while appearing to follow it:
re-framing the same diff, renaming the same approach, and trading one failure for
another inside budget.
"""

from __future__ import annotations

import pytest

from forge.stuck import (
    MAX_MATERIAL_REPAIRS,
    AttemptRecord,
    Rung,
    Strategy,
    StuckDetector,
    StuckError,
    StuckReason,
    StuckVerdict,
    materially_different,
    patch_hash,
)

RETRY = Strategy(Rung.SAME_EDIT, "retry the same edit")
SWAP_ALGO = Strategy(Rung.MECHANISM, "replace the algorithm")
INVERT = Strategy(Rung.INTERFACE, "invert the dependency")


def _detector(*attempts):
    detector = StuckDetector("FORGE-T-001")
    for index, (patch, strategy, failing) in enumerate(attempts, 1):
        detector.record(
            AttemptRecord("FORGE-T-001", index, patch, strategy, failing, f"evidence-{index}")
        )
    return detector


# ---------------------------------------------------------------------------
# patch_hash — repetition measured on content, not on narrative
# ---------------------------------------------------------------------------


def test_same_edit_reframed_hashes_the_same():
    """The loop an agent cannot talk its way out of."""
    first = patch_hash("diff --git a/x b/x\nindex 111..222\n@@ -1,3 +1,3 @@\n ctx\n-old\n+new\n")
    second = patch_hash("@@ -420,9 +420,9 @@ def elsewhere():\n other ctx\n-old   \n+new\t\n")
    assert first == second


def test_a_genuinely_different_edit_hashes_differently():
    assert patch_hash("@@ @@\n-old\n+new\n") != patch_hash("@@ @@\n-old\n+other\n")


def test_context_only_changes_do_not_change_the_hash():
    """Context lines move when unrelated code shifts; they are not the change."""
    assert patch_hash("@@ @@\n ctx a\n-old\n+new\n") == patch_hash("@@ @@\n ctx b\n-old\n+new\n")


def test_an_empty_diff_is_hashable_and_distinct():
    assert patch_hash("") == patch_hash("@@ -1 +1 @@\n unchanged\n")


# ---------------------------------------------------------------------------
# materially_different — measured on declared strategy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relabelled",
    [
        "Retry The Same Edit",
        "retry  the   same edit!!",
        "edit same the retry",
        "RETRY-THE-SAME-EDIT",
    ],
)
def test_relabelling_a_mechanism_is_not_a_material_difference(relabelled):
    assert not materially_different(RETRY, Strategy(Rung.SAME_EDIT, relabelled))


def test_same_mechanism_at_a_different_rung_is_material():
    assert materially_different(RETRY, Strategy(Rung.MECHANISM, "retry the same edit"))


def test_same_mechanism_and_rung_on_different_files_is_not_material():
    """The case a file-list comparison waves through: one idea, pointed elsewhere."""
    here = Strategy(Rung.MECHANISM, "add a retry loop", surfaces=("src/a.py",))
    there = Strategy(Rung.MECHANISM, "add a retry loop", surfaces=("src/b.py",))
    assert not materially_different(here, there)


def test_a_strategy_must_name_its_mechanism():
    with pytest.raises(StuckError, match="must name its mechanism"):
        Strategy(Rung.SAME_EDIT, "   ")


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def test_the_first_attempt_is_never_stuck():
    assessment = StuckDetector("FORGE-T-001").assess(
        patch_digest="a", strategy=RETRY, failing_checks={"t1"}
    )
    assert assessment.verdict is StuckVerdict.CONTINUE
    assert assessment.reason is StuckReason.NOT_STUCK


def test_a_repeated_patch_is_refused_and_escalated():
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    assessment = detector.assess(patch_digest="a", strategy=SWAP_ALGO, failing_checks={"t1"})
    assert assessment.reason is StuckReason.REPEATED_PATCH
    assert assessment.verdict is StuckVerdict.ESCALATE


def test_a_repeated_patch_is_caught_even_from_an_older_attempt():
    """Comparing only against the previous attempt permits an A-B-A loop."""
    detector = _detector(("a", RETRY, {"t1", "t2"}), ("b", SWAP_ALGO, {"t1"}))
    assessment = detector.assess(patch_digest="a", strategy=INVERT, failing_checks={"t1"})
    assert assessment.reason is StuckReason.REPEATED_PATCH


def test_a_non_material_strategy_is_refused():
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    assessment = detector.assess(
        patch_digest="b",
        strategy=Strategy(Rung.SAME_EDIT, "Retry the same EDIT"),
        failing_checks={"t1"},
    )
    assert assessment.reason is StuckReason.NOT_MATERIALLY_DIFFERENT
    assert assessment.verdict is StuckVerdict.ESCALATE
    assert assessment.next_rung is Rung.MECHANISM


def test_escalation_names_the_next_rung_up():
    detector = _detector(("a", SWAP_ALGO, {"t1", "t2"}))
    assessment = detector.assess(patch_digest="a", strategy=SWAP_ALGO, failing_checks={"t1"})
    assert assessment.next_rung is Rung.INTERFACE


def test_dropping_back_down_the_ladder_is_refused():
    detector = _detector(("a", RETRY, {"t1", "t2"}), ("b", SWAP_ALGO, {"t1"}))
    assessment = detector.assess(
        patch_digest="c", strategy=Strategy(Rung.SAME_EDIT, "try harder"), failing_checks=set()
    )
    assert assessment.reason is StuckReason.RUNG_ALREADY_TRIED


def test_a_materially_different_escalation_with_improvement_continues():
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    assessment = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks={"t1"})
    assert assessment.verdict is StuckVerdict.CONTINUE
    assert assessment.material_repairs_used == 0


# ---------------------------------------------------------------------------
# "If evidence does not improve, return to canonical intent" (AGENT_RULES)
# ---------------------------------------------------------------------------


def test_trading_one_failure_for_another_is_not_improvement():
    """Motion is not progress, and a rule that accepted it would loop inside budget."""
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    assessment = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks={"t1", "t3"})
    assert assessment.reason is StuckReason.NO_IMPROVEMENT
    assert assessment.verdict is StuckVerdict.RETURN_TO_INTENT


def test_an_equal_failure_set_is_not_improvement():
    detector = _detector(("a", RETRY, {"t1"}))
    assessment = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks={"t1"})
    assert assessment.reason is StuckReason.NO_IMPROVEMENT


def test_a_clean_run_always_counts_as_improvement():
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    assessment = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks=set())
    assert assessment.verdict is StuckVerdict.CONTINUE


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_the_first_attempt_does_not_spend_repair_budget():
    """Counting the original work as a repair would spend a third of the budget."""
    assert _detector(("a", RETRY, {"t1"})).material_repairs_used == 0


def test_material_repairs_are_counted_by_distinct_strategy():
    detector = _detector(
        ("a", RETRY, {"t1", "t2", "t3"}),
        ("b", SWAP_ALGO, {"t1", "t2"}),
        ("c", INVERT, {"t1"}),
    )
    assert detector.material_repairs_used == MAX_MATERIAL_REPAIRS


def test_exhausting_the_repair_budget_returns_to_intent():
    detector = _detector(
        ("a", RETRY, {"t1", "t2", "t3"}),
        ("b", SWAP_ALGO, {"t1", "t2"}),
        ("c", INVERT, {"t1"}),
    )
    assessment = detector.assess(
        patch_digest="d", strategy=Strategy(Rung.DESIGN, "split the module"), failing_checks=set()
    )
    assert assessment.verdict is StuckVerdict.RETURN_TO_INTENT
    assert assessment.reason is StuckReason.REPAIR_BUDGET_EXHAUSTED


def test_the_budget_is_configurable_but_never_zero():
    with pytest.raises(StuckError, match="cannot permit any repair"):
        StuckDetector("FORGE-T-001", max_material_repairs=0)


# ---------------------------------------------------------------------------
# Ladder exhaustion reaches the owner, and stops
# ---------------------------------------------------------------------------


def test_exhausting_the_ladder_reaches_the_owner():
    """At INTENT the requirement is the constraint, and only the owner changes one."""
    detector = _detector(("a", Strategy(Rung.INTENT, "revisit the requirement"), {"t1"}))
    assessment = detector.assess(
        patch_digest="a",
        strategy=Strategy(Rung.INTENT, "revisit the requirement"),
        failing_checks={"t1"},
    )
    assert assessment.verdict is StuckVerdict.OWNER
    assert assessment.reason is StuckReason.LADDER_EXHAUSTED
    assert assessment.next_rung is None


def test_owner_verdict_is_a_stop_not_a_permission():
    """Nothing in an assessment can be mistaken for authority to proceed."""
    detector = _detector(("a", Strategy(Rung.INTENT, "revisit"), {"t1"}))
    assessment = detector.assess(
        patch_digest="a", strategy=Strategy(Rung.INTENT, "revisit"), failing_checks={"t1"}
    )
    assert assessment.verdict is not StuckVerdict.CONTINUE
    assert not hasattr(assessment, "authority")
    assert not hasattr(assessment, "grant")


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def test_attempts_must_arrive_in_order():
    detector = StuckDetector("FORGE-T-001")
    with pytest.raises(StuckError, match="Expected attempt 1"):
        detector.record(AttemptRecord("FORGE-T-001", 2, "a", RETRY, {"t1"}, "e"))


def test_attempts_must_belong_to_the_packet():
    detector = StuckDetector("FORGE-T-001")
    with pytest.raises(StuckError, match="belongs to"):
        detector.record(AttemptRecord("FORGE-OTHER-001", 1, "a", RETRY, {"t1"}, "e"))


def test_an_attempt_must_carry_evidence():
    with pytest.raises(StuckError, match="carry evidence"):
        AttemptRecord("FORGE-T-001", 1, "a", RETRY, {"t1"}, "")


def test_recording_keeps_history_even_when_the_assessment_blocked():
    """A blocked attempt that happened anyway is still a fact the next one needs."""
    detector = _detector(("a", RETRY, {"t1"}))
    detector.record(AttemptRecord("FORGE-T-001", 2, "a", RETRY, {"t1"}, "e2"))
    assert len(detector.attempts) == 2


def test_assessment_digest_is_stable_and_content_addressed():
    detector = _detector(("a", RETRY, {"t1", "t2"}))
    first = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks={"t1"})
    second = detector.assess(patch_digest="b", strategy=SWAP_ALGO, failing_checks={"t1"})
    assert first.digest == second.digest
    assert first.as_dict()["verdict"] == "CONTINUE"
