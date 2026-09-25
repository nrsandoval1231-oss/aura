# FORGE-SENTINEL-002 — local proving result awaiting independent audit

## Identities and authority

- Forge pre-call candidate: `da5d6a4f5542a7eb858a67b4127eb0463f7c7ac3` on `codex/forge-sentinel-proof`; independent Astra pre-call PASS for that exact candidate.
- Sentinal target base: `d43e2629f2c3db87fdb1437a16f5e94a37136c53`; first local candidate: `a9c464bcc2b683014b54082a615501e09bb4df8e`; repaired candidate: `61258ab0590ffb65c2c96e2117e547ae38ddfda7` on `codex/forge-sentinel-run`. The target worktree is clean.
- No remote push, merge, deployment, or product/field-data claim. The authorized two-call grant is exhausted by one UNKNOWN attempt in FORGE-SENTINEL-001 and this one completed request.

## Provider evidence

- Recovery request `REQ-abebec1bcbdd4f26abbc8ffa1b79733d`, `deepseek-flash`, thinking disabled, 3,143 serialized request bytes, exact wire digest `19c40c24551cb8127998365564b023959e8d98288ef762886f70615fb0d1f05c`.
- Provider response ID `53e3a9fc-dcf8-4410-9d0a-15cfbf18dd8c`, HTTP 200, finish `stop`, 747 prompt tokens and 589 completion tokens. Schema-valid bounded proposal digest `2ac5152c15febc1819894e9ca9c2ff646c0fbae6a1d651c4a1be836f6ec33df2`.
- Core ledger reload: 3 receipts at checkpoint head `aee9d81527c75263cedc68523387f713e6408ebdaa6b2d77b72fdc8ced2bd35f`, verification exit 0. Claim retained; no retry.
- Actual billing for this request is UNKNOWN; the API token usage is recorded. The owner reports $0.03 charge for the first attempt, which remains outcome UNKNOWN. The second call used the remaining authorization; no further paid calls are authorized by this packet.
- The first failure cause cannot be inferred. Disabling default thinking is a plausible recovery difference, not established attribution.

## Proposal review and local application

The proposal replaced only `scripts/ci_local.py::run_step`, selecting Git Bash ahead of the WindowsApps WSL launcher. Sol inspected the one-function AST scope before applying it. Sol removed only excess blank lines introduced during insertion; the function body in the local target candidate is the model's proposed body. The source/product contract and tests were not edited. No candidate was sent to the remote.

The unchanged target baseline with normal Windows PATH was 411 passed, 6 failed, 3 skipped; all six failures were in `tests/test_ci_local.py` at the local shell selection boundary. With the local candidate:

| Validation | Exit | Result |
| --- | ---: | --- |
| `python -m pytest -q tests/test_ci_local.py` | 0 | 12 passed |
| `python -m pytest -q` | 0 | 417 passed, 3 skipped |
| `python -m ruff check src tests scripts` | 0 | All checks passed |
| `python scripts/ci_local.py --job research --skip-install`, with isolated venv Scripts on PATH | 0 | Local research job passed pytest, Ruff, and wheel steps |
| `git diff --check` | 0 | No whitespace error |

A prior invocation of `ci_local.py` using the venv Python executable without activating its Scripts directory failed because the step command `python` resolved to the WindowsApps store stub (exit 49). The documented active-venv invocation passed. The local runner warned that the host is Python 3.13.15 while the workflow declares 3.12; this is a toolchain parity limitation, not a claim of hosted CI equivalence.

## Independent FIX and bounded repair

Astra audited Forge `6f01196edc37076951f810e4bc8ae265be5a3833` and the first Sentinal candidate `a9c464bcc2b683014b54082a615501e09bb4df8e`, returning FIX. The model proposal's `WindowsApps` substring check was case sensitive and also rejected a valid POSIX path containing that text. The finding reproduced both behaviors despite the local machine's green tests.

A bounded Luna repair changed only `run_step` and `tests/test_ci_local.py`: reject a WindowsApps path component case insensitively only on Windows, preserve POSIX Bash paths, and test Git Bash priority, case variants, no-Bash fallback, and subprocess arguments. This repair is human-governed local code after the model proposal; do not attribute the repaired function wholly to the model. No additional model call was made.

The repaired target is clean commit `61258ab0590ffb65c2c96e2117e547ae38ddfda7`. Independent controller validation on that exact content: affected tests 17 passed, full suite 422 passed/3 skipped, Ruff passed, `git diff --check` passed, and the local research runner passed tests, Ruff, and wheel with the isolated venv active. The runner still warns of Python 3.13.15 versus declared 3.12. A fresh independent audit of the repaired Forge/target pair was then completed.

## Independent bounded audit

An independent Astra review returned PASS for exact clean Forge `8c6cbfdcdca9534610bdddc3ac18d07c58a73f7b` and Sentinal `61258ab0590ffb65c2c96e2117e547ae38ddfda7`. It independently reran 17 affected tests, 422 full tests with 3 skips, Ruff, the local research runner, graph, both Sentinel ledger loads, and diff checks. It challenged Windows path-component matching, POSIX preservation, similarly named directories, Git Bash priority, and subprocess argument preservation. Its limitation was that native Linux execution was not performed; the new platform tests isolate module references and the host remains Python 3.13.15 versus the workflow's 3.12.

This is Sol's transcription of that independent verdict, not a self-issued audit. The verdict accepts this local bounded result only. Full Phase 9 Sentinel release-packet requirements in Canonical Architecture Sections 255–256 and V0 PRD remain to be proven; no remote merge receipt, field data, or final completion verdict is claimed.

## Finish Contract and learning boundary

This is one real Builder proposal and local execution against a bounded defect. The bounded local result passed independent audit of the exact Forge effect evidence and target commit. It does not supply field data, an external repository trial with remote push authority, a final V0 completion audit, or a proved live self-improvement outcome. No lesson about the first failure's cause is promoted. The diagnostic capture and non-thinking request are candidate execution lessons, subject to later attribution and validation.
