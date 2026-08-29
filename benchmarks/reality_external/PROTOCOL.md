# Reality External Benchmark Protocol v1

## Scope

This branch is benchmark assets only. It MUST NOT modify Reality, Space, Soul, FOIL, Power, Time, or Mind production code. It MUST NOT run either inference arm during Gold Builder construction.

## Arms

Every prediction contract permits exactly two inference arms:

- `BASELINE`
- `REALITY`

Gold/reveal data is inaccessible to both arms until scoring.

## Seed and opaque IDs

Selection seed: `REALITY-EXT-BENCH-V1-2026-08-29`.

Opaque IDs are HMAC-SHA-256 identifiers. The HMAC key is generated locally and MUST NOT be committed. Selection order uses SHA-256 over the public seed, benchmark namespace, and source identifier, so pilot membership is deterministic for a pinned source revision while opaque IDs remain non-reversible without the local key.

## Benchmark-specific blinding

### RINoBench

Blind payload keeps only the research idea and benchmark-supplied related works. Gold novelty score, novelty reasoning, prior model outputs, and lookup-friendly original indices are withheld. The pilot targets 100 items, 20 per gold label 1–5 when the pinned test split has sufficient items.

### ResearchBench — Hypothesis Composition

Blind payload keeps the research question and task-authorized inspiration/context fields. Gold hypothesis, fine-grained answer fields, target-paper results, evaluator outputs, DOI, and other answer-bearing fields remain sealed. Pilot selection is balanced across disciplines as evenly as possible.

Because the full dataset is gated and redistribution-restricted, all materialized ResearchBench payloads are local-only unless upstream permission changes.

### LiveIdeaBench v2

Blind payload contains only opaque sample ID and keyword. Domain is sealed because the official generation prompt is keyword-only. Full index uses every pinned keyword. Pilot selection takes two deterministic items from each pinned domain; the pinned classification table exposes 22 domains, yielding 44 items when every domain has at least two keywords.

### AXIOMATIC_ADAPTATION_V1

Until authoritative executable code/data is verified, this package does not claim an official reproduction. Adaptation inputs must use opaque pool IDs and hide condition names, expected directions, probe family, and focal-paper/task mapping. Gold is the expected monotonic ordering under R/V/T manipulations, not a human novelty score.

### PROJECTIONBENCH_ADAPTATION_V1

Until an authoritative release is verified, this package does not claim an official reproduction. A valid adaptation must use recent open-access papers under the published contamination logic and expose only L0/L1/L2 disclosure fields. Titles/DOIs, results/conclusions, extracted result claims, and downstream evaluation stay sealed whenever they create lookup risk.

## Canonical gold

Gold files are canonical UTF-8 JSON/JSONL with LF newlines and a final newline. `tools/seal_gold.py` canonicalizes a local gold directory into sorted-key JSON, hashes the plaintext bytes, encrypts using AES-256-GCM with a fresh random key and nonce, immediately decrypts, verifies the plaintext SHA-256, and only then writes ciphertext/hash commitments. The key file is local-only and mode 0600 where supported.

## Scoring boundary

Scoring scripts operate only after predictions are complete and gold is revealed to the scoring process. Gold Builder tests use synthetic fixtures only. Scripts that depend on an external judge label their outputs as compatible/adapted rather than official when the exact official judge pipeline is unavailable.

## Leakage audit

Before any commit containing blind data:

- scan for known gold fields and answer-bearing identifiers;
- confirm no ID key or encryption key appears;
- confirm ResearchBench restricted content is absent from public Git;
- confirm no readable gold fragments are present;
- spot-check at least 10 records per materialized benchmark;
- hash each committed blind input.

## Completion rule

`COMPLETE` is forbidden unless all five benchmark packages are materialized under their verified rights/access conditions, schemas validate, counts match the manifest, deterministic selection is reproducible, sealing round-trip passes, scoring fixtures pass, and the committed tree contains no readable gold or key.
