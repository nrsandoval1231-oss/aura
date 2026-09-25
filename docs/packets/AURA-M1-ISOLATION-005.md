# AURA-M1-ISOLATION-005 — Exact review patch repair

The exact `83775200a99914f97bb2ec3f62cc24b76d5efdd9` offline runner candidate
received independent `CORRECT`: a candidate-local Git diff setting could conceal
the human review patch while its bundle and test evidence still passed. The
rejected source and AURA-M1-ISOLATION-003/004 historical evidence remain intact.

This repair makes the independent verifier the source of patch bytes and binds
them to the imported candidate objects. Both fixed test runs must pass, and their
digests remain strictly compared after normalizing only Python unittest's
elapsed-time text; both raw outputs remain in evidence. The patch is derived
with external diff and text conversion disabled. It remains offline and
unwired, with no provider calls, owner-pinned audit trust, merge eligibility,
or CLI activation.
The [task packet](../../.agent/tasks/AURA-M1-ISOLATION-005.md) sets the exact
scope, tests, and budget.

The 005 patch repair is implemented but remains pending independent security
review. The focused WSL sandbox gates pass. The full repository pytest gate
remains red on an unrelated executor timeout-budget assertion; canonical slice
generation therefore wrote no 005 slice or ledger evidence. Detached external
audit status is `UNKNOWN`, and this candidate is not approved for merge or live
dispatch.
