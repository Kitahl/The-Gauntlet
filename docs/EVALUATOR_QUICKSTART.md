# 5-Minute Evaluator Path

This page is for grant reviewers, research collaborators, and technical evaluators who need to answer four questions quickly: **What is this? Why does it matter? What evidence exists? What is not yet proven?**

## Minute 0–1 — what is it?

Read `README.md` and `docs/ARCHITECTURE.md`.

The project is a modular research-software toolkit for evidence-governed AI-assisted reasoning. It routes work according to the evidence obligation—proof, prior art, execution, evaluation, or process assurance—and keeps unresolved claims explicit.

## Minute 1–2 — what is the distinctive research idea?

Read `RESEARCH.md`.

The core hypothesis is that separating generation, verification, prior-art search, evaluation, and self/process audit can make AI-assisted research more traceable and less vulnerable to false confidence, correlated agreement, and verification-scope errors. FOIL adds a separate hypothesis: assistance should adapt to missing capability while being evaluated by what the user can later do independently.

## Minute 2–3 — what can I inspect now?

Inspect:

- `skills/` — executable method specifications;
- `research/FOIL_RESEARCH_BASIS.md` — cited research basis and transport limits;
- `validation/` — structural/source/specification evidence;
- `docs/content-provenance.json` — public claim → source mapping.

## Minute 3–4 — can I reproduce the current checks?

Follow `REPRODUCIBILITY.md`.

The current public package provides deterministic/source-level validation and a browser/showcase validator. These checks establish repository/specification properties only.

## Minute 4–5 — what remains scientifically open?

Read `ROADMAP.md`.

The main open requirement is **prospective behavioral evidence** against strong baselines under matched budgets. The repository deliberately does not claim that passing specification checks proves improved human reasoning, scientific discovery, or general AI capability.

## Reviewer summary

**Implemented:** modular research methods, portable control/assurance architecture, public evidence trail, structural validation, reproducibility/citation infrastructure.

**Research-ready:** explicit hypotheses, baselines, ablations, endpoints, negative-result policy, and evidence-first roadmap.

**Not yet established:** behavioral efficacy of the complete system or FOIL's learning benefit in prospective deployment.
