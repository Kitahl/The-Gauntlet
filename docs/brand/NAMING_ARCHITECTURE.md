# Naming Architecture

## 1. Decision

| Level | New public identity | Status | Existing identity retained for compatibility |
|---|---|---|---|
| Organization | **Lattice** | `DESIGN_DECISION` | Independent project ownership remains unchanged |
| Product suite | **Prism** | `DESIGN_DECISION` | Repository: `Kitahl/The-Gauntlet`; CLI: `gauntlet` |
| Runtime | **Quartz** | `DESIGN_DECISION` | `gauntlet_host`; pinned Hermes Agent runtime source |
| Principle | **Evidence before authority** | `DESIGN_DECISION` | Existing authority/evidence separation |
| Visual method | **Scholarly Antiquarian Framing** | coined internal label | No claim that this is an established academic term |

**Lattice** is selected because it is a short scientific term for an ordered structural arrangement. **Prism** is selected because it is a short scientific instrument/object term associated with separating a complex input into inspectable components. These are working public identities only; this document does not claim legal incorporation, trademark availability, domain availability, or institutional endorsement.

## 2. Public module map

| New public name | Existing public/technical name | Stable ID / command | Feature definition | Authority ceiling |
|---|---|---|---|---|
| **Diamond** | Soul / Research Orchestrator | `soul`, `/soul` | Goal hashing, task creation, typed obligations, deterministic ownership, receipt integration, release gate | Release authority within existing rules |
| **Sapphire** | Mind / Formal Reasoning | `mathbot`, `/mind` | Formal objects, assumptions, proof obligations, negations, exact arithmetic, optional solver checks, counterexamples | Claim-scoped formal receipt |
| **Emerald** | Space / Research Discovery | `scoutbot`, `/space` | Bounded search plans, literature and software discovery, identity deduplication, saturation, source assessment | Claim-scoped discovery receipt |
| **Ruby** | Reality / Method Synthesis | `novelbot`, `/reality` | Verified gap, mechanism delta, assumptions, failure modes, negative control, transfer, ablation, verifier plan | Candidate mechanism only until verified |
| **Garnet** | Power / Engineering Verification | `codebot`, `/power` | Typed verification plans, bounded execution, known verifier families, output hashes, defect-class coverage | Claim-scoped engineering receipt |
| **Topaz** | Time / Evaluation & Benchmarking | `benchbot`, `/time` | Frozen arms, matched baselines, exclusions, contamination handling, uncertainty, multiplicity, decision consequence | Evaluation receipt only |
| **Onyx** | Gauntlet / Process Assurance | `infinity-gauntlet`, `/gauntlet` | Stale-state, false-green, inherited-number, frame/costume, event, and ledger-integrity checks | May identify issues; cannot replace claim-native evidence |
| **Citrine** | Meditate / Decision Preflight | `meditate` | Facts, assumptions, unknowns, options, blocker, action, value of computation | Decision preparation only |
| **Amethyst** | Council / Evidence Review Panel | `council-of-elders`, `/council` | Frozen artifact/budget, independent seats, commitment/reveal, skeptic seat, cross-critique, controlled synthesis | Review receipt; no automatic factual warrant outside scope |
| **Opal** | Mirror / adaptive complement; technical `foil` | `foil`, `/foil` | Conservative user/task evidence, capability-gap routing, calibrated assistance, transfer tracking | Advisory/adaptation only |

## 3. Additional systems

| Public name | Existing technical identity | Included feature set | Status |
|---|---|---|---|
| **Quartz** | `gauntlet_host`, pinned Hermes Agent source | Provider access, tools, MCP, context, sessions, memory, skills, retry, interruption, delegation, typed IPC, CLI | Interim pinned-runtime alpha; observation-only authority |
| **Obsidian** | Black Gem / `blackgem` | Independent breaker seats, frozen rubric, participation accounting, injection canary, cross-critique, break triples | Adversarial instrument; may raise `ISSUE`; can never return `CLEARED` |
| **Moonstone Candidate** | archived mechanism-planner candidate | Exact minimum successful repair over a declared finite repair universe and hardening checks | Engineering candidate only; not promoted |
| **Zircon Candidate** | archived Math Foundry candidate | Trusted-base minimality and isolated qualification hardening | Engineering candidate only; not promoted |

## 4. Compatibility policy

The rename is intentionally non-breaking:

- do not rename Python packages or source modules;
- do not rename skill directories or slash commands;
- do not change task, obligation, receipt, evidence-reference, or verdict schemas;
- do not rewrite historical benchmark condition names;
- do not rewrite hashes, source ledgers, checkpoint records, or citation paths;
- do not make the public brand an authority-bearing field;
- do not infer that a new public name changes a component’s validation state.

A future code-level migration requires an explicit specification, redirects/aliases, tests, receipt compatibility review, and a release note.

## 5. Source basis

| Feature area | Repository source |
|---|---|
| Core typed architecture and module features | `docs/VNEXT_IMPLEMENTATION_REPORT.md`; `docs/ARCHITECTURE.md`; `docs/specs/` |
| Hermes-derived runtime architecture | `docs/engineering/GAUNTLET_FAST_BUILD_HERMES_INTERNAL_RUNTIME_2026-08-28.md` |
| Runtime CLI and authority boundary | `docs/engineering/PHASE8_USER_CLI_BOOT.md` |
| Runtime checkpoint and limitations | `docs/engineering/HERMES_FAST_P8_CHECKPOINT.json` |
| Obsidian/Black Gem semantics | `docs/specs/BLACKGEM_ENGINEERING_SPEC.md` |
| Candidate status and scoped validation | `research/postbench-candidate2/README.md` |
| Visual and marketing system | `SOURCE_PACKAGE.md` and supplied package identified there |
