"""Governed specification evolution and restart reconciliation (FORGE-EVO-001).

Two Finish Contract clauses were implemented and never demonstrated. As with the
self-improvement proof, the tests that matter most are the ones showing the
demonstration is capable of failing — a proof that cannot fail proves nothing, which
is the F12 objection applied to a harness instead of a provider.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from forge.trust_kernel import MissionState

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def prover():
    spec = importlib.util.spec_from_file_location(
        "prove_governed_evolution", ROOT / "scripts" / "prove_governed_evolution.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evidence(prover):
    return prover.prove()


def test_all_acceptance_requirements_are_met(evidence):
    unmet = sorted(key for key, met in evidence["acceptance"].items() if not met)
    assert unmet == []


# ---------------------------------------------------------------------------
# Specification evolution with lineage
# ---------------------------------------------------------------------------


def test_the_specification_hash_actually_changes(evidence):
    evolution = evidence["specification_evolution"]
    assert evolution["specification_changed"]
    assert evolution["specification_hash_before"] != evolution["specification_hash_after"]


def test_lineage_retains_the_superseded_version(evidence):
    """Evolution that discards the previous version is a rewrite, not a lineage."""
    lineage = evidence["specification_evolution"]["lineage"]
    assert lineage["versions_retained"] == 2
    assert lineage["superseded_status"] == "SUPERSEDED"
    assert lineage["current_status"] == "ACTIVE"
    assert lineage["current_version"] == 2
    assert lineage["discovery_cited_in_receipt"]


def test_the_evolution_receipt_carries_its_discovery_and_grant(evidence):
    receipt = evidence["specification_evolution"]["evolution_receipt"]
    assert receipt["state_before"] == MissionState.ACCEPTED.value
    assert receipt["state_after"] == MissionState.SPEC_EVOLUTION.value
    assert receipt["carries_discovery"]
    assert receipt["carries_authority_grant"]


@pytest.mark.parametrize(
    "refusal",
    [
        "evolution_without_a_discovery_record",
        "evolution_with_insufficient_authority",
        "evolution_from_an_unvalidated_discovery",
    ],
)
def test_the_ungoverned_paths_are_refused(evidence, refusal):
    """ "Discovery can validate *or reject*" — the reject half needs proving too."""
    assert refusal in evidence["specification_evolution"]["refusals"]


def test_later_work_binds_to_the_evolved_specification_and_not_the_old_one(evidence):
    """The clause beyond "producing a packet".

    If a packet bound to the superseded hash still registered, the evolution would
    have changed a hash and nothing that consumes it.
    """
    binding = evidence["specification_evolution"]["subsequent_execution"]
    assert binding["packet_bound_to_evolved_specification_accepted"]
    assert binding["packet_bound_to_superseded_specification_refused"]


def test_the_mission_reached_spec_evolution_by_the_only_legal_path(prover):
    """Asserted against the kernel's own table, so loosening it fails here."""
    from forge.trust_kernel import _TRANSITIONS

    path = prover.PATH_TO_EVOLUTION
    for before, after in zip(path, path[1:], strict=False):
        assert after in _TRANSITIONS[before], f"{before} -> {after}"


def test_the_mission_replays_deterministically(evidence):
    evolution = evidence["specification_evolution"]
    assert evolution["replays_to"] == evolution["mission_state_after_replan"]


# ---------------------------------------------------------------------------
# Restart
# ---------------------------------------------------------------------------


def test_restart_rebuilds_the_same_state_from_disk(evidence):
    restart = evidence["restart_and_reconciliation"]["restart"]
    assert restart["replayed_identically"]
    assert restart["head_hash_preserved"]
    assert restart["receipts"] == 5


def test_a_truncated_ledger_does_not_restore(evidence):
    """Restoring a shorter but self-consistent chain loses history silently."""
    assert evidence["restart_and_reconciliation"]["restart"]["truncated_restore_refused"] == (
        "LEDGER_CHECKPOINT_MISMATCH"
    )


def test_restoring_without_an_independent_checkpoint_is_refused(evidence):
    assert (
        evidence["restart_and_reconciliation"]["restart"]["restore_without_checkpoint_refused"]
        == "LEDGER_CHECKPOINT_REQUIRED"
    )


# ---------------------------------------------------------------------------
# Reconciliation, separately per effect class
# ---------------------------------------------------------------------------


def test_local_remote_and_runtime_reconcile_to_different_verdicts(evidence):
    """One combined verdict would hide the case this exists for: local landed,
    remote did not."""
    reconciliation = evidence["restart_and_reconciliation"]["reconciliation"]
    assert reconciliation["local_worktree_edit"] == "EFFECT_COMPLETED"
    assert reconciliation["remote_push"] == "SAFE_TO_RETRY"
    assert reconciliation["runtime_process"] == "UNKNOWN"


def test_absent_evidence_is_unknown_not_an_assumption(evidence):
    assert evidence["restart_and_reconciliation"]["reconciliation"]["missing_evidence"] == "UNKNOWN"


def test_evidence_about_the_wrong_effect_is_refused_outright(evidence):
    """Authentic evidence about the wrong thing is worse than none, so it raises."""
    assert evidence["restart_and_reconciliation"]["mismatched_effect_refused"] == (
        "UNTRUSTED_RECONCILIATION_EVIDENCE"
    )


def test_an_unknown_disposition_writes_no_reconciliation_receipt(evidence):
    """Otherwise the ledger would record a resolution that did not happen."""
    restart = evidence["restart_and_reconciliation"]
    assert restart["unknown_dispositions_write_no_receipt"]
    assert restart["reconciliation_receipts_persisted"] == 2


def test_reconciliation_does_not_move_the_mission_state(evidence):
    assert evidence["restart_and_reconciliation"]["state_unchanged_by_reconciliation"]


def test_the_ledger_still_verifies_after_reconciliation(evidence):
    assert evidence["restart_and_reconciliation"]["ledger_verifies_after_reconciliation"]


# ---------------------------------------------------------------------------
# The proof must be capable of failing
# ---------------------------------------------------------------------------


def test_the_proof_is_deterministic(prover):
    assert prover.prove() == prover.prove()


def test_the_recorded_artifact_matches_a_fresh_derivation(prover):
    assert prover.main(["--check"]) == 0


def test_the_proof_states_its_boundary(evidence):
    boundary = evidence["boundary"]
    assert "No model is called" in boundary
    assert "claims nothing about the quality of agent output" in boundary
