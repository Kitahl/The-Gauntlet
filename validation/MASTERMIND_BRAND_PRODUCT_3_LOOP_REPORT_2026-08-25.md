# Mastermind Brand & Product Architecture — Three-Loop Report

**Date:** 2026-08-25  
**Scope:** company identity, first-product architecture, public module naming, and pre-product positioning for the repository currently named `The-Gauntlet`  
**Decision class:** working pre-product identity, not legal clearance

## Decision

**Working company brand:** **Rigilum**  
**First product:** **Instrument 01**  
**Release frame:** **free pre-product preview**

The decision intentionally separates company identity from product identity. The company name should remain useful if later products have nothing to do with this repository; the product name should be able to describe a coherent suite without becoming the company itself.

`Sigma Scientific Systems` remains a discarded continuity candidate, not the working winner. `S3` is rejected as a product/company shorthand because Amazon S3 already dominates that identifier in software infrastructure and because Sigma has material adjacent-name crowding in Canadian software.

This report does **not** establish trademark availability, corporate-name availability, domain availability, or freedom to operate. Those are separate release gates.

---

## Loop 1 — Continuity architecture

### Question

If the existing idea **Sigma Scientific Systems** is retained, what is the strongest company/product structure that does not collapse the company and product into one name?

### Work performed

This loop did not generate a large clean-slate name list. It treated Sigma as a fixed continuity candidate and focused on architecture:

1. separate the durable company identity from the first software product;
2. reject `S3` as the main public identifier;
3. determine whether the ten modules should remain individually themed or become a coordinated product family;
4. preserve technical IDs so branding does not become a breaking runtime migration.

### Strongest continuity configuration

- **Company:** Sigma Scientific Systems
- **Product:** Instrument 01
- **Product modules:** functional names
- **Technical namespace:** unchanged

### What survived

The **company → product → modules** hierarchy survived all later loops. The idea of calling both the company and product `S3` did not.

### What failed

The continuity company name has real adjacent-name risk in the target market. Canadian records show a live `SIGMA SYSTEMS` software mark now owned by Hansen Technologies Canada, and a live `SIGMA SOFTWARE & DESIGN` registration owned by Sigma Software Canada. This does not by itself decide legal confusion, but it materially weakens distinctiveness for a Canadian software company.

Sources:

- Canadian Intellectual Property Office, `SIGMA SYSTEMS`, application 1847333: https://ised-isde.canada.ca/cipo/trademark-search/pdf/1847333?lang=eng
- Canadian Intellectual Property Office, `SIGMA SOFTWARE & DESIGN`, application 2103698: https://ised-isde.canada.ca/cipo/trademark-search/pdf/2103698?lang=eng
- Investment Canada record describing Sigma Systems Canada LP as a software business: https://ised-isde.canada.ca/site/investment-canada-act/en/search/decisions-and-notification-index/h?page=6&wbdisable=true

**Loop 1 disposition:** keep the product hierarchy; do not default to Sigma.

---

## Loop 2 — Clean-slate collision search

### Question

If Sigma is not privileged, what company identity best fits a scientific/research-software publisher while remaining short, expandable, and comparatively distinctive?

### Work performed

This loop branched away from Loop 1. It generated candidate naming families, then used current web/company/software searches as a kill screen. A name was not retained merely because its etymology or sound was attractive.

Examples rejected during the screen included names such as **Acriter**, **Ordinant**, **Veritum**, and **Nexmora** after active technology/software uses surfaced. Additional generic families around *proof*, *evidence*, *foundry*, *axiom*, and *research* were deprioritized because the adjacent research-tool market is already crowded with those constructions.

### Working survivor

**Rigilum**

Why it survived the screen:

- one token;
- pronounceable and visually compact;
- not tied to one discipline, model class, or current product;
- has a technical/structural feel without making a scientific claim;
- the current exact-name screen did not surface an operating science/software company by that name;
- can own a family such as `Rigilum Instrument 01`, later instruments, hosted systems, or research programs without renaming the company.

The word has historical/lexical matches; that is not the same as corporate or trademark clearance. Absence from this search screen is **not** evidence of legal availability.

### Product naming branch

The loop also rejected turning every module into another fanciful sub-brand. The first product should be legible in under a minute. The functional public names therefore became:

| Product name | Stable technical identity |
|---|---|
| Route | `soul` / `/soul` |
| Prove | `mathbot` / `/mind` |
| Discover | `scoutbot` / `/space` |
| Synthesize | `novelbot` / `/reality` |
| Verify | `codebot` / `/power` |
| Measure | `benchbot` / `/time` |
| Assure | `infinity-gauntlet` / `/gauntlet` |
| Preflight | `meditate` |
| Review | `council-of-elders` / `/council` |
| Adapt | `foil` / `/foil` |

