"""Outcome and lesson engines.

`docs/self-improvement-acceptance.md` says the Learning Engine "cannot be accepted
merely because it stores lessons", so these tests are mostly about what the store
refuses. The nine numbered requirements are cited per section.
"""

from __future__ import annotations

import pytest

from forge.learning import (
    ApplicationRecord,
    CandidateLesson,
    LearningError,
    LessonDecision,
    LessonScope,
    LessonState,
    LessonStore,
    MeasurementVerdict,
    Metric,
    MetricDirection,
    OutcomeRecord,
    failure_signature,
    similarity,
)

REPO = "repo-digest-1"
FAILING = Metric("failing_tests", 5, MetricDirection.LOWER_IS_BETTER)
SIGNATURE = failure_signature({"test_env_order", "test_import_time"})


def _outcome(store, *, packet="FORGE-T-001", candidate="cand-1", metric=FAILING):
    record = OutcomeRecord(
        packet,
        REPO,
        candidate,
        "strategy-1",
        "evidence-1",
        metric,
        frozenset({"test_env_order", "test_import_time"}),
        False,
    )
    store.record_outcome(record)
    return record


def _candidate(outcome, *, author="luna", change="load env in the fixture, not at import time"):
    return CandidateLesson(
        id="L-1",
        author=author,
        context="import-order flake in the provider suite",
        diagnosis="module imported before the env fixture ran",
        intended_change=change,
        metric_name="failing_tests",
        negative_knowledge=("patching sys.modules did not help",),
        failure_signatures=(SIGNATURE,),
        derived_from=(outcome.digest,),
    )


def _validated_store():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    store.validate(
        LessonDecision("L-1", "astra", True, LessonScope.REPOSITORY, "evidence-2", "reproduced"),
        baseline=FAILING,
    )
    return store


# ---------------------------------------------------------------------------
# Requirement 1 — attributable experience
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "blank", ["packet_id", "repository_digest", "candidate_digest", "strategy_digest"]
)
def test_an_unattributable_outcome_is_refused(blank):
    fields = {
        "packet_id": "P",
        "repository_digest": REPO,
        "candidate_digest": "c",
        "strategy_digest": "s",
        "evidence_digest": "e",
        "metric": FAILING,
    }
    fields[blank] = ""
    with pytest.raises(LearningError, match="attributed"):
        OutcomeRecord(**fields)


def test_a_store_refuses_another_repositorys_outcome():
    """Accepting foreign experience would be global promotion by accident."""
    store = LessonStore(REPO)
    other = OutcomeRecord("P", "different-repo", "c", "s", "e", FAILING)
    with pytest.raises(LearningError, match="different repository"):
        store.record_outcome(other)


# ---------------------------------------------------------------------------
# Requirement 2 — the candidate lesson's required content
# ---------------------------------------------------------------------------


def test_a_lesson_must_record_negative_knowledge():
    """Recording only what worked discards the more reusable half."""
    store = LessonStore(REPO)
    outcome = _outcome(store)
    with pytest.raises(LearningError, match="negative knowledge"):
        CandidateLesson(
            id="L-1",
            author="luna",
            context="c",
            diagnosis="d",
            intended_change="x",
            metric_name="failing_tests",
            negative_knowledge=(),
            failure_signatures=(SIGNATURE,),
            derived_from=(outcome.digest,),
        )


def test_a_lesson_must_cite_its_outcomes():
    with pytest.raises(LearningError, match="cite the outcome"):
        CandidateLesson(
            id="L-1",
            author="luna",
            context="c",
            diagnosis="d",
            intended_change="x",
            metric_name="failing_tests",
            negative_knowledge=("tried y",),
            failure_signatures=(SIGNATURE,),
            derived_from=(),
        )


def test_a_lesson_citing_an_unknown_outcome_is_refused():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    stranger = CandidateLesson(
        id="L-2",
        author="luna",
        context="c",
        diagnosis="d",
        intended_change="x",
        metric_name="failing_tests",
        negative_knowledge=("tried y",),
        failure_signatures=(SIGNATURE,),
        derived_from=("not-a-real-digest",),
    )
    with pytest.raises(LearningError, match="outcome records this store holds"):
        store.propose(stranger)
    assert outcome.digest in store.outcomes


