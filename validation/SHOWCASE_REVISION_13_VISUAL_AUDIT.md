# Showcase Revision 13 — Mechanism Visual Audit

Date: 2026-08-22

## Version boundary

**Showcase Revision 13** is a presentation/review-surface revision. The research software remains **v0.4.0**. Revision 13 must not be interpreted as a software, protocol, benchmark, or scientific-evidence version.

## Requirement

The public site should visually show what the tool is and how it works rather than relying almost entirely on prose and cards. Visuals must remain research-grade: source-grounded, accessible, locally hosted, reviewable, and unable to silently strengthen the underlying evidence.

## Visual 1 — Gauntlet system map

File: `docs/visuals/gauntlet-system-map.svg`

Purpose:
- make the Research Orchestrator visibly central;
- show bounded formal, discovery, synthesis, engineering, evaluation, assurance, review, preflight, and FOIL responsibilities;
- communicate that this is an evidence-routing control system rather than an undifferentiated agent swarm.

Source boundary:
- `docs/ARCHITECTURE.md`;
- public module `SKILL.md` specifications.

This is a conceptual architecture rendering, not an execution trace.

## Visual 2 — FOIL diagnostic loop

File: `docs/visuals/foil-diagnostic-loop.svg`

Purpose:
- show the transition from observed behavior to competing explanations;
- show the smallest-complement step;
- show claim-matched verification and changed-context/assistance-free transfer;
- make `joint task success != independent competence` visually explicit.

Source boundary:
- `skills/foil/SKILL.md`;
- `research/FOIL_RESEARCH_BASIS.md`;
- existing FOIL research-integration audit.

This is specification-derived. It is not evidence of learning benefit or psychometric validity.

## Visual 3 — exploratory benchmark evidence

File: `docs/visuals/benchmark-evidence.svg`

Purpose:
- render the already-published HLE, ARC-AGI-1, and GPQA-Diamond pilot outcomes;
- keep the GPQA null result visually co-equal with positive deltas;
- show sample sizes and the exploratory/non-leaderboard boundary in the figure itself.

Source boundary:
- `docs/BENCHMARKS.md`;
- `benchmarks/results/2026-08-22-blinded-pilot.json`.

The visual does not add a significance test, causal interpretation, or general-efficacy claim.

## Release obligations added for Revision 13

The public showcase validator now additionally requires:

1. all three SVG assets exist and are non-trivial;
2. all three assets are referenced locally from the homepage;
3. each visual has meaningful alt text;
4. explicit image dimensions are declared;
5. `SHOWCASE R13` is visibly separated from software version `0.4.0`;
6. all visual assets load and render in the deterministic desktop and mobile Chromium passes;
7. remote image dependencies remain prohibited;
8. HTML + CSS + visual CSS + SVG payload remains below the existing 100 KB static payload budget;
9. a missing-visual-reference mutant is detected.

## Design rationale

The external audit used software-architecture and evidence-dashboard literature as design anchors. The relevant general lesson is not that diagrams make a project better; it is that architecture and evidence relationships become easier to inspect when structure is made explicit and when visual summaries preserve underlying evidence states rather than hiding them behind a single aggregate score.

## Release decision

This file is not a green receipt. Promotion still requires the exact final PR head to pass the normal Research software validation workflow and CodeQL. The generated `validation/showcase-validation.json` must correspond to the exact release candidate rather than an earlier visual build.
