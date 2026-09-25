# AURA-M1-ISOLATION-004 — Fresh evidence for restart repair

The prior runner candidate `ecd2cefbf1e374e75b7968bf886774e7c663f5bf`
had simulated slice evidence. The real fresh-process kill regression changed
covered test bytes in `825dba817461a54ccbe0b76d6603635e172075b6`; the
prior slice and append-only ledger remain untouched and are stale by design.
This successor binds the corrected offline code and exact restart evidence to
new packet evidence. The runner remains unwired and returns a review request,
never an approval. The owner-held audit key is still unprovisioned, so the
external detached gate remains UNKNOWN and blocks merge or live dispatch.

See [task packet](../../.agent/tasks/AURA-M1-ISOLATION-004.md) for scope,
budget, acceptance, and exclusions.