# ---------------------------------------------------------------------------
# Requirement 9 — a lesson may not weaken governance or reach protected policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        "skip the failing test",
        "disable the audit gate",
        "remove the assertion that keeps failing",
        "mark it pytest.mark.skip until later",
        "relax the threshold so it passes",
        "lower the coverage bar",
        "quarantine the test",
        "bypass the authority check",
        "weaken the invariant",
        "widen the scope permission",
    ],
)
def test_a_lesson_that_lowers_the_bar_is_refused(change):
    """The failure mode that makes self-improvement dangerous rather than useless."""
    store = LessonStore(REPO)
    outcome = _outcome(store)
    with pytest.raises(LearningError, match="lowering the bar"):
        store.propose(_candidate(outcome, change=change))


@pytest.mark.parametrize(
    "path",
    [
        "src/forge/trust_kernel.py",
        "src/forge/ledger_store.py",
        "scripts/validate.sh",
        ".agent/graph/work-graph.json",
        "AGENTS.md",
    ],
)
def test_a_lesson_may_not_propose_editing_a_protected_surface(path):
    store = LessonStore(REPO)
    outcome = _outcome(store)
    with pytest.raises(LearningError, match="protected surface"):
        store.propose(_candidate(outcome, change=f"adjust the handling in {path}"))


def test_a_lesson_may_propose_editing_an_ordinary_surface():
    """The guard must not make all self-improvement impossible."""
    store = LessonStore(REPO)
    outcome = _outcome(store)
    lesson = store.propose(
        _candidate(outcome, change="move the fixture in tests/conftest.py earlier")
    )
    assert lesson.state is LessonState.CANDIDATE


def test_the_protected_guard_reads_the_same_registry_as_the_authority_check():
    """F9 was one protection list drifting from another. There is only one list."""
    from forge import learning, policy

    assert learning.requires_owner_authority is policy.requires_owner_authority


# ---------------------------------------------------------------------------
# Requirements 3 and 4 — independent decision, repository scope only
# ---------------------------------------------------------------------------


def test_a_lesson_cannot_be_validated_by_its_author():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome, author="luna"))
    with pytest.raises(LearningError, match="own author"):
        store.validate(
            LessonDecision("L-1", "luna", True, LessonScope.REPOSITORY, "e", "looks fine"),
            baseline=FAILING,
        )


def test_global_promotion_is_disabled_in_v0():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    with pytest.raises(LearningError, match="global promotion is disabled"):
        store.validate(
            LessonDecision("L-1", "astra", True, LessonScope.GLOBAL, "e", "great"),
            baseline=FAILING,
        )


def test_a_decision_must_cite_evidence():
    with pytest.raises(LearningError, match="cite its evidence"):
        LessonDecision("L-1", "astra", True, LessonScope.REPOSITORY, "", "because")


def test_validation_requires_the_metric_the_lesson_named():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    with pytest.raises(LearningError, match="needs the metric"):
        store.validate(
            LessonDecision("L-1", "astra", True, LessonScope.REPOSITORY, "e", "ok"),
            baseline=Metric("latency_ms", 100, MetricDirection.LOWER_IS_BETTER),
        )


def test_a_rejected_lesson_is_not_applicable():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    lesson = store.validate(
        LessonDecision("L-1", "astra", False, LessonScope.REPOSITORY, "e", "did not reproduce"),
        baseline=FAILING,
    )
    assert lesson.state is LessonState.REJECTED
    assert not lesson.is_applicable


def test_a_lesson_cannot_be_decided_twice():
    store = _validated_store()
    with pytest.raises(LearningError, match="not a candidate"):
        store.validate(
            LessonDecision("L-1", "astra", True, LessonScope.REPOSITORY, "e", "again"),
            baseline=FAILING,
        )


# ---------------------------------------------------------------------------
# Requirement 5 — retrieval evidence
# ---------------------------------------------------------------------------


def test_a_validated_lesson_is_retrieved_for_a_similar_failure():
    store = _validated_store()
    record = store.retrieve("FORGE-T-002", SIGNATURE)
    assert record.lesson_ids == ("L-1",)


def test_an_unrelated_failure_does_not_retrieve_the_lesson():
    store = _validated_store()
    record = store.retrieve("FORGE-T-002", failure_signature({"test_billing_rounding"}))
    assert record.lesson_ids == ()


