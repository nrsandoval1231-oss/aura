#!/usr/bin/env python3
"""Drive one real Build Packet end to end against this repository.

This is FORGE-FIX-003: the first time the Architect-Builder-Auditor loop runs on
actual repository state rather than test fixtures. It is deliberately small. The
point is not the change being shipped — it is that packet, build, audit,
merge-eligibility, receipt, and reload are exercised once against reality, so the
next defect on an unexecuted path gets found by running rather than by reading.

What is real here: the git base and candidate identity, the changed paths, and
the evidence digests, which are hashes of actual `pytest` and `ruff` output. What
is simulated: the agent roles. No model is called; the Builder's "claim" is the
work already in the tree. That boundary is stated in the emitted evidence rather
than glossed over, because a slice that overstates itself is worse than none.

    python scripts/run_slice.py [--check]

`--check` verifies the persisted evidence without rewriting it. It is one of
the gates `scripts/validate.sh` runs.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from forge import (
    AgentRole,
    AssembledContext,
    Assumption,
    AuditReport,
    Authority,
    Budget,
    BudgetLedger,
    BuilderHandoff,
    BuildPacket,
    CandidateIdentity,
    CandidateInspection,
    ContextAssembler,
    ContextIdentity,
    ContextItem,
    ContextProvenance,
    DiscoveryVerdict,
    EvidenceReceipt,
    ExecutionLoop,
    FinishContract,
    ImplementationVerdict,
    LedgerStore,
    NorthStar,
    OwnerAuthorization,
    ProductBrain,
    RepositoryIdentity,
    Requirement,
    RequirementStatus,
    SourceType,
)
from forge.audit_receipts import exact_candidate, verify_detached_audit
from forge.context_engine import ROLE_POLICY
from forge.execution_loop import (
    _audit_report_payload_digest,
    _builder_handoff_payload_digest,
    _candidate_inspection_payload_digest,
    _digest,
)
from forge.paths import path_matches
from forge.trust_kernel import ActionKind, AuthorityGrant, ForgeError

ROOT = Path(__file__).resolve().parent.parent
#: Graph statuses that mean "authorized and being worked on". A PROPOSED node
#: has no evidence yet and is not expected to; a COMPLETE one's binding is
#: history. Only these are bind-checked.
# A packet waiting for its independent audit still has a live candidate.  Its
# evidence must remain bound until the auditor resolves it; dropping it here
# makes the default gate silently certify an empty set.
UNDER_DEVELOPMENT = frozenset({"READY", "READY_AUTHORIZED", "IN_PROGRESS", "AWAITING_AUDIT"})
LEDGER_ROOT = ROOT / ".agent" / "ledger"
TASKS = ROOT / ".agent" / "tasks"
ARTIFACT_ROOT = ROOT / ".agent" / "artifacts"
RECONCILIATION_STREAM_ID = "FORGE-EVID-003"
AURA_RECONCILIATION_STREAM_ID = "AURA-EVID-001"
INTEGRATED_AUDIT_PACKET = "FORGE-INTEGRATED-001"

# Role signing keys. In V0 these are process-local: the loop's guarantee is that
# roles cannot forge each other's contexts, and distinct keys deliver that. Real
# key custody is a later packet and is not claimed here.
ARCHITECT_KEY = b"slice-architect-key-000000000000"
BUILDER_KEY = b"slice-builder-key-00000000000000"
AUDITOR_KEY = b"slice-auditor-key-00000000000000"
GOVERNOR_KEY = b"slice-governor-key-0000000000000"
OWNER_KEY = b"slice-owner-key-0000000000000000"


@dataclasses.dataclass(frozen=True)
class Packet:
    """A packet's identity and scope, read from its own markdown.

    The packet document is the authority on the packet's scope, so it is the only
    place that scope is written down. A second copy in code is a copy that drifts
    — which is what the 2026-09-21 audit found in the documents, and what review
    then found again in this script's own hand-maintained path list.
    """

    id: str
    objective: str
    allowed_paths: tuple[str, ...]
    #: The commit this packet built on, from its `## Base` section. `AGENT_RULES`
    #: already requires a packet to record its base identity; nothing read it until
    #: a branch carried two packets and each one's scope check saw the other's
    #: changed paths. Diffing every packet against `origin/main` silently assumes
    #: one packet per branch, and fails in the direction that blocks correct work.
    #: `None` keeps the old behaviour for a packet that declares no base.
    base_ref: str | None = None

    @property
    def artifacts(self) -> Path:
        return ARTIFACT_ROOT / self.id

    @property
    def self_produced(self) -> tuple[str, ...]:
        """Paths this packet's own run writes.

        Evidence cannot bind to itself: including these would make the recorded
        tree depend on the file recording it.
        """
        return (".agent/ledger/**", f".agent/artifacts/{self.id}/**")


def active_packet_ids() -> tuple[str, ...]:
    """Packets still under development, per the work graph.

    Candidate binding is a development-time gate. Once a packet is COMPLETE its
    evidence describes the candidate that was audited and merged, and a later
    packet may legitimately change files that evidence covered — re-checking it
    against a moved tree would report a failure that is really just the passage
    of time, and the only way to silence it would be to rewrite a completed
    audit's chain. What stays verifiable forever is the ledger itself, which
    `forge ledger verify` checks for every stream regardless of status.
    """
    graph = json.loads((ROOT / ".agent" / "graph" / "work-graph.json").read_text("utf-8"))
    packet_ids: set[str] = set()
    for node in graph.get("nodes", []):
        if node.get("status") not in UNDER_DEVELOPMENT:
            continue
        node_id = node.get("id", "<unknown>")
        reference = node.get("packet")
        if not isinstance(reference, str) or not reference:
            raise SystemExit(f"Active graph node {node_id} has no packet reference")
        packet_path = (ROOT / reference).resolve()
        try:
            packet_path.relative_to(TASKS.resolve())
        except ValueError as exc:
            raise SystemExit(
                f"Active graph node {node_id} has an invalid packet reference"
            ) from exc
        if packet_path.suffix != ".md" or not packet_path.is_file():
            raise SystemExit(
                f"Active graph node {node_id} references a missing packet: {reference}"
            )
        packet_ids.add(packet_path.stem)
    return tuple(sorted(packet_ids))


def load_packet(packet_id: str) -> Packet:
    """Parse a packet's objective and allowed files out of its markdown."""
    path = TASKS / f"{packet_id}.md"
    if not path.is_file():
        raise SystemExit(f"No packet document at {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")

    allowed = tuple(
        match.group(1)
        for match in re.finditer(r"^- `([^`]+)`", _section(text, "Allowed files"), re.MULTILINE)
    )
    if not allowed:
        raise SystemExit(f"{path.relative_to(ROOT)} declares no allowed files")

    objective = " ".join(_section(text, "Objective").split())
    base_match = re.search(
        r"^- `([0-9a-f]{7,40})`", _section(text, "Base", required=False), re.MULTILINE
    )
    return Packet(packet_id, objective[:200], allowed, base_match.group(1) if base_match else None)


