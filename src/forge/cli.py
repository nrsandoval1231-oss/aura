"""Command line surface for Forge.

Deliberately small. Forge's V0 obligations are to make its own governed state
inspectable and verifiable from outside the process, so the commands here read
durable evidence rather than drive the loop:

    forge ledger verify <stream>   re-derive the hash chain from disk
    forge ledger replay <stream>   replay receipts to a mission state
    forge graph check              assert docs do not contradict the work graph
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from forge.audit_receipts import verify_detached_audit
from forge.config import load_env
from forge.ledger_store import LedgerStore
from forge.trust_kernel import CandidateIdentity, ForgeError

DEFAULT_LEDGER_ROOT = Path(".agent/ledger")
DEFAULT_GRAPH = Path(".agent/graph/work-graph.json")

#: Documents that narrate execution state and must not contradict the graph.
#: `CURRENT_STATE.md` belongs here as much as `README.md` does: it is authority
#: layer 6 in AGENTS.md, and both drifted together through five merges. Checking
#: only one of them leaves the other free to go stale while the gate stays green.
STATE_BEARING_DOCS = (Path("README.md"), Path(".agent/CURRENT_STATE.md"))

#: Documents that must not assert execution state contradicting the graph.
#: Kept narrow on purpose: this is a contradiction check, not a style gate.
STATUS_CLAIM_PATTERN = re.compile(r"^\*\*Implementation:\*\*\s*(?P<claim>.+?)\s*$", re.MULTILINE)

#: Any mention of a node id, with or without backticks.
#:
#: Audit F14 found the backtick-only match leaving a blind spot:
#: `.agent/CURRENT_STATE.md` referred to FORGE-FIX-001 bare, and the gate could not
#: see it. A guardrail that only inspects the well-formatted half of a document
#: reports on formatting, not on agreement.
NODE_MENTION = re.compile(r"(?P<tick>`)?(?P<node>FORGE-[A-Z]+-\d+)`?")

#: The full status vocabulary, not just the statuses a given graph happens to use.
#:
#: Deriving the contradiction words from the graph under test looks tidier and is
#: wrong: a graph whose every node is PROPOSED contains no other status, so a
#: document claiming one of those nodes is COMPLETE would have had nothing to
#: contradict. The vocabulary has to come from outside the data being checked.
KNOWN_STATUSES: frozenset[str] = frozenset(
    {
        "PROPOSED",
        "READY",
        "READY_AUTHORIZED",
        "IN_PROGRESS",
        "BLOCKED",
        # Built, locally validated, evidence bound to a candidate — and not
        # certified. `AGENTS.md` separates producing evidence from certifying it
        # ("Builders produce evidence; they do not certify it"), but the graph had
        # no status for the gap between, so finished-but-unaudited work had to be
        # called either IN_PROGRESS, which understates it, or COMPLETE, which is a
        # builder certifying itself. Candidate binding deliberately does not cover
        # this status: the candidate it bound is history, exactly as for COMPLETE.
        "AWAITING_AUDIT",
        "COMPLETE",
        "ABSORBED",
        "REJECTED",
        "REDIRECTED",
        "MANDATORY_V0_GATE",
    }
)

#: Claims that contradict an accepted decision no matter which node they sit near.
#: Each entry is (regex, why it is false, the decision that settles it). This is
#: the half of F14 the node-status check structurally could not catch: "gates run
#: in CI" contradicted DEC-009 and README.md's own line 31, but named no node, so
#: proximity matching had nothing to compare it against.
DOCTRINE_CONTRADICTIONS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"gates?\s+run\s+in\s+CI|runs?\s+in\s+CI|CI\s+(?:gates|enforces|runs)", re.I),
        "asserts that CI runs the gates",
        "DEC-009: validation is local; there is no CI",
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge", description=__doc__)
    sub = parser.add_subparsers(dest="group", required=True)

    ledger = sub.add_parser("ledger", help="inspect a durable evidence ledger")
    ledger_sub = ledger.add_subparsers(dest="action", required=True)
    for action in ("verify", "replay", "recover"):
        node = ledger_sub.add_parser(action)
        node.add_argument("stream")
        node.add_argument("--root", type=Path, default=DEFAULT_LEDGER_ROOT)

    graph = sub.add_parser("graph", help="check governed graph state")
    graph_sub = graph.add_subparsers(dest="action", required=True)
    check = graph_sub.add_parser("check")
    check.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    check.add_argument(
        "--docs",
        type=Path,
        nargs="*",
        default=None,
        help="state-bearing documents to scan; defaults to STATE_BEARING_DOCS",
    )

    audit = sub.add_parser("audit", help="verify externally supplied audit evidence")
    audit_sub = audit.add_subparsers(dest="action", required=True)
    audit_verify = audit_sub.add_parser("verify")
    audit_verify.add_argument("receipt", type=Path)
    audit_verify.add_argument("trust_anchor", type=Path)
    audit_verify.add_argument("repository_digest")
    audit_verify.add_argument("revision")
    audit_verify.add_argument("tree")
    audit_verify.add_argument("packet_id")
    audit_verify.add_argument("--root", type=Path, default=Path("."))
    check.add_argument(
        "--tasks",
        type=Path,
        default=None,
        help="packet directory; defaults to <graph parent>/../tasks",
    )

    args = parser.parse_args(argv)
    load_env()
    try:
        if args.group == "ledger":
            return _ledger(args)
        if args.group == "audit":
            candidate = CandidateIdentity(
                args.repository_digest, args.revision, args.tree, args.packet_id
            )
            receipt = verify_detached_audit(
                args.root.resolve(),
                candidate,
                receipt_path=args.receipt.resolve(),
                trust_anchor=args.trust_anchor.resolve(),
            )
            print(f"OK detached audit: {receipt['candidate_digest']} by {receipt['auditor_id']}")
            return 0
        return _graph_check(args)
    except ForgeError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 1


def _ledger(args: argparse.Namespace) -> int:
    store = LedgerStore(args.root, args.stream)
    if args.action == "recover":
        pending = store.pending_recovery()
        recovered = store.recover()
        checkpoint = recovered.checkpoint
        verb = "re-pinned" if pending else "already pinned"
        print(
            f"OK {args.stream}: {verb} at {checkpoint.sequence} receipts, "
            f"head {checkpoint.head_hash} ({pending} recovered)"
        )
        return 0
    # A stream whose checkpoint a crash left behind is intact, not corrupt. Say so
    # and name the command that fixes it, rather than reporting the same failure as
    # destroyed evidence and pushing the operator toward `rebind`.
    pending = store.pending_recovery()
    if pending:
        print(
            f"RECOVERABLE {args.stream}: {pending} receipt(s) on disk beyond the checkpoint, "
            f"consistent with a crash between the two writes. "
            f"Run `forge ledger recover {args.stream}` to re-pin the head.",
            file=sys.stderr,
        )
        return 1
    loaded = store.load()
    if args.action == "verify":
        loaded.verify()
        checkpoint = loaded.checkpoint
        print(f"OK {args.stream}: {checkpoint.sequence} receipts, head {checkpoint.head_hash}")
        return 0
    state = loaded.replay()
    print(f"OK {args.stream}: replays to {state.value if state else 'UNKNOWN'}")
    return 0


#: Sentence end, or the end of a Markdown block. Deliberately not a blank line
#: alone: list items and table rows are separate claims without one between them.
_SENTENCE_END = re.compile(r"(?:[.!?](?=\s|$))|\n\s*\n|\n\s*[-*|]|\n#")


def _mentions_status(text: str, status: str) -> bool:
    """Whether `text` names this status as a word.

    Substring matching looked adequate and was not: "already" contains "ready", so
    prose reading "which FORGE-EVO-001 already does" was reported as claiming the node
    was READY. Underscores count as word characters, so `MANDATORY_V0_GATE` still
    matches as one token.
    """
    return re.search(rf"(?<![\w]){re.escape(status.casefold())}(?![\w])", text) is not None


def _same_sentence_after(text: str, start: int, limit: int = 300) -> str:
    """The rest of the sentence following `start`.

    Status agreement is judged inside one sentence rather than inside a character
    window. A fixed window reads across sentence boundaries and borrows words from
    whatever follows: scoped to 200 characters, a narrative line ending
    "(DEC-006, FORGE-FIX-001)" picked up the word "complete" from the next
    section's heading and reported a contradiction that nobody had written. Both
    failure directions cost the same thing — a gate people learn to work around.
    """
    window = text[start : start + limit]
    match = _SENTENCE_END.search(window)
    return window[: match.start()] if match else window


def _graph_check(args: argparse.Namespace) -> int:
    """Fail when a hand-maintained document contradicts the work graph.

    Execution state is derived from the graph and the ledger; prose may point at
    that state but may not assert a different one. This is the enforcement half
    of FORGE-FIX-001 — the README drift it catches is exactly the drift that went
    unnoticed through five merges.
    """
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", [])
    complete = sorted(n["id"] for n in nodes if n.get("status") == "COMPLETE")
    problems: list[str] = []

    for doc in args.docs if args.docs is not None else STATE_BEARING_DOCS:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for match in STATUS_CLAIM_PATTERN.finditer(text):
            claim = match.group("claim")
            if complete and "not started" in claim.casefold():
                problems.append(
                    f"{doc}: claims implementation {claim!r} while "
                    f"{len(complete)} node(s) are COMPLETE: {', '.join(complete)}"
                )
        for pattern, what, settled_by in DOCTRINE_CONTRADICTIONS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{doc}:{line}: {what} — {settled_by}")

        status_by_node = {node["id"]: node.get("status", "") for node in nodes}
        # Every mention, backticked or not (F14). Scanning the document for node
        # ids rather than scanning the node list for backticked markers also means
        # a reference to a node that does not exist is caught here instead of
        # passing silently.
        for match in NODE_MENTION.finditer(text):
            node_id = match.group("node")
            if node_id not in status_by_node:
                problems.append(f"{doc}: mentions {node_id}, which has no node in {args.graph}")
                continue
            status = status_by_node[node_id]
            # Case-insensitive: prose saying "is complete" agrees with a
            # COMPLETE node. This gate exists to catch contradictions, not
            # to dictate how status is spelled in a sentence.
            following = _same_sentence_after(text, match.end()).casefold()
            if _mentions_status(following, status):
                continue
            # Backticked and bare mentions carry different obligations, and
            # collapsing them breaks the gate in one direction or the other.
            #
            # A backticked id in a state-bearing document is a deliberate status
            # reference, so it must recite the status — the strict rule that caught
            # the original README drift. Prose that paraphrases ("shipped last week
            # and is done") is exactly what it is for.
            #
            # A bare mention is ordinary prose. Holding it to the same rule would
            # demand every passing cross-reference recite a status, so it only has
            # to avoid asserting a different one. Before F14 bare mentions were not
            # examined at all.
            if match.group("tick"):
                problems.append(
                    f"{doc}: mentions {node_id} without its graph status {status!r} nearby"
                )
                continue
            contradicting = sorted(
                {
                    other
                    for other in KNOWN_STATUSES | set(status_by_node.values())
                    if other
                    and other.casefold() != status.casefold()
                    and _mentions_status(following, other)
                }
            )
            if contradicting:
                problems.append(
                    f"{doc}: says {node_id} is {contradicting} but the graph says {status!r}"
                )

    # Derived from the graph path rather than hardcoded, so the check operates on
    # whichever tree it is pointed at instead of always reading the real repo.
    tasks = args.tasks if args.tasks is not None else args.graph.parent.parent / "tasks"
    known = {n["id"] for n in nodes}
    for packet in sorted(tasks.glob("FORGE-*.md")):
        node_id = packet.stem
        if node_id not in known:
            problems.append(f"{packet}: packet has no node in {args.graph}")

    if problems:
        print("Document and graph state disagree:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"OK: {len(nodes)} graph nodes consistent with documents")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
