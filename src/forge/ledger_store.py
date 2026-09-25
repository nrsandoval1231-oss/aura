"""Durable append-only storage for the evidence ledger.

The trust kernel's `Ledger` already owns the hash chain, verification, and replay.
This module gives it a disk representation, which the Finish Contract's replay and
interrupted-effect reconciliation obligations require: an in-memory ledger cannot
survive the interruption it is supposed to reconcile.

Layout, for a stream named `S`:

    <root>/S.jsonl            one JSON receipt record per line, append-only
    <root>/S.checkpoint.json  sequence + head hash, written separately

The checkpoint is deliberately a second file. `Ledger.from_records` compares the
reconstructed chain against it, so a truncated or partially written `.jsonl` is
detected instead of silently loading as a shorter but internally consistent ledger.

Two writes, and the gap between them
------------------------------------
Every persist writes the receipt line first and the checkpoint second. A crash in
that window leaves the JSONL one or more receipts *ahead* of the checkpoint, which
audit F10 found made the stream permanently unloadable: `load` is the only reader,
`verify` and `replay` both route through it, and the only escape was `rebind`,
which discards the evidence. A module whose purpose is surviving interruption
could not survive an interruption in its own write path.

The two directions are not symmetrical and are not treated alike:

- **JSONL behind the checkpoint** is loss. Receipts the checkpoint pinned are gone,
  nothing can reconstruct them, and `load` refuses.
- **JSONL ahead of the checkpoint** is a crash between the two writes. The evidence
  is all present; only the pointer is stale.

The second case is recoverable, but recovery is not automatic. The checkpoint's
security value is pinning the head: the chain is hash-linked with no secret, so
anyone who can write the JSONL can append a well-formed continuation. If `load`
silently accepted any chain that extended the pinned head, the sidecar would stop
detecting appended forgery — it would only detect truncation. So `load` stays
strict and reports `LEDGER_CHECKPOINT_BEHIND`, and `recover` is a separate,
deliberate call that verifies the surviving prefix still reproduces the pinned
head before advancing it. Same reasoning as `write` versus `rebind`: discarding or
re-pinning evidence is a decision, never a side effect of reading.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from forge.trust_kernel import ForgeError, Ledger, LedgerCheckpoint, Receipt

__all__ = ["LedgerStore"]

_RECORD_KEYS = frozenset(
    {"sequence", "event", "state_before", "state_after", "payload", "previous_hash", "receipt_hash"}
)


class LedgerStore:
    """Reads and writes a `Ledger` as append-only JSONL plus a checkpoint sidecar."""

    def __init__(self, root: Path | str, stream_id: str):
        if not stream_id or "/" in stream_id or os.sep in stream_id or stream_id.startswith("."):
            raise ForgeError("INVALID_STREAM_ID", "Stream id must be a simple file-safe name")
        self._root = Path(root)
        self._stream_id = stream_id

    @property
    def stream_id(self) -> str:
        return self._stream_id

    @property
    def receipts_path(self) -> Path:
        return self._root / f"{self._stream_id}.jsonl"

    @property
    def checkpoint_path(self) -> Path:
        return self._root / f"{self._stream_id}.checkpoint.json"

    @property
    def exists(self) -> bool:
        return self.receipts_path.exists() and self.checkpoint_path.exists()

    def append(self, receipt: Receipt, ledger: Ledger) -> None:
        """Persist one receipt that has already been appended to `ledger`.

        The in-memory ledger stays the authority on whether the append is legal; by
        the time we are called it has accepted the receipt, so writing it out cannot
        introduce a chain the kernel would reject.
        """
        if not ledger.receipts or ledger.receipts[-1].receipt_hash != receipt.receipt_hash:
            raise ForgeError(
                "LEDGER_STORE_DESYNC",
                "Receipt being persisted is not the in-memory ledger's head",
            )
        self._root.mkdir(parents=True, exist_ok=True)
        # Take the serialized form from the ledger itself so the on-disk record
        # shape stays defined in exactly one place.
        record = ledger.to_records()[-1]
        newly_created = not self.receipts_path.exists()
        with self.receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if newly_created:
            _fsync_directory(self.receipts_path.parent)
        self._write_checkpoint(ledger.checkpoint)

    def write(self, ledger: Ledger) -> None:
        """Persist a ledger without destroying history.

        An append-only store whose writer silently replaces the whole chain is
        not append-only. If the stream already exists, the persisted receipts
        must be an exact prefix of what is being written; then only the new
        records are appended. Anything else is a divergent history and is
        refused — re-running a producer must not quietly erase the evidence of
        the previous run.

        Use `rebind` to deliberately replace a stream whose candidate no longer
        exists.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        records = ledger.to_records()
        if self.exists:
            existing = self.load().to_records()
            if records[: len(existing)] != existing:
                raise ForgeError(
                    "LEDGER_HISTORY_DIVERGED",
                    f"Persisted stream '{self._stream_id}' is not a prefix of the ledger "
                    "being written; refusing to destroy existing evidence",
                )
            if len(records) == len(existing):
                return
            with self.receipts_path.open("a", encoding="utf-8") as handle:
                for record in records[len(existing) :]:
                    handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._write_checkpoint(ledger.checkpoint)
            return
        self._write_all(ledger, records)

    def rebind(self, ledger: Ledger) -> None:
        """Replace the stream outright, discarding any existing history.

        Separate from `write` on purpose: discarding evidence is a decision, not
        a side effect of calling the ordinary writer. Callers reach for this only
        when the candidate the old chain described no longer exists.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        self._write_all(ledger, ledger.to_records())

    def _write_all(self, ledger: Ledger, records: list[dict[str, Any]]) -> None:
        body = "".join(
            json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n" for record in records
        )
        _atomic_write(self.receipts_path, body)
        self._write_checkpoint(ledger.checkpoint)

    def load(self) -> Ledger:
        """Rebuild the ledger from disk, verifying the chain against the checkpoint."""
        if not self.exists:
            raise ForgeError("LEDGER_NOT_FOUND", f"No persisted ledger stream '{self._stream_id}'")
        checkpoint = self._read_checkpoint()
        records = self._read_records()
        pending = len(records) - checkpoint.sequence
        if pending > 0:
            # Distinguished from the generic mismatch on purpose: this stream is
            # intact and recoverable, and reporting it as corruption is what sent
            # the only remaining route to `rebind`. Callers get a code they can act
            # on and a count of what is unpinned.
            raise ForgeError(
                "LEDGER_CHECKPOINT_BEHIND",
                f"Ledger stream '{self._stream_id}' holds {pending} receipt(s) beyond its "
                "checkpoint, consistent with a crash between the two writes; "
                "call recover() to re-pin the head after verifying the prefix",
                details={
                    "stream_id": self._stream_id,
                    "checkpoint_sequence": checkpoint.sequence,
                    "records_on_disk": len(records),
                    "pending": pending,
                },
            )
        # from_records re-derives every receipt hash and compares the rebuilt
        # checkpoint to the sidecar, so truncation and tampering both fail here.
        return Ledger.from_records(records, checkpoint=checkpoint)

    def pending_recovery(self) -> int:
        """Receipts on disk beyond the checkpoint. Zero when the stream is pinned.

        Read-only, and safe on a stream that `load` refuses: a gate needs to be
        able to tell "crashed mid-write" from "evidence destroyed" without first
        having to handle an exception.
        """
        if not self.exists:
            return 0
        return max(0, len(self._read_records()) - self._read_checkpoint().sequence)

    def recover(self) -> Ledger:
        """Re-pin the checkpoint onto receipts a crash left unpinned.

        Only ever advances, and only after the receipts the old checkpoint pinned
        are shown to still be exactly what it pinned. That prefix check is the
        whole guarantee: it proves the extension continues the evidence the
        checkpoint vouched for rather than replacing it. Truncation is still
        refused, because there is nothing to recover from.
        """
        if not self.exists:
            raise ForgeError("LEDGER_NOT_FOUND", f"No persisted ledger stream '{self._stream_id}'")
        checkpoint = self._read_checkpoint()
        records = self._read_records()
        if len(records) < checkpoint.sequence:
            raise ForgeError(
                "LEDGER_TRUNCATED",
                f"Ledger stream '{self._stream_id}' is shorter than its checkpoint; "
                "receipts are missing and recovery cannot invent them",
                details={
                    "checkpoint_sequence": checkpoint.sequence,
                    "records_on_disk": len(records),
                },
            )
        if len(records) == checkpoint.sequence:
            return Ledger.from_records(records, checkpoint=checkpoint)
        # Refuses unless the surviving prefix reproduces the pinned head exactly.
        Ledger.from_records(records[: checkpoint.sequence], checkpoint=checkpoint)
        recovered = Ledger.from_records(
            records,
            checkpoint=LedgerCheckpoint(
                sequence=len(records),
                head_hash=records[-1]["receipt_hash"],
                stream_id=checkpoint.stream_id,
            ),
        )
        self._write_checkpoint(recovered.checkpoint)
        return recovered

    def _read_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self.receipts_path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ForgeError(
                        "MALFORMED_RECEIPT",
                        f"Ledger line {number} is not valid JSON",
                    ) from exc
                if not isinstance(record, dict) or not _RECORD_KEYS <= record.keys():
                    raise ForgeError(
                        "MALFORMED_RECEIPT",
                        f"Ledger line {number} does not match the receipt schema",
                    )
                records.append(record)
        return records

    def _write_checkpoint(self, checkpoint: LedgerCheckpoint) -> None:
        _atomic_write(
            self.checkpoint_path,
            json.dumps(
                {
                    "sequence": checkpoint.sequence,
                    "head_hash": checkpoint.head_hash,
                    "stream_id": checkpoint.stream_id,
                },
                sort_keys=True,
                ensure_ascii=True,
            )
            + "\n",
        )

    def _read_checkpoint(self) -> LedgerCheckpoint:
        try:
            raw = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            return LedgerCheckpoint(
                sequence=raw["sequence"],
                head_hash=raw["head_hash"],
                stream_id=raw.get("stream_id"),
            )
        except json.JSONDecodeError as exc:
            raise ForgeError("LEDGER_CORRUPT", "Ledger checkpoint is not valid JSON") from exc
        except (KeyError, TypeError) as exc:
            raise ForgeError(
                "LEDGER_CORRUPT", "Ledger checkpoint is missing required fields"
            ) from exc


def _atomic_write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    try:
        with handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    """Persist a rename, not just the bytes it points at.

    `os.replace` is atomic with respect to readers, but on several filesystems the
    directory entry it rewrites can still be lost to power failure while the file
    contents survive. Without this, a crash could leave the checkpoint pointing at
    the pre-rename inode — which is the same stale-pointer state F10 is about,
    reached by a different route. Best-effort: platforms that refuse to open a
    directory for fsync are not a reason to fail a write that already succeeded.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
