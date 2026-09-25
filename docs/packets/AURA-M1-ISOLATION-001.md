# AURA-M1-ISOLATION-001 feasibility record

Source candidate `0acb95d59436f73bfbc326f6a69b23689549fa63` received
independent `CORRECT`. A repository-local `core.fsmonitor` command wrote a
marker before the executor recorded its durable intent. This follows an earlier
`CORRECT` for a passing test rewriting its own candidate. Both exact candidate
records are retained; neither executor is production-authorized.

## Environment observed on 2026-09-25

- Windows Docker CLI is installed, but the Docker Desktop Linux daemon socket
  was unavailable (`npipe:////./pipe/dockerDesktopLinuxEngine`).
- Ubuntu WSL is installed. `/usr/bin/bwrap` and `/usr/bin/unshare` are present.
- A minimal Bubblewrap shell with `--unshare-all`, read-only `/usr`, `/bin`,
  `/lib`, `/lib64`, a private `/tmp`, `/proc`, and `/dev` executed successfully.
- In that shell, `/mnt/c/Windows/win.ini` was invisible and a socket connection
  to `1.1.1.1:53` failed with OS error 101 (network unreachable). These are
  narrow probes, not proof that a candidate or its Git configuration is safe.
- Ubuntu has Python 3.14.4 and Git 2.53.0, but no Linux pytest or pip. The
  supported test runtime must be provisioned and pinned before execution.
- In `/tmp/aura-bwrap-git-nYR1jy`, repository-local `core.fsmonitor` was
  demonstrably invoked (`FSMONITOR_EXECUTED`) inside a Bubblewrap shell with a
  read-only source bind. Attempts to write `/outside/host-marker` and
  `/repo/worktree-marker` failed; neither marker existed afterward.
- In `/tmp/aura-bwrap-git-effects-79DQ3y`, repository-local `include.path`
  loaded a malicious clean filter. The filter was invoked twice and a
  `pre-commit` hook once in a writable disposable candidate bind. All three
  attempts to write `/outside` failed; no outside markers existed afterward.
  Candidate-local writes remained possible by design. These were one-host
  denial probes, not a production sandbox implementation or test-runtime proof.
- In a separate Windows process test at
  `C:/Users/nrsan/AppData/Local/Temp/aura-interrupt-proof-e57f82a7f48b47b1a883368baf6fde12`,
  the executor was killed with exit 91 immediately after its durable intent
  append. A fresh process loaded one `AURA_EXEC_INTENT` receipt, returned
  `UNKNOWN_EFFECT`, and did not create a worktree. This proves the current
  ledger's interrupted-intent refusal, not containment of pre-intent Git
  effects or reconciliation into a safe retry.

## Replanned trust boundary

The trusted controller writes and verifies an append-only intent *before any
Git command on the target repository*. It then launches one disposable sandbox
with no network, no home directory, no credentials, no controller receipt mount,
and no sibling worktree mount. Only the required source bytes are available
read-only; a bounded output location holds the candidate. All Git operations
that might read repository-local configuration, includes, fsmonitor, filters,
or hooks occur inside the sandbox. Fixed checks run there with finite CPU,
memory, process, output, and wall-time limits. The controller treats sandbox
exit ambiguity as UNKNOWN and does not retry until it reconciles the output and
receipt chain. It verifies exact candidate bytes and test evidence outside the
sandbox before requesting independent review. No sandbox result grants audit
approval by itself.

## Acceptance before implementation claims

1. A disposable repository with local fsmonitor, filter, hooks, and include
   commands cannot write a marker outside the sandbox before or after intent.
2. A test cannot read a host file or access the network; source and sibling
   worktrees remain unchanged.
3. An allowed change yields an exact commit/tree and a passing fixed test on
   those same bytes; self-rewrite and post-check mutation are refused.
4. A process kill after intent leaves UNKNOWN across restart and blocks retry;
   reconciliation is explicit and append-only.
5. The Linux runtime and package versions are pinned and available without
   mounting host credentials. A missing sandbox/runtime fails closed.
6. Independent Astra reviews the exact implementation candidate; the
   owner-pinned Aura detached-review trust remains a separate protected gate.

Next implementation packet: `AURA-M1-ISOLATION-002`, disjoint from trust-key
provisioning and provider routing. It may wire one offline proposal to a WSL
Bubblewrap runner after the denial probes above pass. No DeepSeek call or CLI
activation is part of that packet. Its exact file scope and budget must be
frozen after the runtime feasibility check.
