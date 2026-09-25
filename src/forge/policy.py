"""The protected-surface registry: the single source of truth for A3 authority.

`AGENTS.md` says which surfaces need explicit owner authority. This module is the
executable form of that sentence, and it is the only executable form — every gate
that asks "does touching this path require the owner?" asks here.

Why this file exists at all
---------------------------
The 2026-09-22 audit (F9) measured the previous answer against the real tree and
found it protected two surfaces out of twelve. The denylist had been written
against a file layout that was never built: `governor.py`, `authority.py`,
`policy.py`, `evidence_ledger.py`, `secrets.py`. None of those files existed. The
real evidence ledger is `ledger_store.py`; the real secrets surface is
`config.py`; the real validation authority is `scripts/validate.sh`; the real
authority on node status is `.agent/graph/work-graph.json`. All four were
writable by a routine A1 packet, which means a builder could have promoted its
own node to READY and deleted the gate that would have caught it.

That failure has one root cause worth naming: a denylist of names nobody checks
against the filesystem degrades silently, and it degrades in the unsafe
direction. So this module carries two kinds of entry and treats them differently.

- `PROTECTED_PATHS` names surfaces that **exist right now**. `tests/test_policy.py`
  asserts every one of them is present in the working tree, so an entry that
  stops being real fails the build instead of quietly protecting nothing. That
  test is the whole anti-rot mechanism; deleting it re-opens F9.
- `PROTECTED_PREFIXES`, `PROTECTED_MODULE_PATTERNS`, `PROTECTED_BASENAMES`, and
  `PROTECTED_PACKAGES` are forward-looking. They cover governance modules that do
  not exist yet, so they are deliberately *not* existence-checked. Their job is to
  catch a future `governor.py` on the day it is written rather than the day
  somebody remembers to add it here.

What earns protection
---------------------
A surface is protected when it *decides* authority, scope, evidence, validation,
or graph status — not merely when it is important. `context_engine.py` is protected, because it
enforces role-context independence structurally, and an independence guarantee
that a routine packet can edit is not a guarantee.

This file is itself protected, by the `src/**/policy.py` pattern it defines. That
is intentional: the rule that decides what needs the owner should need the owner.
"""

from __future__ import annotations

import fnmatch
import posixpath

__all__ = [
    "PROTECTED_BASENAMES",
    "PROTECTED_MODULE_PATTERNS",
    "PROTECTED_PACKAGES",
    "PROTECTED_PATHS",
    "PROTECTED_PREFIXES",
    "normalize_for_policy",
    "pattern_reaches_protected_surface",
    "requires_owner_authority",
]


#: Surfaces that exist in the tree today. Spelled exactly as they appear on disk
#: so `tests/test_policy.py` can assert each one is real; comparison normalizes
#: both sides, so hyphen-versus-underscore and case never decide a match.
PROTECTED_PATHS: frozenset[str] = frozenset(
    {
        # Canonical authority and governance (AGENTS.md "Protected surfaces").
        "AGENTS.md",
        "AURA_ARCHITECTURE.md",
        "AURA_PRD.md",
        ".agent/AGENT_RULES.md",
        ".agent/DECISIONS.md",
        "docs/finish-contract.md",
        "docs/self-improvement-acceptance.md",
        # The authority on node status. Unprotected until F9: a packet could
        # promote its own node to READY.
        ".agent/graph/work-graph.json",
        # The sole validation authority (DEC-009) and the harness that produces
        # candidate-bound evidence. Unprotected until F9: a packet could delete
        # the gate that would have failed it.
        "scripts/validate.sh",
        "scripts/run_slice.py",
        # Verifies the owner-pinned detached audit that the canonical slice
        # gate uses for the integrated successor.
        "src/forge/audit_receipts.py",
        # The owner-approved public-key fingerprint for the integrated audit.
        ".agent/audit-trust.json",
        # Owner-pinned detached review for Aura itself.
        "src/forge/aura_audit.py",
        ".agent/aura-audit-trust.json",
        # Trust kernel, loop, and specification.
        "src/forge/trust_kernel.py",
        "src/forge/execution_loop.py",
        "src/forge/product_brain.py",
        # The evidence ledger. AGENTS.md protects "evidence-ledger modules"; the
        # one in this repository is named ledger_store.py, which the pre-F9
        # denylist did not recognise.
        "src/forge/ledger_store.py",
        # This registry.
        "src/forge/policy.py",
        # Credential loading. AGENTS.md protects secrets; this is that surface.
        "src/forge/config.py",
        ".env.example",
        # Decides whether a path is inside scope, for every gate that asks.
        "src/forge/paths.py",
        # Implements `graph check` and `ledger verify` — the two commands that
        # verify governed state from outside the process.
        "src/forge/cli.py",
        # Enforces role-context independence structurally.
        "src/forge/context_engine.py",
        # Decides cross-family audit independence.
        "src/forge/providers/model_provider.py",
        # Turn free-text owner intent into a signed owner contract and Mission.
        "src/forge/ingestion/refine.py",
        "src/forge/ingestion/handoff.py",
        # Enforces the budgets the Finish Contract names alongside state, scope,
        # authority and transitions.
        "src/forge/governor.py",
        # Bounds recovery and decides when work returns to the owner.
        "src/forge/stuck.py",
        # Decides which retained experience may change later engineering behaviour,
        # and enforces that a lesson cannot weaken the governance it was measured
        # against. Self-modification policy is governance.
        "src/forge/learning.py",
        # Shared slice learning, recovery projection and Athena comparison.
        "src/forge/slice_learning.py",
        "src/forge/athena_engineering.py",
    }
)