def _section(text: str, heading: str, *, required: bool = True) -> str:
    """One section's body. Missing is fatal unless the caller says it is optional.

    `Objective` and `Allowed files` are part of the packet contract, so their
    absence is a malformed packet. `Base` is not: packets written before the branch
    carried two of them declare none, and treating that as malformed would fail
    every existing packet to add an optional field.
    """
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not match:
        if required:
            raise SystemExit(f"Packet document has no '## {heading}' section")
        return ""
    return match.group(1)


def git(*args: str) -> str:
    return _git_raw(*args).strip()


def _git_raw(*args: str) -> str:
    """Unstripped stdout.

    `git status --porcelain` encodes state in the first two columns, so its
    leading space is data. Stripping the whole output eats the first line's
    space and shifts every subsequent column read by one — which silently
    dropped changed paths rather than failing loudly.
    """
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def changed_paths(base_ref: str, self_produced: Iterable[str]) -> tuple[str, ...]:
    """Every path this branch changes, derived from git.

    This was a hand-maintained tuple, which is the exact failure the audit found
    in `README.md` and `CURRENT_STATE.md` — reproduced inside the fix for it. A
    curated list silently shrinks the candidate: paths it omits are absent from
    `changed_paths` (so they skip the loop's scope validation) and absent from
    the tree hash (so the "exact-candidate" evidence does not cover them).

    Committed changes and working-tree changes are unioned, because the slice
    runs against the worktree, not against HEAD. Paths the run writes itself
    are excluded — see Packet.self_produced.
    """
    committed = git("diff", "--name-only", f"{base_ref}...HEAD").splitlines()
    # Porcelain is "XY <path>", or "XY <old> -> <new>" for a rename. Splitting
    # once on whitespace keeps paths containing spaces intact.
    worktree = [
        line.split(maxsplit=1)[1].split(" -> ")[-1].strip('"')
        for line in _git_raw("status", "--porcelain").splitlines()
        if line.strip() and len(line.split(maxsplit=1)) > 1
    ]
    found = {path.strip() for path in (*committed, *worktree) if path.strip()}
    return tuple(
        sorted(
            path
            for path in found
            if (ROOT / path).is_file()
            and not any(path_matches(path, pattern) for pattern in self_produced)
        )
    )


def run_gate(name: str, command: list[str]) -> tuple[str, bool, str]:
    """Run a deterministic gate and hash its output into an evidence digest."""
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    output = proc.stdout + proc.stderr
    digest = hashlib.sha256(f"{name}\n{proc.returncode}\n{output}".encode()).hexdigest()
    return digest, proc.returncode == 0, output.strip().splitlines()[-1] if output else ""


def tree_hash(paths: Iterable[str]) -> str:
    """Content hash over an explicit, ordered path list."""
    return hashlib.sha256(
        "\n".join(
            f"{path}:{hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}" for path in paths
        ).encode()
    ).hexdigest()


def _external_audit(packet: Packet) -> bool:
    """Require an independent receipt for the current clean commit.

    A generic slice retains a pre-commit ``base+worktree`` candidate for its
    append-only loop receipts and selected-file hash.  That identity is not a
    Git commit, so it cannot be the subject of a detached audit that requires a
    clean exact HEAD and complete tracked manifest.  Keep both evidence classes:
    verify the retained local identity elsewhere in ``check_recorded_evidence``
    and verify the separately derived committed identity here.  Missing,
    malformed, self-referential, or mismatched documents fail closed.
    """
    try:
        verify_detached_audit(ROOT, exact_candidate(ROOT, packet.id))
    except (ForgeError, OSError, subprocess.CalledProcessError):
        return False
    return True


