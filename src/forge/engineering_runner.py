"""Local, callback-driven governed engineering runner.

Provider execution is deliberately injected. This module owns packet boundaries,
worktrees, deterministic checks, persisted recovery decisions and review gates.
It never pushes, merges, or invokes a provider itself.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from forge.paths import paths_in_scope
from forge.stuck import Rung, Strategy, StuckDetector, patch_hash

Builder = Callable[["LaneTask"], Mapping[str, Any]]
Reviewer = Callable[[str, str], bool]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class LaneTask:
    packet_id: str
    lane: str
    worktree: Path
    allowed_paths: tuple[str, ...]
    strategy: Strategy
    lessons: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class Packet:
    id: str
    base: str
    allowed_paths: tuple[str, ...]
    checks: tuple[Check, ...]
    context_key: str = "engineering/local"
    required_checks: tuple[str, ...] = ()
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not self.id or not self.base or not self.allowed_paths or not self.checks:
            raise ValueError("packet identity, base, allowed paths and checks are required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if len(set(self.allowed_paths)) != len(self.allowed_paths):
            raise ValueError("allowed paths must be unique")
        names = tuple(check.name for check in self.checks)
        if len(set(names)) != len(names) or any(not n for n in names):
            raise ValueError("check names must be unique and nonempty")
        if self.required_checks and set(self.required_checks) != set(names):
            raise ValueError("required_checks must exactly match fixed checks")
        object.__setattr__(self, "required_checks", self.required_checks or names)


class EngineeringRunner:
    """Run one or two disjoint local lanes; every continuation is evidence-gated."""

    def __init__(
        self,
        repository: Path,
        state_dir: Path,
        *,
        review_policy_id: str,
        verify_review: Reviewer,
        learning: Any | None = None,
    ) -> None:
        if not review_policy_id or not callable(verify_review):
            raise ValueError("a pinned review policy and trusted verifier are required")
        self.repository = Path(repository).resolve()
        self.state_dir = Path(state_dir).resolve()
        self.review_policy_id = review_policy_id
        self._verify_review = verify_review
        self.learning = learning
        self._lock = threading.RLock()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / "engineering-runner.json"
        if not self.state_path.exists():
            self._write({"schema": 1, "runs": {}})
        self._read()  # Reject damaged or incompatible restart state immediately.

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("runner state is UNKNOWN; reconcile it before resuming") from exc
        if data.get("schema") != 1 or not isinstance(data.get("runs"), dict):
            raise RuntimeError("runner state is UNKNOWN; unsupported or incomplete state")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(temp, self.state_path)

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ("git", *args), cwd=cwd or self.repository, text=True, capture_output=True, check=False
        )
        if result.returncode:
            raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _changed_paths(self, worktree: Path) -> tuple[str, ...]:
        result = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=all"),
            cwd=worktree,
            text=True,
            capture_output=True,
            check=True,
        )
        lines = result.stdout.splitlines()
        return tuple(sorted(line[3:] for line in lines if len(line) > 3))

    def run(
        self,
        packets: tuple[Packet, ...],
        builders: Mapping[str, Builder],
        *,
        strategies: Mapping[str, Strategy] | None = None,
        cancel: threading.Event | None = None,
    ) -> dict[str, Any]:
        if not 1 <= len(packets) <= 2 or len({p.id for p in packets}) != len(packets):
            raise ValueError("run requires one or two uniquely identified packets")
        if set(builders) != {"deepseek", "luna"}:
            raise ValueError("both named builder callbacks must be explicitly configured")
        if len(packets) == 2 and set(packets[0].allowed_paths) & set(packets[1].allowed_paths):
            raise ValueError("overlapping write scopes must be serialized")
        cancel = cancel or threading.Event()
        strategies = strategies or {}
        results: dict[str, Any] = {}
        lesson_snapshots: dict[str, tuple[Mapping[str, Any], ...]] = {}
        with self._lock:
            state = self._read()
            for index, packet in enumerate(packets):
                lane = ("deepseek", "luna")[index]
                if packet.id in state["runs"]:
                    raise RuntimeError(
                        "packet already has durable state; inspect/reconcile before replay"
                    )
                state["runs"][packet.id] = {
                    "status": "RUNNING",
                    "lane": lane,
                    "base": packet.base,
                    "allowed_paths": list(packet.allowed_paths),
                    "checks": list(packet.required_checks),
                    "attempts": [],
                    "review_policy_id": self.review_policy_id,
                }
                if self.learning is not None:
                    started = self.learning.command(
                        f"{packet.id}:slice-started",
                        "slice_started",
                        {
                            "packet_id": packet.id,
                            "lane": lane,
                            "context_key": packet.context_key,
                            "required_checks": list(packet.required_checks),
                            "baseline_strategy": {"rung": 0, "mechanism": "initial-implementation"},
                            "query_signature": packet.context_key,
                        },
                    )
                    lesson_snapshots[packet.id] = tuple(started.get("snapshot", {}).values())
            self._write(state)
        worktrees: dict[str, Path] = {}
        for index, packet in enumerate(packets):
            lane = ("deepseek", "luna")[index]
            safe_id = hashlib.sha256(packet.id.encode()).hexdigest()[:16]
            path = self.state_dir / "worktrees" / f"{safe_id}-{lane}"
            path.parent.mkdir(parents=True, exist_ok=True)
            self._git("worktree", "add", "--detach", str(path), packet.base)
            worktrees[packet.id] = path
            state = self._read()
            state["runs"][packet.id]["worktree"] = str(path)
            self._write(state)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(packets)) as pool:
            futures = {
                pool.submit(
                    self._run_packet,
                    packet,
                    ("deepseek", "luna")[i],
                    worktrees[packet.id],
                    builders[("deepseek", "luna")[i]],
                    strategies.get(packet.id),
                    cancel,
                    lesson_snapshots.get(packet.id, ()),
                ): packet
                for i, packet in enumerate(packets)
            }
            for future in concurrent.futures.as_completed(futures):
                packet = futures[future]
                try:
                    results[packet.id] = future.result()
                except Exception as exc:
                    results[packet.id] = self._finish(
                        packet.id, {"status": "UNKNOWN", "reason": f"{type(exc).__name__}: {exc}"}
                    )
        return results

    def _run_packet(
        self,
        packet: Packet,
        lane: str,
        worktree: Path,
        builder: Builder,
        strategy: Strategy | None,
        cancel: threading.Event,
        lessons: tuple[Mapping[str, Any], ...] = (),
    ) -> dict[str, Any]:
        detector = StuckDetector(packet.id)
        strategy = strategy or Strategy(Rung.SAME_EDIT, "initial-implementation")
        failure_history: list[frozenset[str]] = []
        for attempt_no in range(1, packet.max_attempts + 1):
            if cancel.is_set():
                return self._finish(packet.id, {"status": "UNKNOWN", "reason": "cancelled"})
            if attempt_no > 1 and (
                detector.material_repairs_used >= 2
                or strategy.rung in detector.rungs_tried
                or strategy.rung <= max(detector.rungs_tried)
            ):
                return self._finish(
                    packet.id,
                    {
                        "status": "ESCALATE",
                        "reason": "recovery requires a new higher strategy rung",
                    },
                )
            if attempt_no > 2 and failure_history[-1] >= failure_history[0]:
                return self._finish(
                    packet.id,
                    {
                        "status": "ESCALATE",
                        "reason": "failing check evidence did not strictly improve",
                    },
                )
            if attempt_no > 1 and self.learning is not None:
                recovery = self.learning.recovery_plan(packet.id, strategy)
                if recovery.get("action") != "REPAIR":
                    return self._finish(packet.id, {"status": "ESCALATE", "recovery": recovery})
            try:
                builder(
                    LaneTask(packet.id, lane, worktree, packet.allowed_paths, strategy, lessons)
                )
            except Exception as exc:
                return self._finish(
                    packet.id,
                    {"status": "UNKNOWN", "reason": f"builder interrupted: {type(exc).__name__}"},
                )
            changed = self._changed_paths(worktree)
            if not changed or not paths_in_scope(changed, packet.allowed_paths):
                return self._finish(
                    packet.id,
                    {
                        "status": "REJECTED",
                        "reason": "empty or out-of-scope changed paths",
                        "changed": changed,
                    },
                )
            check_results = []
            for check in packet.checks:
                try:
                    proc = subprocess.run(
                        check.command, cwd=worktree, text=True, capture_output=True, check=False
                    )
                    check_results.append({"name": check.name, "exit_code": proc.returncode})
                except OSError:
                    check_results.append({"name": check.name, "exit_code": None})
            ran = {r["name"] for r in check_results if r["exit_code"] is not None}
            failed = {r["name"] for r in check_results if r["exit_code"] not in (0, None)}
            diff = self._git("diff", "HEAD", cwd=worktree)
            untracked = {
                name: (worktree / name).read_bytes().hex()
                for name in changed
                if "?" in self._git("status", "--porcelain", "--", name, cwd=worktree)[:2]
                and (worktree / name).is_file()
            }
            pdigest = _digest({"tracked_patch": patch_hash(diff), "untracked": untracked})
            candidate = _digest({"base": packet.base, "diff": diff, "untracked": untracked})
            evidence = _digest({"checks": check_results, "changed": changed})
            attempt_record = {
                "candidate": candidate,
                "checks": check_results,
                "changed": changed,
                "patch_digest": pdigest,
                "strategy": asdict(strategy),
            }
            self._record_attempt(packet.id, attempt_record)
            if self.learning is not None:
                self.learning.command(
                    f"{packet.id}:attempt:{attempt_no}",
                    "attempt_recorded",
                    {
                        "packet_id": packet.id,
                        "candidate_digest": candidate,
                        "patch_digest": pdigest,
                        "evidence_digest": evidence,
                        "strategy": {
                            "rung": int(strategy.rung),
                            "mechanism": strategy.mechanism,
                            "surfaces": list(strategy.surfaces),
                            "rationale": strategy.rationale,
                        },
                        "checks_run": sorted(ran),
                        "failing_checks": sorted(failed),
                    },
                )
            from forge.stuck import AttemptRecord

            detector.record(
                AttemptRecord(
                    packet.id,
                    attempt_no,
                    pdigest,
                    strategy,
                    frozenset(failed | {f"MISSING:{n}" for n in set(packet.required_checks) - ran}),
                    evidence,
                )
            )
            if ran != set(packet.required_checks):
                return self._finish(
                    packet.id,
                    {"status": "UNKNOWN", "candidate": candidate, "checks": check_results},
                )
            if failed:
                failure_history.append(frozenset(failed))
                strategy = self._next_strategy(strategy)
                continue
            review_payload = {
                "repository": str(self.repository),
                "packet": packet.id,
                "candidate": candidate,
                "patch": pdigest,
                "checks": check_results,
                "check_spec": [
                    {"name": item.name, "command": item.command} for item in packet.checks
                ],
                "policy": self.review_policy_id,
            }
            review_digest = _digest(review_payload)
            with self._lock:
                state = self._read()
                state["runs"][packet.id]["status"] = "REVIEW_PENDING"
                state["runs"][packet.id]["review_digest"] = review_digest
                self._write(state)
            return self._finish(
                packet.id,
                {
                    "status": "REVIEW_PENDING",
                    "candidate": candidate,
                    "review_digest": review_digest,
                    "checks": check_results,
                },
            )
        return self._finish(packet.id, {"status": "ESCALATE", "reason": "attempt budget exhausted"})

    @staticmethod
    def _next_strategy(current: Strategy) -> Strategy:
        if current.rung >= Rung.DESIGN:
            raise RuntimeError("recovery ladder exhausted; replan from intent")
        return Strategy(Rung(int(current.rung) + 1), f"recovery-{int(current.rung) + 1}")

    def review(self, packet_id: str, proof: str) -> dict[str, Any]:
        """Accept a review only through the verifier pinned at runner construction."""
        if not proof:
            raise ValueError("authenticated review proof required")
        with self._lock:
            state = self._read()
            run = state["runs"].get(packet_id)
            if not run or run.get("status") != "REVIEW_PENDING":
                raise ValueError("no review-pending candidate")
            digest = run.get("review_digest")
            worktree = Path(run.get("worktree", ""))
            if not worktree.is_dir():
                raise ValueError("candidate worktree is unavailable; review remains UNKNOWN")
            changed = self._changed_paths(worktree)
            if not changed or not paths_in_scope(changed, run["allowed_paths"]):
                raise ValueError("candidate changed or empty; review remains UNKNOWN")
            diff = self._git("diff", "HEAD", cwd=worktree)
            untracked = {
                name: (worktree / name).read_bytes().hex()
                for name in changed
                if "?" in self._git("status", "--porcelain", "--", name, cwd=worktree)[:2]
                and (worktree / name).is_file()
            }
            current_candidate = _digest({"base": run["base"], "diff": diff, "untracked": untracked})
            if current_candidate != run["attempts"][-1]["candidate"]:
                raise ValueError("candidate mutated after checks; fresh checks and review required")
            if not isinstance(digest, str) or self._verify_review(digest, proof) is not True:
                raise ValueError("trusted independent review verification failed")
            run["status"] = "REVIEWED"
            run["review_proof_digest"] = hashlib.sha256(proof.encode()).hexdigest()
            self._write(state)
            return {
                "packet_id": packet_id,
                "status": "REVIEWED",
                "candidate": run["attempts"][-1]["candidate"],
            }

    def _record_attempt(self, packet_id: str, attempt: dict[str, Any]) -> None:
        with self._lock:
            state = self._read()
            run = state["runs"][packet_id]
            run["attempts"].append(attempt)
            self._write(state)

    def _finish(self, packet_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            run = state["runs"][packet_id]
            if result["status"] != "REVIEW_PENDING":
                run["status"] = result["status"]
            run["result"] = result
            self._write(state)
        return result


def main() -> int:
    """Read-only status command; runtime integrations use the Python API."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("status", choices=("status",), help="show durable run state")
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.state_dir / "engineering-runner.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != 1 or not isinstance(data.get("runs"), dict):
            raise ValueError("unsupported state schema")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "UNKNOWN", "reason": str(exc)}))
        return 2
    print(json.dumps(data, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
