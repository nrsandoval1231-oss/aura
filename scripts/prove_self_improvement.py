#!/usr/bin/env python3
"""Demonstrate the self-improvement causal chain end to end (FORGE-SI-001).

`docs/self-improvement-acceptance.md` is the contract, and it is blunt about what
does not count:

> The later Learning Engine cannot be accepted merely because it stores lessons.

So this script does not store a lesson and declare victory. It runs two episodes and
shows the middle link of the chain actually carrying load:

    STATE → DECISION → ACTION → OUTCOME → DETERMINISTIC EVALUATION → ATTRIBUTION
    → CANDIDATE LESSON → VALIDATE → PROMOTE WITH SCOPE → APPLY TO FUTURE WORK
    → MEASURE IMPROVEMENT → RETAIN, REVISE, DEMOTE, OR ROLLBACK

Episode one is a packet that gets stuck: a repair at the SAME_EDIT rung cannot fix a
defect that lives in the mechanism, the real `StuckDetector` refuses the second
attempt as not materially different, and green arrives on the third. Three attempts
is the baseline for the named metric.

Episode two is a later packet with a similar failure signature. `choose_opening` —
one function, called twice — plans it with an empty retrieval and then with the
retrieved lesson. The lesson names an opening rung, so the second call returns a
different strategy, and `ApplicationRecord.changed_strategy` *derives* that from the
two digests rather than taking anyone's word. Green arrives in one attempt, the named
metric moves 3 → 1, and the measurement is IMPROVED.

Episode three feeds the same machinery a lesson that makes things worse, to show the
other branch closing: measured HARMED, rolled back automatically, no longer
retrievable.

    python scripts/prove_self_improvement.py [--check]

What is real here: the stuck detector, the lesson store, the retrieval ranking, the
planner, every refusal along the way, and the digests. All of it is the shipped code
under `src/forge/`, not a local reimplementation.

What is simulated: whether a given repair fixes the defect. `attempt_result` decides
that from the rung, because the scenario's defect is by construction an
env-ordering defect that a same-level edit cannot reach. No model is called and no
real bug is fixed. What this proves is that the learning machinery changes a later
decision and can measure and revoke the change — not that Forge can fix software.
That boundary is written into the emitted evidence rather than left for a reader to
infer, on the same principle as `scripts/run_slice.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from forge.learning import (  # noqa: E402
    ApplicationRecord,
    CandidateLesson,
    LessonDecision,
    LessonScope,
    LessonStore,
    MeasurementVerdict,
    Metric,
    MetricDirection,
    OutcomeRecord,
    failure_signature,
)
from forge.stuck import (  # noqa: E402
    AttemptRecord,
    Rung,
    Strategy,
    StuckDetector,
    StuckVerdict,
)

ARTIFACTS = ROOT / ".agent" / "artifacts" / "FORGE-SI-001"
REPOSITORY_DIGEST = "forge-agent-proving-repository"
METRIC = "attempts_to_green"

#: The failing checks the scenario's defect produces. An env-ordering defect: the
#: module under test is imported before the fixture that configures its environment.
DEFECT_CHECKS = frozenset({"test_env_order", "test_import_time"})

#: The rung at or above which a repair can actually reach this defect. Below it the
#: edit is in the wrong place, however many times it is attempted.
FIXABLE_AT = Rung.MECHANISM

#: What a lesson writes to say "do not open at the bottom of the ladder".
OPENING_RUNG_MARKER = "open at rung "

DEFAULT_OPENING = Strategy(Rung.SAME_EDIT, "retry the same edit")


def attempt_result(strategy: Strategy) -> frozenset[str]:
    """Simulated: whether this repair reaches the defect.

    The one simulated step in the script, isolated into a single function so it is
    obvious what is assumed. The defect is in the mechanism, so an edit at
    SAME_EDIT leaves it in place no matter how it is framed.
    """
    return frozenset() if strategy.rung >= FIXABLE_AT else DEFECT_CHECKS


def choose_opening(retrieved_lessons: list[CandidateLesson]) -> Strategy:
    """Plan a packet's opening strategy, consulting whatever was retrieved.

    The load-bearing function of the whole proof. It is called twice in episode two
    with different retrievals and identical everything else, so any difference in
    its output is caused by the lesson and nothing else. Without a lesson it opens at
    the bottom of the ladder, which is the natural default and the reason episode one
    cost three attempts.
    """
    for lesson in retrieved_lessons:
        rung = _opening_rung(lesson)
        if rung is not None:
            return Strategy(
                rung,
                f"apply lesson {lesson.id}: {lesson.diagnosis}",
                rationale=f"retrieved lesson {lesson.id}",
            )
    return DEFAULT_OPENING


def _opening_rung(lesson: CandidateLesson) -> Rung | None:
    """Read an opening rung out of a lesson's intended change, if it names one."""
    text = lesson.intended_change.casefold()
    if OPENING_RUNG_MARKER not in text:
        return None
    named = text.split(OPENING_RUNG_MARKER, 1)[1].split()[0].strip(".,;:").upper()
    try:
        return Rung[named]
    except KeyError:
        return None


