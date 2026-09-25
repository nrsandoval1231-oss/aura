# Aura local engineering runner

`forge.engineering_runner.EngineeringRunner` is a local, callback-driven
orchestrator. It creates persistent detached Git worktrees, assigns at most one
packet to each named lane, rejects overlapping write scopes, runs the packet's
fixed local check commands, and persists candidate and review state. It does not
call a model, push, merge, or deploy. Provider adapters and their identity,
credentials, and billing authority remain deployment work.

```python
runner = EngineeringRunner(
    repository=Path("/path/to/checkout"),
    state_dir=Path("/path/to/private-run-state"),
    review_policy_id="owner-pinned-policy-id",
    verify_review=trusted_detached_signature_verifier,
)
result = runner.run((packet,), {"deepseek": deepseek_adapter, "luna": luna_adapter})
```

The `verify_review` callable is supplied when the trusted runtime is constructed;
review proof strings and caller labels are never used as keys or roots. A candidate
stays `REVIEW_PENDING` until that verifier accepts the digest bound to repository,
packet, candidate, fixed check results, and review policy. A packet already present
in durable state cannot be replayed. Corrupt state and interrupted builders report
`UNKNOWN`, requiring explicit reconciliation.

Checks are declared in a `Packet` before dispatch and run as argument arrays in the
candidate worktree. Missing or unstartable checks remain `UNKNOWN`; nonzero checks
do not qualify a candidate for review. Each callback receives a `LaneTask` scoped
to its worktree and allowed paths. The runner detects changed paths outside that
scope after the callback returns. A callback is trusted runtime code: this local
runner is not a sandbox against a malicious process with host access.

The runner exposes read-only durable status:

```powershell
python -m forge.engineering_runner status --state-dir .agent/runtime
```

Recovery attempts are bounded by the packet and use strictly higher strategy rungs;
after two material repairs the runner escalates. The current implementation does
not automatically integrate reviewed candidates or close SliceLearning outcome
measurements. It can start a `SliceLearning` slice and record attempt evidence when
one is injected, but production review authentication, lesson proposal/measurement,
restart reconciliation tooling, integration policy, full repository validation,
and live provider adapters remain separate work.
