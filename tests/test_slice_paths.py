"""Changed-path derivation for the proving slice.

The slice's candidate is only as honest as this path set. A path it misses is a
path that skips the loop's scope validation and is absent from the tree hash
that the evidence calls "exact-candidate" — so under-reporting here is silent
and consequential, which is why it gets its own tests.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_slice  # noqa: E402

#: A packet's own evidence paths, as Packet.self_produced supplies them.
SELF_PRODUCED = (".agent/ledger/**", ".agent/artifacts/FORGE-T-001/**")


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repository with one commit on main."""
    _run("git", "init", "-q", "-b", "main", cwd=tmp_path)
    _run("git", "config", "user.email", "t@example.test", cwd=tmp_path)
    _run("git", "config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    _run("git", "add", "-A", cwd=tmp_path)
    _run("git", "commit", "-q", "-m", "seed", cwd=tmp_path)
    monkeypatch.setattr(run_slice, "ROOT", tmp_path)
    return tmp_path


def test_modified_file_is_detected(repo):
    """Regression: stripping porcelain output ate the leading status column.

    `git status --porcelain` emits ' M path'. Stripping the whole output removed
    the first line's leading space, so a fixed 3-character slice returned
    'cripts/run_slice.py' — a path that does not exist, silently filtered out.
    """
    (repo / "seed.txt").write_text("changed\n", encoding="utf-8")
    assert run_slice.changed_paths("main", SELF_PRODUCED) == ("seed.txt",)


def test_untracked_file_is_detected(repo):
    (repo / "brand_new.py").write_text("x = 1\n", encoding="utf-8")
    assert "brand_new.py" in run_slice.changed_paths("main", SELF_PRODUCED)


def test_several_changes_are_all_detected(repo):
    """The first line is the one the strip bug corrupted; later lines survived it."""
    (repo / "seed.txt").write_text("changed\n", encoding="utf-8")
    (repo / "second.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "third.py").write_text("z = 3\n", encoding="utf-8")

    assert run_slice.changed_paths("main", SELF_PRODUCED) == ("second.py", "seed.txt", "third.py")


def test_paths_with_spaces_survive(repo):
    (repo / "a file with spaces.txt").write_text("x\n", encoding="utf-8")
    assert "a file with spaces.txt" in run_slice.changed_paths("main", SELF_PRODUCED)


def test_committed_changes_on_a_branch_are_detected(repo):
    _run("git", "checkout", "-q", "-b", "feature", cwd=repo)
    (repo / "feature.py").write_text("f = 1\n", encoding="utf-8")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "feature", cwd=repo)

    assert run_slice.changed_paths("main", SELF_PRODUCED) == ("feature.py",)


def test_self_produced_evidence_is_excluded(repo):
    """Evidence cannot bind to itself."""
    ledger = repo / ".agent" / "ledger"
    ledger.mkdir(parents=True)
    (ledger / "STREAM.jsonl").write_text("{}\n", encoding="utf-8")
    (repo / "real.py").write_text("r = 1\n", encoding="utf-8")

    assert run_slice.changed_paths("main", SELF_PRODUCED) == ("real.py",)


def test_no_changes_yields_an_empty_set(repo):
    assert run_slice.changed_paths("main", SELF_PRODUCED) == ()


def test_tree_hash_is_order_sensitive_and_content_sensitive(repo):
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")

    baseline = run_slice.tree_hash(["a.txt", "b.txt"])
    assert baseline == run_slice.tree_hash(["a.txt", "b.txt"])
    assert baseline != run_slice.tree_hash(["b.txt", "a.txt"])

    (repo / "b.txt").write_text("b changed\n", encoding="utf-8")
    assert baseline != run_slice.tree_hash(["a.txt", "b.txt"])


# ---------------------------------------------------------------------------
# Packet scope is read from the packet document, not duplicated in code
# ---------------------------------------------------------------------------


def _packet_doc(body: str, tmp_path, packet_id: str = "FORGE-T-001") -> None:
    tasks = tmp_path / ".agent" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / f"{packet_id}.md").write_text(body, encoding="utf-8")


@pytest.fixture
def packet_root(tmp_path, monkeypatch):
    monkeypatch.setattr(run_slice, "ROOT", tmp_path)
    monkeypatch.setattr(run_slice, "TASKS", tmp_path / ".agent" / "tasks")
    monkeypatch.setattr(run_slice, "ARTIFACT_ROOT", tmp_path / ".agent" / "artifacts")
    return tmp_path


def test_scope_is_parsed_from_the_packet_document(packet_root):
    """The packet document is the authority on its own scope.

    A second copy in code is a copy that drifts — which review already caught
    once in this script's hand-maintained path list.
    """
    _packet_doc(
        """# FORGE-T-001

## Objective

Do the bounded thing
described across two lines.

## Allowed files

- `src/forge/**`
- `tests/**`
- `pyproject.toml`

## Explicit exclusions

- `should_not_be_read.py`
""",
        packet_root,
    )

    packet = run_slice.load_packet("FORGE-T-001")
    assert packet.id == "FORGE-T-001"
    assert packet.allowed_paths == ("src/forge/**", "tests/**", "pyproject.toml")
    assert packet.objective == "Do the bounded thing described across two lines."


def test_exclusions_section_is_not_mistaken_for_scope(packet_root):
    """Section parsing must stop at the next heading."""
    _packet_doc(
        "# T\n\n## Objective\n\nx\n\n## Allowed files\n\n- `src/**`\n\n## Explicit exclusions\n\n- `secrets/**`\n",
        packet_root,
    )
    assert run_slice.load_packet("FORGE-T-001").allowed_paths == ("src/**",)


def test_self_produced_paths_are_derived_from_the_packet_id(packet_root):
    _packet_doc("# T\n\n## Objective\n\nx\n\n## Allowed files\n\n- `src/**`\n", packet_root)
    packet = run_slice.load_packet("FORGE-T-001")
    assert packet.self_produced == (".agent/ledger/**", ".agent/artifacts/FORGE-T-001/**")


def test_missing_packet_document_fails_closed(packet_root):
    with pytest.raises(SystemExit):
        run_slice.load_packet("FORGE-ABSENT-001")


def test_packet_without_allowed_files_fails_closed(packet_root):
    _packet_doc("# T\n\n## Objective\n\nx\n\n## Allowed files\n\nnone declared\n", packet_root)
    with pytest.raises(SystemExit):
        run_slice.load_packet("FORGE-T-001")


def test_packet_without_an_objective_fails_closed(packet_root):
    _packet_doc("# T\n\n## Allowed files\n\n- `src/**`\n", packet_root)
    with pytest.raises(SystemExit):
        run_slice.load_packet("FORGE-T-001")


def test_real_packets_in_this_repository_all_parse():
    """Every committed packet must be loadable, or the harness cannot drive it."""
    for path in sorted((Path(__file__).resolve().parent.parent / ".agent" / "tasks").glob("*.md")):
        packet = run_slice.load_packet(path.stem)
        assert packet.allowed_paths, path.stem
        assert packet.objective, path.stem