def check_integrated_audit() -> int:
    """Verify the sole clean-HEAD detached-audit successor.

    This path intentionally has no SLICE.json, process-local Auditor receipt, or
    Governor merge-eligibility receipt.  Those are generated by the generic
    proving harness and cannot establish independent authority.  EVID-003 has
    already preserved and checked the redirected history; this successor binds
    the complete current committed tree to an owner-pinned external signer.
    """
    try:
        candidate = exact_candidate(ROOT, INTEGRATED_AUDIT_PACKET)
        receipt = verify_detached_audit(ROOT, candidate)
    except (ForgeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"{INTEGRATED_AUDIT_PACKET}: detached audit rejected: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {INTEGRATED_AUDIT_PACKET} detached PASS for clean HEAD "
        f"{candidate.revision} (tree {candidate.tree[:16]}, auditor {receipt['auditor_id']})"
    )
    return 0


def verify_reconciliation_records(root: Path = ROOT) -> tuple[str, ...]:
    """Verify redirected history across the immutable Forge and additive Aura streams."""
    stores = [
        LedgerStore(root / ".agent" / "ledger", stream_id)
        for stream_id in (RECONCILIATION_STREAM_ID, AURA_RECONCILIATION_STREAM_ID)
    ]
    ledgers: list[tuple[str, Any]] = []
    for store in stores:
        receipts_exist = store.receipts_path.exists()
        checkpoint_exists = store.checkpoint_path.exists()
        if not receipts_exist and not checkpoint_exists:
            continue
        ledger = store.load()
        ledger.verify()
        ledgers.append((store.stream_id, ledger))
    if not ledgers:
        raise ForgeError("LEDGER_NOT_FOUND", "No persisted reconciliation ledger stream")
    graph_path = root / ".agent" / "graph" / "work-graph.json"
    if not graph_path.is_file():
        raise SystemExit("Reconciliation graph is missing")
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit("Reconciliation graph cannot be verified") from exc
    if not isinstance(graph, Mapping) or not isinstance(graph.get("nodes"), list):
        raise SystemExit("Reconciliation graph cannot be verified")

    known_nodes: set[str] = set()
    redirected_successors: dict[str, str] = {}
    for node in graph["nodes"]:
        if not isinstance(node, Mapping):
            raise SystemExit("Reconciliation graph cannot be verified")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in known_nodes:
            raise SystemExit("Reconciliation graph has invalid node identities")
        known_nodes.add(node_id)
        if node.get("status") != "REDIRECTED":
            continue
        packet = node.get("packet")
        successor = node.get("redirected_to")
        if not isinstance(packet, str) or not packet or not Path(packet).stem:
            raise SystemExit(f"Redirected graph node has invalid packet binding: {node_id}")
        if not isinstance(successor, str) or not successor:
            raise SystemExit(f"Redirected graph node lacks successor binding: {node_id}")
        packet_id = Path(packet).stem
        if successor == node_id or successor == packet_id:
            raise SystemExit(f"Redirected graph node self-loops: {node_id}")
        existing_successor = redirected_successors.get(packet_id)
        if existing_successor is not None and existing_successor != successor:
            raise SystemExit(
                f"Redirected graph packet has conflicting successor bindings: {packet_id}"
            )
        redirected_successors[packet_id] = successor
    missing_successors = sorted(set(redirected_successors.values()) - known_nodes)
    if missing_successors:
        raise SystemExit(
            "Reconciliation successor is not a graph node: " + ", ".join(missing_successors)
        )

    seen: set[str] = set()
    packet_ids: list[str] = []
    records = [
        (stream_id, receipt)
        for stream_id, ledger in ledgers
        for receipt in ledger.receipts
    ]
    if not records:
        raise SystemExit("Reconciliation ledgers have no records")
    for line_number, (stream_id, receipt) in enumerate(records, 1):
        if receipt.event != "RECONCILIATION_RECORDED":
            raise SystemExit(f"Reconciliation ledger contains an unrelated event at receipt {line_number}")
        record = receipt.payload
        if not isinstance(record, Mapping):
            raise SystemExit(f"Malformed reconciliation record at receipt {line_number}")
        required = (
            "packet_id",
            "status",
            "evidence_class",
            "reason",
            "successor_packet_id",
        )
        if any(not isinstance(record.get(key), str) or not record.get(key) for key in required):
            raise SystemExit(f"Incomplete reconciliation record at receipt {line_number}")
        packet_id = str(record["packet_id"])
        if record["status"] != "REDIRECTED" or packet_id in seen:
            raise SystemExit(f"Invalid or duplicate reconciliation at receipt {line_number}")
        successor_packet_id = str(record["successor_packet_id"])
        expected_successor = redirected_successors.get(packet_id)
        if expected_successor is None:
            raise SystemExit(f"Reconciliation record names non-redirected packet: {packet_id}")
        if successor_packet_id != expected_successor:
            raise SystemExit(f"Reconciliation successor mismatch at receipt {line_number}")
        evidence_class = record["evidence_class"]
        if evidence_class not in {"FULL_SLICE_AND_LEDGER", "LEDGER_ONLY", "NO_LEGACY_EVIDENCE"}:
            raise SystemExit(f"Invalid evidence class at receipt {line_number}")
        old_stream = record.get("old_ledger_stream")
        slice_path = record.get("slice_path")
        canonical_stream = packet_id
        canonical_slice = f".agent/artifacts/{packet_id}/SLICE.json"
        if evidence_class == "NO_LEGACY_EVIDENCE":
            if (
                old_stream
                or slice_path
                or record.get("old_candidate_digest")
                or record.get("old_ledger_head")
                or (root / ".agent" / "ledger" / f"{canonical_stream}.jsonl").exists()
                or (root / ".agent" / "ledger" / f"{canonical_stream}.checkpoint.json").exists()
                or (root / canonical_slice).exists()
            ):
                raise SystemExit(
                    f"No-evidence record contains legacy evidence at receipt {line_number}"
                )
        else:
            if old_stream != canonical_stream:
                raise SystemExit(f"Legacy ledger path is required at receipt {line_number}")
            ledger_path = root / ".agent" / "ledger" / f"{old_stream}.jsonl"
            checkpoint_path = root / ".agent" / "ledger" / f"{old_stream}.checkpoint.json"
            if not ledger_path.is_file() or not checkpoint_path.is_file():
                raise SystemExit(f"Legacy ledger is incomplete at receipt {line_number}")
            try:
                old_store = LedgerStore(root / ".agent" / "ledger", old_stream)
                old_ledger = old_store.load()
                old_ledger.verify()
            except (OSError, UnicodeError, ForgeError, ValueError) as exc:
                raise SystemExit(
                    f"Retained ledger cannot be verified at receipt {line_number}"
                ) from exc
            if record.get("old_ledger_head") != old_ledger.checkpoint.head_hash:
                raise SystemExit(f"Retained evidence identity mismatch at receipt {line_number}")
            if evidence_class == "LEDGER_ONLY":
                if (root / canonical_slice).exists():
                    raise SystemExit(
                        f"Ledger-only evidence has a retained slice at receipt {line_number}"
                    )
                if record.get("old_candidate_digest") is not None:
                    raise SystemExit(
                        f"Ledger-only evidence cannot claim a candidate digest at receipt {line_number}"
                    )
            elif (
                not isinstance(record.get("old_candidate_digest"), str)
                or not record["old_candidate_digest"]
            ):
                raise SystemExit(f"Old candidate digest is required at receipt {line_number}")
        if evidence_class == "FULL_SLICE_AND_LEDGER":
            if slice_path != canonical_slice:
                raise SystemExit(f"Present evidence paths are required at receipt {line_number}")
            slice_file = (root / slice_path).resolve()
            try:
                slice_file.relative_to(root.resolve())
                slice_record = json.loads(slice_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError, ForgeError, ValueError) as exc:
                raise SystemExit(
                    f"Retained evidence cannot be verified at receipt {line_number}"
                ) from exc
            if (
                not isinstance(slice_record, Mapping)
                or slice_record.get("candidate_digest") != record["old_candidate_digest"]
                or slice_record.get("ledger", {}).get("head_hash") != record["old_ledger_head"]
                or old_ledger.checkpoint.head_hash != record["old_ledger_head"]
            ):
                raise SystemExit(f"Retained evidence identity mismatch at receipt {line_number}")
            candidates = [
                item.payload.get("handoff", {}).get("candidate")
                for item in old_ledger.receipts
                if item.event == "CANDIDATE_REGISTERED"
            ]
            old_candidate = candidates[-1] if candidates else None
            try:
                old_identity = (
                    CandidateIdentity(**old_candidate)
                    if isinstance(old_candidate, Mapping)
                    else None
                )
            except (ForgeError, TypeError):
                old_identity = None
            if old_identity is None or old_identity.digest != record["old_candidate_digest"]:
                raise SystemExit(f"Retained ledger candidate mismatch at receipt {line_number}")
        elif evidence_class == "LEDGER_ONLY" and slice_path:
            raise SystemExit(f"Ledger-only record has a slice path at receipt {line_number}")
        if packet_id == successor_packet_id:
            raise SystemExit(f"Reconciliation successor loops to {packet_id}")
        seen.add(packet_id)
        packet_ids.append(packet_id)
    redirected_packets = set(redirected_successors)
    missing = sorted(redirected_packets - seen)
    if missing:
        raise SystemExit(
            "Redirected graph packets lack reconciliation records: " + ", ".join(missing)
        )
    extra = sorted(seen - redirected_packets)
    if extra:
        raise SystemExit("Reconciliation records name non-redirected packets: " + ", ".join(extra))
    return tuple(packet_ids)


