# AURA-M1-ISOLATION-005 patch binding regression

Source candidate under repair: `83775200a99914f97bb2ec3f62cc24b76d5efdd9`.

The regression was run against that unchanged source candidate before the
repair. Its disposable repository base was
`5a466acd03d4545b67f0dbeaf403b158889f2cad`, and its candidate was
`0273e76d35ed45d40a2f1495c9853b15c437d902` (tree
`2643f7a253c214a9c435345050516a729ddf8eb3`). Both builder and independent
checks passed with matching check digests and the API returned
`REVIEW_REQUESTED`, but the stored patch omitted the source marker
`AURA_REVIEW_PATCH_MUST_SHOW_THIS`. The failing assertion and exact command are
in `review-patch-base-regression.raw.b64` and
`review-patch-base-regression.command.txt`.

After repair, the same regression passed in the full seven-test sandbox suite.
That successful disposable repository had base
`9a98a60ee01c3ee0026985c5299ddcfc3c6f39d4`, candidate
`b41451e266e008d365f294c5526fe0b4d604c85a`, tree
`2643f7a253c214a9c435345050516a729ddf8eb3`, and independently derived patch
SHA-256 `c78b3b5ad7994c49b99234a84c5de11032a657bad35ad4c5de51542321ff157b`.
The patch contains both authorized paths and the marker; verifier-returned
bytes equal persisted bytes. Candidate, tree, sorted changed paths, and
independent check digest are present in the patch binding. See
`full-sandbox-tests.raw.b64`.

The two check executions still must both succeed and their digests must match.
To make this deterministic across process runtimes, only the `Ran N test(s) in
T seconds` duration line is normalized before hashing. Unnormalized builder and
verifier outputs remain recorded. A unit regression confirms duration-only
changes preserve the digest and a test-result change does not.

No independent security audit has been performed on the repaired candidate.
No detached owner-pinned audit is available; audit status and merge eligibility
remain pending/UNKNOWN.
