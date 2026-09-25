# FORGE-LIVE-001 builder handoff

## Scope delivered

Added a no-network, one-shot runner for the authorized DeepSeek Builder request.
It performs a conservative preflight, records a sanitized `CALL_INTENT` receipt
through `LedgerStore` before transport, makes one request with no retry, and
records a `CALL_OUTCOME` receipt afterward. It returns a validated proposal for
the `README.md` Credentials section; it does not apply the edit automatically.

The ledger contains only packet/base/request identity, prompt digest, token
bounds, authority reference, sanitized provider receipt, status, and output
digest. It never records the API key or full prompt. Billing remains `UNKNOWN`
unless a later provider receipt supplies billing evidence.

## Fail-closed behavior

- Preflight requires `DEEPSEEK_API_KEY`, `BUILDER_MODEL=deepseek-flash`, and a
  conservative request estimate below the owner-authorized $15 ceiling.
- The serialized prompt/schema request is bounded at 8192 bytes before the intent
  receipt is written, with a one-token-per-byte estimate plus a fixed safety
  margin for cost preflight. An existing or partial packet ledger refuses any
  second invocation.
- An atomic exclusive `.claim.json` is durably created before the intent receipt;
  an existing claim is never deleted or reused, including after interrupted
  write or fsync.
- The size check measures the actual DeepSeek adapter JSON payload, including its
  schema instruction, rather than a surrogate representation.
- The output is schema validated and then restricted to `README.md` / `Credentials`.
- Malformed output, transport failure, interruption, and incomplete provider
  outcomes return `UNKNOWN` and never retry.
- Out-of-scope but syntactically valid proposals are `REFUSED` and are never
  applied.
- A successful proposal is stored in the `CALL_OUTCOME` receipt with its digest,
  so reload recovers the nonsecret proposal rather than relying on memory.
- The CLI verifies the requested base SHA is exact `HEAD` and the worktree has
  no visible tracked or untracked changes before loading the env file.
- `run_once` performs the same exact HEAD and clean-worktree verification itself,
  and reloads/verifies `CALL_INTENT` before crossing the provider boundary.

## Validation evidence

- `python -m pytest tests/test_first_live_builder.py -q` — exit 0, 13 passed.
- `python -m pytest -q` — exit 1, 521 passed, 1 pre-existing failure:
  `tests/test_gate_parity.py::test_runner_is_executable` on Windows.
- `python -m ruff check src tests scripts` — exit 0.
- `python -m ruff format --check src tests scripts` — exit 0.
- `git diff --check` — exit 0.

The full repository test result and the executable-bit failure are reported for
Sol to rerun on the integrated candidate. No live request was made.

## Handoff identity and limits

Base worktree HEAD at handoff: `6fe9bf6a2e3a482b5f85b3d1b3d2492fe8829f14`.
Changes are uncommitted. No `.env` or key was read, and no push, merge,
deployment, README edit, or external effect occurred. Independent audit and the
single authorized live request remain Sol-controlled.

Changed files: `scripts/first_live_builder.py`,
`tests/test_first_live_builder.py`, and this artifact.
