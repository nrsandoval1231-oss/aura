# FORGE-EXT-DIAG-001 — explain external proposal refusals safely

**Status:** READY_AUTHORIZED
**Repository:** `nrsandoval1231-oss/forge-agent`
**Base:** `eca487838ed3bdeb53064f1bea43d126f94bd36e`
**Dependency:** `FORGE-EXT-001` REDIRECTED with retained refusal evidence
**Authority:** A3 recovery packet under the owner's V0 completion direction; implementation A1 and local only
**Risk:** MEDIUM because this code shapes evidence for a possible later paid call
**Retry budget:** two materially different local repair attempts

## Objective

Make a future external proposal refusal independently explainable without
persisting provider response bodies, proposal content that failed validation, or
credentials. Preserve the `FORGE-EXT-001` stream and claim unchanged.

## Allowed files

- `scripts/external_trial_builder.py`
- `tests/test_external_trial_builder.py`
- `.agent/artifacts/FORGE-EXT-DIAG-001/**`

## Exclusions

No provider request, Hallam edit, ledger mutation, retry of `FORGE-EXT-001`,
credential output, graph/status edit by the builder, push, merge, deployment,
canonical architecture/PRD/Finish Contract change, or self-improvement claim.

## Required behavior

1. Replace generic proposal-validation `ValueError` outcomes with a closed,
   allowlisted refusal-reason code that identifies the failed rule without
   including rejected content or exception text.
2. When a schema-valid proposal is refused for a non-sensitive validation rule,
   retain bounded metadata only: allowed path, old/new length, and content
   digests. Never retain the rejected old/new/rationale strings.
3. If any configured credential is detected, retain no proposal metadata or
   content digest; record only the sensitive-output refusal code.
4. HTTP, schema, provider-usage, and scope refusals must have distinct safe codes.
   Transport ambiguity remains `UNKNOWN`, never a refusal.
5. The successful path may retain the validated proposal for Sol review.
6. All prior one-call, durable-intent, secret-suppression, request-bound,
   exact-identity, proposal-only, and retry-blocking tests remain green.

## Acceptance

- Offline adversarial tests cover every refusal rule and prove the persisted
  reason is deterministic, allowlisted, and content-free.
- A refused schema-valid proposal records enough bounded metadata to locate the
  rejected hunk while the raw response and rejected proposal remain absent.
- Sensitive-output, malformed-schema, invalid-usage, HTTP, and transport cases
  remain fail-closed with the correct evidence class.
- Full Forge tests, graph check, Ruff, format check, and diff check pass.
- Independent Astra audit accepts the exact local candidate before any later
  packet is allowed to make a provider request.

## Handoff

Return exact candidate identity, changed files, commands and exit codes, reason
code table, persisted metadata schema, adversarial evidence, and unknowns. Do not
self-certify, call a provider, edit Hallam, push, merge, or deploy.
