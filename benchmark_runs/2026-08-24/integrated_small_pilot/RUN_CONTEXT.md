# FOIL v5 integrated small pilot run context

- Date: 2026-08-24
- Implementation/protocol freeze:
  `82cb73d2af2ed50ab8e7f893bbf8bbde2bf4c4e3`
- Python: `3.12.10`
- Protocol SHA-256:
  `4e2699477e8893757bd6524cc90df71b5455135b80e027331da0e48cb82b3849`
- Report SHA-256:
  `df30671e506d5e7f352cd4cd42cced2fd1683827ce3ba732fa2f17efb66dcf53`
- Exit code: `0`

Command:

```powershell
python benchmarks/harness/foil_v5_integrated_small_pilot.py `
  --output benchmark_runs/2026-08-24/integrated_small_pilot/report.json
```

The working tree contained only the already-existing untracked graph-output
directories when the implementation/protocol freeze was committed. The result
is synthetic integration evidence and does not advance an empirical gate.
