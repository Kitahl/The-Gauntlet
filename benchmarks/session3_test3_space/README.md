# Session 3 / Test 3 — Space vs BASE

Fresh-session benchmark package for the frozen Research Discovery (`Space`) skill.

The generated package contains 40 unique web-research tasks:

- 20 FreshQA tasks
- 20 AssistantBench validation tasks
- 20 predictions assigned to BASE (10 + 10)
- 20 predictions assigned to SPACE (10 + 10)

Gold/reference data is generated into `gold/SEALED_UNTIL_BOTH_ARMS_COMMIT/` and must not be accessed by the inference session until both condition receipts are committed.

The package is deterministically generated with seed `2026082503` from pinned/public sources. The generated `MANIFEST.json` records source snapshots and SHA-256 hashes.