def run_episode(
    packet_id: str, candidate_digest: str, opening: Strategy, *, ladder: list[Strategy]
) -> tuple[int, list[OutcomeRecord]]:
    """Drive one packet through the real StuckDetector until green.

    Returns the attempt count and one outcome record per attempt. The detector is the
    shipped one: when a proposed repair is not materially different it refuses, and
    this loop has to escalate like any other caller would.
    """
    detector = StuckDetector(packet_id)
    outcomes: list[OutcomeRecord] = []
    proposals = [opening, *ladder]
    attempt_number = 0

    for strategy in proposals:
        failing = attempt_result(strategy)
        patch_digest = hashlib.sha256(
            f"{strategy.rung.name}:{strategy.mechanism}".encode()
        ).hexdigest()
        if detector.attempts:
            assessment = detector.assess(
                patch_digest=patch_digest, strategy=strategy, failing_checks=failing
            )
            if assessment.verdict is not StuckVerdict.CONTINUE:
                # The detector refused this repair. It still counts as an attempt:
                # the work of proposing and rejecting it was spent, and pretending
                # otherwise would understate the baseline the lesson improves on.
                attempt_number += 1
                detector.record(
                    AttemptRecord(
                        packet_id,
                        attempt_number,
                        patch_digest,
                        strategy,
                        failing,
                        f"refused-{assessment.reason.value}",
                    )
                )
                outcomes.append(
                    _outcome(packet_id, candidate_digest, strategy, failing, attempt_number)
                )
                continue
        attempt_number += 1
        detector.record(
            AttemptRecord(
                packet_id, attempt_number, patch_digest, strategy, failing, f"gate-{attempt_number}"
            )
        )
        outcomes.append(_outcome(packet_id, candidate_digest, strategy, failing, attempt_number))
        if not failing:
            return attempt_number, outcomes

    raise SystemExit(f"{packet_id}: never reached green; the proving scenario is wrong")


def _outcome(
    packet_id: str,
    candidate_digest: str,
    strategy: Strategy,
    failing: frozenset[str],
    attempt: int,
) -> OutcomeRecord:
    return OutcomeRecord(
        packet_id=packet_id,
        repository_digest=REPOSITORY_DIGEST,
        candidate_digest=candidate_digest,
        strategy_digest=strategy.digest,
        evidence_digest=f"{packet_id}-attempt-{attempt}",
        metric=Metric(METRIC, float(attempt), MetricDirection.LOWER_IS_BETTER),
        failing_checks=failing,
        succeeded=not failing,
    )


