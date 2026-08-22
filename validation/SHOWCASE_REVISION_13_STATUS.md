# Showcase Revision 13 status

Research software version: `0.4.0`

Showcase revision: `13`

Release state: **RELEASED**

Release pull request: `#15 — Add mechanism-native visuals for Showcase Revision 13`

Validated release-candidate head: `c16be13124527c0d1bf6374d8037019008f62998`

Merged release commit: `7c08a132b876153fb1feaef4388c879e354d444b`

Release evidence:

- showcase validation: **53/53 PASS**;
- desktop mechanism visuals rendered: **PASS**;
- mobile mechanism visuals rendered: **PASS**;
- static HTML/CSS/SVG payload: **66,164 bytes**;
- 37/37 runtime/layout tests: **PASS**;
- Research Orchestrator + Process Assurance validation: **PASS**;
- CodeQL: **PASS**.

The validation receipt was committed before promotion. The exact PR head containing that receipt and the pre-promotion status record then passed the normal Research software validation and CodeQL workflows before PR #15 was promoted and merged.

Revision 13 is a showcase/presentation revision only. The research software remains version `0.4.0`; no runtime, benchmark result, protocol, or scientific-evidence version was changed by this release.
