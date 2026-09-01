# BASTION-01 research roadmap

The roadmap is ordered by evidence value, not feature count.

## R1 — Release engineering baseline

**Goal:** make every public release reproducible, citable, reviewable, and safe to evaluate.

- [x] public license
- [x] `CITATION.cff`
- [x] semantic version baseline and changelog
- [x] contribution/security/conduct policies
- [x] CI validation
- [ ] current release tag and GitHub Release
- [ ] archival DOI after first evidence-bearing stable release

**Exit criterion:** an independent reviewer can identify the exact version, run the mechanical checks, and cite the software.

## R2 — Behavioral harness

**Question:** does the complete workflow improve outcomes over a strong direct baseline?

- define representative task families;
- freeze success metrics and failure classes;
- implement strong direct-model baseline;
- implement matched-budget modular workflow;
- retain raw runs and analysis code;
- report quality, cost, latency, false blockers, and verification success.

**Exit criterion:** reproducible matched-budget evidence on at least three materially different task families.

## R3 — Counterform adaptation study

**Question:** does adaptive complementary assistance improve independent user capability beyond ordinary strong AI assistance?

- direct AI vs static complement vs adaptive Counterform;
- delayed assistance-free transfer primary endpoint;
- near/far transfer, retention, error detection, calibration;
- assistance exposure recorded per item;
- learner-state predictions frozen before follow-up probes.

**Exit criterion:** prospective evidence with preregistered endpoints and transparent negative results.

## R4 — Routing and review ablations

**Question:** which orchestration components add value after controlling for evidence and compute?

- Crown vs direct baseline;
- Aegis on/off;
- Conclave vs matched-evidence direct control;
- native verifier vs same-model self-critique;
- optional route value and stopping analysis.

**Exit criterion:** mechanism-level evidence identifying components that improve results and components that only add cost.

## R5 — External reproduction

- publish stable benchmark package;
- recruit independent reproducers/collaborators;
- resolve reproducibility defects without moving target metrics;
- archive the evidence-bearing release;
- publish a concise technical report/preprint if warranted.

**Exit criterion:** at least one independent reproduction or a documented discrepancy that materially improves the method.

## R6 — Research integrations

Only after R2–R4 establish value:

- formal theorem-prover adapters;
- research-literature retrieval adapters;
- repository/code-analysis adapters;
- experiment tracking and provenance export;
- standardized research-state interchange.

Feature expansion is deliberately downstream of behavioral evidence.
