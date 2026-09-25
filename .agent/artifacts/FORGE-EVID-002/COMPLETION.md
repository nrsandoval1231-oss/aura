# FORGE-EVID-002 implementation handoff

This candidate adds truthful reconciliation verification on a new
`FORGE-EVID-002` ledger stream and detached audit verification. The rejected
`FORGE-EVID-001` stream remains untouched. Reconciliation records derive their
legacy evidence class from canonical paths and reject missing, partial,
duplicated, extra, truncated, or mismatched records.

Detached audit acceptance requires an externally supplied JSON receipt, detached
OpenSSL signature, and public trust anchor. The receipt binds the repository
identity, exact HEAD, candidate digest and tree, manifest, validation digest,
verdict, auditor identity, and signature domain. Missing or in-repository trust
material fails closed. No independent audit is present in this candidate, so
the repository validation gate is expected to remain red until Sol supplies one.

Validation evidence is recorded by Sol after the exact candidate is audited.
