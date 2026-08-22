# Research Website Benchmark — FOIL + Mastermind Report

Date: 2026-08-22

Branch: `website/showcase-r15-research-benchmark`

Research software version: `0.4.0`

Showcase design system: `R14` retained. This pass changes research information architecture, not the visual-system version.

## Input benchmark

Ten public benchmark surfaces were reviewed:

1. Arc Institute
2. Google DeepMind Research
3. Anthropic Research
4. OpenAI Research
5. Our World in Data
6. Ai2
7. Broad Institute
8. Janelia Research Campus
9. scikit-learn GitHub repository
10. PyTorch GitHub repository

Full comparison: `docs/RESEARCH_WEBSITE_BENCHMARK_2026-08-22.md`.

## FOIL diagnosis

### Candidate explanations

- **D1 Visual quality gap** — rejected. R14 already supplies an editorial publication-style visual system and mechanism-native figures.
- **D2 Missing decorative media** — rejected. Research benchmark sites use visuals successfully when the visual is itself a research object; decorative media would weaken The Gauntlet's evidence identity.
- **D3 Research-state discoverability gap** — supported. The current question, artifact classes, evidence chain, and next planned studies existed but required repository traversal.
- **D4 Missing search/filter UI** — not yet supported. The canonical output corpus is too small for client-side filtering to be load-bearing.
- **D5 Missing publication list** — scope split. The project does not yet have a canonical paper/preprint and must not rename software/research artifacts as publications.

### FOIL resolution

**Supported defect:** research-state discoverability and representation.

**Smallest useful complement:** add a bounded Research Dossier that indexes the real artifacts and states without changing their evidence level.

## Mastermind loop 1 — Put the research question before the machinery

**Observed defect:** R14 opens with a strong project identity and architecture, but the canonical behavioral research question lives one click away in `RESEARCH.md`.

**Mechanism:** expose a concise, source-faithful statement of the current research question immediately after the hero, together with the explicit boundary that a positive full behavioral answer is not established.

**Negative control:** do not convert the question into a claim of effectiveness.

**Result:** Research Dossier added with direct link to `RESEARCH.md`.

## Mastermind loop 2 — Index research objects by type and state

**Observed defect:** question, architecture, FOIL basis, mechanical validation, specification coverage, benchmark pilots, roadmap, and reproduction material were individually strong but spread across separate page chapters and repository paths.

**Mechanism:** add a static Research Output Index with stable fields:

- research object;
- type;
- current state;
- canonical source.

**Negative control:** do not call internal reports “papers,” “publications,” or peer-reviewed findings.

**Result:** eight canonical research objects are indexed from open question through external reproduction.

## Mastermind loop 3 — Show the next evidence program

**Observed defect:** `ROADMAP.md` already prioritizes evidence value, but the homepage did not make R2–R4 visibly central to the scientific state.

**Mechanism:** expose the next evidence program directly: matched-budget behavioral harness, prospective FOIL adaptation study with delayed assistance-free transfer, and mechanism-level routing/review ablations. Keep release tags/DOI and external reproduction as distinct obligations.

**Negative control:** planned studies remain planned; no future work is displayed as completed.

**Result:** roadmap strip added to the Research Dossier.

## Mastermind admission gates

- **A — Causal adequacy: PASS.** The changes directly reduce the number of repository traversals needed to reconstruct current scientific state.
- **B — Identifier independence: PASS.** No benchmark-site branding, CSS, imagery, or names are copied into the product.
- **C — Representation transformation: PASS.** Existing artifacts are represented as a dossier/index; their evidence levels are unchanged.
- **D — Negative control: PASS.** No stock science imagery, invented metrics, fake publication badges, gradients, or decorative research dashboards.
- **E — Cross-domain transfer: PASS.** The research-object/index pattern appears across AI labs, biomedical institutes, open-science catalogs, data research, and mature research software.
- **F — Existing-mechanism compression: PASS.** Existing R14 HTML/CSS components are reused; no JavaScript, search library, or framework is added.
- **G — Ablation: PASS.** Removing the dossier leaves every underlying source artifact intact; the dossier improves retrieval and state compression only.
- **H — Regression: PENDING exact-head CI.** Existing showcase validator, browser checks, payload budget, provenance checks, overclaim boundary, Research Orchestrator/Process Assurance validation, unit tests, and CodeQL remain authoritative.

## Claim boundaries

This pass does **not** establish:

- complete-system behavioral efficacy;
- independent reproduction;
- peer review;
- a DOI;
- a stable evidence-bearing release tag;
- superiority over any benchmark research website;
- formal FAIR4RS, SOC 2, ISO, or accessibility certification.

## Release rule

Do not merge until the exact final PR head passes the existing Research software validation and CodeQL workflows. If the existing R14 validator detects overflow, missing sources, broken links, payload growth, visual failure, accessibility regression, or overclaim, fix the candidate rather than weakening the gate.
