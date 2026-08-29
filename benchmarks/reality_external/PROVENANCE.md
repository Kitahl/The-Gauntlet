# Upstream Provenance — 2026-08-29

Retrieval date for every entry below: **2026-08-29**.

## Inherited Reality

- Repository: `https://github.com/Kitahl/The-Gauntlet`
- Branch: `upgrade/challenge-vnext-reality`
- Commit: `b4d4e0de4e18096ab6a2853e57318b2bc11de3bb`
- Tree: `a4b1cd67c38b7ea28708ac1ad903a26a91ba731c`
- Pin result: exact match before benchmark branch creation.

## RINoBench

- Official repository: `https://github.com/TimSchopf/RINoBench`
- Repository commit: `d94cd7b3ae8b336cd97e6ae274b3120268dbea82`
- Repository tree: `e7b2d7d215eddbf10fb6bd770a3af02e3833b3ac`
- Official test JSON blob SHA: `9e2c335974047475781a8bc0d57299565d658779`
- Hugging Face dataset: `https://huggingface.co/datasets/TimSchopf/RINoBench`
- Hugging Face revision observed: `a528b08ecaf62b2238d1e6a4ee66aaf245b82cb7`
- Test parquet SHA-256 observed: `fe58f2cc3d3da4bcb0c688a5c35bd45d06137e5912e222de397efb6118a8edd9`
- Reported benchmark size: 1,381 research ideas across train/test.
- License status: no repository license was declared by the pinned GitHub metadata; redistribution rights are therefore **not assumed** by this builder.
- Build disposition: local materializer provided; no RINoBench text copied into this public repository.

## ResearchBench

- Official repository: `https://github.com/ankitala/ResearchBench`
- Repository commit: `03873e075c8f33544adeac37745fdc14f0c16c50`
- Repository tree: `1f276e787b4fbea53edaa634853bf52a51a224a9`
- Full dataset: `https://huggingface.co/datasets/ankilok/ResearchBench`
- Dataset revision observed: `345650c236d4482dcc196ad3dc9165538865e11c`
- License displayed by dataset page: CC BY-NC 4.0.
- Access status: gated.
- Additional access term observed: raw dataset files may not be redistributed, re-hosted, or published outside the research group.
- Official repository data: 12-sample smoke-test subset only; it is not substituted for the full benchmark.
- Build disposition: restricted local-only materialization; no full-data content copied into this public repository.

## LiveIdeaBench v2

- Official repository: `https://github.com/x66ccff/liveideabench`
- Repository commit: `6fc8285269c7679ed427b20864d1f1b127b1a228`
- Repository tree: `2764c31382ff040036b9f848e6fb1b6d1c2374ab`
- Official keyword CSV blob: `13e75dec28065a1595538a8075287bbc7b536800`
- Official keyword classification blob: `2a2f4841e8c8f27d14a7ad91a31a29a3cae91726`
- Official prompt blob: `4285e8c3ef93eaa7e67d91f6c32c4e9de7aec20c`
- Hugging Face dataset: `https://huggingface.co/datasets/6cf/liveideabench-v2`
- Hugging Face revision observed: `163d44a56b4e2a01b4e701dcbe3417dcae7d7562`
- Hugging Face license: Apache-2.0.
- Reported v2 dataset size: about 1.14 GB.
- Pinned classification file exposes 22 domains.
- Official generation prompt exposes the assigned keyword, not the domain.
- Materialization: 1,180 full blind keyword items; 44-item pilot, exactly 2 selected deterministically per each of 22 domains.
- Full blind SHA-256: `4c96e5fe7355a9075a3ab0c885925f80a68914440de315aaa380e07616652b34`.
- Pilot blind SHA-256: `a07d8718b6e3b65be654a517fa5ebf0449f2b99b96a172c12e70e9a536184254`.
- Build disposition: materialized and committed as keyword-only blind inputs; domain mapping remains local/sealed.

## Axiomatic novelty benchmark

- Paper: `arXiv:2604.15145v2`, *An Axiomatic Benchmark for Evaluation of Scientific Novelty Metrics*.
- User-specified revision date: 2026-08-05.
- Public abstract advertises benchmark code as supplementary material.
- Authoritative standalone executable repository: not verified in this build.
- Build disposition: `AXIOMATIC_ADAPTATION_V1` protocol scaffolding only until authoritative code/data is obtained and pinned.

## ProjectionBench

- Paper: `arXiv:2605.30284`, *ProjectionBench: Evaluating Scientific Hypothesis Generation in LLMs Under Progressive Information Disclosure*.
- Public paper reports 45 papers, 15 each in bioactive materials, mechanical materials, and nanomaterials, with progressive L0/L1/L2 disclosure.
- Authoritative executable repository/dataset: not verified in this build.
- Build disposition: `PROJECTIONBENCH_ADAPTATION_V1` protocol scaffolding only until an official release is found or a fresh adaptation is explicitly constructed and pinned.