def check_recorded_evidence(store: LedgerStore, packet: Packet) -> int:
    """Verify the committed evidence still describes the committed tree.

    The recorded `changed_paths` are the authority on what the audit covered, so
    they are what gets re-hashed. Re-deriving the path set from `git diff` makes
    this check branch-relative, which is wrong in both directions: on the base
    branch there is no diff at all, so the gate fails for having nothing to
    compare, and on a feature branch the set grows with unrelated edits, so the
    gate fails for files the audit never claimed. Neither compares what the
    audit actually bound to.
    """
    reloaded = store.load()
    reloaded.verify()
    recorded = json.loads((packet.artifacts / "SLICE.json").read_text(encoding="utf-8"))

    # SLICE.json is retained evidence and is deliberately excluded from the
    # candidate tree.  Bind its identity back to the immutable ledger so an
    # edited candidate digest, audit result, or eligibility summary cannot make
    # pending evidence appear to describe the audited candidate.
    candidates = [
        receipt.payload.get("handoff", {}).get("candidate")
        for receipt in reloaded.receipts
        if receipt.event == "CANDIDATE_REGISTERED"
    ]
    candidate_payload = candidates[-1] if candidates else None
    if not isinstance(candidate_payload, Mapping):
        print("Pending candidate binding is missing from the ledger.", file=sys.stderr)
        return 1
    try:
        candidate = CandidateIdentity(**candidate_payload)
    except (ForgeError, TypeError) as exc:
        print(f"Pending candidate binding is invalid: {exc}", file=sys.stderr)
        return 1
    if candidate.packet_id != packet.id:
        print("Pending candidate binding names a different packet.", file=sys.stderr)
        return 1
    if recorded.get("candidate_digest") != candidate.digest:
        print(
            "Pending candidate binding mismatch: SLICE.json candidate does not match the ledger.",
            file=sys.stderr,
        )
        return 1
    if recorded.get("candidate_tree") != candidate.tree:
        print(
            "Pending candidate binding mismatch: recorded tree does not match the ledger.",
            file=sys.stderr,
        )
        return 1
    candidate_positions = [
        index
        for index, receipt in enumerate(reloaded.receipts)
        if receipt.event == "CANDIDATE_REGISTERED"
    ]
    audit_receipts = [
        (index, receipt)
        for index, receipt in enumerate(reloaded.receipts)
        if receipt.event == "AUDIT_RECORDED"
    ]
    eligibility_receipts = [
        (index, receipt)
        for index, receipt in enumerate(reloaded.receipts)
        if receipt.event == "MERGE_ELIGIBILITY_GRANTED"
    ]
    if not candidate_positions or not audit_receipts:
        print("Pending candidate binding is missing an AUDIT_RECORDED receipt.", file=sys.stderr)
        return 1
    if not eligibility_receipts:
        print(
            "Pending candidate binding is missing a MERGE_ELIGIBILITY_GRANTED receipt.",
            file=sys.stderr,
        )
        return 1
    audit_index, audit_receipt = audit_receipts[-1]
    eligibility_index, eligibility_receipt = eligibility_receipts[-1]
    if not candidate_positions[-1] < audit_index < eligibility_index:
        print("Pending candidate receipts are out of order.", file=sys.stderr)
        return 1
    if audit_receipt.payload.get("candidate_digest") != candidate.digest:
        print("Pending audit is not bound to the ledger candidate.", file=sys.stderr)
        return 1
    if eligibility_receipt.payload.get("candidate_digest") != candidate.digest:
        print("Pending eligibility is not bound to the ledger candidate.", file=sys.stderr)
        return 1
    if recorded.get("audit", {}).get("bound_to_candidate") is not True:
        print("Pending audit does not assert exact candidate binding.", file=sys.stderr)
        return 1
    if recorded.get("merge_eligibility", {}).get("candidate_digest") != candidate.digest:
        print("Pending eligibility summary does not bind to the ledger candidate.", file=sys.stderr)
        return 1
    audited = recorded["changed_paths"]

    missing = [path for path in audited if not (ROOT / path).is_file()]
    if missing:
        print("Audited files are missing from the tree: " + ", ".join(missing), file=sys.stderr)
        return 1

    current = tree_hash(audited)
    if current != recorded["candidate_tree"]:
        print(
            "Audited files have changed since the slice evidence was written.\n"
            f"  recorded tree: {recorded['candidate_tree']}\n"
            f"  current tree:  {current}\n"
            "Retained evidence is stale; preserve it and obtain a fresh candidate audit.",
            file=sys.stderr,
        )
        return 1
    if recorded["ledger"]["head_hash"] != reloaded.checkpoint.head_hash:
        print("Ledger head does not match the recorded evidence.", file=sys.stderr)
        return 1
    if not _external_audit(packet):
        print(
            "Pending candidate lacks a separately supplied, exact-commit external audit; "
            "the local simulated Auditor cannot certify it.",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: {reloaded.checkpoint.sequence} receipts verified; "
        f"{len(audited)} audited files unchanged (tree {current[:16]})"
    )
    return 0


