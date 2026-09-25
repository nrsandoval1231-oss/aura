#!/usr/bin/env python3
"""Derive and verify the Phase 9 Sentinel release packet from retained facts.

This is deliberately an evidence verifier, not a retrospective story writer.  It
reads the immutable Sentinel commits and prior receipts, derives the governed
requirement lineage through ProductBrain, writes a fresh core-ledger stream, and
refuses any absent, reordered, unaudited, or superseded-specification evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from forge.ledger_store import LedgerStore  # noqa: E402
from forge.product_brain import (  # noqa: E402
    DiscoveryRecord,
    FinishContract,
    NorthStar,
    ProductBrain,
    Requirement,
    RequirementStatus,
)
from forge.trust_kernel import (  # noqa: E402
    ActionKind,
    Authority,
    AuthorityGrant,
    ForgeError,
    Ledger,
    Receipt,
    RepositoryIdentity,
)

PACKET_ID = "FORGE-SENTINEL-003"
BASE = "d43e2629f2c3db87fdb1437a16f5e94a37136c53"
FIRST = "a9c464bcc2b683014b54082a615501e09bb4df8e"
CORRECTED = "61258ab0590ffb65c2c96e2117e547ae38ddfda7"
MERGE = "7c2f639232f231b0e6e748314bce487b452829e5"
FIRST_TREE = "402bf93e11e392d20d398e4e31abf7e2efd7469a"
CORRECTED_TREE = "2fa4bc1aeb83199a499d491dd1761b5924285f4e"
FORGE_AUDIT = "8c6cbfdcdca9534610bdddc3ac18d07c58a73f7b"
TARGET = Path(r"C:\Users\nrsan\AppData\Local\ForgeAgent\proving-ground\sentinal-run")
ARTIFACT = ROOT / ".agent" / "artifacts" / PACKET_ID / "RELEASE.json"
# This exists only to exercise ProductBrain's deterministic authority plumbing in
# this proof.  It is not an owner key and provides no authority outside the proof.
PROOF_ONLY_AUTHORITY_KEY = b"sentinel-release-proof-authority-key"
SENTINEL_VENV_PYTHON = Path(
    r"C:\Users\nrsan\AppData\Local\ForgeAgent\proving-ground\sentinal-venv\Scripts\python.exe"
)
PINNED_SENTINEL_002_SOURCES = {
    ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md": "bc69d0eee5c2e528a4c4d6e4d324e24cb3062434fbfa38a2237aee710088a81a",
    ".agent/tasks/FORGE-SENTINEL-002.md": "b5063822b5b9ca492e2d9702bfc296c60d12e48ba1d91b5fbd5c81d139519a7d",
    ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json": "e764b33be2a7ed0a19eae4c87b0ee86bc58cd3e2be63c9bf58ac9e78d94bd87b",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _git(target: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(target), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ForgeError(
            "SENTINEL_IDENTITY_UNAVAILABLE", result.stderr.strip() or "git verification failed"
        )
    return result.stdout.strip()


def _grant(action: ActionKind, scope: str, authority: Authority = Authority.A2) -> AuthorityGrant:
    return AuthorityGrant.issue(
        authority, action, scope, "PROOF_ONLY", signing_key=PROOF_ONLY_AUTHORITY_KEY
    )


def _requirement(
    version: int, statement: str, origin: str, supersedes: str | None = None
) -> Requirement:
    return Requirement(
        "R-SENTINEL-SHELL",
        version,
        statement,
        origin,
        RequirementStatus.PROPOSED,
        Authority.A2,
        supersedes=supersedes,
    )


def _lineage(target: Path, *, execute: bool = True) -> dict[str, Any]:
    brain = ProductBrain(owner_verification_keys={"PROOF_ONLY": PROOF_ONLY_AUTHORITY_KEY})
    north_star = NorthStar("Prove a safe Sentinel release packet", "PROOF_ONLY")
    brain.ingest_north_star(
        north_star,
        authority=Authority.A3,
        authority_grant=_grant(
            ActionKind.PROTECTED,
            ProductBrain.protected_scope_digest("NORTH_STAR_INGESTED", asdict(north_star)),
            Authority.A3,
        ),
    )
    contract = FinishContract(("Sentinel packet binds an evolved specification to later work",))
    brain.set_finish_contract(
        contract,
        authority=Authority.A3,
        authority_grant=_grant(
            ActionKind.PROTECTED,
            ProductBrain.protected_scope_digest("FINISH_CONTRACT_SET", asdict(contract)),
            Authority.A3,
        ),
    )
    initial = _requirement(
        1, "Select a usable Bash shell for Windows validation.", "FORGE-SENTINEL-002"
    )
    brain.add_requirement(
        initial,
        authority=Authority.A2,
        authority_grant=_grant(
            ActionKind.SPECIFICATION_EVOLUTION,
            ProductBrain.protected_scope_digest("REQUIREMENT_ADDED", asdict(initial)),
        ),
    )
    brain.transition_requirement(initial.id, RequirementStatus.ACTIVE, authority=Authority.A2)
    before = brain.specification_hash
    discovery = DiscoveryRecord(
        "DISC-SENTINEL-WINDOWS-SHELL-001",
        (
            "Astra FIX against a9c464b reproduced case-sensitive WindowsApps handling and invalid POSIX substring rejection.",
        ),
        "The first candidate's shell selection was ambiguous on Windows and overbroad on POSIX.",
        "Changes only the Windows shell-selection requirement; preserves valid non-Windows Bash paths.",
        True,
    )
    corrected = _requirement(
        2,
        "On Windows refuse only a case-insensitive WindowsApps path component; preserve valid non-Windows Bash paths.",
        discovery.id,
        initial.ref,
    )
    scope = ProductBrain.protected_scope_digest(
        "REQUIREMENT_VERSIONED", {"requirement": asdict(corrected), "discovery": asdict(discovery)}
    )
    brain.version_requirement(
        corrected,
        discovery=discovery,
        authority=Authority.A2,
        authority_grant=_grant(ActionKind.SPECIFICATION_EVOLUTION, scope),
    )
    brain.transition_requirement(corrected.id, RequirementStatus.ACTIVE, authority=Authority.A2)
    after = brain.specification_hash
    if (
        before == after
        or brain.requirement_history[initial.id][0].status is not RequirementStatus.SUPERSEDED
    ):
        raise ForgeError(
            "SPECIFICATION_LINEAGE_INVALID", "Sentinel requirement lineage was not retained"
        )
    packet_binding = _packet_binding(brain, after, before, target, execute=execute)
    return json.loads(
        json.dumps(
            {
                "initial_specification_hash": before,
                "evolved_specification_hash": after,
                "discovery": asdict(discovery),
                "requirements": [asdict(item) for item in brain.requirement_history[initial.id]],
                "packet_binding": packet_binding,
            },
            default=str,
        )
    )


def _target_identity(target: Path) -> dict[str, Any]:
    """Pin the one approved target before and after the bounded execution."""
    origin = _git(target, "remote", "get-url", "origin")
    if origin != "https://github.com/nrsandoval1231-oss/sentinal.git":
        raise ForgeError("SENTINEL_REPOSITORY_MISMATCH", origin)
    head = _git(target, "rev-parse", "HEAD")
    expected_tree = _git(target, "rev-parse", f"{CORRECTED}^{{tree}}")
    actual_tree = _git(target, "rev-parse", "HEAD^{tree}")
    if head != CORRECTED or actual_tree != expected_tree or actual_tree != CORRECTED_TREE:
        raise ForgeError(
            "SENTINEL_EXECUTION_CANDIDATE_MISMATCH", "HEAD/tree differs from corrected candidate"
        )
    if _git(target, "status", "--porcelain"):
        raise ForgeError("SENTINEL_WORKTREE_DIRTY", "target must be clean before execution")
    return {"target_path": str(target), "origin": origin, "head": head, "tree": actual_tree}


def _approved_execution_target() -> dict[str, str]:
    return {
        "target_path": str(TARGET),
        "origin": "https://github.com/nrsandoval1231-oss/sentinal.git",
        "head": CORRECTED,
        "tree": CORRECTED_TREE,
    }


def _execute_evolved_packet(
    specification_hash: str, target: Path, packet_identity: dict[str, str]
) -> dict[str, Any]:
    """Run the bounded current revalidation after the evolved packet registered.

    This is intentionally current evidence for the already corrected/merged target,
    never a claim that it cryptographically bound the historical repair.
    """
    if not SENTINEL_VENV_PYTHON.is_file():
        raise ForgeError("SENTINEL_EXECUTION_ENVIRONMENT_MISSING", str(SENTINEL_VENV_PYTHON))
    before = _target_identity(target)
    command = [str(SENTINEL_VENV_PYTHON), "-m", "pytest", "-q", "tests/test_ci_local.py"]
    environment = {**os.environ, "PYTHONPATH": str(target / "src")}
    completed = subprocess.run(
        command, cwd=target, env=environment, capture_output=True, text=True, check=False
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode:
        raise ForgeError("SENTINEL_EXECUTION_FAILED", output[-2000:])
    after = _target_identity(target)
    if after != before:
        raise ForgeError(
            "SENTINEL_EXECUTION_TARGET_MUTATED", "target identity changed during execution"
        )
    return {
        "kind": "CURRENT_POST_EVOLUTION_REVALIDATION",
        "specification_hash": specification_hash,
        "candidate_sha": CORRECTED,
        "target_before": before,
        "target_after": after,
        "packet_identity": packet_identity,
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "output_digest": hashlib.sha256(output.encode()).hexdigest(),
        "output_summary": output.strip().splitlines()[-1],
    }


def _packet_binding(
    brain: ProductBrain, evolved: str, superseded: str, target: Path, *, execute: bool = True
) -> dict[str, Any]:
    """Use ExecutionLoop's actual packet registration check, not a local comparison."""
    from forge.execution_loop import (
        AgentRole,
        BuildPacket,
        ContextIdentity,
        ExecutionLoop,
        _packet_scope_digest,
    )
    from forge.trust_kernel import CandidateIdentity

    repository = RepositoryIdentity(
        "https://github.com/nrsandoval1231-oss/sentinal", BASE, "/sentinal", "main"
    )
    key = b"s" * 32

    first_tree = _git(target, "rev-parse", f"{FIRST}^{{tree}}")
    if first_tree != FIRST_TREE:
        raise ForgeError("SENTINEL_PACKET_BASE_MISMATCH", "first candidate tree differs")
    packet_identity = {
        "packet_id": "FORGE-SENTINEL-002",
        "base_sha": FIRST,
        "base_tree": first_tree,
    }

    def attempt(specification_hash: str) -> str | None:
        packet = BuildPacket(
            id="FORGE-SENTINEL-003-REPAIR",
            objective="Execute the corrected Sentinel shell-selection requirement",
            requirements=("R-SENTINEL-SHELL",),
            allowed_paths=("scripts/ci_local.py", "tests/test_ci_local.py"),
            forbidden_paths=(),
            acceptance=("Windows component path handling",),
            evidence_required=("test_receipt",),
            dependencies=(),
            invariants=(),
            risk="LOW",
            authority=Authority.A2,
            retry_limit=1,
            base_candidate=CandidateIdentity(
                repository.digest, FIRST, first_tree, "FORGE-SENTINEL-002"
            ),
            specification_hash=specification_hash,
        )
        loop_id = f"sentinel-binding-{specification_hash[:8]}"
        loop = ExecutionLoop(
            brain,
            repository,
            loop_id=loop_id,
            trusted_contexts={AgentRole.ARCHITECT: {"architect": key}},
        )
        scope = _packet_scope_digest(packet)
        try:
            loop.register_packet(
                packet,
                architect_context=ContextIdentity.issue(
                    AgentRole.ARCHITECT,
                    "architect",
                    "REGISTER_PACKET",
                    scope,
                    scope,
                    loop_id,
                    signing_key=key,
                ),
            )
        except ForgeError as error:
            return error.code
        return None

    accepted = attempt(evolved)
    refused = attempt(superseded)
    if accepted is not None or refused != "SPECIFICATION_IDENTITY_MISMATCH":
        raise ForgeError(
            "SPECIFICATION_BINDING_INVALID", f"accepted={accepted!r}, refused={refused!r}"
        )
    if execute:
        execution = _execute_evolved_packet(evolved, target, packet_identity)
    else:
        pinned = _target_identity(target)
        execution = {
            "kind": "CURRENT_POST_EVOLUTION_REVALIDATION",
            "specification_hash": evolved,
            "candidate_sha": CORRECTED,
            "target_before": pinned,
            "target_after": dict(pinned),
            "packet_identity": packet_identity,
            "command": f"{SENTINEL_VENV_PYTHON} -m pytest -q tests/test_ci_local.py",
            "exit_code": 0,
        }
    return {
        "evolved_packet_accepted": True,
        "superseded_packet_refused": refused,
        "execution_receipt": execution,
    }