**Loop 2 disposition:** advance Rigilum + Instrument 01; preserve technical compatibility.

---

## Loop 3 — External comparator analysis

### Question

Do the Loop 1 and Loop 2 architectures resemble durable naming patterns among major science/research companies, and which candidate better fits those patterns without copying them?

### Comparator

The concrete comparator is the **Nature Index 2026 Research Leaders: Leading corporate institutions**, based on Nature Index data from 1 January through 31 December 2025.

Source: https://www.nature.com/nature-index/research-leaders/2026/institution/corporate/all/global

Nature Index is used here only as a reproducible cohort of 100 research-active companies. Nature explicitly cautions that its publication-based metric covers a limited journal set and is not a comprehensive assessment of institutional quality. This audit uses the list for **name/product architecture comparison**, not research-performance ranking.

### Cohort observations

A simple token count over the displayed 100 institutional names gives:

- **52 / 100** use a one-token institutional brand;
- **72 / 100** use at most two tokens;
- median displayed name length is **1 token**;
- `Scientific` appears as part of only one displayed company name in the cohort: **Thermo Fisher Scientific**.

The cohort contains short durable company brands including Roche, AstraZeneca, Alphabet, IBM, Pfizer, Lilly, Novartis, Microsoft, Amazon, Meta, Intel, Huawei, Sony, NVIDIA, Thales, Bosch, Siemens, Hitachi, Quantinuum, and Xanadu.

The comparator therefore does **not** support a rule that science companies should literally contain words such as `Scientific`, `Research`, or `Systems`. Short institutional brands are common.

### Product/company separation check

Selected research/deep-tech companies in or adjacent to the cohort also separate company and product names:

- **Xanadu** publishes **PennyLane** as open-source quantum software: https://xanadu.ai/pennylane
- **Quantinuum** presents a multi-product/software stack under the Quantinuum company brand: https://www.quantinuum.com/
- **NVIDIA** uses **DGX** as a distinct product/platform family: https://docs.nvidia.com/dgx/

The inference is architectural, not causal: durable short company brands can support separately named technical products without forcing the company name into every tool.

### Decision rubric

This is a Mastermind decision rubric, not a market survey or legal score.

| Dimension | Weight | Sigma Scientific Systems + Instrument 01 | Rigilum + Instrument 01 |
|---|---:|---:|---:|
| Distinctiveness / collision screen | 25 | 8 | 21 |
| Scientific/technical credibility | 20 | 18 | 16 |
| Company-product separation | 20 | 16 | 19 |
| Expansion beyond first suite | 15 | 11 | 14 |
| Fit with comparator naming pattern | 20 | 10 | 18 |
| **Weighted total** | **100** | **63** | **88** |

The score is intentionally penalized by known collision evidence; it does not pretend to estimate trademark registrability.

**Loop 3 disposition:** choose **Rigilum + Instrument 01** as the working pre-product architecture.

---

## Public product architecture

```text
RIGILUM
└── INSTRUMENT 01
    ├── Route
    ├── Prove
    ├── Discover
    ├── Synthesize
    ├── Verify
    ├── Measure
    ├── Assure
    ├── Preflight
    ├── Review
    └── Adapt
```

The old repository and runtime names are compatibility surfaces, not the new product hierarchy. They remain in source paths, commands, benchmark receipts, specifications, tests, and historical records until a separate technical migration is justified.

## Pre-product positioning

**Category:** research software / AI-assisted research infrastructure  
**Launch state:** pre-product preview  
**Price:** free, MIT licensed  
**Primary promise:** coordinate technical work around the evidence obligation rather than presenting one undifferentiated assistant  
**Trust strategy:** source + mechanical validation + reproducibility + explicit research boundary + preserved null/negative evidence  
**Commercial strategy:** deliberately unspecified at this stage

The preview should establish whether people value the instrument before a hosted service, enterprise packaging, support model, or proprietary layer is designed.

## Gates before a real corporate launch

1. Canadian and US trademark search by relevant classes and confusingly similar marks.
2. British Columbia / federal corporate-name search and reservation strategy.
3. Domain and social-handle acquisition.
4. Counsel review of the final company and product identity if commercialization proceeds.
5. GitHub organization creation and repository-transfer plan.
6. Package, Pages, redirects, release URLs, signing, CI secrets, and dependency references audited before any repository move.
7. Only after those gates: remove the `working identity` qualifier and migrate organization/repository surfaces.

## Final status

**Rigilum / Instrument 01 is approved for a reversible pre-product presentation branch. It is not approved as a legally cleared corporate identity.**
