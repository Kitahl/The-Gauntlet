# Strong Inference

**Open Research Suite · pre-product preview · free research software · version 0.5.1**

**Strong Inference** is the first open product line from the working company identity **Strong Inference Systems**: a coordinated research-software suite for AI-assisted technical work where evidence, verification, reproducibility, competing explanations, and explicit unresolved state matter.

> **Brand status:** `Strong Inference Systems` is a working company identity selected by the August 25, 2026 redo of the repository's three-loop naming audit. It is **not** represented as trademark, corporate-name, or domain clearance. `Strong inference` is an established scientific-method term associated with John R. Platt's 1964 formulation of competing hypotheses and discriminating experiments; the brand uses that scientific meaning rather than claiming the phrase itself as a new concept. The repository slug, technical IDs, slash commands, runtime modules, benchmark condition names, and historical records remain unchanged until a separate clearance and migration decision is made.

[![Research software validation](https://github.com/Kitahl/The-Gauntlet/actions/workflows/validate.yml/badge.svg)](https://github.com/Kitahl/The-Gauntlet/actions/workflows/validate.yml)
[![CodeQL](https://github.com/Kitahl/The-Gauntlet/actions/workflows/codeql.yml/badge.svg)](https://github.com/Kitahl/The-Gauntlet/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.5.1-informational.svg)](CHANGELOG.md)

**Preview:** https://kitahl.github.io/The-Gauntlet/  
**5-minute evaluator path:** [`docs/EVALUATOR_QUICKSTART.md`](docs/EVALUATOR_QUICKSTART.md)  
**Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)  
**Benchmarks:** [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)  
**Research statement:** [`RESEARCH.md`](RESEARCH.md)  
**Reproducibility:** [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)

---

## Why Strong Inference

The name is methodological, not decorative. Strong inference asks researchers to construct competing hypotheses, design observations or experiments that discriminate among them, eliminate what fails, and iterate on what survives. That is close to the operating philosophy of this suite: do not reward agreement; identify the obligation, choose the appropriate method, expose alternatives, seek decisive evidence, and preserve unresolved state when the evidence does not decide.

The product does not claim to implement Platt's method literally in every workflow, nor does the name imply that every output is a scientific inference. It is the umbrella for a broader evidence-governed research system.

## The open research suite

Research workflows often fail at the handoffs: deciding what needs proof, what needs current evidence, what needs implementation, what needs measurement, what should be independently challenged, and what must remain unresolved.

Strong Inference puts those obligations behind one coordinated surface. Its public modules are named for the job they perform:

| Strong Inference module | Responsibility | Stable technical ID / command |
|---|---|---|
| **Route** | Frame work, decompose it, route obligations, integrate evidence, and govern release | `soul` · `/soul` |
| **Prove** | Formal reasoning, mathematics, probability, statistics, counterexamples, and proof structure | `mathbot` · `/mind` |
| **Discover** | Literature, prior art, existing software, current evidence, and cross-domain terminology | `scoutbot` · `/space` |
| **Synthesize** | Construct new mechanisms only after known methods fail a named constraint | `novelbot` · `/reality` |
| **Verify** | Architecture, implementation, integration, execution, and software verification | `codebot` · `/power` |
| **Measure** | Baselines, capability measurement, ceilings, cost, ablations, and stop/go evidence | `benchbot` · `/time` |
| **Assure** | Process checks, stale-state detection, frame/costume boundaries, and false-green defense | `infinity-gauntlet` · `/gauntlet` |
| **Preflight** | Grounding before consequential decisions and after failures | `meditate` |
| **Review** | Selective independent evidence and method review | `council-of-elders` · `/council` |
| **Adapt** | Task- and user-specific complementary assistance with calibrated evidence about coverage | `foil` · `/foil` |

These are **public product names**, not runtime migrations. Existing integrations continue to use the stable identifiers in the right-hand column.

## Why a pre-product preview

Strong Inference is being published before a commercial product exists for three reasons:

1. **Inspectability.** The architecture, source, validation logic, benchmark receipts, and known limitations can be examined directly.
2. **Falsifiability.** Positive, null, and mixed results remain visible rather than being reduced to a launch claim.
3. **Product discovery.** The preview can establish which parts of the suite are genuinely useful before packaging, hosted infrastructure, enterprise integrations, or paid support are designed.

The preview is free under the [`MIT License`](LICENSE). No hosted service, support SLA, commercial-readiness claim, or behavioral-efficacy claim is implied.

## Evidence boundary

The software includes executable runtime checks, structural/source validation, benchmark harnesses, and exploratory evaluation receipts. Those establish particular engineering facts. They do **not** establish that the complete suite improves human reasoning, scientific discovery, or general AI capability in prospective deployment.

The repository deliberately preserves null and negative evidence. Current benchmark artifacts and their validity boundaries are documented in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md). Prospective research obligations remain in [`ROADMAP.md`](ROADMAP.md).

## Architecture

```mermaid
flowchart LR
    U[Researcher] --> R[Route]
    R --> P[Prove]
    R --> D[Discover]
    R --> S[Synthesize]
    R --> V[Verify]
    R --> M[Measure]
    R --> A[Assure]
    R --> F[Preflight]
    R --> W[Review]
    R --> C[Adapt]
    P --> R
    D --> R
    S --> R
    V --> R
    M --> R
    A --> R
    F --> R
    W --> R
    C --> R
    R --> O[Supported result + explicit unresolved state]
```

The implementation retains the historical internal vocabulary used by the runtime and research record. In particular, the earlier public labels **Research Orchestrator**, **Formal Reasoning**, **Research Discovery**, **Method Synthesis**, **Engineering Verification**, **Evaluation & Benchmarking**, **Process Assurance Framework**, **Decision Preflight Protocol**, **Evidence Review Panel**, and **Mirror — Adaptive Reasoning Complement** are migration references rather than the new product-facing names. Adapt's technical skill name remains `foil`, its slash command remains `/foil`, its runtime modules remain `tools/foil_*`, and historical benchmark condition names remain unchanged. Assure's stable technical command remains `/gauntlet` even though **The Gauntlet** is no longer used as the public product brand.

## Quick evaluation

```bash
git clone https://github.com/Kitahl/The-Gauntlet.git
cd The-Gauntlet
python -m venv .venv
```

Activate the environment, then install the hash-locked development and runtime dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install --require-hashes -r requirements-lock.txt
python -m playwright install chromium
```

Run the principal mechanical checks:

```bash
python -m pytest
python validation/validate_soul_gauntlet_public.py
python validation/validate_showcase.py
```

See [`docs/RUNTIME_SETUP.md`](docs/RUNTIME_SETUP.md) for runtime configuration and [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the interpretation boundary of these checks.

## Product and company decision record

The working identity was selected through a fresh three-loop Mastermind pass in which each loop did different work:

- **Loop 1 — meaning and architecture:** defined what the company must be able to become and generated names from real scientific ideas rather than startup-style invented words.
- **Loop 2 — collision attack:** killed attractive candidates when current companies, trademarks, software projects, or adjacent research brands occupied the same territory. This also killed **The Gauntlet** as the preferred public product name after a directly adjacent 2026 LLM-evaluation Gauntlet was found.
- **Loop 3 — external comparison:** compared the surviving architecture against the 2026 Nature Index corporate-research cohort and against the naming behavior of durable scientific/technical companies, then selected the strongest surviving company/product pair.

The full decision record is [`validation/MASTERMIND_BRAND_PRODUCT_3_LOOP_REPORT_2026-08-25.md`](validation/MASTERMIND_BRAND_PRODUCT_3_LOOP_REPORT_2026-08-25.md).

## Release surfaces

- [`SECURITY.md`](SECURITY.md) — security policy
- [`GOVERNANCE.md`](GOVERNANCE.md) — governance
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution process
- [`CITATION.cff`](CITATION.cff) — machine-readable citation metadata
- [`CHANGELOG.md`](CHANGELOG.md) — software history
- [`ROADMAP.md`](ROADMAP.md) — research and engineering roadmap
- [`docs/content-provenance.json`](docs/content-provenance.json) — public claim provenance

**Strong Inference Systems / Strong Inference is a working pre-product identity. Formal legal-name availability, trademark clearance, domains, organization transfer, and final launch identity are separate gates.**
