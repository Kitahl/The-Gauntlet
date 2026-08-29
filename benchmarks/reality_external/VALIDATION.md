# Reality External Benchmark Validation — 2026-08-29

Status: `PARTIAL_FAIL_CLOSED`.

No BASELINE or REALITY inference was run. No real prediction was generated or scored.

## Inherited pin

```text
EXPECTED_HEAD=b4d4e0de4e18096ab6a2853e57318b2bc11de3bb
OBSERVED_HEAD=b4d4e0de4e18096ab6a2853e57318b2bc11de3bb
EXPECTED_TREE=a4b1cd67c38b7ea28708ac1ad903a26a91ba731c
OBSERVED_TREE=a4b1cd67c38b7ea28708ac1ad903a26a91ba731c
PIN=PASS
```

## Synthetic tests

Command:

```text
python -m unittest discover -s benchmarks/reality_external/tests -v
```

Output:

```text
test_liveidea_hides_domain_and_balances (test_materialize.MaterializeTests.test_liveidea_hides_domain_and_balances) ... ok
test_rinobench_hides_gold (test_materialize.MaterializeTests.test_rinobench_hides_gold) ... ok
test_axiomatic_tie_is_failure (test_scoring.ScoringTests.test_axiomatic_tie_is_failure) ... ok
test_liveidea_five_dimensions (test_scoring.ScoringTests.test_liveidea_five_dimensions) ... ok
test_projection_auc (test_scoring.ScoringTests.test_projection_auc) ... ok
test_researchbench_aggregation (test_scoring.ScoringTests.test_researchbench_aggregation) ... ok
test_rinobench_metrics (test_scoring.ScoringTests.test_rinobench_metrics) ... ok
test_seal_round_trip (test_scoring.ScoringTests.test_seal_round_trip) ... ok

----------------------------------------------------------------------
Ran 8 tests in 3.140s

OK
```

## Schema / compilation / leakage validation

```text
SCHEMAS_VALID=5
LEAKAGE_AUDIT=PASS
FILES_SCANNED=39
PYTHON_COMPILE=PASS
```

## LiveIdeaBench v2 materialization

Pinned official input Git blobs were reconstructed byte-for-byte before materialization:

```text
KEYWORD_CSV_GIT_BLOB=13e75dec28065a1595538a8075287bbc7b536800
CLASSIFICATION_CSV_GIT_BLOB=2a2f4841e8c8f27d14a7ad91a31a29a3cae91726
SOURCE_BLOB_IDENTITY=PASS
```

Materialization output:

```text
LIVEIDEABENCH_FULL=1180
LIVEIDEABENCH_UNIQUE_OPAQUE_IDS=1180
LIVEIDEABENCH_DOMAINS=22
LIVEIDEABENCH_PILOT=44
LIVEIDEABENCH_PILOT_PER_DOMAIN=2
DETERMINISTIC_REBUILD=PASS
```

Committed blind input hashes:

```text
4c96e5fe7355a9075a3ab0c885925f80a68914440de315aaa380e07616652b34  liveideabench_v2_full_blind.jsonl
a07d8718b6e3b65be654a517fa5ebf0449f2b99b96a172c12e70e9a536184254  liveideabench_v2_pilot_blind.jsonl
```

Remote Git blob identity check:

```text
LOCAL_FULL_GIT_BLOB=fc98ef3d894e6c3eb55ede817941843a8de77c49
REMOTE_FULL_GIT_BLOB=fc98ef3d894e6c3eb55ede817941843a8de77c49
FULL_REMOTE_IDENTITY=PASS
LOCAL_PILOT_GIT_BLOB=c9c759f374ef1199369127f077408cbf8185a4b2
REMOTE_PILOT_GIT_BLOB=c9c759f374ef1199369127f077408cbf8185a4b2
PILOT_REMOTE_IDENTITY=PASS
```

Deterministic 10-item manual spot check of committed-format blind rows:

```text
MANUAL_SPOT_CHECK=PASS
SPOT_CHECK_COUNT=10
libv2_c837220a82968ea7e708ef9b  astrobiology  PASS
libv2_7947b14c0f8d5b2b5aecb2ef  stellarators  PASS
libv2_f538026cfe4e3b65b520bf03  rock cycle  PASS
libv2_22abfdbb7d7e861a135d7287  science diplomacy  PASS
libv2_da962eb6139975b0fc44c2c8  origin of life  PASS
libv2_088ea47a1fce8574ea796f27  life cycle analysis  PASS
libv2_c7c8fc29829ccc47377ce94a  graphene  PASS
libv2_2308e68a84d0106f67146620  reynolds number  PASS
libv2_f06d94a1f51b5b68dfa24560  molecular genetics  PASS
libv2_d54f9cd5541752190ff6b800  complex analysis  PASS
```

Each checked blind row contained exactly `sample_id` and `keyword`; no domain or evaluation metadata was present.

Local-only partial LiveIdea gold was deterministic across a same-key rebuild:

```text
LOCAL_PARTIAL_LIVEIDEA_GOLD_SHA256=ef66cd264b9eb8b14462b63d6c33fb7c8a70fbf0c15b50106cfc7459db214dcf
LIVEIDEA_LOCAL_GOLD_REBUILD=PASS
```

This is **not** the complete suite gold commitment and is intentionally not committed as `gold_plaintext.sha256`.

## Gold sealing state

```text
COMPLETE_GOLD_MATERIALIZED=NO
GOLD_CIPHERTEXT_COMMITTED=NO
GOLD_KEY_GENERATED=NO
GOLD_KEY_PATH=/mnt/data/REALITY_BENCHMARK_GOLD_KEY.txt
GOLD_KEY_PATH_EXISTS=NO
LOCAL_ID_KEY_PATH=/mnt/data/REALITY_BENCHMARK_ID_KEY.txt
LOCAL_ID_KEY_PATH_EXISTS=YES
READABLE_GOLD_IN_GIT=NO
KEY_IN_GIT=NO
```

The AES-256-GCM sealing implementation itself passed its synthetic decrypt-and-hash round-trip test. Complete-suite sealing was not run because complete canonical gold does not yet exist.

## Blocked / not-applicable gates

- RINoBench: public benchmark data identified and pinned, but this builder does not assume redistribution rights without a declared upstream repository license; public derived text was therefore not committed.
- ResearchBench full data: gated and subject to terms prohibiting redistribution/re-hosting/publishing raw data outside the research group; no restricted content was committed.
- Axiomatic benchmark: authoritative standalone executable code/data was not verified in this build; only `AXIOMATIC_ADAPTATION_V1` scaffolding is present.
- ProjectionBench: authoritative executable release was not verified in this build; only `PROJECTIONBENCH_ADAPTATION_V1` scaffolding is present.
- Complete plaintext gold hash / ciphertext hash / encryption round-trip: not applicable until the complete legally usable suite gold exists. Placeholder commitments are forbidden.

## Scope audit

All changes from the inherited Reality pin are under `benchmarks/reality_external/`. Production Reality/Space/Soul/FOIL/Power/Time/Mind code was not modified. PR #59 was not modified and main was not merged.
