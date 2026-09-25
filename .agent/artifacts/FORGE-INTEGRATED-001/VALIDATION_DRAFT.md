# FORGE-INTEGRATED-001 validation artifact format

The committed `VALIDATION.json` records the deterministic pre-audit gates.
Its schema contains only:

```json
{
  "schema_version": 1,
  "pre_audit_gates": {
    "python floor": 0,
    "import surface": 0,
    "lint": 0,
    "format": 0,
    "tests": 0,
    "doc/graph": 0,
    "ledger <every current .agent/ledger/*.jsonl stream>": 0,
    "self-improvement": 0,
    "governed evolution": 0
  },
  "slice_gate": "PENDING_SIGNATURE"
}
```

The independent detached receipt signs the SHA-256 digest of that committed
file, the complete tracked-file manifest, the exact HEAD, and `HEAD^{tree}`.
The receipt, signature, and auditor public key stay outside the repository.