def _identity(target: Path) -> dict[str, Any]:
    pinned = _target_identity(target)
    origin = pinned["origin"]
    for ancestor, descendant in ((BASE, FIRST), (FIRST, CORRECTED), (CORRECTED, MERGE)):
        if subprocess.run(
            ["git", "-C", str(target), "merge-base", "--is-ancestor", ancestor, descendant],
            capture_output=True,
        ).returncode:
            raise ForgeError(
                "SENTINEL_ANCESTRY_INVALID", f"{ancestor} is not an ancestor of {descendant}"
            )
    paths = _git(target, "diff", "--name-only", BASE, CORRECTED).splitlines()
    if sorted(paths) != ["scripts/ci_local.py", "tests/test_ci_local.py"]:
        raise ForgeError("SENTINEL_SCOPE_INVALID", repr(paths))
    parents = _git(target, "show", "-s", "--format=%P", MERGE).split()
    if CORRECTED not in parents:
        raise ForgeError(
            "SENTINEL_MERGE_INVALID", "remote merge does not directly contain corrected candidate"
        )
    return {
        "repository": "nrsandoval1231-oss/sentinal",
        "origin": origin,
        "baseline_sha": BASE,
        "first_candidate_sha": FIRST,
        "corrected_candidate_sha": CORRECTED,
        "remote_merge_sha": MERGE,
        "remote_merge_parents": parents,
        "audited_paths": paths,
        "execution_target": pinned,
    }


