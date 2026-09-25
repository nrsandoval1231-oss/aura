# Aura

Nick Sandoval's autonomous engineering agent, built on the Forge foundation.

**Start here:** [Engineering handoff](docs/AURA_HANDOFF.md)

## Architecture
Sol leads engineering; DeepSeek V4.1 Flash and Luna 6 are the intended parallel builders; MiniMax handles utility work; Astra independently audits; a deterministic Governor controls authority and integration. Exact provider IDs remain to be verified.

The imported implementation includes stuck recovery and shared, reviewed per-slice learning using an Athena-derived engineering comparison adapter. Live two-builder execution and production review verification still require integration.

## Status
This repository contains the complete Forge source snapshot at `3fcbb2ee6e5f7fd1d6c0c8c19adc1a9f34b86508`, including the controller from Forge draft PR #16. Source implementation evidence: 116 focused tests and independent bounded review passed. Full Aura repository validation is **UNKNOWN** until run.

Inherited governance and evidence files describe Forge's historical state. They do not certify Aura or authorize live execution. See the handoff for migration and integration work.

## Development
Existing package and CLI names remain `forge`.

```bash
pip install -e ".[dev]"
./scripts/validate.sh
```

- [Adaptive engineering design](docs/integration/parallel-adaptive-engineering.md)
- [Original Forge README](docs/source/forge-readme.md)
- [Canonical architecture](FORGE_AGENT_CANONICAL_ARCHITECTURE_V1.md)
- [Repository instructions](AGENTS.md)
