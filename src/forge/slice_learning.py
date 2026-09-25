"""Durable shared experience and isolated stuck recovery for two builder lanes.

Call from the trusted Governor, not directly from a model tool. This controller
does not execute tools, schedule models, grant scope or merge candidates. It
persists planning/attempt/outcome/lesson boundaries for the live runner to use.
Every write is serialized with an OS lock and replays the core LedgerStore first.
External effects are never replayed. Incomplete evidence stays UNKNOWN.

The injected verifier must authenticate a detached review against an owner-pinned
trust anchor. It receives a digest bound to repository, review policy, candidate
and evidence. There is deliberately no default that accepts an author string.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from forge.athena_engineering import compare_outcomes, validate_metric
from forge.learning import (
    ApplicationRecord,
    CandidateLesson,
    LessonDecision,
    LessonStore,
    MeasurementVerdict,
    Metric,
    OutcomeRecord,
)
from forge.ledger_store import LedgerStore
from forge.stuck import AttemptRecord, Strategy, StuckDetector, materially_different
from forge.trust_kernel import Ledger, Receipt

LANES = frozenset({"deepseek", "luna"})
ReviewVerifier = Callable[[str, str], bool]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, set | frozenset):
        return sorted(_plain(v) for v in value)
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def _json(value: Any) -> str:
    return json.dumps(_plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _metric(data: Mapping[str, Any]) -> Metric:
    metric = Metric(**data)
    validate_metric(metric)
    return metric


class SliceLearning:
    """One project-scoped stream, shared by DeepSeek and Luna worker sessions.

    command IDs are caller-stable idempotency keys. Reusing an ID with changed
    content is refused. inspect() returns copies; callers cannot mutate projection
    state. The review policy ID must name the pinned verifier policy/version.
    """

    def __init__(
        self,
        root: Path,
        repository_digest: str,
        *,
        review_policy_id: str,
        verify_review: ReviewVerifier,
    ):
        _require(
            bool(repository_digest and review_policy_id), "Repository and review policy required"
        )
        self.root = Path(root)
        self.repository = repository_digest
        self.review_policy = review_policy_id
        self.verify_review = verify_review
        self.store = LedgerStore(self.root, "slice-learning")
        self._mutex = threading.RLock()

    def review_digest(self, event: str, payload: Mapping[str, Any]) -> str:
        """Reviewer signs this envelope after inspecting the exact referenced evidence."""
        return _digest(
            {
                "schema": 1,
                "repository": self.repository,
                "review_policy": self.review_policy,
                "event": event,
                "payload": payload,
            }
        )

    @contextmanager
    def _locked(self):
        # Kernel locks release on process exit; no stale lock-file deletion needed.
        # The lock is advisory: builders must not have access to the ledger root.
        with self._mutex:
            self.root.mkdir(parents=True, exist_ok=True)
            with (self.root / "slice-learning.lock").open("a+b") as handle:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0, os.SEEK_END)
                    if handle.tell() == 0:
                        handle.write(b"0")
                        handle.flush()
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load(self):
        if not self.store.exists:
            _require(
                not self.store.receipts_path.exists() and not self.store.checkpoint_path.exists(),
                "Incomplete ledger; reconcile explicitly instead of overwriting history",
            )
            ledger = Ledger(stream_id=self.store.stream_id)
        else:
            ledger = self.store.load()  # Checkpoint recovery is explicit, never automatic.
        state = {
            "lessons": LessonStore(self.repository),
            "slices": {},
            "lesson_contexts": {},
            "measured": set(),
            "contexts": {},
        }
        results = {}
        for record in ledger.to_records():
            envelope = record["payload"]
            _require(
                envelope["repository"] == self.repository
                and envelope["review_policy"] == self.review_policy
                and envelope["schema"] == 1,
                "Ledger belongs to another repository or review policy",
            )
            _require(record["event"] == envelope["event"], "Event envelope mismatch")
            event_id = envelope["id"]
            _require(event_id not in results, "Duplicate persisted command identity")
            result = self._apply(state, envelope)
            results[event_id] = (envelope, json.loads(_json(result)))
        return ledger, state, results

    def command(
        self, command_id: str, event: str, payload: Mapping[str, Any], *, proof: str = ""
    ) -> dict[str, Any]:
        """Validate, persist and project one trusted-runtime event atomically."""
        _require(bool(command_id.strip()), "Command identity required")
        envelope = json.loads(
            _json(
                {
                    "schema": 1,
                    "id": command_id,
                    "repository": self.repository,
                    "review_policy": self.review_policy,
                    "event": event,
                    "payload": payload,
                    "proof": proof,
                }
            )
        )
        with self._locked():
            ledger, state, results = self._load()
            if command_id in results:
                existing, result = results[command_id]
                _require(existing == envelope, "Idempotency key reused with different content")
                return json.loads(_json(result))
            result = self._apply(state, envelope)
            receipt = Receipt.create(
                len(ledger.receipts) + 1,
                event,
                None,
                None,
                envelope,
                ledger.checkpoint.head_hash,
            )
            ledger.append(receipt)
            self.store.write(ledger)
            return json.loads(_json(result))

    def inspect(self) -> dict[str, Any]:
        with self._locked():
            ledger, state, _ = self._load()
            return json.loads(
                _json(
                    {
                        "head": ledger.checkpoint.head_hash,
                        "slices": {
                            key: {
                                k: v
                                for k, v in value.items()
                                if k not in {"detector", "learning_view"}
                            }
                            for key, value in state["slices"].items()
                        },
                        "lessons": {
                            key: asdict(value) for key, value in state["lessons"].lessons.items()
                        },
                    }
                )
            )

    def recovery_plan(self, packet_id: str, proposed: Strategy) -> dict[str, str]:
        """Preflight a repair before the Governor spends another tool/model call.

        This advice cannot authorize writes. Scope and budgets remain Governor-owned.
        Observations still record even an out-of-policy attempt as historical fact.
        """
        with self._locked():
            _, state, _ = self._load()
            item = state["slices"][packet_id]
            _require(not item["closed"], "Slice is closed")
            detector = item["detector"]
            if not item["attempts"]:
                return {"action": "BUILD", "reason": "First attempt"}
            last = item["attempts"][-1]
            verdict = last["assessment"]["verdict"]
            if verdict == "CHECKS_PASSED":
                return {"action": "AUDIT", "reason": "Checks passed; independent review required"}
            if verdict == "UNKNOWN":
                return {"action": "RECONCILE", "reason": "Missing check evidence"}
            if verdict == "OWNER":
                return {"action": "OWNER", "reason": "Intent decision required"}
            if any(not state["lessons"].lessons[key].is_applicable for key in item["snapshot"]):
                return {
                    "action": "REPLAN",
                    "reason": "A pinned lesson has been withdrawn; refresh the plan before another repair",
                }
            if verdict == "RETURN_TO_INTENT" or detector.material_repairs_used >= 2:
                return {"action": "REPLAN", "reason": "Sol must revise the bounded approach"}
            previous = detector.attempts[-1].strategy
            if not materially_different(previous, proposed) or proposed.rung <= max(
                detector.rungs_tried
            ):
                return {
                    "action": "ESCALATE",
                    "reason": "A materially different higher-rung strategy is required",
                }
            return {"action": "REPAIR", "reason": "Bounded materially different repair"}

    def _verify(self, envelope: Mapping[str, Any]) -> None:
        digest = self.review_digest(envelope["event"], envelope["payload"])
        _require(
            bool(envelope["proof"]) and self.verify_review(digest, envelope["proof"]) is True,
            "Independent authenticated review required",
        )

    def _apply(self, state: dict, envelope: dict) -> dict:
        event, p = envelope["event"], envelope["payload"]
        lessons: LessonStore = state["lessons"]
        slices = state["slices"]
        if event == "slice_started":
            packet, lane = p["packet_id"], p["lane"]
            _require(packet not in slices and bool(packet), "Slice identity already used or empty")
            _require(lane in LANES, "Unknown builder lane")
            _require(
                not any(s["lane"] == lane and not s["closed"] for s in slices.values()),
                "Builder lane already owns an active slice",
            )
            _require(
                bool(p["context_key"] and p["required_checks"] and p["baseline_strategy"]),
                "Task/protocol context, required checks and baseline strategy required",
            )
            _require(
                len(p["required_checks"]) == len(set(p["required_checks"]))
                and all(isinstance(x, str) and x.strip() for x in p["required_checks"]),
                "Required check identities must be unique and nonempty",
            )
            protocol = sorted(p["required_checks"])
            context = p["context_key"]
            _require(
                context not in state["contexts"] or state["contexts"][context] == protocol,
                "Context key is already bound to a different required-check protocol",
            )
            state["contexts"][context] = protocol
            retrieval = lessons.retrieve(packet, p["query_signature"])
            # Retrieval stays recorded, but context filtering narrows actual exposure.
            ids = tuple(
                key
                for key in retrieval.lesson_ids
                if state["lesson_contexts"][key] == p["context_key"]
            )
            snapshot = {key: asdict(lessons.lessons[key]) for key in ids}
            item = {
                **p,
                "closed": False,
                "snapshot": snapshot,
                "policy_digest": _digest(snapshot),
                "retrieval_digest": retrieval.digest,
                "attempts": [],
                "outcome": None,
                "applications": [],
            }
            slices[packet] = {
                **item,
                "detector": StuckDetector(packet),
                "learning_view": copy.deepcopy(lessons),
            }
            return item
        if event == "lesson_proposed":
            candidate = CandidateLesson(**p)
            _require(candidate.id not in lessons.lessons, "Lesson IDs are immutable")
            _require(
                len(candidate.derived_from) == 1, "Scoped lesson requires one attributable baseline"
            )
            source = self._source_slice(slices, candidate.derived_from[0])
            _require(
                self._quality(source) is not None,
                "Incomplete baseline evidence cannot motivate a lesson",
            )
            _require(
                candidate.metric_name == source["outcome"]["metric"]["name"],
                "Lesson metric must match source outcome",
            )
            lessons.propose(candidate)
            state["lesson_contexts"][candidate.id] = source["context_key"]
            return {"lesson_id": candidate.id, "state": "CANDIDATE"}
        if event == "lesson_reviewed":
            self._verify(envelope)
            decision = LessonDecision(**p["decision"])
            lesson = lessons.lessons[decision.lesson_id]
            _require(
                p["candidate_digest"] == lesson.candidate.digest, "Review binds another lesson"
            )
            source = self._source_slice(slices, lesson.candidate.derived_from[0])
            baseline = _metric(source["outcome"]["metric"])
            _require(p["baseline_digest"] == _digest(asdict(baseline)), "Review baseline mismatch")
            result = lessons.validate(decision, baseline=baseline)
            return {"lesson_id": result.id, "state": result.state.value}
        if event == "lesson_measured":
            self._verify(envelope)
            pair = (p["lesson_id"], p["outcome_digest"])
            _require(pair not in state["measured"], "Outcome already measured for this lesson")
            lesson = lessons.lessons[p["lesson_id"]]
            source = self._source_slice(slices, lesson.candidate.derived_from[0])
            target = self._source_slice(slices, p["outcome_digest"])
            outcome = target["outcome"]
            observed = _metric(outcome["metric"])
            comparison = compare_outcomes(
                _metric(source["outcome"]["metric"]),
                observed,
                baseline_context=source["context_key"],
                observed_context=target["context_key"],
                quality_passed=self._quality(target),
            )
            # Attribution comes from the retained retrieval/application chain, not speed alone.
            measurement = (
                target["learning_view"].measure(
                    lesson.id, observed, candidate_digest=outcome["candidate_digest"]
                )
                if lesson.id in target["learning_view"].lessons
                else None
            )
            verdict = comparison.verdict
            if measurement is None or measurement.verdict is MeasurementVerdict.UNKNOWN:
                verdict = MeasurementVerdict.UNKNOWN
            if verdict is MeasurementVerdict.HARMED:
                lessons.demote(lesson.id, reason=comparison.reason, rollback=True)
            state["measured"].add(pair)
            return {
                "lesson_id": lesson.id,
                "verdict": verdict.value,
                "comparison": asdict(comparison),
                "attribution": {
                    "verdict": verdict.value,
                    "metric_evidence": asdict(measurement)
                    if measurement is not None
                    and comparison.verdict is not MeasurementVerdict.UNKNOWN
                    else None,
                },
                "policy_promotion": False,
            }
        _require(p.get("packet_id") in slices, "Unknown slice")
        item = slices[p["packet_id"]]
        _require(not item["closed"], "Slice is closed")
        if event == "attempt_recorded":
            _require(
                bool(p["candidate_digest"] and p["patch_digest"] and p["evidence_digest"]),
                "Candidate, patch and evidence identity required",
            )
            strategy = Strategy(**p["strategy"])
            required, ran, failed = map(
                set, (item["required_checks"], p["checks_run"], p["failing_checks"])
            )
            _require(failed <= ran, "A failing check was not executed")
            missing = required - ran
            unresolved = failed | {f"MISSING:{name}" for name in missing}
            detector = item["detector"]
            if missing:
                assessment = {"verdict": "UNKNOWN", "reason": "INCOMPLETE_CHECKS"}
            elif not failed:
                assessment = {
                    "verdict": "CHECKS_PASSED",
                    "reason": "INDEPENDENT_AUDIT_STILL_REQUIRED",
                }
            else:
                assessment = detector.assess(
                    patch_digest=p["patch_digest"], strategy=strategy, failing_checks=unresolved
                ).as_dict()
            detector.record(
                AttemptRecord(
                    p["packet_id"],
                    len(detector.attempts) + 1,
                    p["patch_digest"],
                    strategy,
                    frozenset(unresolved),
                    p["evidence_digest"],
                )
            )
            item["attempts"].append(
                {**p, "assessment": assessment, "unresolved": sorted(unresolved)}
            )
            return {"attempt": len(detector.attempts), "assessment": assessment}
        _require(bool(item["attempts"]), "No attempt evidence")
        last = item["attempts"][-1]
        if event == "lesson_applied":
            lesson_id = p["lesson_id"]
            _require(lesson_id in item["snapshot"], "Lesson was not in the slice's pinned context")
            identity = {"lesson_id": lesson_id, "candidate_digest": last["candidate_digest"]}
            _require(
                identity not in item["applications"], "Lesson already applied to this candidate"
            )
            application = ApplicationRecord(
                p["packet_id"],
                lesson_id,
                item["retrieval_digest"],
                last["candidate_digest"],
                item["baseline_strategy"],
                Strategy(**last["strategy"]).digest,
            )
            # Record the fact against the snapshot under which this work happened.
            # A concurrent demotion affects future work, not historical provenance.
            item["learning_view"].record_application(application)
            item["applications"].append(identity)
            return {
                "application_digest": application.digest,
                "changed_strategy": application.changed_strategy,
            }
        if event == "outcome_recorded":
            metric = _metric(p["metric"])
            if metric.name == "attempts_to_green":
                _require(
                    metric.value == len(item["attempts"]), "Attempt count differs from evidence"
                )
            outcome = OutcomeRecord(
                p["packet_id"],
                self.repository,
                last["candidate_digest"],
                Strategy(**last["strategy"]).digest,
                last["evidence_digest"],
                metric,
                frozenset(last["unresolved"]),
                not last["unresolved"],
            )
            _require(
                not any(
                    o.candidate_digest == outcome.candidate_digest
                    for o in lessons.outcomes.values()
                ),
                "Candidate identity must identify one slice outcome",
            )
            lessons.record_outcome(outcome)
            item["outcome"] = asdict(outcome)
            item["closed"] = True
            return {"outcome_digest": outcome.digest, "succeeded": outcome.succeeded}
        raise ValueError(f"Unknown learning event {event!r}")

    @staticmethod
    def _quality(item: dict) -> bool | None:
        last = item["attempts"][-1]
        if set(item["required_checks"]) - set(last["checks_run"]):
            return None
        return not last["failing_checks"]

    @staticmethod
    def _source_slice(slices: dict, outcome_digest: str) -> dict:
        for item in slices.values():
            data = item["outcome"]
            if data is not None:
                outcome = OutcomeRecord(**{**data, "metric": _metric(data["metric"])})
                if outcome.digest == outcome_digest:
                    return item
        raise ValueError("Outcome is absent from this project history")
