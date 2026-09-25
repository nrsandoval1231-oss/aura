# Canonical Source Lineage

## Imported source

The architecture and PRD were derived from the bounded ChatGPT conversation titled “Build Hermes Agent” and consolidated in the staging workspace:

`C:\Users\nrsan\Documents\Codex\2026-09-18\referenced-chatgpt-conversation-this-is-an-2`

Imported source identities:

- `FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md` — SHA-256 `20057563B902C8C983C13C052F333572EDB08E491FA827052B1F33BCE7645096`, 135459 bytes
- `FORGE_AGENT_V0_PRD.md` — SHA-256 `551C4448B5E48ABAC0D25AA8886FB1324DF708148C1A817DD3112472403C2316`, 7426 bytes

## Governed import normalization

The repository copy normalizes line endings and final newline handling.

Independent review then found four malformed continuation boundaries in the imported architecture. The repository copy applies formatting-only corrections:

1. close the Section 25 tool-call fence before its continuation;
2. remove the duplicated partial Section 63 mission-report block;
3. remove the duplicated partial Section 103 repository-state block;
4. move the Section 181 heading and exclusions outside a malformed fence and combine the exclusion list.

No numbered section, canonical doctrine, requirement, authority boundary, or product decision is added or removed by these corrections.
