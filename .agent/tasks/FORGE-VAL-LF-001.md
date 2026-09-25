# FORGE-VAL-LF-001 — Keep the local gate runnable in Windows checkouts

**Node:** FORGE-VAL-LF-001
**Status:** COMPLETE
**Repository:** nrsandoval1231-oss/forge-agent
**Branch/worktree:** codex/forge-v0-completion, isolated managed worktree
**Base SHA:** 57409c0e9057316907c923582a2bbc3d9daade09
**Authority:** A3 governance packet under the owner's V0 completion direction; builder edit is A1
**Risk:** MEDIUM
**Retry budget:** two materially different bounded repairs

## Objective

Make the existing `scripts/validate.sh` runnable from a fresh Windows Git checkout.
The current `.gitattributes` leaves shell scripts under `text=auto` while system
`core.autocrlf=true` checks the tracked LF script out with CRLF. Git Bash then
fails before any gate runs. Preserve the script's Git executable mode and all
existing validation checks.

## Base

- `57409c0e9057316907c923582a2bbc3d9daade09`

## Allowed files

- `.gitattributes`
- `tests/test_gate_parity.py`
- `.agent/tasks/FORGE-VAL-LF-001.md`
- `.agent/graph/work-graph.json`
- `.agent/artifacts/FORGE-VAL-LF-001/**`

## Ownership

- Builder owns `.gitattributes`, `tests/test_gate_parity.py`, and a completion
  artifact under `.agent/artifacts/FORGE-VAL-LF-001/` only.
- Sol owns this packet and `.agent/graph/work-graph.json` only.
- The separate UI builder owns its own branch. Do not edit UI files, product
  requirements, trust kernel, ledger, runner logic, or historical receipts.

## Acceptance

1. Record baseline `git ls-files --eol scripts/validate.sh` as `i/lf w/crlf`
   and the shell parse failure on the base.
2. Force LF checkout for tracked shell scripts. Test Git attributes and, where
   practical, a fresh Windows checkout. Keep the executable-mode assertion.
3. Run the repository validation through the installed Git Bash with the
   documented Python environment; report command, exit code, candidate SHA,
   changed files, and any remaining environment limits.
4. Sol independently reruns the checks and obtains independent audit before
   accepting the candidate. No builder self-certification, push, merge,
   deployment, model call, or spend.
