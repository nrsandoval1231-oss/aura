"""CLI tests.

The doc-vs-graph check is itself a gate, so it needs its own regression cover:
a consistency check that cannot fail is indistinguishable from no check, which
is the state this repository was in when the README drifted through five merges.
"""

from __future__ import annotations

import json

import pytest

from forge.cli import main
from forge.ledger_store import LedgerStore
from forge.trust_kernel import Ledger, Receipt


def _graph(tmp_path, nodes):
    path = tmp_path / "work-graph.json"
    path.write_text(json.dumps({"graph_version": 3, "nodes": nodes}), encoding="utf-8")
    return path


def _readme(tmp_path, body):
    path = tmp_path / "README.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_graph_check_passes_when_documents_agree(tmp_path, capsys):
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "**Implementation:** see the work graph\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0
    assert "consistent" in capsys.readouterr().out


def test_graph_check_catches_a_not_started_claim(tmp_path, capsys):
    """The exact drift the 2026-09-21 audit found."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "**Implementation:** Not started\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 1
    assert "Not started" in capsys.readouterr().err


def test_graph_check_catches_a_stale_node_status(tmp_path, capsys):
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "PROPOSED"}])
    readme = _readme(tmp_path, "`FORGE-A-001` shipped last week and is done.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 1
    assert "FORGE-A-001" in capsys.readouterr().err


def test_graph_check_accepts_status_in_prose_casing(tmp_path):
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "Phase 0 (`FORGE-A-001`) is complete.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_ledger_verify_reports_the_head(tmp_path, capsys):
    ledger = Ledger(stream_id="S")
    previous = None
    for index in range(1, 4):
        receipt = Receipt.create(index, "EVENT", None, None, {"n": index}, previous)
        ledger.append(receipt)
        previous = receipt.receipt_hash
    LedgerStore(tmp_path, "S").write(ledger)

    assert main(["ledger", "verify", "S", "--root", str(tmp_path)]) == 0
    assert "3 receipts" in capsys.readouterr().out


def test_ledger_verify_reports_a_missing_stream(tmp_path, capsys):
    assert main(["ledger", "verify", "ABSENT", "--root", str(tmp_path)]) == 1
    assert "LEDGER_NOT_FOUND" in capsys.readouterr().err


def test_ledger_verify_reports_tampering(tmp_path, capsys):
    ledger = Ledger(stream_id="S")
    ledger.append(Receipt.create(1, "EVENT", None, None, {"n": 1}, None))
    store = LedgerStore(tmp_path, "S")
    store.write(ledger)
    store.receipts_path.write_text(
        json.dumps(
            {
                "sequence": 1,
                "event": "TAMPERED",
                "state_before": None,
                "state_after": None,
                "payload": {"n": 1},
                "previous_hash": None,
                "receipt_hash": "deadbeef",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert main(["ledger", "verify", "S", "--root", str(tmp_path)]) == 1
    assert "LEDGER_CORRUPT" in capsys.readouterr().err


def test_graph_check_scans_every_state_bearing_document(tmp_path):
    """CURRENT_STATE.md is authority layer 6 and drifted alongside README."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "PROPOSED"}])
    readme = _readme(tmp_path, "nothing to see\n")
    state = tmp_path / "CURRENT_STATE.md"
    state.write_text("`FORGE-A-001` is COMPLETE and shipped.\n", encoding="utf-8")

    code = main(["graph", "check", "--graph", str(graph), "--docs", str(readme), str(state)])
    assert code == 1


def test_graph_check_defaults_cover_both_documents():
    from forge.cli import STATE_BEARING_DOCS

    names = {doc.name for doc in STATE_BEARING_DOCS}
    assert names == {"README.md", "CURRENT_STATE.md"}


def test_no_subcommand_is_an_error():
    with pytest.raises(SystemExit):
        main([])


# ---------------------------------------------------------------------------
# F14: the consistency gate could not see the contradiction in its own README.
# ---------------------------------------------------------------------------


def test_graph_check_catches_a_doctrine_contradiction(tmp_path, capsys):
    """README:31 said "There is no CI" and README:69 said gates run in CI.

    Neither line names a node, so node-status proximity had nothing to compare
    them against and the gate stayed green through the contradiction.
    """
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "The deterministic gates run in CI on every push.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 1
    assert "DEC-009" in capsys.readouterr().err


def test_graph_check_allows_stating_that_there_is_no_ci(tmp_path):
    """The doctrine check must not fire on the true statement of the doctrine."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "There is no CI; validation runs locally (DEC-009).\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_graph_check_sees_an_unbackticked_contradiction(tmp_path, capsys):
    """Bare ids were invisible to the gate before F14."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "PROPOSED"}])
    readme = _readme(tmp_path, "Work on FORGE-A-001 is COMPLETE as of today.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 1
    err = capsys.readouterr().err
    assert "FORGE-A-001" in err and "PROPOSED" in err


def test_graph_check_tolerates_a_bare_passing_reference(tmp_path):
    """A cross-reference in prose is not a status claim and must not need one.

    This is the other half of the F14 fix: scanning bare mentions is only safe if
    they are held to "do not contradict" rather than "recite the status", or every
    passing mention of a node becomes a build failure.
    """
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "ABSORBED"}])
    readme = _readme(tmp_path, "The rationale is recorded in DEC-006, FORGE-A-001.\n\n## Next\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_graph_check_does_not_borrow_words_from_the_next_sentence(tmp_path):
    """Character-window proximity read across sentence boundaries and false-fired."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "ABSORBED"}])
    readme = _readme(
        tmp_path, "See the note at FORGE-A-001.\n\n## Repository\n\nPhase 0 is COMPLETE.\n"
    )

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_graph_check_flags_a_reference_to_an_unknown_node(tmp_path, capsys):
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "COMPLETE"}])
    readme = _readme(tmp_path, "`FORGE-A-001` is COMPLETE, unlike FORGE-Z-999.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 1
    assert "FORGE-Z-999" in capsys.readouterr().err


def test_status_words_are_matched_as_words_not_substrings(tmp_path):
    """ "already" contains "ready", and substring matching reported it as a claim.

    Found by the gate firing on `.agent/CURRENT_STATE.md` prose that read "which
    FORGE-EVO-001 already does". A consistency gate that invents contradictions is on
    its way to being ignored, the same as one that misses them.
    """
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "AWAITING_AUDIT"}])
    readme = _readme(tmp_path, "`FORGE-A-001` is AWAITING_AUDIT, which it already does.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_a_compound_status_still_matches_as_one_token(tmp_path):
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "MANDATORY_V0_GATE"}])
    readme = _readme(tmp_path, "`FORGE-A-001` is MANDATORY_V0_GATE until proven.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0


def test_a_status_word_inside_a_longer_word_does_not_contradict(tmp_path):
    """ "incomplete" must not read as COMPLETE."""
    graph = _graph(tmp_path, [{"id": "FORGE-A-001", "status": "PROPOSED"}])
    readme = _readme(tmp_path, "Work on FORGE-A-001 is incomplete for now.\n")

    assert main(["graph", "check", "--graph", str(graph), "--docs", str(readme)]) == 0