#: Exact paths that are protected but do not exist yet, so they are deliberately
#: excluded from the existence assertion. Kept separate from `PROTECTED_PATHS`
#: rather than mixed in, because the two carry opposite obligations: an entry here
#: that never becomes real costs nothing, while an entry there that stops being
#: real is exactly the F9 defect. Anything that graduates to a real file moves up.
PROTECTED_FUTURE_PATHS: frozenset[str] = frozenset(
    {
        # AGENTS.md protects the North Star explicitly. It has no file yet.
        "NORTH_STAR.md",
        "docs/north-star.md",
        # Governance modules named by AGENTS.md as "future".
        "src/forge/authority.py",
        "src/forge/evidence_ledger.py",
    }
)

#: Directory prefixes. Forward-looking: these need not exist.
PROTECTED_PREFIXES: tuple[str, ...] = (
    ".agent/graph/",
    "docs/adr/",
    "src/forge/governor/",
    "src/governor/",
    "src/forge/authority/",
    "src/authority/",
    "src/forge/policy/",
    "src/policy/",
    "src/forge/deployment/",
    "src/deployment/",
    "src/forge/secrets/",
    "src/secrets/",
    "src/forge/destructive_effects/",
    "src/destructive_effects/",
    "src/forge/trust_kernel/",
    "src/trust_kernel/",
    "src/forge/execution_loop/",
    "src/execution_loop/",
    "src/forge/product_brain/",
    "src/product_brain/",
    "src/forge/north_star/",
    "src/north_star/",
)

#: Glob patterns for governance modules that may be written later.
PROTECTED_MODULE_PATTERNS: tuple[str, ...] = (
    "src/**/governor.py",
    "src/**/governor_*.py",
    "src/**/authority.py",
    "src/**/authority_*.py",
    "src/**/policy.py",
    "src/**/policy_*.py",
    "src/**/evidence_ledger.py",
    "src/**/evidence_ledger_*.py",
    "src/**/ledger_store.py",
    "src/**/deployment.py",
    "src/**/deployment_*.py",
    "src/**/secret.py",
    "src/**/secrets.py",
    "src/**/secret_*.py",
    "src/**/destructive_effect.py",
    "src/**/destructive_effects.py",
    "src/**/destructive_effect_*.py",
)

#: Basenames that carry governance meaning wherever they appear under `src/`.
PROTECTED_BASENAMES: tuple[str, ...] = (
    "governor.py",
    "governor_*.py",
    "authority.py",
    "authority_*.py",
    "policy.py",
    "policy_*.py",
    "evidence_ledger.py",
    "evidence_ledger_*.py",
    "ledger_store.py",
    "deployment.py",
    "deployment_*.py",
    "secret.py",
    "secrets.py",
    "secret_*.py",
    "destructive_effect.py",
    "destructive_effects.py",
    "destructive_effect_*.py",
    "trust_kernel.py",
    "execution_loop.py",
    "product_brain.py",
    "north_star.py",
)

#: Package directory names that make everything beneath them protected.
PROTECTED_PACKAGES: frozenset[str] = frozenset(
    {
        "governor",
        "authority",
        "policy",
        "evidence_ledger",
        "deployment",
        "secret",
        "secrets",
        "destructive_effect",
        "destructive_effects",
        "trust_kernel",
        "execution_loop",
        "product_brain",
        "north_star",
    }
)


def normalize_for_policy(raw_path: str) -> str:
    """Collapse the spellings that must not decide a protection answer.

    Separators, case, and hyphen-versus-underscore are presentation. Treating
    `docs/finish-contract.md` and `docs/finish_contract.md` as different paths is
    how a guardrail gets walked around without anyone lying.
    """
    path = posixpath.normpath(raw_path.replace("\\", "/")).lower()
    return "/".join(part.replace("-", "_") for part in path.split("/"))


_NORMALIZED_PATHS = frozenset(
    normalize_for_policy(path) for path in (*PROTECTED_PATHS, *PROTECTED_FUTURE_PATHS)
)
_NORMALIZED_PREFIXES = tuple(sorted({normalize_for_policy(p) + "/" for p in PROTECTED_PREFIXES}))


def _pattern_matches(path: str, pattern: str) -> bool:
    """Glob match where `*` stays inside a segment and `**` spans segments."""
    path_parts = tuple(part for part in path.split("/") if part)
    pattern_parts = tuple(part for part in pattern.split("/") if part)

    def matches(path_index: int, pattern_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        part = pattern_parts[pattern_index]
        if part == "**":
            return matches(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches(path_index + 1, pattern_index)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], part)
            and matches(path_index + 1, pattern_index + 1)
        )

    return matches(0, 0)


def requires_owner_authority(raw_path: str) -> bool:
    """True when writing `raw_path` requires an explicit A3 owner grant."""
    path = normalize_for_policy(raw_path)
    parts = path.split("/")
    return (
        path in _NORMALIZED_PATHS
        or path.startswith(_NORMALIZED_PREFIXES)
        or any(_pattern_matches(path, normalize_for_policy(p)) for p in PROTECTED_MODULE_PATTERNS)
        or (
            path.startswith("src/")
            and any(
                fnmatch.fnmatchcase(posixpath.basename(path), normalize_for_policy(name))
                for name in PROTECTED_BASENAMES
            )
        )
        or any(part in PROTECTED_PACKAGES for part in parts[:-1])
    )


#: Concrete paths a wildcard is tested against, so a pattern cannot reach a
#: protected surface while claiming routine authority. Includes sentinels for the
#: forward-looking prefixes, which have no real files to test against yet.
_PROBE_PATHS: tuple[str, ...] = (
    *sorted(PROTECTED_PATHS),
    *sorted(PROTECTED_FUTURE_PATHS),
    *(f"{prefix}__probe__.py" for prefix in PROTECTED_PREFIXES),
    "src/forge/deployment.py",
    "src/forge/secrets.py",
    "src/forge/destructive_effects.py",
    "docs/adr/0001-probe.md",
)


def _basename_rule_can_reach(normalized_pattern: str) -> bool:
    """Whether the basename heuristic can apply to this pattern at all.

    `requires_owner_authority` only consults `PROTECTED_BASENAMES` for paths under
    `src/`, so the pattern-level check has to be scoped the same way or it decides a
    different rule. Unscoped, it escalated `tests/unit/*.py` — because `*.py` fnmatches
    `governor.py` — even though nothing protected lives under `tests/`.

    A pattern qualifies when it has no directory part, when its first segment is `src`,
    or when its first segment is a wildcard that could turn out to be `src`.
    """
    segments = normalized_pattern.split("/")
    if len(segments) == 1:
        return True
    first = segments[0]
    return first == "src" or any(token in first for token in ("*", "?", "["))


def pattern_reaches_protected_surface(pattern: str) -> bool:
    """True when an allowed-paths pattern could match a protected surface.

    Scope is declared as globs, so authority has to be decided on the glob rather
    than on whichever files happen to exist when the packet runs. A pattern that
    *could* reach a protected surface is treated as reaching it — the fail-closed
    reading, and the one that survives somebody adding the file later.
    """
    normalized = normalize_for_policy(pattern)
    if requires_owner_authority(normalized):
        return True
    # A wildcard anywhere under src/ can name a governance module on any future
    # day, so it is protected without having to enumerate what it might match.
    if normalized.startswith("src/") and any(token in normalized for token in ("*", "?", "[")):
        return True
    basename = posixpath.basename(normalized)
    # A basename that is nothing but wildcard says nothing about which files the
    # pattern reaches — `**` fnmatches every protected basename there is, so this
    # check alone escalated `docs/packets/**` and `tests/**` to A3. Where such a
    # pattern reaches is decided by its directory part, which the segment analysis and
    # the probe sweep below both cover, and `**` on its own still matches every probe.
    #
    # Precision matters here in the same way coverage does. A gate that demands owner
    # authority for editing tests is a gate people learn to wave through, and F9 is
    # what waving it through costs.
    if (
        basename.strip("*?[]")
        and _basename_rule_can_reach(normalized)
        and any(
            fnmatch.fnmatchcase(normalize_for_policy(name), basename)
            or fnmatch.fnmatchcase(normalize_for_policy(name).replace("*", "module"), basename)
            for name in PROTECTED_BASENAMES
        )
    ):
        return True
    # A wildcard in any non-final segment reaches into whatever directory it
    # matches, so if it could name a protected package it is treated as naming
    # one. Probing against concrete paths cannot decide this: `*/core.py` reaches
    # `governor/core.py` whether or not that file has been written yet, and
    # enumerating every module name a protected package might contain is exactly
    # the unbounded list that produced F9.
    segments = normalized.split("/")
    for index, segment in enumerate(segments[:-1]):
        if not any(token in segment for token in ("*", "?", "[")):
            continue
        if segment == "**":
            return True
        if any(fnmatch.fnmatchcase(package, segment) for package in PROTECTED_PACKAGES):
            return True
        if index == 0 and any(
            fnmatch.fnmatchcase(normalize_for_policy(path).split("/")[0], segment)
            for path in (*PROTECTED_PATHS, *PROTECTED_FUTURE_PATHS)
        ):
            return True
    return any(_pattern_matches(normalize_for_policy(probe), normalized) for probe in _PROBE_PATHS)