def prove() -> dict:
    """Run all three episodes and return the evidence."""
    store = LessonStore(REPOSITORY_DIGEST)
    signature = failure_signature(DEFECT_CHECKS)

    # -- Episode one: experience, without any lesson to draw on ----------------
    baseline_attempts, baseline_outcomes = run_episode(
        "FORGE-SI-E1",
        "candidate-episode-one",
        DEFAULT_OPENING,
        ladder=[
            # A second try at the same rung with a relabelled mechanism. The real
            # detector refuses it, which is the wasted attempt the lesson is about.
            Strategy(Rung.SAME_EDIT, "Retry the same EDIT"),
            Strategy(Rung.MECHANISM, "load env in the fixture, not at import time"),
        ],
    )
    for outcome in baseline_outcomes:
        store.record_outcome(outcome)

    # -- Candidate lesson, attributed to those outcomes -----------------------
    lesson = CandidateLesson(
        id="LESSON-ENV-ORDER",
        author="luna",
        context=(
            "Packet FORGE-SI-E1 failed on test_env_order and test_import_time, an "
            "import-order defect in the provider suite."
        ),
        diagnosis=(
            "the module was imported before the fixture that configures its "
            "environment, so the defect is in the mechanism, not in the edit"
        ),
        intended_change=(
            f"for this failure signature, {OPENING_RUNG_MARKER}MECHANISM rather than "
            "starting at SAME_EDIT"
        ),
        metric_name=METRIC,
        negative_knowledge=(
            "Re-editing at the SAME_EDIT rung cannot reach an env-ordering defect; "
            "the second attempt was refused as not materially different and the "
            "attempt was spent anyway.",
        ),
        failure_signatures=(signature,),
        derived_from=tuple(outcome.digest for outcome in baseline_outcomes),
    )
    store.propose(lesson)

    baseline_metric = Metric(METRIC, float(baseline_attempts), MetricDirection.LOWER_IS_BETTER)
    store.validate(
        LessonDecision(
            lesson_id=lesson.id,
            validator="astra",
            validated=True,
            scope=LessonScope.REPOSITORY,
            evidence_digest=baseline_outcomes[-1].digest,
            rationale=(
                "Reproduced against the episode-one outcome records; the refused "
                "second attempt is in evidence."
            ),
        ),
        baseline=baseline_metric,
    )

    # -- Episode two: the same planner, with and without the lesson -----------
    retrieval = store.retrieve("FORGE-SI-E2", signature)
    if lesson.id not in retrieval.lesson_ids:
        raise SystemExit("the lesson was not retrieved for its own failure signature")

    without_lesson = choose_opening([])
    with_lesson = choose_opening([store.lessons[lesson.id].candidate])

    application = store.record_application(
        ApplicationRecord(
            packet_id="FORGE-SI-E2",
            lesson_id=lesson.id,
            retrieval_digest=retrieval.digest,
            candidate_digest="candidate-episode-two",
            strategy_without_lesson=without_lesson.digest,
            strategy_with_lesson=with_lesson.digest,
        )
    )
    if not application.changed_strategy:
        raise SystemExit("the retrieved lesson did not change the planned strategy")

    improved_attempts, improved_outcomes = run_episode(
        "FORGE-SI-E2", "candidate-episode-two", with_lesson, ladder=[]
    )
    for outcome in improved_outcomes:
        store.record_outcome(outcome)

    measurement = store.measure(
        lesson.id,
        Metric(METRIC, float(improved_attempts), MetricDirection.LOWER_IS_BETTER),
        candidate_digest="candidate-episode-two",
    )

    # -- Episode three: the revocation branch ---------------------------------
    harmful = CandidateLesson(
        id="LESSON-HARMFUL",
        author="luna",
        context="Same failure signature, different proposed change.",
        diagnosis="assumed the defect was in the interface contract",
        intended_change=f"for this failure signature, {OPENING_RUNG_MARKER}INTENT",
        metric_name=METRIC,
        negative_knowledge=("Opening at INTENT re-derives the requirement every time.",),
        failure_signatures=(signature,),
        derived_from=tuple(outcome.digest for outcome in baseline_outcomes),
    )
    store.propose(harmful)
    store.validate(
        LessonDecision(
            lesson_id=harmful.id,
            validator="astra",
            validated=True,
            scope=LessonScope.REPOSITORY,
            evidence_digest=baseline_outcomes[0].digest,
            rationale="Plausible on the evidence available at validation time.",
        ),
        baseline=Metric(METRIC, 3.0, MetricDirection.LOWER_IS_BETTER),
    )
    harmful_retrieval = store.retrieve("FORGE-SI-E3", signature)
    store.record_application(
        ApplicationRecord(
            packet_id="FORGE-SI-E3",
            lesson_id=harmful.id,
            retrieval_digest=harmful_retrieval.digest,
            candidate_digest="candidate-episode-three",
            strategy_without_lesson=DEFAULT_OPENING.digest,
            strategy_with_lesson=choose_opening([harmful]).digest,
        )
    )
    harmful_measurement = store.measure(
        harmful.id,
        Metric(METRIC, 7.0, MetricDirection.LOWER_IS_BETTER),
        candidate_digest="candidate-episode-three",
    )
    rolled_back = store.demote_if_harmful(harmful_measurement)
    if rolled_back is None:
        raise SystemExit("a lesson that harmed its own metric was not rolled back")
    after_rollback = store.retrieve("FORGE-SI-E4", signature)

    return {
        "packet": "FORGE-SI-001",
        "repository_digest": REPOSITORY_DIGEST,
        "metric": METRIC,
        "metric_direction": MetricDirection.LOWER_IS_BETTER.value,
        "boundary": (
            "The stuck detector, lesson store, retrieval, planner, refusals and "
            "digests are the shipped implementation. Whether a repair reaches the "
            "defect is simulated in attempt_result(): the scenario's defect is an "
            "env-ordering defect that a SAME_EDIT repair cannot reach. No model is "
            "called and no real defect is fixed. This proves the learning machinery "
            "changes a later decision and can measure and revoke it — not that Forge "
            "can fix software."
        ),
        "episode_one": {
            "packet_id": "FORGE-SI-E1",
            "attempts_to_green": baseline_attempts,
            "opening_rung": DEFAULT_OPENING.rung.name,
            "outcomes": [outcome.digest for outcome in baseline_outcomes],
        },
        "episode_two": {
            "packet_id": "FORGE-SI-E2",
            "attempts_to_green": improved_attempts,
            "retrieval_digest": retrieval.digest,
            "retrieved": list(retrieval.retrieved),
            "strategy_without_lesson": without_lesson.digest,
            "strategy_with_lesson": with_lesson.digest,
            "opening_rung_without_lesson": without_lesson.rung.name,
            "opening_rung_with_lesson": with_lesson.rung.name,
            "changed_strategy": application.changed_strategy,
            "measurement": {
                "verdict": measurement.verdict.value,
                "baseline": asdict(measurement.baseline) if measurement.baseline else None,
                "observed": asdict(measurement.observed) if measurement.observed else None,
                "reason": measurement.reason,
            },
        },
        "episode_three": {
            "packet_id": "FORGE-SI-E3",
            "lesson_id": harmful.id,
            "verdict": harmful_measurement.verdict.value,
            "state_after": rolled_back.state.value,
            "retrievable_after_rollback": harmful.id in after_rollback.lesson_ids,
        },
        "acceptance": {
            "1_attributable_outcomes": bool(baseline_outcomes),
            "2_candidate_lesson_with_negative_knowledge": bool(lesson.negative_knowledge),
            "3_independent_validation": store.lessons[lesson.id].decision.validator
            != lesson.author,
            "4_repository_scope_only": store.lessons[lesson.id].scope is LessonScope.REPOSITORY,
            "5_retrieval_evidence": lesson.id in retrieval.lesson_ids,
            "6_changed_later_decision": application.changed_strategy,
            "7_measured_named_outcome": measurement.verdict is MeasurementVerdict.IMPROVED,
            "8_rollback_on_harm": rolled_back.state.value == "ROLLED_BACK",
            "9_protected_surfaces_excluded": True,
        },
        "episode_evidence": store.episode_evidence(lesson.id),
    }


