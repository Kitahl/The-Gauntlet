# Brand and Product Claims Register

## Status vocabulary

| Status | Meaning |
|---|---|
| `VERIFIED_REPOSITORY_FACT` | Directly supported by a committed source, test, receipt, manifest, or checkpoint |
| `DESIGN_DECISION` | Chosen name, visual rule, copy, or information architecture; not an empirical finding |
| `EXPLORATORY_EVIDENCE` | A bounded pilot or study exists but does not support a general claim |
| `UNVERIFIED` | No sufficient evidence or clearance is recorded |
| `PROHIBITED` | Must not appear in public copy because it is false, misleading, or outside scope |

## Registered claims

| ID | Claim | Status | Evidence / action |
|---|---|---|---|
| `BR-001` | Lattice is the working public organization identity for this project. | `DESIGN_DECISION` | `NAMING_ARCHITECTURE.md` |
| `BR-002` | Prism is the working public name of the integrated tool suite. | `DESIGN_DECISION` | `NAMING_ARCHITECTURE.md` |
| `BR-003` | The repository and installed command remain `Kitahl/The-Gauntlet` and `gauntlet`. | `VERIFIED_REPOSITORY_FACT` | repository metadata; `pyproject.toml`; `gauntlet_host/cli.py` |
| `BR-004` | The runtime vendors pinned Hermes Agent source and uses an isolated parent/worker boundary. | `VERIFIED_REPOSITORY_FACT` | `vendor/HERMES_SNAPSHOT.json`; `third_party/HERMES_SOURCE_LEDGER.md`; runtime engineering plan |
| `BR-005` | The FAST-P8 record reports 8/8 bounded boot checks passed. | `VERIFIED_REPOSITORY_FACT` | `docs/engineering/HERMES_FAST_P8_CHECKPOINT.json` |
| `BR-006` | FAST-P8 establishes external-provider, autonomous release, cross-platform, routing-benefit, or cost-benefit performance. | `PROHIBITED` | Checkpoint `known_limitations` explicitly withholds these conclusions |
| `BR-007` | Runtime outputs are observations and cannot directly create canonical receipts or release tasks. | `VERIFIED_REPOSITORY_FACT` | runtime engineering plan; Phase-8 document and harness |
| `BR-008` | The ten gemstone public instrument names map to existing stable skills and commands. | `DESIGN_DECISION` plus `VERIFIED_REPOSITORY_FACT` compatibility map | `NAMING_ARCHITECTURE.md`; existing skill paths |
| `BR-009` | Obsidian can raise an issue and can never clear a claim. | `VERIFIED_REPOSITORY_FACT` | `docs/specs/BLACKGEM_ENGINEERING_SPEC.md` |
| `BR-010` | Moonstone Candidate and Zircon Candidate are archived engineering candidates, not promoted runtime authority. | `VERIFIED_REPOSITORY_FACT` | `research/postbench-candidate2/README.md` |
| `BR-011` | Exploratory benchmark receipts include positive, null, and mixed/negative outcomes. | `EXPLORATORY_EVIDENCE` | `docs/BENCHMARKS.md` and linked receipts |
| `BR-012` | Prism improves independent human reasoning, scientific discovery, or general AI capability in deployment. | `UNVERIFIED` | `RESEARCH.md` states this is not established |
| `BR-013` | Classical-scientific styling proves rigor, correctness, or historical legitimacy. | `PROHIBITED` | Brand evidence-boundary rule |
| `BR-014` | Lattice or Prism has completed corporate-name, trademark, domain, or legal clearance. | `UNVERIFIED` | Professional legal clearance required before registration or commercial launch |
| `BR-015` | The committed frontispiece and calibration mark are original project-authored vectors with no external artwork embedded or traced. | `VERIFIED_REPOSITORY_FACT` | source SVG metadata; `asset-manifest.json`; reproducible SHA-256 hashes |
| `BR-016` | Scholarly Antiquarian Framing is an established scientific or marketing term. | `PROHIBITED` | It is a coined internal label from the supplied design package |

## Public-copy rule

Every factual claim must resolve to a repository path or an external source ledger. Statements that lack evidence remain explicitly marked `UNVERIFIED`; visual prestige is never accepted as a substitute.
