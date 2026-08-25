# FOIL R1.5 run context

- Branch: `codex/foil-v5-full-system`
- Runtime base: `4ca0e72c5cdc5fd852fe680efeeeef561aea3e84`
- Preregistration/harness commit:
  `951e04b1ddba4eb9e2d3cd61a6c5dd6e519bf129`
- Protocol SHA-256:
  `9bfcb65b92ff42d515643ebafa16a2a26c5f07f7e278f53f398e4d908b026058`
- Python: `3.12.10`
- Model/provider calls: `0`
- External bots: `0`
- Token spend: `0`
- Fixed public source downloads: `2`
- Report SHA-256:
  `f392ea7b69cd2b814d3e4c54c3b1d9619494d51b64ab16e826eca1b8f4f3f260`

The protocol and harness were committed before the source archives were fetched
or benchmark gold was reconstructed. The run was executed once with:

```powershell
python benchmarks/harness/foil_r15_natural_miss_pilot.py `
  --allow-source-network `
  --protocol-commit 951e04b1ddba4eb9e2d3cd61a6c5dd6e519bf129 `
  --output benchmark_runs/2026-08-24/r15_natural_miss_pilot/report.json
```

The historical positive control reproduced 27/36 and nine misses. The primary
R1.5 association result is `NOT_IDENTIFIABLE`; the oracle-bound RC4 replay is a
separate executable-route smoke result and is non-promoting.