def assemble_role_contexts(
    packet_spec: Packet,
    packet: BuildPacket,
    brain: ProductBrain,
    paths: tuple[str, ...],
    gates: dict[str, tuple[str, bool, str]],
) -> dict[str, AssembledContext]:
    """Assemble each role's context under the Context Engine's policy and budget.

    The item lists are deliberately written per role rather than filtered from one
    shared list. A shared list plus a filter puts the independence guarantee in the
    filter, which is a place it can be got wrong quietly; here the Builder's list
    simply has no specification in it, and the assembler refuses the forbidden source
    types on top of that. Two independent reasons the Auditor never sees Builder
    reasoning is the right number for the property the whole audit rests on.
    """
    assembler = ContextAssembler()
    requirement_ref = requirement_for(packet_spec)

    def item(
        item_id: str,
        source: SourceType,
        body: str,
        *,
        authority: Authority = Authority.A1,
        confidence: float = 1.0,
    ) -> ContextItem:
        """One provenance-bearing context item.

        Confidence is 1.0 and authority A1 by default because everything assembled
        here is read from the repository itself — the packet document, the graph, the
        real gate output — not retrieved or inferred. The canonical sources that
        carry higher authority are raised explicitly below, so a reader can see which
        items claim it.
        """
        return ContextItem(
            id=item_id,
            content=body,
            provenance=ContextProvenance(
                source_type=source,
                source_id=item_id,
                version=1,
                authority=authority,
                confidence=confidence,
            ),
        )

    packet_item = item("packet", SourceType.PACKET, packet_spec.objective)
    requirement_item = item("requirement", SourceType.REQUIREMENT, requirement_ref)
    # Invariants and decisions are canonical, so they carry A3 rather than the
    # default: an item's authority is what a role weighs it by, and flattening
    # everything to A1 would make a canonical invariant indistinguishable from a
    # path listing.
    invariant_items = [
        item(f"invariant-{name}", SourceType.INVARIANT, name, authority=Authority.A3)
        for name in sorted(packet.invariants)
    ]
    evidence_items = [
        item(f"evidence-{name}", SourceType.EVIDENCE, f"{name}: {'PASS' if ok else 'FAIL'}")
        for name, (_, ok, _) in sorted(gates.items())
    ]
    diff_item = item("diff", SourceType.DIFF, "\n".join(paths))
    acceptance_items = [
        item(f"acceptance-{index}", SourceType.ACCEPTANCE_CRITERION, text)
        for index, text in enumerate(packet.acceptance)
    ]

    return {
        "architect": assembler.assemble(
            AgentRole.ARCHITECT,
            objective=packet_spec.objective,
            packet_id=packet_spec.id,
            items=[
                packet_item,
                requirement_item,
                *invariant_items,
                *(
                    item(f"decision-{ref}", SourceType.DECISION, ref, authority=Authority.A3)
                    for ref in sorted(brain.decisions)
                ),
            ],
        ),
        "builder": assembler.assemble(
            AgentRole.BUILDER,
            objective=packet_spec.objective,
            packet_id=packet_spec.id,
            items=[
                packet_item,
                requirement_item,
                *invariant_items,
                *(item(f"slice-{path}", SourceType.REPOSITORY_SLICE, path) for path in paths),
            ],
        ),
        "auditor": assembler.assemble(
            AgentRole.AUDITOR,
            objective=packet_spec.objective,
            packet_id=packet_spec.id,
            items=[packet_item, diff_item, *acceptance_items, *evidence_items, *invariant_items],
        ),
    }


