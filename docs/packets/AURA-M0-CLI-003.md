# AURA-M0-CLI-003 evidence boundary

The M0 CLI implementation at `581c450` was independently reviewed, but its
retained AURA-M0-CLI-002 local slice binds an earlier selected-file tree.
Later trust work changed that tree. The old ledger and slice remain immutable.

This packet will create new local evidence for the integrated candidate after
the owner signs the separately reviewed trust checkpoint at `cc3e78f` and its
packet-specific detached check passes. The graph then marks AURA-TRUST-002
COMPLETE before AURA-M0-CLI-003 becomes READY; otherwise the active slice gate
would keep rechecking trust's old selected-file binding against this changed
graph. The
new detached review must cover the entire committed candidate, including M0
CLI and trust code. The local slice's simulated Auditor cannot substitute for
that independent review or owner attestation. No live builder call is part of
this packet.
