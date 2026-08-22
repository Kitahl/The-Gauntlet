# Reproducibility

This repository distinguishes **mechanical/specification reproducibility** from **behavioral research reproducibility**.

## 1. Mechanical validation

From a clean checkout of the release under test:

```bash
python validation/validate_soul_gauntlet_public.py
python validation/validate_showcase.py
python -m compileall -q validation
```

The browser validator requires Python Playwright plus Chromium. CI installs those dependencies before execution.

Expected interpretation:

- a pass means the checked repository/package/showcase invariants passed;
- it does not prove model behavior, research efficacy, or downstream scientific validity.

## 2. FOIL specification evidence

Inspect:

- `validation/FOIL_RESEARCH_INTEGRATION_VALIDATION.json`
- `validation/FOIL_RESEARCH_INTEGRATION_BEHAVIORAL_CONTRACT_VALIDATION.json`
- `validation/FOIL_RESEARCH_INTEGRATION_3_LOOP_REPORT.md`
- `research/FOIL_RESEARCH_BASIS.md`

`PASS-SPEC` means the specification contains the required decision behavior. It is not a behavioral execution result.

## 3. Public-release assurance

Inspect `validation/SOUL_GAUNTLET_PUBLIC_AUDIT.md` for the public portability audit and the explicit boundary around missing/private runtime dependencies.

## 4. Behavioral experiments

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
- machine-readable environment/dependency lock;
- commit SHA and release version.

## 5. Archival releases

Evidence-bearing stable releases should be tagged and archived. A DOI should be added to `CITATION.cff` after an archival service such as Zenodo has minted one for the corresponding release.

## 6. Reproduction report

Independent reproducers are encouraged to report:

- repository version/commit;
- environment;
- command executed;
- observed result;
- expected result/source;
- any divergence;
- whether the divergence affects a stated research claim.

Use the reproduction issue form when available.