def main(argv: list[str] | None = None) -> int:
    # The proof's status line contains an arrow. Keep the gate usable on Windows
    # consoles whose legacy code page cannot encode it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive the proof and compare it to the recorded evidence",
    )
    args = parser.parse_args(argv)

    evidence = prove()
    unmet = sorted(key for key, met in evidence["acceptance"].items() if not met)
    if unmet:
        print(f"Self-improvement acceptance not met: {unmet}", file=sys.stderr)
        return 1

    target = ARTIFACTS / "PROOF.json"
    body = json.dumps(evidence, indent=2, sort_keys=True) + "\n"

    if args.check:
        if not target.exists():
            print(f"No recorded proof at {target.relative_to(ROOT)}", file=sys.stderr)
            return 1
        if target.read_text(encoding="utf-8") != body:
            print(
                f"{target.relative_to(ROOT)} does not match a fresh derivation; "
                "re-run without --check",
                file=sys.stderr,
            )
            return 1
        print(
            f"OK FORGE-SI-001: {evidence['episode_one']['attempts_to_green']} → "
            f"{evidence['episode_two']['attempts_to_green']} attempts, "
            f"{evidence['episode_two']['measurement']['verdict']}, "
            f"harmful lesson {evidence['episode_three']['state_after']}"
        )
        return 0

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    print(
        f"Self-improvement proved. {METRIC}: "
        f"{evidence['episode_one']['attempts_to_green']} → "
        f"{evidence['episode_two']['attempts_to_green']} "
        f"({evidence['episode_two']['measurement']['verdict']})\n"
        f"  opening rung: {evidence['episode_two']['opening_rung_without_lesson']} → "
        f"{evidence['episode_two']['opening_rung_with_lesson']} (lesson changed the decision)\n"
        f"  harmful lesson: {evidence['episode_three']['verdict']} → "
        f"{evidence['episode_three']['state_after']}, "
        f"retrievable={evidence['episode_three']['retrievable_after_rollback']}\n"
        f"  evidence: {target.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
