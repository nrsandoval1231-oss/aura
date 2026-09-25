#!/usr/bin/env bash
# The validation authority for this repository.
#
# There is no CI. Validation runs here, on a machine the owner controls, and the
# result is recorded as evidence rather than inferred from a badge. That is a
# deliberate choice (DEC-009), and it carries a real obligation: nothing runs
# these gates on your behalf, so a claim that a change is validated means
# somebody ran this and read the output. An unrun gate is UNKNOWN, never a pass.
#
#   ./scripts/validate.sh
#   PYTHON=/path/to/python ./scripts/validate.sh
#
# Every gate runs even if an earlier one fails, so one broken thing does not
# hide the state of everything behind it. Exit status is non-zero if any failed.

set -uo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"
failures=()

run() {
    local name="$1"
    shift
    printf '\n\033[1m== %s\033[0m\n' "$name"
    if "$@"; then
        printf '\033[32mPASS\033[0m %s\n' "$name"
    else
        printf '\033[31mFAIL\033[0m %s\n' "$name"
        failures+=("$name")
    fi
}

# Gate zero. When validation is local and nothing runs it on your behalf, the most
# likely reason a gate reports UNKNOWN is the interpreter on PATH, and
# `pip install -e .` fails on the version floor with a message about wheels rather
# than about Python. Say it plainly first, before anything else has a chance to
# fail confusingly. (Audit F16.)
require_python_floor() {
    "$PY" - <<'PYFLOOR'
import sys
import tomllib
from pathlib import Path

floor = tomllib.loads(Path("pyproject.toml").read_text())["project"]["requires-python"]
minimum = tuple(int(part) for part in floor.removeprefix(">=").strip().split("."))
if sys.version_info[: len(minimum)] < minimum:
    running = ".".join(str(part) for part in sys.version_info[:3])
    sys.exit(
        f"This repository requires Python {floor} and you are running {running}"
        f" ({sys.executable}).\n"
        f"Re-run with an interpreter that satisfies it, for example:\n"
        f"    PYTHON=python3.12 ./scripts/validate.sh"
    )
print(f"Python {'.'.join(str(p) for p in sys.version_info[:3])} satisfies {floor}")
PYFLOOR
}
run "python floor"    require_python_floor

# Catches the failure mode that once hid undeclared dependencies: a subpackage
# nothing imports cannot break a green test suite.
#
# Counting the exports was not enough: `load_env` sat in `__all__` unimported, so
# `from forge import *` raised while this gate reported a healthy surface. Every
# name is now resolved, which is what "import surface" was always supposed to mean.
check_import_surface() {
    "$PY" - <<'PYSURFACE'
import forge

missing = sorted(name for name in forge.__all__ if not hasattr(forge, name))
if missing:
    raise SystemExit(
        f"forge.__all__ exports {missing} that the package does not define; "
        "`from forge import *` would raise."
    )
print(f"{len(forge.__all__)} exports, all resolvable")
PYSURFACE
}
run "import surface"  check_import_surface
run "lint"            "$PY" -m ruff check src/ tests/ scripts/
run "format"          "$PY" -m ruff format --check src/ tests/ scripts/
run "tests"           "$PY" -m pytest -q
run "doc/graph"       "$PY" -m forge.cli graph check

# Every ledger chain, not one: chain integrity is the permanent guarantee and
# stays meaningful for a packet long after it is complete.
for ledger in .agent/ledger/*.jsonl; do
    [ -e "$ledger" ] || continue
    stream=$(basename "$ledger" .jsonl)
    run "ledger $stream" "$PY" -m forge.cli ledger verify "$stream"
done

# Candidate binding is a development-time gate, so it covers the packets still
# under development. See active_packet_ids() in scripts/run_slice.py.
run "slice"           "$PY" scripts/run_slice.py --check

# FORGE-SI-001 is a mandatory V0 gate, so its proof re-derives on every run rather
# than being trusted from a committed file. A stored artifact that nobody
# recomputes is the failure mode DEC-009 is about, one level up.
run "self-improvement" "$PY" scripts/prove_self_improvement.py --check

# Governed specification evolution and restart reconciliation, re-derived for the same
# reason: a proof nobody recomputes decays into a file that says it once passed.
run "governed evolution" "$PY" scripts/prove_governed_evolution.py --check

printf '\n'
if [ ${#failures[@]} -eq 0 ]; then
    printf '\033[32mAll gates green.\033[0m\n'
    exit 0
fi
printf '\033[31m%d gate(s) failed:\033[0m %s\n' "${#failures[@]}" "${failures[*]}"
exit 1
