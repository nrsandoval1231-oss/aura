"""Path scope primitives.

One implementation, used by every gate that decides whether a path is inside a
packet's scope. It previously existed twice: `execution_loop` did it correctly,
and the decision layer re-derived it with bare `fnmatch`, which accepts
traversal (`fnmatch("src/../AGENTS.md", "src/**")` is `True`) and lets `*` cross
a path separator. Two implementations of one security-relevant rule means the
weaker one decides whenever it is the one on the path.
"""

from __future__ import annotations

import fnmatch
import posixpath
from collections.abc import Iterable

__all__ = ["is_safe_path", "normalize_path", "path_matches", "paths_in_scope"]


def normalize_path(raw_path: str) -> str | None:
    """Normalize to a repository-relative POSIX path, or `None` if unsafe.

    Unsafe means absolute, drive-qualified, or escaping the repository root.
    Returning `None` rather than raising lets callers treat an unsafe path as
    simply not in scope, which is the fail-closed reading.
    """
    portable = raw_path.replace("\\", "/")
    normalized = posixpath.normpath(portable)
    if (
        portable.startswith("/")
        or normalized in {".", ".."}
        or normalized.startswith("../")
        or ":" in normalized.split("/", 1)[0]
    ):
        return None
    return normalized


def is_safe_path(raw_path: str) -> bool:
    return normalize_path(raw_path) is not None


def path_matches(path: str, pattern: str) -> bool:
    """Glob match where `*` does not cross a separator and `**` spans segments."""
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


def paths_in_scope(paths: Iterable[str], allowed_patterns: Iterable[str]) -> bool:
    """True only if every path is safe and matches some allowed pattern.

    Fails closed on all three empty/unsafe edges, because each one is a way of
    proving nothing while looking like a pass:

    - no allowed patterns: nothing is permitted, so nothing is in scope;
    - no paths: nothing was declared, so nothing was shown to be in scope. An
      `all()` over an empty sequence is vacuously true, which would silently
      disable this gate for exactly the tools whose paths are hardest to
      enumerate up front — `shell` being the obvious one;
    - any path that normalizes away (absolute, drive-qualified, or `..`-escaping).
    """
    patterns = [normalize_path(pattern) or pattern for pattern in allowed_patterns]
    candidates = list(paths)
    if not patterns or not candidates:
        return False
    for raw_path in candidates:
        path = normalize_path(raw_path)
        if path is None:
            return False
        if not any(path_matches(path, pattern) for pattern in patterns):
            return False
    return True
