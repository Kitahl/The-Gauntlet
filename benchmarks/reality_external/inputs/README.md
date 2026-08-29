# Blind input materialization status

No benchmark payload is committed by this partial fail-closed build.

- RINoBench: local-only until redistribution rights are verified.
- ResearchBench: local-only because current upstream access terms prohibit redistribution of the raw dataset outside the research group.
- LiveIdeaBench v2: may be materialized from the pinned official keyword/classification CSVs; commit only after deterministic count/hash validation.
- Axiomatic and ProjectionBench: pending faithful adaptation source construction or authoritative upstream release.

Use `../tools/materialize.py`; never use empty placeholder JSONL files as if a benchmark were complete.