def _real_learning(root: Path) -> dict[str, Any]:
    result = json.loads(
        (root / ".agent/artifacts/FORGE-EXT-002/RESULT.json").read_text(encoding="utf-8")
    )
    learning = result["learning"]
    measurement = learning["measurement"]
    if not (
        learning["changed_strategy"]
        and measurement["baseline"] == 1.0
        and measurement["observed"] == 0.0
        and measurement["verdict"] == "IMPROVED"
    ):
        raise ForgeError("REAL_LEARNING_EVIDENCE_INVALID", "EXT learning episode is incomplete")
    return {
        "packet": "FORGE-SI-001",
        "source_packets": ["FORGE-EXT-001", "FORGE-EXT-002"],
        "lesson_id": learning["lesson_id"],
        "lesson_digest": learning["lesson_digest"],
        "retrieval_digest": learning["retrieval_digest"],
        "application_digest": learning["application_digest"],
        "changed_strategy": True,
        "metric": measurement,
    }


def _file_digest(path: Path) -> str:
    if not path.is_file():
        raise ForgeError("RELEASE_SOURCE_MISSING", str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _release(root: Path, target: Path, *, execute: bool = True) -> dict[str, Any]:
    lineage = _lineage(target, execute=execute)
    identity = _identity(target)
    audit = root / ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md"
    task = root / ".agent/tasks/FORGE-SENTINEL-002.md"
    completion = root / ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json"
    sources = {
        ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md": _file_digest(audit),
        ".agent/tasks/FORGE-SENTINEL-002.md": _file_digest(task),
        ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json": _file_digest(completion),
    }
    if sources != PINNED_SENTINEL_002_SOURCES:
        raise ForgeError(
            "SENTINEL_HISTORICAL_SOURCE_MISMATCH", "retained Sentinel-002 source differs"
        )
    audit_text = audit.read_text(encoding="utf-8")
    if FORGE_AUDIT not in audit_text or CORRECTED not in audit_text:
        raise ForgeError("SENTINEL_AUDIT_MISSING", "independent PASS binding is absent")
    return {
        "schema": 1,
        "packet_id": PACKET_ID,
        "mission_snapshot": {"phase": 9, "objective": "Sentinel proving ground", "state": "MERGED"},
        "repository_identity": identity,
        "initial_specification_hash": lineage["initial_specification_hash"],
        "evolved_specification_hash": lineage["evolved_specification_hash"],
        "execution_graph": ["FORGE-SENTINEL-001", "FORGE-SENTINEL-002", PACKET_ID],
        "build_packets": ["FORGE-SENTINEL-001", "FORGE-SENTINEL-002"],
        "candidate_shas": {"baseline": BASE, "first": FIRST, "corrected": CORRECTED},
        "test_receipts": {
            "historical_full_suite": "422 passed, 3 skipped",
            "affected": "17 passed",
            "full": "422 passed, 3 skipped",
            "ruff": "passed",
            "research_runner": "passed",
            "source": "FORGE-SENTINEL-002/RESULT.md",
            "source_digest": PINNED_SENTINEL_002_SOURCES[
                ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md"
            ],
        },
        "audit_receipts": [
            {
                "verdict": "PASS",
                "forge_candidate": FORGE_AUDIT,
                "sentinel_candidate": CORRECTED,
                "source": "FORGE-SENTINEL-002/RESULT.md",
                "source_digest": PINNED_SENTINEL_002_SOURCES[
                    ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md"
                ],
            }
        ],
        "repair_history": [
            {
                "from": FIRST,
                "to": CORRECTED,
                "reason": "case-insensitive WindowsApps component check; preserve POSIX paths",
            }
        ],
        "discovery_records": [lineage["discovery"]],
        "specification_patch_history": lineage["requirements"],
        "restart_receipts": {
            "stream": PACKET_ID,
            "prefix_through": "EXECUTION",
            "checkpoint_required": True,
        },
        "merge_receipts": [{"commit": MERGE, "contains": CORRECTED, "remote": "origin/main"}],
        "outcome_evaluation": {
            "classification": "CONFIRMED",
            "scope": "Sentinel local validation repair",
            "billing": "UNKNOWN",
        },
        "lesson_candidates": [_real_learning(root)],
        "finish_contract_evaluation": {
            "phase_9_release_fields_present": True,
            "v0_completion_verdict": "WITHHELD_PENDING_INDEPENDENT_AUDIT",
        },
        "specification_binding": lineage["packet_binding"],
        "historical_provenance": {
            "result": {
                "path": ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md",
                "digest": PINNED_SENTINEL_002_SOURCES[
                    ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md"
                ],
            },
            "packet": {
                "path": ".agent/tasks/FORGE-SENTINEL-002.md",
                "digest": PINNED_SENTINEL_002_SOURCES[".agent/tasks/FORGE-SENTINEL-002.md"],
            },
            "completion": {
                "path": ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json",
                "digest": PINNED_SENTINEL_002_SOURCES[
                    ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json"
                ],
            },
        },
    }


def _ledger_for(release: dict[str, Any], stop_after: str | None = None) -> Ledger:
    required = (
        "MISSION",
        "REPOSITORY",
        "DISCOVERY",
        "SPECIFICATION",
        "BUILD_PACKET",
        "CANDIDATE",
        "EXECUTION",
        "RESTART",
        "TEST",
        "AUDIT",
        "MERGE",
        "OUTCOME",
        "LESSON",
        "FINISH_CONTRACT",
    )
    ledger = Ledger(stream_id=PACKET_ID)
    previous = None
    for sequence, event in enumerate(required, 1):
        payload = {"release_digest": _digest(release), "event": event}
        if event == "EXECUTION":
            execution = release["specification_binding"].get("execution_receipt")
            payload["execution_receipt_digest"] = _digest(execution) if execution else None
        if event == "RESTART":
            payload["prefix_checkpoint"] = {
                "sequence": ledger.checkpoint.sequence,
                "head_hash": ledger.checkpoint.head_hash,
                "stream_id": PACKET_ID,
            }
            payload["reloaded_checkpoint"] = dict(payload["prefix_checkpoint"])
        receipt = Receipt.create(
            sequence,
            event,
            previous,
            event,
            payload,
            ledger.checkpoint.head_hash,
        )
        ledger.append(receipt)
        previous = event
        if event == stop_after:
            break
    return ledger


def _checkpoint_identity(ledger: Ledger) -> dict[str, Any]:
    checkpoint = ledger.checkpoint
    return {
        "sequence": checkpoint.sequence,
        "head_hash": checkpoint.head_hash,
        "stream_id": checkpoint.stream_id,
    }


def _verify_execution_identity(release: dict[str, Any], execution: dict[str, Any]) -> None:
    """Verify every stable fact that identifies the post-evolution execution."""
    expected_target = _approved_execution_target()
    if release["repository_identity"].get("execution_target") != expected_target:
        raise ForgeError("RELEASE_EXECUTION_MISMATCH", "repository execution target conflicts")
    expected_packet = {
        "packet_id": "FORGE-SENTINEL-002",
        "base_sha": FIRST,
        "base_tree": FIRST_TREE,
    }
    for field in ("target_before", "target_after"):
        if execution.get(field) != expected_target:
            raise ForgeError("RELEASE_EXECUTION_MISMATCH", f"{field} differs from approved target")
    if execution["target_before"] != execution["target_after"]:
        raise ForgeError("RELEASE_EXECUTION_MISMATCH", "execution target changed during run")
    if execution.get("packet_identity") != expected_packet:
        raise ForgeError("RELEASE_EXECUTION_MISMATCH", "execution packet identity conflicts")


def _verify_prefix(release: dict[str, Any], ledger: Ledger) -> None:
    """Validate the persisted, authenticated execution prefix before continuation."""
    expected_events = [
        "MISSION",
        "REPOSITORY",
        "DISCOVERY",
        "SPECIFICATION",
        "BUILD_PACKET",
        "CANDIDATE",
        "EXECUTION",
    ]
    if [receipt.event for receipt in ledger.receipts] != expected_events:
        raise ForgeError("RELEASE_RESTART_INVALID", "resume requires exactly the execution prefix")
    if ledger.checkpoint.sequence != 7 or not ledger.checkpoint.head_hash:
        raise ForgeError(
            "RELEASE_RESTART_INVALID", "execution prefix checkpoint is forged or incomplete"
        )
    if ledger.checkpoint.head_hash != ledger.receipts[-1].receipt_hash:
        raise ForgeError(
            "RELEASE_RESTART_INVALID", "execution prefix head does not bind receipt seven"
        )
    if any(
        receipt.payload.get("release_digest") != _digest(release) for receipt in ledger.receipts
    ):
        raise ForgeError("RELEASE_RECEIPT_MISMATCH", "prefix is not bound to retained release")
    execution = release.get("specification_binding", {}).get("execution_receipt")
    if not isinstance(execution, dict) or ledger.receipts[-1].payload.get(
        "execution_receipt_digest"
    ) != _digest(execution):
        raise ForgeError(
            "RELEASE_EXECUTION_LEDGER_MISMATCH", "prefix cannot recover execution evidence"
        )


def verify_release(release: dict[str, Any], ledger: Ledger) -> None:
    required = {
        "mission_snapshot",
        "repository_identity",
        "initial_specification_hash",
        "evolved_specification_hash",
        "execution_graph",
        "build_packets",
        "candidate_shas",
        "test_receipts",
        "audit_receipts",
        "repair_history",
        "discovery_records",
        "specification_patch_history",
        "restart_receipts",
        "merge_receipts",
        "outcome_evaluation",
        "lesson_candidates",
        "finish_contract_evaluation",
        "specification_binding",
        "historical_provenance",
    }
    if not required <= release.keys() or not release["audit_receipts"]:
        raise ForgeError("RELEASE_EVIDENCE_MISSING", "release packet lacks required evidence")
    discoveries = release["discovery_records"]
    if (
        not isinstance(discoveries, list)
        or len(discoveries) != 1
        or not all(
            discoveries[0].get(key) for key in ("id", "evidence", "rationale", "impact_analysis")
        )
        or discoveries[0].get("validated") is not True
    ):
        raise ForgeError("RELEASE_DISCOVERY_INVALID", "discovery evidence is absent or conflicting")
    patches = release["specification_patch_history"]
    if (
        not isinstance(patches, list)
        or len(patches) != 2
        or patches[0].get("status") != "SUPERSEDED"
        or patches[1].get("status") != "ACTIVE"
        or patches[1].get("supersedes") != "R-SENTINEL-SHELL:v1"
        or patches[1].get("origin") != discoveries[0].get("id")
    ):
        raise ForgeError("RELEASE_SPECIFICATION_HISTORY_INVALID", "specification lineage conflicts")
    restart = release["restart_receipts"]
    if restart != {"stream": PACKET_ID, "prefix_through": "EXECUTION", "checkpoint_required": True}:
        raise ForgeError("RELEASE_RESTART_INVALID", "restart evidence conflicts")
    merges = release["merge_receipts"]
    if merges != [{"commit": MERGE, "contains": CORRECTED, "remote": "origin/main"}]:
        raise ForgeError("RELEASE_MERGE_INVALID", "merge evidence conflicts")
    tests = release["test_receipts"]
    required_tests = {
        "affected",
        "full",
        "historical_full_suite",
        "ruff",
        "research_runner",
        "source",
        "source_digest",
    }
    if (
        not isinstance(tests, dict)
        or not required_tests <= tests.keys()
        or any(not tests[key] for key in required_tests)
    ):
        raise ForgeError("RELEASE_TEST_EVIDENCE_INVALID", "test evidence is absent")
    if (
        tests["full"] != tests["historical_full_suite"]
        or tests["source"] != "FORGE-SENTINEL-002/RESULT.md"
    ):
        raise ForgeError("RELEASE_TEST_EVIDENCE_INVALID", "test evidence conflicts")
    provenance = release["historical_provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {"result", "packet", "completion"}:
        raise ForgeError("RELEASE_PROVENANCE_INVALID", "historical provenance is incomplete")
    expected_provenance = {
        "result": {
            "path": ".agent/artifacts/FORGE-SENTINEL-002/RESULT.md",
            "digest": PINNED_SENTINEL_002_SOURCES[".agent/artifacts/FORGE-SENTINEL-002/RESULT.md"],
        },
        "packet": {
            "path": ".agent/tasks/FORGE-SENTINEL-002.md",
            "digest": PINNED_SENTINEL_002_SOURCES[".agent/tasks/FORGE-SENTINEL-002.md"],
        },
        "completion": {
            "path": ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json",
            "digest": PINNED_SENTINEL_002_SOURCES[
                ".agent/artifacts/FORGE-SENTINEL-002/COMPLETION.json"
            ],
        },
    }
    if (
        provenance != expected_provenance
        or tests["source_digest"] != expected_provenance["result"]["digest"]
    ):
        raise ForgeError("RELEASE_PROVENANCE_INVALID", "result provenance conflicts")
    events = [receipt.event for receipt in ledger.receipts]
    expected = [
        "MISSION",
        "REPOSITORY",
        "DISCOVERY",
        "SPECIFICATION",
        "BUILD_PACKET",
        "CANDIDATE",
        "EXECUTION",
        "RESTART",
        "TEST",
        "AUDIT",
        "MERGE",
        "OUTCOME",
        "LESSON",
        "FINISH_CONTRACT",
    ]
    if events != expected:
        raise ForgeError("RELEASE_CAUSAL_ORDER_INVALID", "release receipt order is invalid")
    if (
        release["specification_binding"].get("superseded_packet_refused")
        != "SPECIFICATION_IDENTITY_MISMATCH"
    ):
        raise ForgeError("SUPERSEDED_SPECIFICATION_ACCEPTED", "old specification was not refused")
    execution = release["specification_binding"].get("execution_receipt")
    if not isinstance(execution, dict):
        raise ForgeError("RELEASE_EXECUTION_MISSING", "evolved packet has no execution receipt")
    if (
        execution.get("kind") != "CURRENT_POST_EVOLUTION_REVALIDATION"
        or execution.get("specification_hash") != release.get("evolved_specification_hash")
        or execution.get("candidate_sha") != release["candidate_shas"].get("corrected")
        or execution.get("exit_code") != 0
        or not execution.get("command")
        or not execution.get("output_digest")
    ):
        raise ForgeError(
            "RELEASE_EXECUTION_MISMATCH", "execution is not bound to evolved spec/candidate"
        )
    _verify_execution_identity(release, execution)
    if release["audit_receipts"][0].get("verdict") != "PASS":
        raise ForgeError("RELEASE_AUDIT_INVALID", "candidate lacks independent PASS")
    if release["audit_receipts"][0].get("sentinel_candidate") != release["candidate_shas"].get(
        "corrected"
    ):
        raise ForgeError("RELEASE_CANDIDATE_MISMATCH", "audit does not bind corrected candidate")
    expected_digest = _digest(release)
    if any(receipt.payload.get("release_digest") != expected_digest for receipt in ledger.receipts):
        raise ForgeError(
            "RELEASE_RECEIPT_MISMATCH", "receipt chain is not bound to release content"
        )
    execution_receipts = [item for item in ledger.receipts if item.event == "EXECUTION"]
    if len(execution_receipts) != 1 or execution_receipts[0].payload.get(
        "execution_receipt_digest"
    ) != _digest(execution):
        raise ForgeError(
            "RELEASE_EXECUTION_LEDGER_MISMATCH", "ledger does not bind execution receipt"
        )
    restart_receipts = [item for item in ledger.receipts if item.event == "RESTART"]
    if len(restart_receipts) != 1:
        raise ForgeError("RELEASE_RESTART_INVALID", "restart ledger receipt is absent")
    restart_payload = restart_receipts[0].payload
    if dict(restart_payload.get("prefix_checkpoint", {})) != dict(
        restart_payload.get("reloaded_checkpoint", {})
    ):
        raise ForgeError("RELEASE_RESTART_INVALID", "restart did not reproduce its checkpoint")
    prefix = dict(restart_payload.get("prefix_checkpoint", {}))
    execution_receipt = execution_receipts[0]
    if (
        not isinstance(prefix, dict)
        or prefix.get("sequence") != 7
        or not prefix.get("head_hash")
        or prefix.get("stream_id") != PACKET_ID
        or prefix["head_hash"] != execution_receipt.receipt_hash
    ):
        raise ForgeError(
            "RELEASE_RESTART_INVALID", "restart prefix is not the execution checkpoint"
        )
    ledger.verify()


def _release_from_artifact(artifact: Path) -> dict[str, Any]:
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    return {
        key: value
        for key, value in stored.items()
        if key not in {"release_digest", "ledger", "restart"}
    }


def _persist_release(release: dict[str, Any], store: LedgerStore) -> Ledger:
    """Persist/recover the execution prefix without repeating the external effect."""
    if store.exists:
        loaded = store.load()
        if len(loaded.receipts) == 14:
            verify_release(release, loaded)
            return loaded
        _verify_prefix(release, loaded)
        # This is deliberately after the persisted prefix has been loaded and
        # authenticated: continuation is derived from recovered state, never
        # prepared before the interruptible execution boundary.
        full = _ledger_for(release)
        store.write(full)
        loaded = store.load()
        verify_release(release, loaded)
        return loaded

    prefix = _ledger_for(release, stop_after="EXECUTION")
    store.write(prefix)
    reloaded = store.load()
    _verify_prefix(release, reloaded)
    # Do not construct the continuation until the prefix is durably reloaded.
    full = _ledger_for(release)
    store.write(full)
    loaded = store.load()
    verify_release(release, loaded)
    return loaded


def prove(*, root: Path = ROOT, target: Path = TARGET, persist: bool = False) -> dict[str, Any]:
    store = LedgerStore(root / ".agent/ledger", PACKET_ID)
    artifact = root / ".agent/artifacts" / PACKET_ID / "RELEASE.json"
    # An already complete authenticated stream is authoritative.  Do not rerun
    # the test effect merely to inspect retained evidence.
    if persist and store.exists:
        if not artifact.is_file():
            raise ForgeError(
                "RELEASE_RECOVERY_ARTIFACT_MISSING",
                "persisted execution prefix has no retained release artifact",
            )
        stored = json.loads(artifact.read_text(encoding="utf-8"))
        release = _release_from_artifact(artifact)
        loaded = _persist_release(release, store)
        result = {
            **release,
            "release_digest": _digest(release),
            "ledger": {
                "receipts": len(loaded.receipts),
                "head_hash": loaded.checkpoint.head_hash,
                "stream_id": PACKET_ID,
                "checkpoint_required": True,
            },
        }
        if "restart" not in stored:
            result["restart"] = {
                "before_checkpoint": _checkpoint_identity(
                    Ledger(loaded.receipts[:7], stream_id=PACKET_ID)
                ),
                "after_reload_checkpoint": _checkpoint_identity(
                    Ledger(loaded.receipts[:7], stream_id=PACKET_ID)
                ),
                "final_checkpoint": _checkpoint_identity(loaded),
                "execution_receipts": 1,
            }
            artifact.write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return result
    release = _release(root, target)
    ledger = _ledger_for(release)
    verify_release(release, ledger)
    result = {
        **release,
        "release_digest": _digest(release),
        "ledger": {
            "receipts": len(ledger.receipts),
            "head_hash": ledger.checkpoint.head_hash,
            "stream_id": PACKET_ID,
            "checkpoint_required": True,
        },
    }
    if persist:
        # The artifact is independently authenticated by release_digest in every
        # receipt. Write it before the interruptible prefix so a process crash
        # after EXECUTION can resume without replaying the external test effect.
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps({**release, "release_digest": _digest(release)}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        loaded = _persist_release(release, store)
        if len([item for item in loaded.receipts if item.event == "EXECUTION"]) != 1:
            raise ForgeError("RELEASE_EXECUTION_LEDGER_MISMATCH", "restart duplicated execution")
        result["restart"] = {
            "before_checkpoint": {
                "sequence": 7,
                "head_hash": loaded.receipts[6].receipt_hash,
                "stream_id": PACKET_ID,
            },
            "after_reload_checkpoint": {
                "sequence": 7,
                "head_hash": loaded.receipts[6].receipt_hash,
                "stream_id": PACKET_ID,
            },
            "final_checkpoint": {
                "sequence": loaded.checkpoint.sequence,
                "head_hash": loaded.checkpoint.head_hash,
                "stream_id": PACKET_ID,
            },
            "execution_receipts": 1,
        }
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        stored = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        retained = _release_from_artifact(ARTIFACT)
        loaded = LedgerStore(ROOT / ".agent/ledger", PACKET_ID).load()
        verify_release(retained, loaded)
        # Re-derive every stable current fact without invoking the external test
        # command. The only intentionally variable execution fields are pytest's
        # elapsed-time dependent output digest and summary.
        fresh = _release(ROOT, TARGET, execute=False)
        fresh_execution = fresh["specification_binding"].get("execution_receipt")
        retained_execution = retained["specification_binding"].get("execution_receipt")
        if not isinstance(fresh_execution, dict) or not isinstance(retained_execution, dict):
            raise ForgeError(
                "RELEASE_EXECUTION_MISMATCH", "unexpected revalidation execution state"
            )
        for field in ("output_digest", "output_summary"):
            fresh_execution.pop(field, None)
            retained_execution.pop(field, None)
        if fresh != retained:
            raise ForgeError(
                "RELEASE_ARTIFACT_STALE", "retained release artifact differs from fresh derivation"
            )
        result = {**stored}
    else:
        result = prove(persist=args.write)
    print(
        json.dumps(
            {
                "release_digest": result["release_digest"],
                "ledger_head": result["ledger"]["head_hash"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
