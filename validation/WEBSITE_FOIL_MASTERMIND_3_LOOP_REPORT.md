# Website FOIL × Mastermind Three-Loop Improvement Record

Date: 2026-08-22

Status: **candidate release record**. This document records the three bounded improvement loops applied to the public GitHub Pages showcase after a new requirement raised the target from a polished research portfolio to a professional, research-grade, enterprise-reviewable public surface.

The prior `validation/MASTERMIND_SHOWCASE_4_LOOP_REPORT.md` remains historical evidence for the earlier release. Its saturation decision is not treated as permanent: the new enterprise-review requirement changes the evaluation frame and legitimately reopens the website.

## Authority and evidence boundary

The website is a communication and review surface for repository evidence. It must not manufacture stronger research claims than the repository supports.

The loops below therefore preserve these boundaries:

- structural/source checks are not behavioral evidence;
- `PASS-SPEC` is specification coverage, not proof of executed model behavior;
- exploratory model benchmark pilots are not official leaderboard submissions or general efficacy evidence;
- positive and null benchmark results remain visible together;
- complete-system behavioral efficacy remains open pending prospective matched-budget evidence;
- visual/professional quality is not represented as scientific validity.

The improvement method follows the existing FOIL/Mastermind discipline: identify the earliest causal defect, prefer the smallest general repair, preserve negative controls, and require release-gate sensitivity rather than accepting appearance alone.

---

# LOOP 1 — Research identity, trust, and evidence hierarchy

## Earliest causal defect

The previous homepage contained strong research artifacts but presented them as a sequence of polished project sections. A reviewer could see architecture, FOIL, benchmarks, modules, and an evidence trail, yet still had to infer the institutional trust model and navigate into GitHub to discover security, governance, citation, reproducibility, contribution, and change-control artifacts.

This was not primarily a missing-document defect. The documents already existed. The defect was **information architecture**: the public entry point did not expose the repository's strongest research-software controls as one coherent reviewer surface.

## Smallest mechanism added

**Evidence-first research portal layout**

1. Brand the public surface explicitly as **The Gauntlet — Evidence-Governed Research Toolkit** while retaining the professional research-software name used in citation metadata.
2. Put current version, license, structural validation, contract coverage, and open behavioral-efficacy status above the fold.
3. Replace the decorative orbital architecture as the primary explanation with an evidence-obligation flow: `Frame → Route → Execute → Verify → Release`.
4. Add an evidence ledger that separates mechanical, specification, exploratory empirical, and prospective research claims.
5. Add direct reviewer paths to research question, reproducibility, citation, security, governance, contribution, changelog, and roadmap artifacts.
6. Preserve all module aliases, specifications, benchmark caveats, and no-efficacy-overclaim language.

## Mastermind admission gates

| Gate | Result | Reason |
|---|---|---|
| A — Causal adequacy | PASS-SPEC | Repairs the actual reviewer-navigation and evidence-hierarchy defect rather than merely changing colors or wording. |
| B — Identifier independence | PASS | Trust-center and evidence-ledger structure generalize to research software beyond this project. |
| C — Representation transformation | PASS-SPEC | The mechanism is information architecture; it survives equivalent wording and visual styling. |
| D — Negative control | PASS-SPEC | It does not turn open behavioral questions into positive evidence and does not hide the GPQA null result. |
| E — Cross-domain transfer | PASS-SPEC | Security, governance, citation, reproducibility, and claim classes are general research-software review surfaces. |
| F — Existing-mechanism compression | PASS | Reuses existing repository evidence and the existing homepage rather than adding a separate product or dashboard. |
| G — Ablation | PASS-STRUCTURAL | Removing the trust/evidence surfaces restores the need for repository archaeology and claim-class inference. |
| H — Regression | PASS-SPEC | Existing module aliases, evidence boundaries, accessibility primitives, and benchmark caveats are retained. |

---

# LOOP 2 — Discoverability and accessibility contract

## Earliest causal defect

The old validator treated every remote `<link>` as a remote runtime asset. That accidentally made standards-friendly metadata such as a canonical URL fail the same gate intended to prevent remote executable/style dependencies. At the same time, the prior mobile CSS hid primary navigation links instead of proving that the real navigation remained usable on narrow viewports.

The site also lacked crawler-level `robots.txt` and sitemap discovery files even though the repository already carried machine-readable citation metadata.

## Smallest mechanism added

**Reviewer-discovery + viewport-access contract**

1. Add a canonical public URL, Open Graph URL, descriptive metadata, `robots.txt`, and `sitemap.xml`.
2. Keep runtime assets local; distinguish non-executable metadata links from remote styles/scripts in validation.
3. Keep primary navigation visible on mobile using a horizontally scrollable navigation rail rather than hiding it.
4. Require primary navigation and button targets to meet the WCAG 2.2 AA 24×24 CSS-pixel minimum in both tested viewports.
5. Preserve skip navigation, visible focus treatment, reduced-motion behavior, principal contrast, and no horizontal document overflow.
6. Remove an unused web-app manifest rather than retaining a non-load-bearing enterprise artifact.