def test_a_candidate_lesson_is_never_retrieved():
    """Only a validated, repository-scoped lesson may influence later work."""
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    assert store.retrieve("FORGE-T-002", SIGNATURE).lesson_ids == ()


def test_an_empty_retrieval_is_still_recorded():
    """It separates "no lesson was relevant" from "nobody looked"."""
    store = _validated_store()
    store.retrieve("FORGE-T-002", failure_signature({"test_unrelated"}))
    assert len(store.retrievals) == 1


def test_retrieval_is_deterministic():
    store = _validated_store()
    first = store.retrieve("FORGE-T-002", SIGNATURE)
    second = store.retrieve("FORGE-T-002", SIGNATURE)
    assert first.retrieved == second.retrieved


def test_failure_signatures_are_order_independent():
    """Runners do not guarantee order; a signature that moved with it would miss."""
    assert failure_signature(["b", "a"]) == failure_signature(["a", "b"])


def test_similarity_is_bounded_and_zero_on_empty():
    assert similarity("", SIGNATURE) == 0.0
    assert similarity(SIGNATURE, SIGNATURE) == 1.0


# ---------------------------------------------------------------------------
# Requirement 6 — did the lesson change the decision?
# ---------------------------------------------------------------------------


def test_an_application_must_cite_a_retrieval_this_store_performed():
    store = _validated_store()
    with pytest.raises(LearningError, match="not one this store performed"):
        store.record_application(
            ApplicationRecord("FORGE-T-002", "L-1", "invented-digest", "cand-2", "a", "b")
        )


def test_an_application_must_cite_a_nonempty_retrieval_for_its_packet():
    store = _validated_store()
    retrieval = store.retrieve("FORGE-T-OTHER", SIGNATURE)
    with pytest.raises(LearningError, match="packet"):
        store.record_application(
            ApplicationRecord(
                "FORGE-T-002",
                "L-1",
                retrieval.digest,
                "cand-2",
                "a",
                "b",
            )
        )


def test_an_application_cannot_cite_an_empty_retrieval():
    store = _validated_store()
    retrieval = store.retrieve("FORGE-T-002", "no matching failure")
    with pytest.raises(LearningError, match="lesson"):
        store.record_application(
            ApplicationRecord(
                "FORGE-T-002",
                "L-1",
                retrieval.digest,
                "cand-2",
                "a",
                "b",
            )
        )


def test_changed_strategy_is_derived_not_asserted():
    """ "The lesson helped" must not be recordable about an identical decision."""
    unchanged = ApplicationRecord("P", "L-1", "d", "cand", "same", "same")
    changed = ApplicationRecord("P", "L-1", "d", "cand", "before", "after")
    assert not unchanged.changed_strategy
    assert changed.changed_strategy


def test_an_application_must_name_its_retrieval():
    with pytest.raises(LearningError, match="cite the retrieval"):
        ApplicationRecord("P", "L-1", "", "cand", "a", "b")


def test_a_demoted_lesson_may_not_be_applied():
    store = _validated_store()
    retrieval = store.retrieve("FORGE-T-002", SIGNATURE)
    store.demote("L-1", reason="conflicts with ADR-0002")
    with pytest.raises(LearningError, match="may not influence work"):
        store.record_application(
            ApplicationRecord("FORGE-T-002", "L-1", retrieval.digest, "cand-2", "a", "b")
        )


# ---------------------------------------------------------------------------
# Requirement 7 — measurement, and UNKNOWN when it cannot be attributed
# ---------------------------------------------------------------------------


def _applied_store():
    store = _validated_store()
    retrieval = store.retrieve("FORGE-T-002", SIGNATURE)
    store.record_application(
        ApplicationRecord(
            "FORGE-T-002",
            "L-1",
            retrieval.digest,
            "cand-2",
            "retry-again",
            "load-env-first",
        )
    )
    return store


def test_an_improvement_on_the_named_metric_is_reported():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.IMPROVED


def test_a_regression_on_the_named_metric_is_reported():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 9, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.HARMED


def test_an_unchanged_metric_is_not_an_improvement():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 5, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNCHANGED


def test_a_measurement_with_no_application_is_unknown():
    """Nothing shows the lesson changed anything, so improvement is unattributable."""
    store = _validated_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN
    assert "cannot be attributed" in measurement.reason


