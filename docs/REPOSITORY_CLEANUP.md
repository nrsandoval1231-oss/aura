# Repository cleanup — September 25, 2026

Owner requested cleanup and appropriate merges/closures. Source base: `0dd62aae4959227a5c5a2d7cb618bbd7616bfef4`.
This records disposition, not live product acceptance.

## PR disposition

PRs #1–#8 were already closed unmerged at 00:05 UTC September 26, before this cleanup.
Their closing comments say they were superseded by the owner-requested usable Aura CLI.
Independent source review supports leaving them closed rather than bulk-merging their
old stack. Each unique tip remains reachable through its existing remote branch and PR.
No unique unmerged branch is deleted by this cleanup.

| PR | Preserved head | Disposition |
| --- | --- | --- |
| [#1](https://github.com/nrsandoval1231-oss/aura/pull/1) | `2d1447cc9b8d665ba78f543ec19171d1a4e89a30` | Superseded specification; current direction contains the agreed CLI, memory and skills requirements. |
| [#2](https://github.com/nrsandoval1231-oss/aura/pull/2) | `581c4506819f8b7e2e393857193cd5f1295ec42a` | Preserve CLI/state scaffold for selective reuse; build is intentionally BLOCKED and Git configuration needs isolation. |
| [#3](https://github.com/nrsandoval1231-oss/aura/pull/3) | `a30c7fca8f6b300cd33012c4eb618897f76794a6` | Preserve rejected executor experiments and negative evidence; no production authority. |
| [#4](https://github.com/nrsandoval1231-oss/aura/pull/4) | `0e4f8382afe5943ab11296e1bae8ba6e7a4cf431` | Preserve owner-held trust design as reference. |
| [#5](https://github.com/nrsandoval1231-oss/aura/pull/5) | `5937f94287251e5cedf0b9d7f7412f24b4286671` | Preserve machine-specific WSL sandbox experiment; independent security review and portable integration remain outstanding. |
| [#6](https://github.com/nrsandoval1231-oss/aura/pull/6) | `b23e3c87a512b6279df3ea11831ccfa499ee3eaf` | Rejected verifier checkpoint; defects repaired in #7. |
| [#7](https://github.com/nrsandoval1231-oss/aura/pull/7) | `cc3e78f74f0dac4982cafb6398bbd71fc1b0e521` | Preserve corrected verifier for a separate integration; owner signature remains unverified here. |
| [#8](https://github.com/nrsandoval1231-oss/aura/pull/8) | `89f0bf093e60d010a9c47a6ec9743a8be8e1fc65` | Obsolete blocked evidence plan; no new runtime implementation. |

[PR #9](https://github.com/nrsandoval1231-oss/aura/pull/9) is the approved new direction,
architecture image and builder handoff. Cleanup repairs are added to this current work
for independent review and passing validation before merge. Check GitHub for final state.
The branch codex/aura-governed-runner currently points to the old main baseline and has
no unique published implementation; do not infer a working runner from its name.

## Reusable code map

- #2: src/forge/aura_cli.py, aura_runtime.py, tests/test_aura_cli.py,
  test_aura_runtime.py, test_aura_routing_policy.py, and the aura entry point.
- #5: aura_sandbox.py, aura_sandbox_verifier.py and their hostile-input/restart tests.
  The experiment pins WSL and exact binaries and limits changed files; adapt and review
  for the selected runtime before use. The earlier aura_executor.py is not isolated.
- #7: aura_audit.py, test_aura_audit.py, protected-surface registry changes and the
  Aura-specific verifier dispatch. Keep keys and attestation outside builder scope.

Do not import branch snapshots over current main: they predate brand and canonical
product changes and include stale graph/evidence state. Reuse bounded changes under
new reviewed tasks. No closed branch's provider, review, or execution path was activated.

## Source validation repairs

The original main baseline reproduced 556 passing and three failing tests, plus lint,
format and graph failures. Repairs keep all validation gates enabled:

- Replace an undefined Any annotation with the actual Ledger type and mark the unused
  stream label explicitly unused; format only the two flagged Python files.
- Assert the missing-ledger error's actual message and LEDGER_NOT_FOUND code.
- Repair reconciliation test setup: derive historical ledger/slice paths from the
  selected packet, retain the modified graph instead of overwriting it with a second
  fixture call, and add a valid control case alongside the malformed-record cases.
  The controls now test the intended rejection, rather than failing on an earlier fixture error.
- Archive four obsolete import/runner packets that lacked current graph nodes. Preserve
  their exact bytes and original path mapping in [the archive](archive/README.md).
  No completed state is invented; current routing, trust, runner and proof nodes remain open.

Existing ledgers, checkpoints, artifacts, runtime policy and validation gate definitions
are unchanged. The slice gate already had no active graph packet on baseline main;
archival does not remove an active graph task or create runtime acceptance.

## Next product work

Follow [the builder handoff](product/AURA_BUILDER_HANDOFF.md): implement one real governed
coding path with memory/skills/restart designed in, then validate continuity, both lanes
and an unattended build. Read current source and account/provider access before dispatch.