## Mastermind admission gates

| Gate | Result | Reason |
|---|---|---|
| A — Causal adequacy | PASS | Fixes a validator semantic error, mobile-navigation disappearance, and missing crawler discovery directly. |
| B — Identifier independence | PASS | Canonical discovery, local-runtime distinction, visible navigation, and target sizing are generic web properties. |
| C — Representation transformation | PASS | Checks are based on semantics and rendered geometry, not exact prose. |
| D — Negative control | PASS-STRUCTURAL | Canonical metadata is permitted while a remote stylesheet mutant is rejected. |
| E — Cross-domain transfer | PASS | Applies to public research portals, documentation sites, and software project sites generally. |
| F — Existing-mechanism compression | PASS | Extends the existing showcase validator and static Pages deployment; no JavaScript framework is added. |
| G — Ablation | PASS-STRUCTURAL | Removing the new checks permits hidden mobile navigation, undersized controls, or broken discovery metadata. |
| H — Regression | PASS-SPEC | Local runtime assets, no executable JavaScript requirement, and prior accessibility checks remain. |

## External standards used as audit anchors

- W3C WCAG 2.2 is used for the target-size and focus/accessibility audit frame.
- FAIR4RS findability principles motivate richer discovery/version metadata, without claiming formal FAIR4RS compliance.
- The repository's root `CITATION.cff` remains the authoritative machine-readable citation artifact; the website does not invent a DOI or archival identifier that does not exist.

---

# LOOP 3 — Release assurance must cover the new enterprise contract

## Earliest causal defect

A redesign can look more professional while silently weakening correctness. The previous showcase validator covered semantics, contrast, accessibility primitives, source presence, module count, evidence boundaries, browser overflow, console errors, and representative mutants, but it did not know about the new trust-center, reproduction, discovery, mobile-navigation, or target-size obligations.

Without changing the gate, a later regression could delete the exact enterprise-review features added in Loops 1–2 while CI stayed green.

## Smallest mechanism added

**Enterprise showcase regression gate**

The existing `validation/validate_showcase.py` is extended to require:

- canonical URL + Open Graph URL + substantial description;
- `robots.txt` and sitemap consistency;
- all trust-center artifacts exposed from the homepage;
- exact public mechanical reproduction commands exposed from the homepage;
- release identity consistency with `CITATION.cff` (`Evidence-Governed Research Toolkit`, version `0.4.0`, MIT);
- visible primary navigation in desktop and mobile renders;
- ≥24×24 rendered targets for primary navigation and calls to action;
- continued source/provenance/module/activation/runtime/evidence-boundary checks;
- continued desktop/mobile no-overflow, no-console-error, core-visibility, keyboard-first-focus, contrast, and payload checks.

Negative controls now include:

- hidden main content;
- collapsed H1 hierarchy;
- undersized interactive targets;
- a remote stylesheet;
- a Pages-breaking relative skill link;
- removal of a required trust-center artifact.

## Mastermind admission gates

| Gate | Result | Reason |
|---|---|---|
| A — Causal adequacy | PASS | Prevents the exact false-green mode created when product obligations evolve but validators do not. |
| B — Identifier independence | PASS | The gate checks generic trust, discoverability, accessibility, provenance, and release-identity properties. |
| C — Representation transformation | PASS-SPEC | Most checks use parsed semantics, source existence, or rendered geometry rather than pixel snapshots. |
| D — Negative control | PASS-STRUCTURAL | Representative remote-asset, target-size, trust-surface, hierarchy, visibility, and link mutants must fail. |
| E — Cross-domain transfer | PASS | The same release-assurance pattern applies to other static research/software portals. |
| F — Existing-mechanism compression | PASS | Extends `validate_showcase.py`; no parallel validator or duplicated CI workflow is introduced. |
| G — Ablation | PASS-STRUCTURAL | Removing the added enterprise checks recreates the false-green release boundary. |
| H — Regression | PENDING-EXACT-HEAD-CI | Final regression status is the exact pull-request head's existing Research software validation and CodeQL checks, not this prose record. |

---

# Release decision rule

This report does **not** declare the branch releasable by itself.

Promotion requires the exact final pull-request head to pass the repository's existing release machinery, including the normal research-software validation workflow and CodeQL. If CI finds a defect, the defect and repair belong to the candidate history; the report is not evidence that the failure did not occur.

# What remains outside this website upgrade

The three loops improve the public research-software review surface and its release assurance. They do not establish:

- that FOIL improves human learning or reasoning;
- that The Gauntlet improves scientific discovery outcomes;
- that exploratory benchmark deltas generalize;
- psychometric validity of the personalization layers;
- external security certification, SOC 2, ISO 27001, or other enterprise compliance certification;
- a DOI or archival release that has not actually been minted;
- independent third-party reproduction.

Those remain separate evidence obligations and should appear as such rather than being implied by professional visual design.
