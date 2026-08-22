# Mastermind + FOIL showcase improvement record

Status: **candidate release record**. This documents the four bounded improvement loops used to build the public showcase. It does not claim that the underlying FOIL learning mechanisms have been behaviorally validated.

## Tools actually used

- Mastermind v4.4.11 closed-answer/reopen candidate runner (`mastermind.py`) for project discovery, obligation planning, and release-evidence closure.
- FOIL for claim-level provenance review, efficacy-overclaim checks, and complementary gap analysis.
- Chromium/Playwright through the local deterministic showcase validator for rendered desktop/mobile evidence.
- Git for immutable loop commits and regression comparison.

The installed environment lacked the configured Claude/Codex agent CLIs, so the Mastermind multi-builder `run` path was **not** represented as executed. The available Mastermind controller/validator paths were used directly instead.

## Loop 1 — deployment and accessibility boundary

Earliest causal defect: the initial `docs/` GitHub Pages design linked to sibling `skills/` paths that would not be published with a branch `/docs` deployment. A repository-correct link could therefore become a deployed-page failure.

Smallest repair:
- canonical GitHub skill links;
- skip navigation;
- visible `:focus-visible` treatment;
- reduced-motion handling;
- explicit license-status disclosure;
- deterministic desktop/mobile render checks.

Result: deployment-path and accessibility obligations gained executable checks.

## Loop 2 — FOIL evidence/provenance pass

Earliest causal defect: the showcase described validation and architecture without exposing a sufficiently direct claim-to-artifact trail. Numeric status presentation could also be misread as performance evidence.

Smallest repair:
- replaced status-like framing with repository/authority facts;
- added a public Evidence Trail;
- added `docs/content-provenance.json`;
- added an explicit boundary that specification validation does not establish learning efficacy;
- added provenance and overclaim checks to the validator.

Result: major architecture/FOIL claims are source-traceable without converting adjacent research into product-efficacy claims.

## Loop 3 — release packaging and gate sensitivity

Earliest causal defect: “GitHub Pages ready” lacked a repository-contained deployment contract, and green checks alone did not show that the gates could detect relevant failures.

Smallest repair:
- added `PAGES_SETUP.md` and `.nojekyll`;
- added page metadata;
- added negative-control mutants for hidden core content, collapsed heading hierarchy, and Pages-breaking relative skill links;
- retained an explicit no-license claim rather than inventing a license.

Result: the release package states the remaining one-time Pages setting and the validator demonstrates sensitivity to representative failure mutations.

## Loop 4 — activation/usability surface

Earliest causal defect: a technical reader could understand the architecture but not know how to invoke it.

Smallest repair:
- added the user-facing slash-command activation surface;
- traced every displayed command to the corresponding skill metadata;
- represented Meditate correctly as an orchestrator-invoked grounding form rather than inventing a general slash command;
- added the same quick-start boundary to the README.

Result: the showcase now covers what the system is, why its evidence rules matter, where the source lives, and how to activate the available lanes.

## Saturation decision

After Loop 4 the deterministic showcase suite reports **30/30 PASS**. No further generalizable defect was found that justified another product mechanism before public review. Additional cosmetic iteration would be preference optimization, not evidence-backed correctness repair, so the loop stops here pending external/user taste feedback.

## Mechanical validation scope

Current checks cover:
- semantic landmarks and unique IDs;
- keyboard skip path and visible focus;
- reduced-motion rules;
- principal text contrast;
- no required JavaScript/remote runtime assets;
- Pages-safe skill links;
- source artifact and provenance presence;
- module-count consistency;
- behavioral-efficacy overclaim boundary;
- activation-trigger provenance;
- desktop/mobile no-overflow and core visibility;
- zero captured browser-console errors in the deterministic render harness;
- payload budget and its negative control;
- render, hierarchy, and Pages-link gate mutants.

The browser harness uses Chromium with the production HTML/CSS loaded through Playwright `set_content` because local `file://`/localhost navigation is blocked in the execution environment. This checks browser layout/render behavior but is not represented as a live deployed HTTP test.

## Remaining evidence required

- User/human aesthetic preference has not been measured by automated validation.
- GitHub Pages must be enabled once in repository settings after merge before the public project-site URL is live.
- FOIL's behavioral claims remain research hypotheses until prospective trials demonstrate delayed independent transfer after assistance is removed.
