# FORGE-EXT-001 — controlled Hallam external trial

**Status:** READY_AUTHORIZED
**Repository:** Forge `nrsandoval1231-oss/forge-agent`; external target `nrsandoval1231-oss/hallam`
**Forge base:** `e96728465656ab00b90509d735ba3d263bb78ff3`
**Hallam base:** `2d687fe51fdc406c35f52cfc8c275615f2792772`
**External branch:** `codex/forge-external-trial`
**Authority:** A3 for the named Hallam branch under the owner's 2026-09-22 selection; A2 up to $15 total for one DeepSeek Builder request under the owner's paired Hallam-trial and live-work authorization
**Risk:** HIGH because this packet permits one paid provider effect and one remote branch push
**Retry budget:** no automatic provider retry; two local code-repair attempts before the call

## Objective

Run one real Forge Builder request against a bounded Hallam defect, apply only a
validated proposal, prove the exact external candidate locally, obtain an
independent audit, and push only the named branch. The Opportunities page labels
an input `Industry` and `/api/opportunities` returns `industry`, but the browser
filter searches only company and title. An industry-only match is incorrectly
hidden.

## Allowed files

- `scripts/external_trial_builder.py`
- `tests/test_external_trial_builder.py`
- `.agent/artifacts/FORGE-EXT-001/**`
- `.agent/ledger/FORGE-EXT-001.*`
- `.agent/tasks/FORGE-EXT-001.md`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`

## Ownership

### Luna builder — Forge harness only

- `scripts/external_trial_builder.py`
- `tests/test_external_trial_builder.py`
- `.agent/artifacts/FORGE-EXT-001/COMPLETION.json`

### Sol — governance and effects

- `.agent/tasks/FORGE-EXT-001.md`
- `.agent/graph/work-graph.json`
- `.agent/CURRENT_STATE.md`
- `.agent/artifacts/FORGE-EXT-001/**` effect and final evidence
- `.agent/ledger/FORGE-EXT-001.*` only at effect time
- Hallam `apps/api/sabra_api/main.py`
- Hallam `tests/test_api.py`

## Exclusions

No other Hallam file, `main` push, merge, deployment, application submission,
candidate data, résumé data, live job application effect, provider retry,
canonical Forge architecture/PRD/Finish Contract change, trust-kernel change,
or weakening of either repository's tests. Never print or persist credentials
or provider response bodies.

## Required behavior

1. Preflight exact clean Forge and Hallam SHAs, target origin, ignored credential
   presence, `deepseek-flash`, one-call claim absence, request bounds, and the
   $15 conservative ceiling.
2. Persist and reload `CALL_INTENT` before the provider effect. One claim permits
   one request. Interruption or ambiguity becomes `UNKNOWN` and blocks retry.
3. The structured proposal may name only the two Hallam paths above and must
   preserve candidate truth, approval-before-submit, and safe-stop behavior.
4. The prompt and proposal must require an industry-only positive match and an
   unrelated-industry negative case. This is a packet acceptance requirement,
   not a promoted lesson or self-improvement claim.
5. Sol reviews and applies the proposal. Focused API tests and Ruff must pass.
   Run the full default suite and report the pre-existing live Greenhouse CAPTCHA
   failure separately if it remains; do not repair it here.
6. Freeze exact Forge and Hallam candidates. Astra independently audits scope,
   behavior, exact identities, and evidence. Only an ACCEPT may authorize the
   named Hallam branch push.
7. After push, verify the remote branch SHA exactly. Do not merge or deploy.

## Acceptance

- Industry-only matching works and unrelated industry values do not match.
- The Hallam diff contains only the two owned files.
- Provider intent/outcome receipts and checkpoint reload with an unbroken chain.
- The provider request count is one and actual billing remains UNKNOWN unless the
  provider supplies it.
- Independent audit accepts the exact candidates.
- Remote `codex/forge-external-trial` resolves to the exact audited Hallam SHA.
- No self-improvement measurement is inferred from this trial. A later packet may
  derive, validate, retrieve, apply, and measure a real lesson from retained trial
  evidence if the evidence supports one.

## Handoff

Return exact commands, exit codes, SHAs, changed files, request/response digests,
sanitized usage, ledger/checkpoint heads, audit verdict, remote branch SHA, spend
status, and remaining unknowns. No builder self-certification, push, merge, or
deployment.
