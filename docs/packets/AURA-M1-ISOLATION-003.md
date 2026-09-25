# AURA-M1-ISOLATION-003 — Offline WSL sandbox runner

**Status:** READY, frozen to base `a30c7fca8f6b300cd33012c4eb618897f76794a6`.
The dependency's independent `ACCEPT` is recorded at that exact candidate in
`.agent/artifacts/AURA-M1-ISOLATION-003/PREREQUISITE-REVIEW.json`; it accepts
reproducible feasibility evidence only.

Implement the single offline proposal path specified in
[the active task packet](../../.agent/tasks/AURA-M1-ISOLATION-003.md). This
module remains unwired. Its caller supplies an exact base SHA, allowlist,
proposal contents, and an external state directory. Durable intent must precede
every WSL and target Git invocation. The implementation uses only the pinned
Ubuntu WSL runtime and Bubblewrap. It runs fixed Python 3.14.4 unittest discovery
in an offline sandbox with a 5 MiB candidate tmpfs, verifies the exact one-commit
candidate in a separate sandbox, and reruns checks while its worktree is mounted
read-only. Outcomes are `REVIEW_REQUESTED`, `REJECTED`, or fail-closed `UNKNOWN`;
there is no approval transition.

The packet's two-file/32 KiB proposal limit, 90 second wall budget, 10 second Git
limit, 30 second check/CPU budgets, 512 MiB address-space limit, 32 process
limit, and 1 MiB output limit are hard caps. Missing runtime identity or any
unavailable isolation/resource boundary fails closed. No provider call, live
dispatch, spend, trust pin, merge, or production authority is included.

The repair follow-up adds a fresh-process restart regression: after durable intent and actual WSL Bubblewrap worker startup, the controller and WSL process tree are killed. A separate Python process retries the same request, observes UNKNOWN, leaves exactly one intent receipt, and does not call the runtime probe. Raw command/output is retained under the packet artifacts.
