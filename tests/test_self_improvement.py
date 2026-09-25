"""The FORGE-SI-001 mandatory V0 gate.

`docs/self-improvement-acceptance.md` requires proof that a validated lesson changed
later engineering behaviour and improved a named outcome — not that lessons can be
stored. These tests assert the causal chain and, more importantly, that the proof
would fail if any link were removed. A demonstration that cannot fail demonstrates
nothing, which is the same objection audit F12 raises against the provider tests.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from forge.learning import (
    CandidateLesson,
    LessonScope,
    MeasurementVerdict,
    MetricDirection,
)
from forge.stuck import Rung

ROOT = Path(__file__).resolve().parent.parent


def _load_prover():
    spec = importlib.util.spec_from_file_location(
        "prove_self_improvement", ROOT / "scripts" / "prove_self_improvement.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prover():
    return _load_prover()


@pytest.fixture(scope="module")
def evidence(prover):
    return prover.prove()


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


def test_all_nine_acceptance_requirements_are_met(evidence):
    unmet = sorted(key for key, met in evidence["acceptance"].items() if not met)
    assert unmet == []


def test_the_lesson_changed_the_opening_rung(evidence):
    """The load-bearing link: one planner, two retrievals, different decisions."""
    episode = evidence["episode_two"]
    assert episode["opening_rung_without_lesson"] == "SAME_EDIT"
    assert episode["opening_rung_with_lesson"] == "MECHANISM"
    assert episode["changed_strategy"] is True
    assert episode["strategy_without_lesson"] != episode["strategy_with_lesson"]


def test_the_named_metric_improved(evidence):
    assert evidence["episode_one"]["attempts_to_green"] == 3
    assert evidence["episode_two"]["attempts_to_green"] == 1
    assert evidence["episode_two"]["measurement"]["verdict"] == MeasurementVerdict.IMPROVED.value


def test_the_baseline_came_from_real_stuck_detection(evidence):
    """Three attempts is what the shipped detector actually charged, not a constant.

    The middle attempt was refused as not materially different and still cost an
    attempt. If the baseline were hardcoded, the improvement would be arithmetic
    rather than evidence.
    """
    assert len(evidence["episode_one"]["outcomes"]) == 3


def test_a_harmful_lesson_is_measured_and_rolled_back(evidence):
    episode = evidence["episode_three"]
    assert episode["verdict"] == MeasurementVerdict.HARMED.value
    assert episode["state_after"] == "ROLLED_BACK"
    assert episode["retrievable_after_rollback"] is False


def test_promotion_stayed_repository_scoped(evidence):
    assert evidence["episode_evidence"]["scope"] == LessonScope.REPOSITORY.value


def test_the_episode_evidence_asserts_both_halves(evidence):
    chain = evidence["episode_evidence"]
    assert chain["changed_later_behaviour"] is True
    assert chain["improved_named_outcome"] is True
    assert chain["negative_knowledge"]
    assert chain["decision"]["validator"] != "luna"


def test_the_proof_states_its_simulated_boundary(evidence):
    """The same obligation run_slice.py meets: say what is not real."""
    boundary = evidence["boundary"]
    assert "simulated" in boundary
    assert "No model is called" in boundary
    assert "not that Forge" in boundary


def test_the_proof_is_deterministic(prover):
    assert prover.prove() == prover.prove()


def test_the_recorded_artifact_matches_a_fresh_derivation(prover):
    """The gate re-derives rather than trusting the committed file."""
    assert prover.main(["--check"]) == 0


# ---------------------------------------------------------------------------
# The demonstration must be capable of failing
# ---------------------------------------------------------------------------


def test_without_a_retrieved_lesson_the_planner_opens_at_the_bottom(prover):
    assert prover.choose_opening([]).rung is Rung.SAME_EDIT


def test_a_lesson_naming_no_opening_rung_changes_nothing(prover):
    """Retrieval alone must not count as influence."""
    silent = CandidateLesson(
        id="L-SILENT",
        author="luna",
        context="c",
        diagnosis="d",
        intended_change="add a regression test for the import order",
        metric_name="attempts_to_green",
        negative_knowledge=("tried something else",),
        failure_signatures=("sig",),
        derived_from=("outcome",),
    )
    assert prover.choose_opening([silent]).digest == prover.choose_opening([]).digest


def test_a_repair_below_the_fixable_rung_does_not_clear_the_defect(prover):
    """The simulated step, asserted explicitly so its assumption is visible."""
    from forge.stuck import Strategy

    assert prover.attempt_result(Strategy(Rung.SAME_EDIT, "retry")) == prover.DEFECT_CHECKS
    assert prover.attempt_result(Strategy(Rung.MECHANISM, "move the fixture")) == frozenset()


def test_the_metric_direction_makes_fewer_attempts_better(evidence):
    assert evidence["metric_direction"] == MetricDirection.LOWER_IS_BETTER.value
