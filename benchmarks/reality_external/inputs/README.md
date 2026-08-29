# Blind input materialization status

This partial fail-closed build commits only blind inputs whose upstream access and redistribution conditions were verified sufficiently for publication.

- RINoBench: local-only until redistribution rights are verified.
- ResearchBench: local-only because current upstream access terms prohibit redistribution of the raw dataset outside the research group.
- LiveIdeaBench v2: **materialized and committed** from the pinned official keyword/classification CSVs: 1,180 full blind items and a 44-item pilot with 2 items per each of 22 domains. Domain labels remain sealed and are not present in inference inputs.
- Axiomatic and ProjectionBench: pending faithful adaptation source construction or authoritative upstream release.

Committed LiveIdeaBench v2 SHA-256:

- `liveideabench_v2_full_blind.jsonl`: `4c96e5fe7355a9075a3ab0c885925f80a68914440de315aaa380e07616652b34`
- `liveideabench_v2_pilot_blind.jsonl`: `a07d8718b6e3b65be654a517fa5ebf0449f2b99b96a172c12e70e9a536184254`

Use `../tools/materialize.py`; never use empty placeholder JSONL files as if a benchmark were complete.
