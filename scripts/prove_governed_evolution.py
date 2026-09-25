#!/usr/bin/env python3
"""Demonstrate governed specification evolution and restart reconciliation.

Two Finish Contract clauses had implementations and no demonstration. Both were
exercised only by unit tests; neither appeared in any harness, so nothing showed the
pieces working together on real state:

  "discovery can validate or reject specification changes with lineage"
  "local, remote, and any runtime state are separately reconciled"

The contract is explicit that the first one is not satisfied by having the states:

> Completion therefore requires demonstrated failure recovery,
> observation-to-discovery processing, governed specification evolution, and
> subsequent execution that uses the evolved specification; producing a packet alone
> is insufficient.

"Subsequent execution that uses the evolved specification" is the hard half, and it is
the half a state machine cannot show on its own. So episode one does not stop at
reaching SPEC_EVOLUTION. It evolves a requirement, then builds two packets — one bound
to the new specification hash and one bound to the old — and shows the loop accepting
the first and refusing the second. A packet that still validates against the
superseded specification would mean the evolution changed a hash and nothing else.

Episode two covers restart and reconciliation. A mission is persisted, the process's
in-memory state is discarded, and the mission is rebuilt from disk and replayed to the
same state. Then three effect classes are reconciled *separately* — a local worktree
edit, a remote push, and a runtime process — because the contract asks for them
separately and one combined verdict would hide the case where local succeeded and
remote did not. The ambiguous case is included deliberately: it must come back UNKNOWN
rather than being resolved in either direction.

    python scripts/prove_governed_evolution.py [--check]

Everything here is the shipped implementation: the trust kernel's transition table and
authority checks, the Product Brain's versioning and lineage, `LedgerStore`, and
`ExecutionLoop`'s specification binding. No model is called, and nothing about agent
quality is claimed — this is about whether the governed machinery holds on real state.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

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
    DiscoveryAuthorization,
    EffectDisposition,
    EvidenceStatus,
    ForgeError,
    MissionState,
    ReconciliationEvidence,
    RepositoryIdentity,
    TransitionEvidence,
    TrustKernel,
)

ARTIFACTS = ROOT / ".agent" / "artifacts" / "FORGE-EVO-001"
MISSION_ID = "FORGE-EVO-001"
EVIDENCE_KEY = b"evolution-evidence-key-000000000"
OWNER_KEY = b"evolution-owner-key-00000000000000"
REPOSITORY = RepositoryIdentity(
    "https://github.com/nrsandoval1231-oss/forge-agent", "proving-revision", "/proving", "main"
)

#: The path from INITIALIZING to a governed specification change, as the kernel's own
#: transition table defines it. Written out rather than searched for, because the point
#: is that this exact sequence is the only legal one — a shortest-path search would
#: quietly pass if the table were loosened.
PATH_TO_EVOLUTION = (
    MissionState.INITIALIZING,
    MissionState.UNDERSTANDING,
    MissionState.PLANNING,
    MissionState.TASK_READY,
    MissionState.IMPLEMENTING,
    MissionState.TESTING,
    MissionState.AUDITING,
    MissionState.DISCOVERY_REVIEW,
    MissionState.ACCEPTED,
    MissionState.SPEC_EVOLUTION,
)


def _evidence(before: MissionState | None, after: MissionState, label: str) -> TransitionEvidence:
    return TransitionEvidence.issue(
        label,
        "validator",
        REPOSITORY.digest,
        before.value if before else None,
        after.value,
        signing_key=EVIDENCE_KEY,
    )


def _kernel() -> TrustKernel:
    return TrustKernel(
        REPOSITORY,
        mission_id=MISSION_ID,
        evidence_verification_keys={"validator": EVIDENCE_KEY},
        owner_verification_keys={"OWNER": OWNER_KEY},
    )


def _brain() -> ProductBrain:
    """A Product Brain with no outstanding contradictions.

    The North Star and Finish Contract are not decoration: `contradictions()` reports
    their absence, and `register_packet` refuses to start work from a contradictory
    product state. Without them the binding check below would refuse both packets for
    the same unrelated reason and prove nothing about the specification hash.
    """
    brain = ProductBrain(owner_verification_keys={"OWNER": OWNER_KEY})
    north_star = NorthStar(
        "Prove governed specification evolution and restart reconciliation", "OWNER"
    )
    brain.ingest_north_star(
        north_star,
        authority=Authority.A3,
        authority_grant=_grant(
            ActionKind.PROTECTED,
            Authority.A3,
            ProductBrain.protected_scope_digest("NORTH_STAR_INGESTED", _asdict(north_star)),
        ),
    )
    contract = FinishContract(
        (
            "a specification change carries validated discovery and lineage",
            "later work binds to the evolved specification",
            "local, remote, and runtime effects reconcile separately",
        )
    )
    brain.set_finish_contract(
        contract,
        authority=Authority.A3,
        authority_grant=_grant(
            ActionKind.PROTECTED,
            Authority.A3,
            ProductBrain.protected_scope_digest("FINISH_CONTRACT_SET", _asdict(contract)),
        ),
    )
    return brain


def _grant(action: ActionKind, authority: Authority, scope_digest: str) -> AuthorityGrant:
    return AuthorityGrant.issue(authority, action, scope_digest, "OWNER", signing_key=OWNER_KEY)


def _requirement(
    version: int, statement: str, *, origin: str, supersedes: str | None = None
) -> Requirement:
    """A requirement version, in the exact lineage shape the Product Brain demands.

    `origin` must be the id of the discovery that motivated the version and
    `supersedes` must be the previous version's `ref`. Both are the Product Brain's
    rules, not this script's, and getting either wrong is refused — which is the
    lineage guarantee this episode is about.
    """
    return Requirement(
        id="R-EVO-001",
        version=version,
        statement=statement,
        origin=origin,
        status=RequirementStatus.PROPOSED,
        authority=Authority.A2,
        supersedes=supersedes,
    )


def prove_specification_evolution() -> dict:
    """Observation → discovery → governed evolution → work that uses the new spec."""
    brain = _brain()
    kernel = _kernel()

    # --- Walk the mission to SPEC_EVOLUTION, one legal transition at a time. ---
    for index, target in enumerate(PATH_TO_EVOLUTION):
        before = PATH_TO_EVOLUTION[index - 1] if index else None
        if target is MissionState.SPEC_EVOLUTION:
            break
        kernel.transition(target, evidence=_evidence(before, target, f"evidence-{index}"))

    # --- The discovery that motivates the change, with its lineage. ---
    discovery = DiscoveryRecord(
        id="DISC-EVO-001",
        evidence=("FORGE-EVO-001 attempt evidence: the stated requirement was unsatisfiable",),
        rationale=(
            "Implementation evidence showed the requirement's acceptance test could not be "
            "met as written, not that the implementation was wrong."
        ),
        impact_analysis=(
            "Versions R-EVO-001 only. No governance surface, no authority change, no "
            "weakening of an invariant."
        ),
        validated=True,
    )
    # The digest the kernel's authority grant is scoped to. Identifies the discovery
    # record itself, so a grant issued for one discovery cannot authorize evolution
    # motivated by another.
    discovery_scope = ProductBrain.protected_scope_digest("DISCOVERY_RECORDED", _asdict(discovery))

    # A requirement to evolve, and the specification hash before the change.
    original = _requirement(
        1,
        "The runtime must satisfy the original, unsatisfiable statement.",
        origin="FORGE-EVO-001-intake",
    )
    brain.add_requirement(
        original,
        authority=Authority.A2,
        authority_grant=_grant(
            ActionKind.SPECIFICATION_EVOLUTION,
            Authority.A2,
            ProductBrain.protected_scope_digest("REQUIREMENT_ADDED", _asdict(original)),
        ),
    )
    # A requirement begins PROPOSED; only an ACTIVE one may be worked on. Activating it
    # here is what makes the *superseded* hash below a real baseline — a packet bound to
    # it would otherwise be refused for the requirement's status rather than for the
    # specification identity, and the episode would prove the wrong refusal.
    brain.transition_requirement("R-EVO-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    specification_before = brain.specification_hash

    # --- The governed state transition. Refuses without a Discovery Record. ---
    refusals: dict[str, str] = {}
    try:
        kernel.transition(
            MissionState.SPEC_EVOLUTION,
            evidence=_evidence(MissionState.ACCEPTED, MissionState.SPEC_EVOLUTION, "no-discovery"),
        )
    except ForgeError as error:
        refusals["evolution_without_a_discovery_record"] = error.code

    authorization = DiscoveryAuthorization(
        record_digest=discovery_scope,
        evidence_digest="FORGE-EVO-001-attempt-evidence",
        rationale=discovery.rationale,
        impact_analysis=discovery.impact_analysis,
    )
    try:
        kernel.transition(
            MissionState.SPEC_EVOLUTION,
            evidence=_evidence(
                MissionState.ACCEPTED, MissionState.SPEC_EVOLUTION, "wrong-authority"
            ),
            discovery=authorization,
            authority_grant=_grant(
                ActionKind.SPECIFICATION_EVOLUTION, Authority.A1, discovery_scope
            ),
        )
    except ForgeError as error:
        refusals["evolution_with_insufficient_authority"] = error.code

    evolution_receipt = kernel.transition(
        MissionState.SPEC_EVOLUTION,
        evidence=_evidence(MissionState.ACCEPTED, MissionState.SPEC_EVOLUTION, "evolution"),
        discovery=authorization,
        authority_grant=_grant(ActionKind.SPECIFICATION_EVOLUTION, Authority.A2, discovery_scope),
    )

    # --- The specification actually changes, and the old version is superseded. ---
    evolved = _requirement(
        2,
        "The runtime must satisfy the corrected, satisfiable statement.",
        origin=discovery.id,
        supersedes=original.ref,
    )
    brain.version_requirement(
        evolved,
        discovery=discovery,
        authority=Authority.A2,
        authority_grant=_grant(
            ActionKind.SPECIFICATION_EVOLUTION,
            Authority.A2,
            ProductBrain.protected_scope_digest(
                "REQUIREMENT_VERSIONED",
                {"requirement": _asdict(evolved), "discovery": _asdict(discovery)},
            ),
        ),
    )
    # The new version also begins PROPOSED, so activating it is part of the evolution
    # taking effect rather than an extra step.
    brain.transition_requirement("R-EVO-001", RequirementStatus.ACTIVE, authority=Authority.A2)
    specification_after = brain.specification_hash
    history = brain.requirement_history["R-EVO-001"]

    # --- An unvalidated discovery cannot drive a specification change. ---
    unvalidated = DiscoveryRecord(
        id="DISC-EVO-002", evidence=(), rationale="", impact_analysis="", validated=False
    )
    try:
        brain.version_requirement(
            _requirement(
                3,
                "A third statement, motivated by nothing validated.",
                origin=unvalidated.id,
                supersedes=evolved.ref,
            ),
            discovery=unvalidated,
            authority=Authority.A2,
            authority_grant=_grant(
                ActionKind.SPECIFICATION_EVOLUTION, Authority.A2, "unused-scope"
            ),
        )
    except ForgeError as error:
        refusals["evolution_from_an_unvalidated_discovery"] = error.code

    # --- Subsequent execution uses the evolved specification. ---
    #
    # The clause the contract adds beyond "producing a packet". A packet bound to the
    # superseded hash must be refused; if both bound, the evolution would have changed
    # a hash and nothing that consumes it.
    binding = {
        "packet_bound_to_evolved_specification_accepted": _packet_binds(brain, specification_after),
        "packet_bound_to_superseded_specification_refused": not _packet_binds(
            brain, specification_before
        ),
    }

    # --- The mission continues from the evolved specification. ---
    kernel.transition(
        MissionState.REPLANNING,
        evidence=_evidence(MissionState.SPEC_EVOLUTION, MissionState.REPLANNING, "replan"),
    )
    kernel.transition(
        MissionState.PLANNING,
        evidence=_evidence(MissionState.REPLANNING, MissionState.PLANNING, "replanned"),
    )

    return {
        "path_taken": [state.value for state in PATH_TO_EVOLUTION],
        "specification_hash_before": specification_before,
        "specification_hash_after": specification_after,
        "specification_changed": specification_before != specification_after,
        "lineage": {
            "versions_retained": len(history),
            "superseded_status": history[0].status.value,
            "current_status": history[-1].status.value,
            "current_version": history[-1].version,
            "discovery_cited_in_receipt": discovery.id in json.dumps(brain.snapshot(), default=str),
        },
        "evolution_receipt": {
            "state_before": evolution_receipt.state_before,
            "state_after": evolution_receipt.state_after,
            "carries_discovery": "discovery" in evolution_receipt.payload,
            "carries_authority_grant": "authority_grant" in evolution_receipt.payload,
        },
        "subsequent_execution": binding,
        "refusals": refusals,
        "mission_state_after_replan": kernel.state.value,
        "replays_to": _replayed_state(kernel),
    }


def _packet_binds(brain: ProductBrain, specification_hash: str) -> bool:
    """Whether the loop accepts a packet bound to this specification hash.

    Uses `ExecutionLoop.register_packet`'s own binding check rather than comparing
    hashes here: comparing them in this script would prove that this script can
    compare hashes.
    """
    from forge.execution_loop import AgentRole, BuildPacket, ContextIdentity, ExecutionLoop
    from forge.trust_kernel import CandidateIdentity

    key = b"evolution-architect-key-00000000"
    candidate = CandidateIdentity(REPOSITORY.digest, "base", "tree-base", "FORGE-EVO-P1")
    packet = BuildPacket(
        id="FORGE-EVO-P1",
        objective="Work planned after the specification evolved",
        requirements=("R-EVO-001",),
        allowed_paths=("docs/packets/**",),
        forbidden_paths=(),
        acceptance=("binds to the current specification",),
        evidence_required=("test_receipt",),
        dependencies=(),
        invariants=(),
        risk="LOW",
        # Matches the requirement's declared authority: a packet may not work on a
        # requirement that outranks it.
        authority=Authority.A2,
        retry_limit=1,
        base_candidate=candidate,
        specification_hash=specification_hash,
    )
    loop = ExecutionLoop(
        brain,
        REPOSITORY,
        loop_id="evolution-loop",
        trusted_contexts={AgentRole.ARCHITECT: {"architect": key}},
    )
    scope = _packet_scope(packet)
    try:
        loop.register_packet(
            packet,
            architect_context=ContextIdentity.issue(
                AgentRole.ARCHITECT,
                "architect",
                "REGISTER_PACKET",
                scope,
                scope,
                "evolution-loop",
                signing_key=key,
            ),
        )
    except ForgeError:
        return False
    return True


def _packet_scope(packet) -> str:
    from forge.execution_loop import _packet_scope_digest

    return _packet_scope_digest(packet)


def prove_restart_and_reconciliation() -> dict:
    """Persist, discard, rebuild from disk, then reconcile three effect classes."""
    with tempfile.TemporaryDirectory() as raw_root:
        root = Path(raw_root)
        store = LedgerStore(root, MISSION_ID)
        kernel = _kernel()
        for index, target in enumerate(
            (
                MissionState.INITIALIZING,
                MissionState.UNDERSTANDING,
                MissionState.PLANNING,
                MissionState.TASK_READY,
                MissionState.IMPLEMENTING,
            )
        ):
            before = None if index == 0 else _previous(index)
            receipt = kernel.transition(
                target, evidence=_evidence(before, target, f"restart-evidence-{index}")
            )
            store.append(receipt, kernel.ledger)

        state_before_restart = kernel.state.value
        head_before_restart = kernel.ledger.checkpoint.head_hash

        # --- Restart: nothing in memory survives; the mission is rebuilt from disk. ---
        del kernel
        reloaded_ledger = store.load()
        restarted = TrustKernel(
            REPOSITORY,
            mission_id=MISSION_ID,
            ledger=reloaded_ledger,
            ledger_checkpoint=reloaded_ledger.checkpoint,
            evidence_verification_keys={"validator": EVIDENCE_KEY},
            owner_verification_keys={"OWNER": OWNER_KEY},
        )

        restart = {
            "state_before_restart": state_before_restart,
            "state_after_restart": restarted.state.value,
            "replayed_identically": restarted.state.value == state_before_restart,
            "head_hash_preserved": restarted.ledger.checkpoint.head_hash == head_before_restart,
            "receipts": reloaded_ledger.checkpoint.sequence,
        }

        # A truncated ledger must not restore. Restoring a shorter but internally
        # consistent chain is how a mission silently loses its own history.
        truncation_refused = None
        try:
            TrustKernel(
                REPOSITORY,
                mission_id=MISSION_ID,
                ledger=type(reloaded_ledger)(reloaded_ledger.receipts[:-1]),
                ledger_checkpoint=reloaded_ledger.checkpoint,
                evidence_verification_keys={"validator": EVIDENCE_KEY},
            )
        except ForgeError as error:
            truncation_refused = error.code
        restart["truncated_restore_refused"] = truncation_refused

        # Restoring without an independent checkpoint is refused too.
        unchecked_refused = None
        try:
            TrustKernel(
                REPOSITORY,
                mission_id=MISSION_ID,
                ledger=reloaded_ledger,
                evidence_verification_keys={"validator": EVIDENCE_KEY},
            )
        except ForgeError as error:
            unchecked_refused = error.code
        restart["restore_without_checkpoint_refused"] = unchecked_refused

        # --- Three effect classes, reconciled separately. ---
        #
        # Separately because the contract says so, and because one combined verdict
        # would hide the case this is really for: the local edit landed and the push
        # did not.
        effects = {
            "local_worktree_edit": (EvidenceStatus.PRESENT, EffectDisposition.COMPLETED),
            "remote_push": (EvidenceStatus.PRESENT, EffectDisposition.NOT_STARTED),
            "runtime_process": (EvidenceStatus.AMBIGUOUS, EffectDisposition.UNKNOWN),
        }
        reconciliation: dict[str, str] = {}
        for name, (status, disposition) in effects.items():
            effect_digest = f"effect-{name}"
            evidence = ReconciliationEvidence.issue(
                status,
                disposition,
                effect_digest,
                f"evidence-{name}",
                "validator",
                REPOSITORY.digest,
                signing_key=EVIDENCE_KEY,
            )
            reconciliation[name] = restarted.reconcile_interrupted(
                effect_digest=effect_digest, evidence=evidence
            ).value

        # Absent evidence is UNKNOWN, not an assumption in either direction.
        reconciliation["missing_evidence"] = restarted.reconcile_interrupted(
            effect_digest="effect-never-observed", evidence=None
        ).value

        # Evidence bound to a different effect is a hard refusal, not an UNKNOWN:
        # authentic evidence about the wrong thing is worse than none.
        mismatched_refused = None
        mismatched = ReconciliationEvidence.issue(
            EvidenceStatus.PRESENT,
            EffectDisposition.COMPLETED,
            "effect-something-else",
            "evidence-mismatch",
            "validator",
            REPOSITORY.digest,
            signing_key=EVIDENCE_KEY,
        )
        try:
            restarted.reconcile_interrupted(
                effect_digest="effect-local_worktree_edit", evidence=mismatched
            )
        except ForgeError as error:
            mismatched_refused = error.code

        # --- The reconciliations are themselves durable. ---
        store.write(restarted.ledger)
        rechecked = store.load()

        return {
            "restart": restart,
            "reconciliation": reconciliation,
            "mismatched_effect_refused": mismatched_refused,
            "reconciliation_receipts_persisted": rechecked.checkpoint.sequence
            - restart["receipts"],
            # Three effects were reconciled and two receipts were written, which is
            # correct rather than a shortfall: an UNKNOWN disposition reconciles
            # nothing, so recording a receipt for it would put a resolution in the
            # ledger where none happened. The UNKNOWN is still returned to the caller
            # and still blocks continuation; it just is not evidence of a reconciled
            # effect.
            "unknown_dispositions_write_no_receipt": (
                rechecked.checkpoint.sequence - restart["receipts"]
                == sum(1 for status, _ in effects.values() if status is EvidenceStatus.PRESENT)
            ),
            "ledger_verifies_after_reconciliation": _verifies(rechecked),
            "state_unchanged_by_reconciliation": restarted.state.value
            == restart["state_after_restart"],
        }


def _previous(index: int) -> MissionState:
    order = (
        MissionState.INITIALIZING,
        MissionState.UNDERSTANDING,
        MissionState.PLANNING,
        MissionState.TASK_READY,
        MissionState.IMPLEMENTING,
    )
    return order[index - 1]


def _verifies(ledger) -> bool:
    try:
        ledger.verify()
    except ForgeError:
        return False
    return True


def _replayed_state(kernel: TrustKernel) -> str:
    replayed = kernel.ledger.replay()
    return replayed.value if replayed else "UNKNOWN"


def _asdict(value) -> dict:
    from dataclasses import asdict

    return asdict(value)


def prove() -> dict:
    evolution = prove_specification_evolution()
    restart = prove_restart_and_reconciliation()
    return {
        "packet": "FORGE-EVO-001",
        "boundary": (
            "Every component here is the shipped implementation: the trust kernel's "
            "transition table and authority checks, the Product Brain's versioning and "
            "lineage, LedgerStore, and ExecutionLoop's specification binding. No model "
            "is called. This proves the governed machinery holds on real state; it "
            "claims nothing about the quality of agent output."
        ),
        "specification_evolution": evolution,
        "restart_and_reconciliation": restart,
        "acceptance": {
            "discovery_validates_a_change_with_lineage": (
                evolution["specification_changed"]
                and evolution["lineage"]["versions_retained"] == 2
                and evolution["lineage"]["superseded_status"] == "SUPERSEDED"
            ),
            "discovery_can_reject_a_change": (
                "evolution_from_an_unvalidated_discovery" in evolution["refusals"]
            ),
            "evolution_requires_a_discovery_record": (
                "evolution_without_a_discovery_record" in evolution["refusals"]
            ),
            "evolution_requires_sufficient_authority": (
                "evolution_with_insufficient_authority" in evolution["refusals"]
            ),
            "subsequent_execution_uses_the_evolved_specification": all(
                evolution["subsequent_execution"].values()
            ),
            "mission_replays_deterministically": evolution["replays_to"]
            == evolution["mission_state_after_replan"],
            "restart_rebuilds_the_same_state": restart["restart"]["replayed_identically"],
            "truncated_restore_is_refused": bool(restart["restart"]["truncated_restore_refused"]),
            "restore_requires_an_independent_checkpoint": bool(
                restart["restart"]["restore_without_checkpoint_refused"]
            ),
            "local_remote_and_runtime_reconcile_separately": (
                restart["reconciliation"]["local_worktree_edit"] == "EFFECT_COMPLETED"
                and restart["reconciliation"]["remote_push"] == "SAFE_TO_RETRY"
                and restart["reconciliation"]["runtime_process"] == "UNKNOWN"
            ),
            "ambiguous_and_absent_effects_stay_unknown": (
                restart["reconciliation"]["runtime_process"] == "UNKNOWN"
                and restart["reconciliation"]["missing_evidence"] == "UNKNOWN"
            ),
            "evidence_for_the_wrong_effect_is_refused": bool(restart["mismatched_effect_refused"]),
            "reconciliation_is_durable": restart["ledger_verifies_after_reconciliation"],
            "unknown_writes_no_reconciliation_receipt": restart[
                "unknown_dispositions_write_no_receipt"
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="re-derive and compare to the record")
    args = parser.parse_args(argv)

    evidence = prove()
    unmet = sorted(key for key, met in evidence["acceptance"].items() if not met)
    if unmet:
        print(f"Governed-evolution acceptance not met: {unmet}", file=sys.stderr)
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
            f"OK FORGE-EVO-001: specification evolved with lineage, later work binds to "
            f"the new hash and not the old, restart replays to "
            f"{evidence['restart_and_reconciliation']['restart']['state_after_restart']}, "
            f"three effect classes reconciled separately"
        )
        return 0

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    evo = evidence["specification_evolution"]
    rec = evidence["restart_and_reconciliation"]["reconciliation"]
    print(
        "Governed evolution and restart proved.\n"
        f"  specification: {evo['specification_hash_before'][:12]} -> "
        f"{evo['specification_hash_after'][:12]} "
        f"({evo['lineage']['versions_retained']} versions retained, "
        f"v1 {evo['lineage']['superseded_status']})\n"
        f"  later work binds to the evolved spec and is refused against the superseded one\n"
        f"  refusals proved: {sorted(evo['refusals'])}\n"
        f"  reconciliation: local={rec['local_worktree_edit']} remote={rec['remote_push']} "
        f"runtime={rec['runtime_process']}\n"
        f"  evidence: {target.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