def requirement_for(packet: Packet) -> str:
    """One requirement per packet, named from it, so the two cannot drift."""
    return f"R-{packet.id.removeprefix('FORGE-')}"


def build_brain(packet: Packet) -> ProductBrain:
    product = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})

    def grant(event: str, data: dict) -> AuthorityGrant:
        return AuthorityGrant.issue(
            Authority.A3,
            ActionKind.PROTECTED,
            product.protected_scope_digest(event, data),
            "OWNER",
            signing_key=OWNER_KEY,
        )

    north_star = NorthStar(
        "Prove the governed loop executes against real repository state", "OWNER"
    )
    product.ingest_north_star(
        north_star,
        authority=Authority.A3,
        authority_grant=grant("NORTH_STAR_INGESTED", dataclasses.asdict(north_star)),
    )
    contract = FinishContract(
        (
            "deterministic gates pass on the exact candidate",
            "evidence is bound to the candidate digest",
            "receipts reload and verify from disk",
        )
    )
    product.set_finish_contract(
        contract,
        authority=Authority.A3,
        authority_grant=grant("FINISH_CONTRACT_SET", dataclasses.asdict(contract)),
    )
    requirement_id = requirement_for(packet)
    product.add_requirement(
        Requirement(requirement_id, 1, packet.objective, "PACKET"),
        authority=Authority.A2,
    )
    product.transition_requirement(requirement_id, RequirementStatus.ACTIVE, authority=Authority.A2)
    product.add_assumption(
        Assumption(
            "A-FIX-000",
            "Agent roles in this slice are simulated; no model provider is called.",
            "slice",
            0.99,
        ),
        authority=Authority.A2,
    )
    return product


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet",
        default=None,
        help=(
            "packet id; its scope is read from .agent/tasks/<id>.md. "
            "With --check and no packet, every packet still under development is checked."
        ),
    )
    parser.add_argument("--check", action="store_true", help="verify without rewriting evidence")
    parser.add_argument(
        "--rebind",
        action="store_true",
        help="discard the existing evidence chain and bind to the current candidate",
    )
    args = parser.parse_args(argv)

    base_sha = git("rev-parse", "HEAD")
    tree_sha = git("rev-parse", "HEAD^{tree}")
    remote = git("remote", "get-url", "origin")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    repository = RepositoryIdentity(remote, base_sha, str(ROOT), branch)
    if args.check:
        try:
            graph = json.loads((ROOT / ".agent" / "graph" / "work-graph.json").read_text())
            if any(n.get("status") == "REDIRECTED" for n in graph["nodes"]):
                verify_reconciliation_records()
        except (SystemExit, ForgeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        # Verification is not branch-relative and needs no live candidate.
        targets = [args.packet] if args.packet else list(active_packet_ids())
        if not targets:
            print("No packet is under development; nothing to bind-check.")
            return 0
        failures = 0
        for packet_id in targets:
            if packet_id == INTEGRATED_AUDIT_PACKET:
                failures += check_integrated_audit()
                continue
            packet = load_packet(packet_id)
            if not (packet.artifacts / "SLICE.json").is_file():
                print(f"{packet_id}: no slice evidence yet", file=sys.stderr)
                failures += 1
                continue
            failures += check_recorded_evidence(LedgerStore(LEDGER_ROOT, packet_id), packet)
        return 1 if failures else 0

    if not args.packet:
        raise SystemExit("--packet is required when producing evidence")
    packet_spec = load_packet(args.packet)

    loop_id = f"{packet_spec.id.lower()}-slice"
    # Precedence: an explicit override, then the packet's own declared base, then
    # the branch point. The packet's declaration wins over the branch default
    # because a packet's candidate is what *it* changed, not what the branch
    # accumulated — two packets on one branch otherwise each inherit the other's
    # changed paths and fail each other's scope check.
    base_ref = os.environ.get("FORGE_SLICE_BASE") or packet_spec.base_ref or "origin/main"
    paths = changed_paths(base_ref, packet_spec.self_produced)
    if not paths:
        print(
            f"No changes against {base_ref}; there is no candidate to certify. "
            "Use --check to verify the committed evidence instead.",
            file=sys.stderr,
        )
        return 1

    # --- Deterministic gates. The Builder produces evidence; it does not certify
    # it, so these are re-run here by the Governor rather than trusted. ---
    gates = {
        "pytest": run_gate("pytest", [sys.executable, "-m", "pytest", "-q"]),
        "ruff_check": run_gate(
            "ruff_check", [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"]
        ),
        "ruff_format": run_gate(
            "ruff_format",
            [sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts"],
        ),
    }
    failed = [name for name, (_, ok, _) in gates.items() if not ok]
    if failed:
        print(f"Gates failed, refusing to certify: {', '.join(failed)}", file=sys.stderr)
        for name in failed:
            print(f"  {name}: {gates[name][2]}", file=sys.stderr)
        return 1

    brain = build_brain(packet_spec)
    base = CandidateIdentity(repository.digest, base_sha, tree_sha, packet_spec.id)
    # The candidate is the working tree: the changes this packet made.
    candidate_tree = tree_hash(paths)
    candidate = CandidateIdentity(
        repository.digest, f"{base_sha}+worktree", candidate_tree, packet_spec.id
    )

    packet = BuildPacket(
        packet_spec.id,
        packet_spec.objective,
        (requirement_for(packet_spec),),
        packet_spec.allowed_paths,
        ("AURA_ARCHITECTURE.md", "docs/finish-contract.md"),
        ("deterministic gates pass on the exact candidate",),
        ("pytest_receipt", "ruff_check_receipt", "ruff_format_receipt"),
        (),
        (),
        "LOW",
        Authority.A3,
        2,
        base,
        brain.specification_hash,
    )

    # This packet's scope reaches protected surfaces (the trust kernel's own
    # module paths and the CI workflow), so the loop demands A3 plus a separately
    # authenticated owner authorization. That authorization is real: the owner
    # instructed this repair after reading the audit that enumerated it.
    owner_authorization = OwnerAuthorization.create(
        packet, owner_ref="OWNER", evidence_digest="docs/packets/AURA-CLEAN-001.md"
    )

    # Budgets come from the Governor, not from this loop: a loop accepts one
    # candidate, so a per-loop budget could never be exhausted (FORGE-GOV-001).
    governor_budget = BudgetLedger(packet_spec.id, Budget(attempts=packet.retry_limit + 1))

    loop = ExecutionLoop(
        brain,
        repository,
        loop_id=loop_id,
        trusted_owner_authorizations=frozenset({owner_authorization.digest}),
        trusted_contexts={
            AgentRole.ARCHITECT: {"architect": ARCHITECT_KEY},
            AgentRole.BUILDER: {"builder": BUILDER_KEY},
            AgentRole.AUDITOR: {"auditor": AUDITOR_KEY},
            AgentRole.GOVERNOR: {"governor": GOVERNOR_KEY},
        },
        budget_ledger=governor_budget,
    )

    # --- Role contexts, assembled under policy and budget (FORGE-SPD-002). ---
    #
    # The Context Engine was built, tested, and imported by nothing: audit F15 found
    # it among roughly 1,760 lines wired to no caller. Assembling the real contexts
    # here is what turns its two independence properties from properties of a library
    # into properties of this run — a Builder cannot be handed the specification and
    # an Auditor cannot be handed Builder reasoning, because the assembler refuses
    # the source type rather than because a prompt asked it not to.
    contexts = assemble_role_contexts(packet_spec, packet, brain, paths, gates)

    scope = owner_authorization.scope_digest
    loop.register_packet(
        packet,
        architect_context=ContextIdentity.issue(
            AgentRole.ARCHITECT,
            "architect",
            "REGISTER_PACKET",
            scope,
            scope,
            loop_id,
            signing_key=ARCHITECT_KEY,
        ),
        owner_authorization=owner_authorization,
    )

    # --- Builder handoff: a claim, not a certification. ---
    claim = BuilderHandoff(
        packet_spec.id,
        candidate,
        ContextIdentity.issue(
            AgentRole.BUILDER,
            "builder",
            "BUILDER_HANDOFF",
            candidate.digest,
            "placeholder",
            loop_id,
            signing_key=BUILDER_KEY,
        ),
        "Declared dependencies, split provider adapters by family, made scope "
        "checking deterministic, and gave the ledger durable storage.",
        ("pytest", "ruff check", "ruff format --check"),
        ("OBS-FIX-000-unexecuted-paths-hide-defects",),
    )
    handoff = dataclasses.replace(
        claim,
        context=ContextIdentity.issue(
            AgentRole.BUILDER,
            "builder",
            "BUILDER_HANDOFF",
            candidate.digest,
            _builder_handoff_payload_digest(claim),
            loop_id,
            signing_key=BUILDER_KEY,
        ),
    )

    evidence = tuple(
        EvidenceReceipt(f"{name}_receipt", candidate.digest, ImplementationVerdict.PASS, digest)
        for name, (digest, _, _) in gates.items()
    )
    inspection_claim = CandidateInspection(
        candidate.digest,
        base.digest,
        paths,
        evidence,
        ContextIdentity.issue(
            AgentRole.GOVERNOR,
            "governor",
            "CANDIDATE_INSPECTION",
            candidate.digest,
            "placeholder",
            loop_id,
            signing_key=GOVERNOR_KEY,
        ),
    )
    inspection = dataclasses.replace(
        inspection_claim,
        context=ContextIdentity.issue(
            AgentRole.GOVERNOR,
            "governor",
            "CANDIDATE_INSPECTION",
            candidate.digest,
            _candidate_inspection_payload_digest(inspection_claim),
            loop_id,
            signing_key=GOVERNOR_KEY,
        ),
    )
    loop.receive_builder_handoff(handoff, inspection=inspection)

    # --- Independent audit, bound to this exact candidate. ---
    audit_claim = AuditReport(
        candidate.digest,
        brain.specification_hash,
        ContextIdentity.issue(
            AgentRole.AUDITOR,
            "auditor",
            "AUDIT",
            candidate.digest,
            "placeholder",
            loop_id,
            signing_key=AUDITOR_KEY,
        ),
        ImplementationVerdict.PASS,
        DiscoveryVerdict.OBSERVATION,
        (),
        (),
        (),
        ("OBS-FIX-000-unexecuted-paths-hide-defects",),
        0.9,
    )
    audit = dataclasses.replace(
        audit_claim,
        context=ContextIdentity.issue(
            AgentRole.AUDITOR,
            "auditor",
            "AUDIT",
            candidate.digest,
            _audit_report_payload_digest(audit_claim),
            loop_id,
            signing_key=AUDITOR_KEY,
        ),
    )
    loop.submit_audit(audit)

    eligibility = loop.mark_merge_eligible(
        governor_context=ContextIdentity.issue(
            AgentRole.GOVERNOR,
            "governor",
            "MERGE_ELIGIBILITY",
            candidate.digest,
            _digest({"candidate_digest": candidate.digest, "audit_digest": audit.digest}),
            loop_id,
            signing_key=GOVERNOR_KEY,
        ),
        candidate=candidate,
    )

    # --- Durable evidence, then prove it reloads. ---
    store = LedgerStore(LEDGER_ROOT, packet_spec.id)
    if args.rebind:
        store.rebind(loop.ledger)
    else:
        try:
            store.write(loop.ledger)
        except ForgeError as exc:
            if exc.code != "LEDGER_HISTORY_DIVERGED":
                raise
            # The stored chain describes a candidate that no longer exists.
            # Discarding it is a decision, so make the operator take it.
            print(
                f"{exc.code}: {exc.message}\n"
                "The stored chain describes an earlier candidate. Re-run with "
                "--rebind to replace it deliberately.",
                file=sys.stderr,
            )
            return 1
    reloaded = store.load()
    reloaded.verify()
    assert reloaded.to_records() == loop.ledger.to_records()

    packet_spec.artifacts.mkdir(parents=True, exist_ok=True)
    slice_evidence = {
        "packet_id": packet_spec.id,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": {"remote": remote, "branch": branch, "base_sha": base_sha},
        "base_candidate_digest": base.digest,
        "candidate_digest": candidate.digest,
        "candidate_tree": candidate_tree,
        "changed_paths": list(paths),
        "gates": {
            name: {"evidence_digest": digest, "passed": ok, "summary": summary}
            for name, (digest, ok, summary) in gates.items()
        },
        "audit": {
            "implementation_verdict": audit.implementation_verdict.value,
            "discovery_verdict": audit.discovery_verdict.value,
            "confidence": audit.confidence,
            "bound_to_candidate": audit.candidate_digest == candidate.digest,
        },
        "owner_authorization": {
            "owner_ref": owner_authorization.owner_ref,
            "evidence": owner_authorization.evidence_digest,
            "bound_to_packet_scope": owner_authorization.scope_digest == scope,
        },
        "merge_eligibility": {
            "candidate_digest": eligibility.candidate_digest,
            "audit_digest": eligibility.audit_digest,
            "authorized_by_role": eligibility.authorized_by.role.value,
        },
        "ledger": {
            "path": str(store.receipts_path.relative_to(ROOT)),
            "receipts": reloaded.checkpoint.sequence,
            "head_hash": reloaded.checkpoint.head_hash,
            "reloaded_and_verified": True,
        },
        # Independence recorded as evidence rather than asserted in prose. The
        # forbidden-source lists are the point: they are what the Context Engine
        # refused to put in front of each role, so a later reader can check the
        # guarantee instead of trusting it.
        "role_contexts": {
            name: {
                "digest": assembled.digest,
                "size_receipt": assembled.size_receipt(),
                "source_types": sorted({i.provenance.source_type.value for i in assembled.items}),
                "forbidden_source_types": sorted(
                    source.value
                    for source in SourceType
                    if source not in ROLE_POLICY[assembled.role]
                ),
            }
            for name, assembled in contexts.items()
        },
        "context_independence": {
            "builder_was_given_specification": any(
                item.provenance.source_type
                in {SourceType.NORTH_STAR, SourceType.DECISION, SourceType.ASSUMPTION}
                for item in contexts["builder"].items
            ),
            "auditor_was_given_builder_reasoning": any(
                item.provenance.source_type is SourceType.BUILDER_REASONING
                for item in contexts["auditor"].items
            ),
        },
        "budget": governor_budget.evidence(),
        "loop_state": loop.state.value,
        "limits": [
            "Agent roles are simulated; no model provider was called.",
            "Role signing keys are process-local, not durably custodied.",
            "Merge eligibility was computed, not acted on; no merge occurred.",
        ],
    }
    (packet_spec.artifacts / "SLICE.json").write_text(
        json.dumps(slice_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"Slice complete. Loop state: {loop.state.value}")
    print(f"Candidate: {candidate.digest[:16]}  receipts: {reloaded.checkpoint.sequence}")
    for name, (_, ok, summary) in gates.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}  {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
