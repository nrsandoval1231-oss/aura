# FORGE-LIVE-001 post-call completion evidence

## Applied bounded effect

The validated Builder proposal was applied exactly in the `README.md`
`Credentials` section:

> `BUILDER_MODEL` takes a DeepSeek API model ID such as `deepseek-flash`, not its display name.

No other README section was changed. The ledger and claim files were preserved
unchanged.

## Real call receipt

- Packet: `FORGE-LIVE-001`
- Execution base SHA: `d5fec8d27f89b4ca7f3b410c9045a2865fbdc223`
- Request ID: `REQ-ea808d2831f1459384c26ea800c8f4bd`
- Provider receipt: `CALL-39161fa3`
- Provider/family: `deepseek` / `deepseek`
- Model: `deepseek-flash`
- Capability/role: `coding` / `builder`
- Input tokens: `226`
- Output tokens: `833`
- Schema valid: `true`
- Billing: `UNKNOWN`
- Ledger receipts: `2`
- Ledger head: `eb6b5f5dd1d365176abe425f3d01bf0f345017210dd81574e317e6020d271cd5`

The API key and full prompt are not recorded here.

## Validation

- `python -m forge.cli graph check` — exit 0.
- `python -m forge.cli ledger verify FORGE-LIVE-001` — exit 0; 2 receipts, exact head above.
- `git diff --check` — exit 0.
- README diff is limited to the Credentials section sentence above.

This artifact records execution evidence only. It does not certify the
candidate or authorize merge, push, or deployment. Independent audit remains
required.
