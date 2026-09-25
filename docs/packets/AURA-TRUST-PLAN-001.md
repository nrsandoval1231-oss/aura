# Aura detached review trust bootstrap proposal

The owner selected an **owner-held, passphrase-protected** audit signing key.
No key, passphrase or public-key fingerprint has been supplied. This document
does not pin a signer or authorize a production audit.

## Exact current gap

`src/forge/audit_receipts.py` verifies the domain
`forge-agent.detached-audit.v1` and the validation artifact
`.agent/artifacts/FORGE-INTEGRATED-001/VALIDATION.json`. Its repository digest
is also Forge-specific. The committed `.agent/audit-trust.json` has empty
`auditor_id` and `public_key_sha256`. Filling those fields cannot verify an
Aura candidate. `scripts/run_slice.py` still requires detached exact-candidate
audit evidence; an offline simulated `MERGE_ELIGIBLE` result is not approval.

## Recommended owner custody

1. The owner generates an encrypted RSA-3072 private key in a location outside
   all Aura and Codex workspaces, preferably on a separate owner-controlled
   device or removable encrypted storage. The owner keeps the passphrase; no
   builder, controller, provider adapter or agent receives either secret.
2. The owner exports only the public key and checks the SHA-256 hash of its
   exact PEM bytes through a separate owner-controlled channel. The owner
   explicitly approves that fingerprint and an attestor identity for a
   protected trust record. A path, filename, or agent claim is insufficient.
3. Astra independently reviews the exact candidate with fresh context and
   produces a raw verdict. After reading that verdict, validation outputs,
   candidate commit/tree and complete manifest, the owner signs a detached
   receipt with the private key. Owner signature attests to the review record;
   it does not replace Astra's independent review or make a failed gate pass.
4. The private key never enters the repository, worktree, ledger, process
   environment, command arguments, PR, or a Codex tool call. The public key
   and detached signature are supplied from outside the candidate worktree.
   If any of these steps is missing, the verifier returns UNKNOWN or reject.

## Proposed protected migration packet

Create `AURA-TRUST-001` only after the owner has independently approved an
exact public-key fingerprint. It may change the protected audit verifier,
the trust record, its tests, the slice verification binding, and a new Aura
validation artifact. Keep it separate from executor/provider work. The new
receipt schema must bind:

- Aura-specific domain and repository identity derived from the configured
  remote, packet ID, exact base and candidate commit/tree, complete committed
  manifest, and candidate digest;
- required local gate names, exit codes and validation artifact digest;
- distinct `reviewer_id` (Astra verdict) and `attestor_id` (owner-held signer),
  exact public-key fingerprint, and detached signature bytes outside the
  candidate tree.

Fail-closed tests must reject a missing or unapproved key, caller-supplied
inline key, missing reviewer record, owner attestation without independent
review, same identity where prohibited, wrong domain/repository/base/packet,
changed commit/tree/blob/check set, absent or altered validation artifact,
signature mismatch, inline signature, dirty checkout, and restart with an
ambiguous receipt. A good test key may be ephemeral **only in tests**. It may
never become the production trust anchor. The existing Forge verifier and
`forge` compatibility remain intact.

## Activation boundary

The trust migration requires a dedicated protected governance packet,
independent exact-candidate audit, owner fingerprint approval, and a fresh
validation run against the resulting candidate. PR #1 remains an unreviewed
draft proposed specification. PR #2 remains an M0 CLI draft with a mandatory
red slice gate. No merge follows from this plan alone.
