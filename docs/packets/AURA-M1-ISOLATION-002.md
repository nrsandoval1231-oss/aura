# AURA-M1-ISOLATION-002 reproducible evidence and successor

Exact source base: `d2f96278e479da7bc1d786fc12824cacd640b4de`.
The independent raw verdict on that candidate was `CORRECT`; see
`.agent/artifacts/AURA-M1-ISOLATION-001/REVIEW-d2f9627.json`. The prior
summary alone was not reproducible. The scripts and unedited raw attempt
outputs for this correction are in
`.agent/artifacts/AURA-M1-ISOLATION-002/probes/`.

## Exact commands on this Windows/Ubuntu WSL host

From the Aura worktree root, using the tested Python in `.venv`:

```powershell
wsl -d Ubuntu -- bash /mnt/c/Users/nrsan/.codex/worktrees/aura-m0-m1/Aura/.agent/artifacts/AURA-M1-ISOLATION-002/probes/sandbox_probe.sh /mnt/c/Users/nrsan/.codex/worktrees/aura-m0-m1/Aura/.agent/artifacts/AURA-M1-ISOLATION-002/probes/sandbox_probe.raw.txt
.\.venv\Scripts\python.exe .agent/artifacts/AURA-M1-ISOLATION-002/probes/restart_probe.py *> .agent/artifacts/AURA-M1-ISOLATION-002/probes/restart_probe.raw.txt
```

On another checkout, replace the two absolute `/mnt/c/...` arguments with
that checkout's WSL paths. Both scripts create unique disposable repositories
under the local temp directory. The WSL script records its environment version
and every denial result. No provider or paid service is called.

The first sandbox run exited 1 because its source repository contained an
untracked fsmonitor probe script; its raw output is preserved as
`sandbox_probe-attempt1.raw.txt`. The script then committed that fixture before
freezing the source base. Its next run exited 0. Raw output shows Bubblewrap
0.11.1, Python 3.14.4, Git 2.53.0; host file invisible; network error 101;
fsmonitor, included filter, and hook actually invoked but unable to write
outside their mounts; one isolated `unittest` passed; exact candidate SHA
`fe7081ba69920c7b6b42f778f8c30a08333817d5`, tree
`e27d65c768a24c8743470e7f738a4429e47f5ac6`; source clean.

The first restart run exited 1 before creating a ledger because the fresh
Windows repository had inconsistent Git line-ending defaults between normal
Git setup and the executor's scrubbed environment. Its raw traceback is
preserved as `restart_probe-attempt1.raw.txt`. The fixture now fixes local
`core.autocrlf=false`; the next run exited 0. Raw output records child exit 91
immediately after durable intent, a fresh process returning `UNKNOWN_EFFECT`,
only one `AURA_EXEC_INTENT` receipt, no candidate worktree, and a clean source.
This is a separate-process ledger proof for the rejected offline executor,
not integrated sandbox restart reconciliation.

## Limits and next packet

The probes establish feasibility on one host and preserve both failed attempts.
They do not constrain every filesystem capability, attest the runtime binary,
or provide a trusted controller. `AURA-M1-ISOLATION-003.md` is a fixed proposed
implementation packet with exact planned files, a zero-dollar model budget,
finite file/CPU/memory/process/output/time limits, required checks, and
rollback. It remains PROPOSED until this evidence receives independent audit;
then Sol must freeze its source base and review authority before dispatch.
Production CLI dispatch, owner-key trust pin, and merge remain blocked.
