# Aura current state

Repository: nrsandoval1231-oss/aura. Canonical branch: main.

Scope: AURA_ARCHITECTURE.md and AURA_PRD.md.
The inherited core and adaptive controller exist and have offline regression coverage.
The M0 CLI records durable bounded requests and refuses builder dispatch. There is no
operational single-builder or two-builder runner. Recovery remains advisory until integrated.
Production role routing and review verification are not configured. Audit trust is
unprovisioned and fails closed. No live Aura performance improvement is claimed.
The owner selected an owner-held, passphrase-protected audit signing key model;
no private key or public-key fingerprint has been provisioned or pinned.
The owner set a $5 ceiling for the first live DeepSeek task; no provider call has
occurred. The current detached verifier still binds Forge's domain and artifact,
so merely adding an audit key cannot validate an Aura candidate.

The graph tracks remaining Aura milestones; no Forge completion status is inherited.
The scope cleanup removes unrelated UI, optional decision services, external product
trial runners, and historical execution records. Source history remains in Git.

The first CLI candidate 53fb0e3 received independent CORRECT for a partial-ledger
loss defect. AURA-M0-CLI-002 is BLOCKED after bounded independent ACCEPT at
581c450; the full gate's slice check still requires owner-pinned detached audit trust.
AURA-M1-EXEC-001 was rejected by independent CORRECT at 84a3d01: an allowed
test could rewrite its own bytes after passing, leaving an untested commit.
AURA-M1-EXEC-002 attempted a bounded repair. Its offline proof cannot grant
production execution authority because candidate tests have host filesystem access.

The exact AURA-M1-EXEC-002 candidate 0acb95d also received independent CORRECT.
The auditor demonstrated repository-local Git fsmonitor running before the
durable intent. The repair budget is exhausted, and both executor candidates
are retained as rejected evidence. AURA-M1-ISOLATION-001 is READY to replan
around a real process sandbox and sterile Git boundary. Ubuntu WSL has a
working Bubblewrap primitive; Docker daemon is unavailable, and Linux pytest
is not yet installed. These observations are feasibility evidence, not a
production runtime claim.

Next: design isolated check and Git effect boundaries, provision trusted review, then connect
one governed task and prove it before two-lane scheduling, stuck recovery, and learning.
