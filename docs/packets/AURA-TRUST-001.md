# AURA-TRUST-001 implementation boundary

Owner approval pins the SHA-256 fingerprint of the exact external public PEM:
`55faf401c993f16fd0a9d4f0e9d58babd61ccb018f6bd6cb2a9c7087505de1c1`.
The signing key is encrypted and held by the owner outside Aura and Codex
workspaces. The owner types the passphrase only into their own terminal when
signing a reviewed exact candidate. Agents and builder adapters have no signing
authority.

Aura's reviewer evidence and the owner's signature have separate roles. An
independent reviewer must inspect the exact candidate and return a verdict;
the owner signature attests to that review record. It cannot turn a failed
validation gate into a pass. The verifier must bind the receipt to the complete
committed tree and an Aura-specific validation artifact, and reject missing or
changed evidence. Forge compatibility remains intact.

The first live builder task, M1 restart proof, and two-builder scheduling are
separate packets. A verified public key alone does not authorize any provider
call, merge, or live review claim. Prior receipts and stale slice evidence remain
unchanged.
