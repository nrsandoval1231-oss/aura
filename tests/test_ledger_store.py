"""Durable ledger tests.

These cover the Finish Contract's replay obligation: a ledger that cannot be
reloaded and re-verified after the process dies cannot support deterministic
replay or interrupted-effect reconciliation.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from forge.ledger_store import LedgerStore
from forge.trust_kernel import (
    ForgeError,
    Ledger,
    LedgerCheckpoint,
    MissionState,
    Receipt,
    RepositoryIdentity,
    TransitionEvidence,
)

EVIDENCE_KEY = b"test-evidence-signing-key"
MISSION_ID = "TEST"
REPOSITORY = RepositoryIdentity("https://example.test/repo", "abc", "C:/repo", "main")


def _transition(target: MissionState, before: str | None, label: str) -> dict:
    evidence = TransitionEvidence.issue(
        label,
        "validator",
        REPOSITORY.digest,
        before,
        target.value,
        signing_key=EVIDENCE_KEY,
    )
    return {
        "repository_digest": REPOSITORY.digest,
        "mission_id": MISSION_ID,
        "evidence": dataclasses.asdict(evidence),
    }


def _mission_chain() -> Ledger:
    """A real, replayable mission chain of STATE_TRANSITION receipts."""
    steps = [
        (None, MissionState.INITIALIZING),
        (MissionState.INITIALIZING, MissionState.UNDERSTANDING),
        (MissionState.UNDERSTANDING, MissionState.PLANNING),
    ]
    ledger = Ledger(stream_id=MISSION_ID)
    previous_hash = None
    for index, (before, after) in enumerate(steps, 1):
        before_value = before.value if before else None
        receipt = Receipt.create(
            index,
            "STATE_TRANSITION",
            before_value,
            after.value,
            _transition(after, before_value, f"evidence-{index}"),
            previous_hash,
        )
        ledger.append(receipt)
        previous_hash = receipt.receipt_hash
    return ledger


def test_round_trip_preserves_chain_and_replay(tmp_path):
    original = _mission_chain()
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(original)

    loaded = LedgerStore(tmp_path, MISSION_ID).load()

    assert loaded.checkpoint == original.checkpoint
    assert loaded.to_records() == original.to_records()
    assert loaded.replay() == original.replay() == MissionState.PLANNING


def test_incremental_append_matches_bulk_write(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    ledger = Ledger(stream_id=MISSION_ID)
    previous_hash = None
    for index, event in enumerate(["A", "B", "C"], 1):
        receipt = Receipt.create(index, event, None, None, {"n": index}, previous_hash)
        ledger.append(receipt)
        previous_hash = receipt.receipt_hash
        store.append(receipt, ledger)

    assert store.load().to_records() == ledger.to_records()


def test_append_rejects_a_receipt_that_is_not_the_head(tmp_path):
    ledger = _mission_chain()
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(ledger)
    stale = ledger.receipts[0]

    with pytest.raises(ForgeError) as excinfo:
        store.append(stale, ledger)
    assert excinfo.value.code == "LEDGER_STORE_DESYNC"


def test_tampered_payload_is_detected(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())

    lines = store.receipts_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["payload"]["mission_id"] = "OTHER"
    lines[1] = json.dumps(record, sort_keys=True)
    store.receipts_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ForgeError) as excinfo:
        store.load()
    assert excinfo.value.code == "LEDGER_CORRUPT"


def test_truncation_is_detected_by_the_checkpoint(tmp_path):
    """A truncated ledger is internally consistent; only the checkpoint catches it."""
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())

    lines = store.receipts_path.read_text(encoding="utf-8").splitlines()
    store.receipts_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    with pytest.raises(ForgeError) as excinfo:
        store.load()
    assert excinfo.value.code == "LEDGER_CHECKPOINT_MISMATCH"


def test_malformed_line_fails_closed(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())
    with store.receipts_path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")

    with pytest.raises(ForgeError) as excinfo:
        store.load()
    assert excinfo.value.code == "MALFORMED_RECEIPT"


def test_record_missing_fields_fails_closed(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())
    with store.receipts_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"sequence": 4}) + "\n")

    with pytest.raises(ForgeError) as excinfo:
        store.load()
    assert excinfo.value.code == "MALFORMED_RECEIPT"


def test_missing_stream_fails_closed(tmp_path):
    with pytest.raises(ForgeError) as excinfo:
        LedgerStore(tmp_path, "ABSENT").load()
    assert excinfo.value.code == "LEDGER_NOT_FOUND"


def test_corrupt_checkpoint_fails_closed(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())
    store.checkpoint_path.write_text("{", encoding="utf-8")

    with pytest.raises(ForgeError) as excinfo:
        store.load()
    assert excinfo.value.code == "LEDGER_CORRUPT"


@pytest.mark.parametrize("stream_id", ["", "../escape", "a/b", ".hidden"])
def test_stream_ids_must_be_file_safe(tmp_path, stream_id):
    with pytest.raises(ForgeError) as excinfo:
        LedgerStore(tmp_path, stream_id)
    assert excinfo.value.code == "INVALID_STREAM_ID"


def test_empty_ledger_round_trips(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(Ledger(stream_id=MISSION_ID))

    loaded = store.load()
    assert loaded.checkpoint == LedgerCheckpoint(0, None, MISSION_ID)
    assert loaded.replay() is None


def test_write_refuses_to_destroy_a_divergent_history(tmp_path):
    """Re-running a producer must not silently erase the previous run's evidence."""
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())
    original = store.load().to_records()

    divergent = Ledger(stream_id=MISSION_ID)
    divergent.append(Receipt.create(1, "DIFFERENT", None, None, {"n": 1}, None))

    with pytest.raises(ForgeError) as excinfo:
        store.write(divergent)
    assert excinfo.value.code == "LEDGER_HISTORY_DIVERGED"
    assert store.load().to_records() == original  # untouched


