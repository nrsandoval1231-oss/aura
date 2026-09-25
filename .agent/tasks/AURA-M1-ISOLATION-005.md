# AURA-M1-ISOLATION-005 — Repair review patch binding

Status: IMPLEMENTED; deterministic repository validation red, independent
review pending. Repair-only successor to independent `CORRECT` at exact source
candidate `83775200a99914f97bb2ec3f62cc24b76d5efdd9`.

## Base

- Repository: `nrsandoval1231-oss/aura`
- Branch/worktree: `codex/aura-m1-isolated-runner` in `C:\Users\nrsan\.codex\worktrees\aura-m1-isolated-runner\Aura`
- Base SHA: `83775200a99914f97bb2ec3f62cc24b76d5efdd9`
- Independent verdict: `CORRECT`. The reviewer demonstrated that candidate-local Git diff configuration can leave `execute_proposal` returning `REVIEW_REQUESTED` with a patch that omits changed file content, even though the independent bundle/tree verifier passes. The prior candidate is rejected and its receipts remain unchanged.

## Objective

Return a review patch derived from the independently verified Git objects, bound
to the exact candidate and allowlisted changed paths. The verifier must reject
or ignore any patch bytes produced by candidate-controlled configuration. The
caller must persist only the independently verified patch and its digest.
Preserve the existing offline execution, denial, exact-check, and restart
behavior. Keep the runner unwired.

## Allowed files

- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/tasks/AURA-M1-ISOLATION-005.md`
- `.agent/artifacts/AURA-M1-ISOLATION-005/**`
- `.agent/ledger/AURA-M1-ISOLATION-005.*`
- `docs/packets/AURA-M1-ISOLATION-005.md`
- `src/forge/aura_sandbox.py`
- `src/forge/aura_sandbox_verifier.py`
- `tests/test_aura_sandbox.py`

No edits to prior packets/artifacts/ledgers, `aura_cli.py`, `aura_runtime.py`,
`aura_executor.py`, provider adapters, Governor/policy, protected audit verifier,
trust anchor, AGENTS, PRD, architecture, or finish contract.

## Acceptance

- Reproduce the review-patch omission using disposable allowed files and
  candidate-controlled Git diff configuration. The regression must fail on
  base and pass after the repair. The returned patch must include both real
  changes or the operation must fail closed; warnings/stderr cannot masquerade
  as patch bytes.
- The fresh read-only verifier derives or verifies patch bytes from the exact
  imported candidate bundle/tree with external diff and text conversion
  disabled. Confirm candidate commit/tree, parent, changed paths, allowlisted
  blobs, patch digest, and check digest all refer to one candidate.
- Rerun denial/resource, fixed unittest, clean source, actual child-process kill
  and fresh-process UNKNOWN without a duplicate effect. Preserve raw command,
  output, exact disposable base/candidate SHA and full validation.
- Run focused tests, Ruff, diff checks, and `./scripts/validate.sh` on a frozen
  candidate. Preserve historical evidence and use only a new append-only 005
  slice/ledger; no `--rebind`. Independent security review must inspect exact
  candidate after the repair. Detached owner-pinned external audit remains
  UNKNOWN and blocks merge/live dispatch.

## Budget and authority

One bounded source repair and at most one materially distinct correction, at
most one new disposable proposal per test case, no model/provider calls, USD
budget $0. Preserve the prior per-task proposal/resource limits. If the patch
cannot be bound safely inside this scope, report the blocker and stop. No push,
merge, deployment, trust activation, or CLI dispatch from this packet.

## Completion checkpoint

- The base regression reproduced `REVIEW_REQUESTED` with both checks passing
  while the review patch omitted a changed test's sentinel. The repaired path
  stores only patch bytes freshly derived by the independent read-only verifier
  from the imported candidate Git objects, with `--no-ext-diff` and
  `--no-textconv`; digest and candidate/tree/path/check bindings are verified
  by the host before persistence.
- Full sandbox tests: `7 passed`; targeted restart/denial tests: `2 passed`.
  Ruff check, Ruff format check, and `git diff --check` passed. Raw commands and
  output are under `.agent/artifacts/AURA-M1-ISOLATION-005/probes/`.
- Full repository pytest: `582 passed, 1 skipped, 1 failed`. The isolated
  failure is the pre-existing `tests/test_aura_executor.py::test_rejects_files_created_by_a_check_and_check_timeout` expectation; with
  a one-second total check budget, setup exhausts the budget before the
  0.2-second per-check timeout, producing `Total check budget exhausted`
  instead of `timed out`. It is outside this packet and remains unmodified.
- Canonical slice generation was attempted once without `--rebind`; it refused
  to write slice/ledger evidence because its pytest gate was red. Its run took
  place while a duplicate local process was also running and reported three
  failures. A subsequent serialized full pytest run and isolated rerun both
  reproduce the single failure above. No slice or ledger is claimed.
- The patch repair is a review candidate only. Independent security review is
  pending. Detached owner-pinned audit status is `UNKNOWN`; no merge/live
  dispatch authority is established.