def test_a_measurement_of_the_wrong_metric_is_unknown():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("latency_ms", 1, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN


def test_a_measurement_not_bound_to_a_candidate_is_unknown():
    store = _applied_store()
    measurement = store.measure(
        "L-1", Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER), candidate_digest=""
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN


def test_a_measurement_bound_to_a_different_candidate_is_unknown():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-other",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN
    assert "candidate" in measurement.reason


def test_a_reversed_metric_direction_is_unknown():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.HIGHER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN
    assert "direction" in measurement.reason


def test_measuring_an_unvalidated_lesson_is_unknown():
    store = LessonStore(REPO)
    outcome = _outcome(store)
    store.propose(_candidate(outcome))
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN


def test_an_application_that_changed_nothing_does_not_support_an_improvement():
    """The decision was identical either way, so the metric move is not the lesson's."""
    store = _validated_store()
    retrieval = store.retrieve("FORGE-T-002", SIGNATURE)
    store.record_application(
        ApplicationRecord("FORGE-T-002", "L-1", retrieval.digest, "cand-2", "same", "same")
    )
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN


def test_higher_is_better_metrics_compare_the_other_way():
    coverage = Metric("coverage", 0.80, MetricDirection.HIGHER_IS_BETTER)
    assert Metric("coverage", 0.90, MetricDirection.HIGHER_IS_BETTER).improves_on(coverage)
    assert Metric("coverage", 0.70, MetricDirection.HIGHER_IS_BETTER).harms(coverage)


def test_comparing_different_metrics_is_refused():
    with pytest.raises(LearningError, match="Cannot compare"):
        Metric("a", 1, MetricDirection.LOWER_IS_BETTER).improves_on(
            Metric("b", 1, MetricDirection.LOWER_IS_BETTER)
        )


# ---------------------------------------------------------------------------
# Requirement 8 — demotion and rollback
# ---------------------------------------------------------------------------


def test_a_harmful_lesson_is_rolled_back():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 12, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    lesson = store.demote_if_harmful(measurement)
    assert lesson is not None
    assert lesson.state is LessonState.ROLLED_BACK
    assert not lesson.is_applicable


def test_an_unknown_measurement_does_not_demote():
    """Demoting on thin evidence would discard sound lessons; UNKNOWN is preserved."""
    store = _validated_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert measurement.verdict is MeasurementVerdict.UNKNOWN
    assert store.demote_if_harmful(measurement) is None
    assert store.lessons["L-1"].is_applicable


def test_an_improvement_does_not_demote():
    store = _applied_store()
    measurement = store.measure(
        "L-1",
        Metric("failing_tests", 1, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    assert store.demote_if_harmful(measurement) is None


def test_demotion_must_record_a_reason():
    store = _validated_store()
    with pytest.raises(LearningError, match="record why"):
        store.demote("L-1", reason="  ")


def test_demotion_and_rollback_are_distinct_states():
    store = _validated_store()
    assert store.demote("L-1", reason="superseded").state is LessonState.DEMOTED
    assert store.demote("L-1", reason="harmful", rollback=True).state is LessonState.ROLLED_BACK


def test_an_unknown_lesson_cannot_be_demoted():
    with pytest.raises(LearningError, match="No lesson"):
        LessonStore(REPO).demote("L-nope", reason="x")


# ---------------------------------------------------------------------------
# The episode evidence an auditor reads
# ---------------------------------------------------------------------------


def test_episode_evidence_reports_the_full_causal_chain():
    store = _applied_store()
    store.measure(
        "L-1",
        Metric("failing_tests", 0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="cand-2",
    )
    evidence = store.episode_evidence("L-1")

    assert evidence["state"] == "VALIDATED"
    assert evidence["scope"] == "REPOSITORY"
    assert evidence["outcomes"]
    assert evidence["negative_knowledge"]
    assert evidence["decision"]["validator"] == "astra"
    assert evidence["retrievals"]
    assert evidence["changed_later_behaviour"] is True
    assert evidence["improved_named_outcome"] is True


def test_episode_evidence_does_not_claim_behaviour_change_without_one():
    store = _validated_store()
    evidence = store.episode_evidence("L-1")
    assert evidence["changed_later_behaviour"] is False
    assert evidence["improved_named_outcome"] is False
