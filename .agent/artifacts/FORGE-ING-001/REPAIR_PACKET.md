# FORGE-ING-001 integrity repair packet

- Objective: repair the three candidate-blocking findings from the independent audit of `e62b96cf77e93646e27fd9c2866fc94fdbeaa6f6` without changing canonical intent.
- Repository: `nrsandoval1231-oss/forge-agent`; worktree `C:/Users/nrsan/Projects/forge-agent-ing-repair`; branch `codex/forge-ing-integrity-repair`; base SHA `e62b96cf77e93646e27fd9c2866fc94fdbeaa6f6` (which descends directly from current `main` at `df51dfa24493344bc1af391b40621d2eb22709f1`).
- Allowed implementation: `src/forge/ingestion/**`, `tests/ingestion/**`. This packet and a completion artifact may be written under `.agent/artifacts/FORGE-ING-001/**` as Sol-controlled evidence.
- Exclusions: no Governor, trust-kernel, Product Brain, core ledger, execution-loop, graph/status, canonical architecture, PRD, Finish Contract, secrets, deployment, or unrelated validation repair.
- Dependencies: existing `TrustKernel.authorize` and `AuthorityGrant` are the owner-key verification boundary; existing `LedgerStore` is the persistence boundary. Do not duplicate their signature or chain standard.
- Invariants: an arbitrary owner name or caller-supplied key mapping is never approval; approval is scoped to the exact unsigned contract; handoff verifies and returns the same immutable contract snapshot; malformed/ambiguous ingestion stream bytes fail closed; history is append-only; no silent legacy migration.
- Acceptance: (1) attacker-selected key with a forged approval fails against the trusted owner authority; (2) valid owner grant bound to the exact contract signs and survives restart; (3) changed contract/signature/receipt fails; (4) source mutation during handoff and mutation of the returned Mission contract cannot alter approved content; (5) whitespace-only, blank-line, partial JSON, missing-newline, truncated, stale-checkpoint, missing-checkpoint, duplicate/reordered/corrupt records fail reload; (6) valid append and restart pass; (7) existing ingestion behavior remains tested.
- Deterministic validation: targeted ingestion tests; `scripts/validate.sh` with a source-based Python environment; `git diff --check`. Report the known Windows `test_runner_is_executable` failure separately and do not change it.
- Authority/risk: owner authorized this bounded repair on 2026-09-21. Changes to protected trust or core ledger modules require Sol escalation and a new packet; do not edit them.
- Retry budget: two materially different local repairs per failure, then return to Sol with evidence. Any interrupted append remains UNKNOWN and blocks further writes.
- Handoff: list changed files, exact base/candidate identity, tests with exit codes, migration impact, remaining UNKNOWNs, and an implementation claim only. Do not self-certify, push, merge, deploy, or change graph status. Sol will rerun gates and request independent audit.

## Sol verification checkpoint — bounded correction 1

Sol reproduced two residual defects in the first builder handoff: replacing `OwnerApproval.proof` with an arbitrary non-empty string still permits signing and handoff against a valid grant, and mutating `Mission.owner_contract.assumptions_accepted[0].lineage` changes the returned approved contract. Correct these without expanding paths. The owner approval receipt must not contain an unverified field presented as cryptographic proof; use the trusted grant as the actual proof and bind any owner-claimed approval metadata that matters. Freeze nested assumption lineage as well as top-level contract collections, then test both reproductions. Keep the base candidate and prior negative evidence intact.

## Sol verification checkpoint — bounded correction 2

Sol reproduced that a ledger loaded before a blank tail is appended still accepts `verify()` and `append()` afterward. The initial load preflight is insufficient. Reuse the same framing check on every persisted read used by verification and append; test mutation of the on-disk stream after the `ReceiptLedger` object is constructed. No changes outside ingestion paths. This is the final default repair attempt for this packet; return any unresolved case to Sol rather than expanding scope.

## Sol direction after independent Astra audit — revised persistence packet

Astra returned `CORRECT` on candidate `201b10efc7776f1a63419682e1d97aea1eeb5237`. The two prior correction attempts are exhausted and retained above. These are newly reproduced persistence invariants, so use a revised strategy within the same ingestion ownership: centralize the pre-append and reload check around an expected stream identity and an explicit fresh-versus-existing state. Do not make another framing-only retry or edit the core ledger.

1. A loaded ledger with receipts must refuse append if both its JSONL and checkpoint have disappeared; reject before mutating in-memory or on-disk history. A genuinely fresh empty ledger may create both files on its first append.
2. A checkpoint whose `stream_id` differs from the expected ingestion stream ID (`path.stem`) must fail on reload, verify, and append. Compare checkpoint identity as well as receipt records; do not trust the identity adopted by `LedgerStore.load()` alone.

Add focused regression tests that first reproduce each failure on `201b10ef` and pass after correction. Also test that normal fresh append/reload and loaded append still work. Keep all changes in `src/forge/ingestion/**`, `tests/ingestion/**`, and the completion artifact. Return an uncommitted implementation claim for Sol to validate; do not push, merge, deploy, or alter graph status.
