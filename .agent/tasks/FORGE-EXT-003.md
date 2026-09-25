# FORGE-EXT-003 — Hallam external trial completion

**Status:** COMPLETE
**Repository:** Forge `nrsandoval1231-oss/forge-agent`; target `nrsandoval1231-oss/hallam`
**Forge base:** `d2870bd9ca3d3f2fba9c9bff0505d2627cd36ee9`
**Hallam base:** `2d687fe51fdc406c35f52cfc8c275615f2792772`
**External branch:** `codex/forge-external-trial`
**Dependencies:** FORGE-EXT-002 independently REDIRECTED with valid evidence; FORGE-EXT-002-CORRECTION-003 independently ACCEPTED
**Authority:** A3 for the owner-selected Hallam branch; A2 for one additional DeepSeek request under the owner's up-to-$15 total remaining live self-improvement authorization
**Risk:** HIGH because this packet permits one paid proposal effect and a later audited named-branch push
**Retry budget:** no automatic provider retry; two local repairs before the call

## Objective

Complete the controlled Hallam trial with one materially narrower model decision.
The model may decide only whether the known search expression must include the
existing `industry` field and confirm the two named behavior cases. Trusted code
constructs the exact two-file patch. The model never supplies file content.

## Allowed files

- `scripts/external_trial_finalize.py`
- `tests/test_external_trial_finalize.py`
- `.agent/artifacts/FORGE-EXT-003/**`
- `.agent/ledger/FORGE-EXT-003.*`
- `.agent/tasks/FORGE-EXT-003.md`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`

After a successful proposal and exact-candidate audit, Sol alone may change:

- Hallam `apps/api/sabra_api/main.py`
- Hallam `tests/test_api.py`

## Required behavior

1. Reuse the accepted EXT-002 trust boundary: exact clean identities, exclusive one-call claim, durable intent before dispatch, checkpoint verification, raw and duplicate-preserving recursive credential scanning, no secret-derived digest, bounded metadata, and UNKNOWN on ambiguous transport.
2. Use a structured selection with only `decision=include_industry`, `positive_case=industry_only`, and `negative_case=unrelated_industry`. Any other output fails closed.
3. Trusted code deterministically creates the audited search-expression edit and a meaningful positive/negative boundary test. No model-authored patch content.
4. Transmit at most 1,024 output tokens. The request's conservative estimate plus the prior cumulative estimate must be at most $0.55408; the cumulative conservative maximum across all three packets is $0.69648, below the owner's $15 ceiling.
5. Make exactly one request and no retry. Record sanitized usage only after full validation; actual billing remains UNKNOWN unless returned.
6. If successful, apply only the two deterministic Hallam edits, run focused tests, Ruff, format, and the full Hallam suite, freeze both candidates, and obtain independent audit before pushing only `codex/forge-external-trial`.
7. Verify the remote branch resolves to the audited Hallam SHA. Do not merge or deploy.

## Acceptance

- One checkpointed request yields a valid bounded proposal.
- Hallam's Industry-only query matches the appropriate row and an unrelated industry does not.
- Hallam changes exactly the two allowed files and passes applicable local gates; any known external live-service failure is reported separately.
- Independent audit accepts exact Forge evidence and Hallam candidates.
- Remote `codex/forge-external-trial` resolves exactly to the audited Hallam SHA.

## Handoff

Return exact commands, exit codes, SHAs, changed files, request/response digests,
sanitized usage, ledger/checkpoint head, audit verdict, remote branch SHA, spend
status, and unknowns. Do not self-certify, merge, or deploy.
