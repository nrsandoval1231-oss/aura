"""The protected-surface registry, and the assertion that keeps it honest.

Audit F9 found the previous denylist protecting two of twelve real surfaces
because it named files that were never created. The first test below is the
mechanism that stops that recurring: it walks the declared surfaces and asserts
each one exists. Delete it and F9 re-opens silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.policy import (
    PROTECTED_FUTURE_PATHS,
    PROTECTED_PATHS,
    normalize_for_policy,
    pattern_reaches_protected_surface,
    requires_owner_authority,
)

ROOT = Path(__file__).resolve().parent.parent


def test_every_declared_protected_path_exists():
    """The anti-rot gate. A protected surface that is not real protects nothing."""
    missing = sorted(path for path in PROTECTED_PATHS if not (ROOT / path).exists())
    assert missing == [], (
        f"PROTECTED_PATHS names {len(missing)} path(s) that do not exist: {missing}. "
        "Either the file moved and the entry must follow it, or the entry is "
        "aspirational and belongs in PROTECTED_FUTURE_PATHS."
    )


def test_future_paths_are_not_yet_real():
    """Keeps the two sets from blurring back together.

    An entry that has become real belongs in PROTECTED_PATHS, where the existence
    assertion covers it. Leaving it here would exempt a live surface from that
    check, which is the F9 shape again.
    """
    already_real = sorted(path for path in PROTECTED_FUTURE_PATHS if (ROOT / path).exists())
    assert already_real == [], (
        f"{already_real} now exist and must move to PROTECTED_PATHS so the "
        "existence assertion covers them."
    )


#: The exact surfaces F9 measured as unprotected. Enumerated rather than derived,
#: so a future refactor that quietly stops covering one of them fails here.
F9_REGRESSION_SURFACES = (
    "src/forge/ledger_store.py",
    "src/forge/config.py",
    "src/forge/paths.py",
    "src/forge/cli.py",
    "src/forge/policy.py",
    "src/forge/context_engine.py",
    "src/forge/providers/model_provider.py",
    "scripts/validate.sh",
    "scripts/run_slice.py",
    ".agent/graph/work-graph.json",
)


@pytest.mark.parametrize("path", F9_REGRESSION_SURFACES)
def test_f9_surfaces_require_owner_authority(path):
    assert requires_owner_authority(path), f"{path} was unprotected in audit F9"


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        "FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md",
        ".agent/AGENT_RULES.md",
        ".agent/DECISIONS.md",
        "docs/finish-contract.md",
        "src/forge/trust_kernel.py",
        "src/forge/execution_loop.py",
        "src/forge/product_brain.py",
        ".env.example",
        "docs/adr/0001-anything.md",
        "NORTH_STAR.md",
        "src/forge/governor.py",
        "src/forge/audit_receipts.py",
        ".agent/audit-trust.json",
    ],
)
def test_governance_surfaces_require_owner_authority(path):
    assert requires_owner_authority(path)


@pytest.mark.parametrize(
    "path",
    [
        # Advisory only; its own docstring records that confidence never confers
        # authority, so it is deliberately routine.
        "src/forge/decisions/jev_decisions.py",
        "README.md",
        "docs/packets/FORGE-ING-001-intent-ingestion.md",
        "tests/test_cli.py",
        "src/forge/ingestion/calibrate.py",
    ],
)
def test_routine_surfaces_do_not_require_owner_authority(path):
    assert not requires_owner_authority(path)


@pytest.mark.parametrize(
    "spelling",
    [
        "docs/finish-contract.md",
        "docs/finish_contract.md",
        "DOCS/FINISH-CONTRACT.MD",
        "./docs/finish-contract.md",
        "docs\\finish-contract.md",
        "src/forge/../forge/trust_kernel.py",
    ],
)
def test_spelling_never_decides_protection(spelling):
    """Separator, case, hyphen, and traversal are presentation, not authority."""
    assert requires_owner_authority(spelling)


@pytest.mark.parametrize(
    "pattern",
    [
        "*/core.py",
        "**",
        "src/**",
        "src/acme/**",
        "src/*/policy_config.json",
        ".agent/graph/*",
        "scripts/validate.sh",
        "src/forge/audit_receipts.py",
        ".agent/audit-trust.json",
        "governor/*.py",
    ],
)
def test_patterns_reaching_protected_surfaces_are_caught(pattern):
    assert pattern_reaches_protected_surface(pattern)


@pytest.mark.parametrize("pattern", ["docs/packets/*.md", "README.md"])
def test_routine_patterns_are_not_escalated(pattern):
    assert not pattern_reaches_protected_surface(pattern)


def test_normalization_is_idempotent():
    for path in (*PROTECTED_PATHS, *PROTECTED_FUTURE_PATHS):
        once = normalize_for_policy(path)
        assert normalize_for_policy(once) == once


def test_execution_loop_delegates_rather_than_keeping_a_second_copy():
    """F9's root cause was two implementations of one security-relevant rule."""
    from forge import execution_loop

    source = Path(execution_loop.__file__).read_text(encoding="utf-8")
    assert "_A3_EXACT_PATHS" not in source
    assert "_A3_PROTECTED_BASENAMES" not in source
    assert execution_loop._path_requires_a3("src/forge/ledger_store.py") is True


# ---------------------------------------------------------------------------
# Precision. A gate that demands the owner for editing tests gets waved through,
# and F9 is what waving it through costs. Both directions are asserted, because
# fixing over-firing is exactly where under-firing gets reintroduced.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    [
        # Basename is pure wildcard: `**` fnmatches every protected basename, which
        # escalated these two on its own.
        "docs/packets/**",
        "tests/**",
        # Nothing protected lives under tests/, so `*.py` there reaches nothing —
        # the basename rule only applies under src/ in requires_owner_authority.
        "tests/unit/*.py",
        "tests/test_cli.py",
        "docs/packets/*.md",
        ".agent/artifacts/FORGE-X/**",
        "README.md",
    ],
)
def test_routine_patterns_are_not_escalated_to_a3(pattern):
    assert not pattern_reaches_protected_surface(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        "**",
        "src/**",
        "src/forge/**",
        "src/**/*.py",
        "src/*/policy_config.json",
        "src/forge/policy*.py",
        "src/forge/ledger_store.py",
        "docs/**",
        "docs/adr/**",
        ".agent/graph/*",
        "*/core.py",
        "governor/*.py",
        "scripts/validate.sh",
        "AGENTS.md",
        "*.py",
    ],
)
def test_patterns_that_can_reach_a_protected_surface_still_do(pattern):
    """The half that must not regress while precision is being improved."""
    assert pattern_reaches_protected_surface(pattern)
