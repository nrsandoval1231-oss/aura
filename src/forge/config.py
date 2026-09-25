"""Local configuration loading.

Credentials and model ids live in `.env` at the repository root, which git
ignores. `.env.example` names every variable the code reads and carries no
values.

`load_env` never overwrites a variable already set in the environment. A shell
export or a CI secret is a deliberate act by whoever is running the process; a
file on disk should not silently win against it, and debugging "why is it using
the wrong key" is far worse than debugging "why did nothing load".
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["ENV_FILE", "load_env"]

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def load_env(path: Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Load `.env` into the process environment. Returns what it set.

    Deliberately tiny and dependency-free: this runs before anything else and
    should not be able to fail for a reason unrelated to the file it is reading.
    Missing file is not an error — the tests never need credentials.
    """
    env_path = path if path is not None else ENV_FILE
    if not env_path.is_file():
        return {}

    loaded: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if not key:
            continue
        value = value.strip()
        # Strip one matching pair of surrounding quotes, so a value containing
        # '#' or spaces can be quoted without the quotes becoming part of it.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not value:
            # An unfilled placeholder from .env.example. Setting it to empty
            # would look "configured" while failing later and further away.
            continue
        if not override and key in os.environ:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded
