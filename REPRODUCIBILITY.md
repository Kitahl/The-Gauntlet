# Reproducibility

This repository distinguishes **mechanical/specification reproducibility** from **behavioral research reproducibility**.

## 1. Mechanical validation

From a clean checkout of the release under test:

```bash
python -m pip install -r requirements-dev.txt -r requirements-runtime.txt
python -m playwright install chromium
ruff check validation tools tests benchmarks/harness
python -m unittest discover -s tests -v
python validation/validate_soul_gauntlet_public.py
python validation/validate_showcase.py
python -m compileall -q validation tools tests benchmarks/harness
```

The browser validator requires Python Playwright plus Chromium. CI installs those dependencies before execution.

Expected interpretation:

- a pass means the checked repository/package/showcase invariants passed;
- it does not prove model behavior, research efficacy, or downstream scientific validity.

## 2. Security and portability gates

Release candidates also run:

- CodeQL Python analysis;
- a full-history Gitleaks scan from `fetch-depth: 0`;
- `pip-audit` over runtime and development requirement sets;
- the full unit-test suite on Linux, Windows, and macOS;
- regression checks that no Mastermind runtime/package/skill/control path is tracked in this repository.

GitHub Actions are pinned to immutable full commit SHAs. Dependabot remains responsible for proposing pinned-action and Python dependency updates.

A passing security scan means the configured scanners found no matching issue in the exact scanned state. It is not a proof that no undiscoverable vulnerability or secret exists.

## 3. FOIL specification evidence

Inspect:

- `validation/FOIL_RESEARCH_INTEGRATION_VALIDATION.json`
- `validation/FOIL_RESEARCH_INTEGRATION_BEHAVIORAL_CONTRACT_VALIDATION.json`
- `validation/FOIL_RESEARCH_INTEGRATION_3_LOOP_REPORT.md`
- `research/FOIL_RESEARCH_BASIS.md`

`PASS-SPEC` means the specification contains the required decision behavior. It is not a behavioral execution result.

## 4. Public-release assurance

Inspect `validation/SOUL_GAUNTLET_PUBLIC_AUDIT.md` for the public portability audit and the explicit boundary around missing/private runtime dependencies. Runtime and profile privacy behavior is documented in `docs/RUNTIME_SETUP.md` and `SECURITY.md`.

The tracked repository can define release requirements, but GitHub server-side enforcement still depends on repository settings. `docs/REPOSITORY_SETTINGS.md` lists the required branch/ruleset, secret-scanning, push-protection, and release settings.

## 5. Behavioral experiments

No repository-wide claim of improved human research performance is currently made. When behavioral experiments are added, each evidence-bearing experiment should include:

- frozen hypothesis and endpoint definitions;
- dataset/item provenance and version;
- participant/model/environment description as applicable;
- baseline and ablation definitions;
- random seeds and stochastic settings;
- exact commands or executable notebook/script;
- raw or minimally processed results;
- analysis script;
- uncertainty/statistical procedure;
- negative and failed runs where material;
- machine-readable environment/dependency identity;
- commit SHA and release version.

## 6. Archival releases

Evidence-bearing stable releases should be tagged and archived only after the **exact candidate SHA** has passed validation, CodeQL, security, and portability gates. A DOI should be added to `CITATION.cff` after an archival service such as Zenodo has minted one for the corresponding release.

## 7. Reproduction report

Independent reproducers are encouraged to report:

- repository version/commit;
- environment;
- command executed;
- observed result;
- expected result/source;
- any divergence;
- whether the divergence affects a stated research claim.

Use the reproduction issue form when available.