def test_write_appends_when_the_existing_chain_is_a_prefix(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    ledger = Ledger(stream_id=MISSION_ID)
    first = Receipt.create(1, "A", None, None, {"n": 1}, None)
    ledger.append(first)
    store.write(ledger)

    ledger.append(Receipt.create(2, "B", None, None, {"n": 2}, first.receipt_hash))
    store.write(ledger)

    assert [r["event"] for r in store.load().to_records()] == ["A", "B"]


def test_rewriting_an_identical_ledger_is_a_no_op(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())
    before = store.receipts_path.read_text(encoding="utf-8")

    store.write(_mission_chain())
    assert store.receipts_path.read_text(encoding="utf-8") == before


def test_rebind_replaces_the_stream_deliberately(tmp_path):
    store = LedgerStore(tmp_path, MISSION_ID)
    store.write(_mission_chain())

    replacement = Ledger(stream_id=MISSION_ID)
    replacement.append(Receipt.create(1, "FRESH", None, None, {"n": 1}, None))
    store.rebind(replacement)

    assert [r["event"] for r in store.load().to_records()] == ["FRESH"]


# ---------------------------------------------------------------------------
# F10: a crash between the receipt write and the checkpoint write.
#
# The pre-existing truncation test above covers the JSONL falling *behind* the
# checkpoint. Nothing covered the other direction, which is the one a crash
# actually produces, and which used to make the stream permanently unloadable.
# ---------------------------------------------------------------------------


def _persisted(tmp_path, receipt_count):
    """A persisted stream of `receipt_count` receipts, plus its in-memory ledger."""
    store = LedgerStore(tmp_path, MISSION_ID)
    ledger = Ledger(stream_id=MISSION_ID)
    previous_hash = None
    for index in range(1, receipt_count + 1):
        receipt = Receipt.create(index, "EVENT", None, None, {"n": index}, previous_hash)
        ledger.append(receipt)
        previous_hash = receipt.receipt_hash
    store.write(ledger)
    return store, ledger


def _rewind_checkpoint(store, receipts_back=1):
    """Reproduce a crash after the receipt write and before the checkpoint write."""
    records = [json.loads(line) for line in store.receipts_path.read_text().splitlines() if line]
    pinned = records[-1 - receipts_back]
    store.checkpoint_path.write_text(
        json.dumps(
            {
                "sequence": pinned["sequence"],
                "head_hash": pinned["receipt_hash"],
                "stream_id": store.stream_id,
            },
            sort_keys=True,
        )
        + "\n"
    )


def test_crash_between_writes_is_reported_as_recoverable_not_corrupt(tmp_path):
    store, ledger = _persisted(tmp_path, 3)
    _rewind_checkpoint(store)

    with pytest.raises(ForgeError) as caught:
        store.load()
    # The distinguishable code is the point: reporting this as generic corruption
    # is what left `rebind` as the only route, which destroys the evidence.
    assert caught.value.code == "LEDGER_CHECKPOINT_BEHIND"
    assert caught.value.details["pending"] == 1
    assert store.pending_recovery() == 1


def test_recover_re_pins_the_head_and_preserves_every_receipt(tmp_path):
    store, ledger = _persisted(tmp_path, 3)
    expected = ledger.to_records()
    _rewind_checkpoint(store)

    recovered = store.recover()

    assert recovered.to_records() == expected
    assert recovered.checkpoint == ledger.checkpoint
    # Recovery is durable: the stream loads normally afterwards.
    assert store.load().to_records() == expected
    assert store.pending_recovery() == 0


def test_recover_handles_more_than_one_unpinned_receipt(tmp_path):
    store, ledger = _persisted(tmp_path, 4)
    expected = ledger.to_records()
    _rewind_checkpoint(store, receipts_back=2)

    assert store.pending_recovery() == 2
    assert store.recover().to_records() == expected


def test_recover_is_a_no_op_on_a_healthy_stream(tmp_path):
    store, ledger = _persisted(tmp_path, 2)
    assert store.pending_recovery() == 0
    assert store.recover().to_records() == ledger.to_records()


def test_recover_refuses_a_truncated_stream(tmp_path):
    """Truncation is loss, not a stale pointer. There is nothing to re-pin."""
    store, ledger = _persisted(tmp_path, 3)
    lines = store.receipts_path.read_text().splitlines()
    store.receipts_path.write_text("\n".join(lines[:-1]) + "\n")

    with pytest.raises(ForgeError) as caught:
        store.recover()
    assert caught.value.code == "LEDGER_TRUNCATED"


def test_recover_refuses_when_the_pinned_prefix_was_altered(tmp_path):
    """The prefix check is the guarantee: recovery continues pinned evidence only.

    Without it, `recover` would accept any self-consistent chain and the sidecar
    would stop detecting a rewritten history — trading F10 for a worse defect.
    """
    store, ledger = _persisted(tmp_path, 3)
    _rewind_checkpoint(store)
    records = [json.loads(line) for line in store.receipts_path.read_text().splitlines() if line]
    records[0]["payload"] = {"tampered": True}
    store.receipts_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    )

    with pytest.raises(ForgeError) as caught:
        store.recover()
    assert caught.value.code in {"LEDGER_CORRUPT", "LEDGER_CHECKPOINT_MISMATCH"}
