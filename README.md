# The Gauntlet

**An evidence-first research skill system for structured reasoning, verification, scouting, building, red-teaming, and personalized gap-filling.**

The repository combines the five specialist “stones,” the Infinity Gauntlet process-audit layer, Meditate grounding, the Council of Elders advisory forum, and FOIL—the personalized complementary operator.

> Status: research/engineering toolkit. The skills encode procedures, evidence obligations, and validation rules; they do not guarantee correctness or scientific performance.

## Skills

| Skill | Role |
|---|---|
| **MIND / mathbot** | Mathematics, logic, proofs, counterexamples, formal reasoning |
| **SPACE / scoutbot** | Search for existing code, papers, tools, and cross-domain analogues before building |
| **REALITY / novelbot** | Novel approaches when known methods fail a named constraint |
| **POWER / codebot** | Software architecture, implementation, tests, benchmarks, formal/software verification |
| **TIME / benchbot** | Capability frontier, benchmark gaps, attainable ceiling, effort/reward |
| **Infinity Gauntlet** | Audits the frame, process, inherited assumptions, stale state, and repeated-failure patterns |
| **Meditate** | Grounding and dispatch discipline before action or after failure |
| **Council of Elders** | Artifact-grounded, evidence-packed advisory forum used selectively |
| **FOIL** | Personalized mirror that supplies missing methods, investigates claims, and tracks independent competence |

## Quick start

Invoke the lane that matches the obligation: `/mind` for proof/logic, `/space` for prior art and reuse, `/reality` for genuinely novel mechanism search, `/power` for software/execution/verification, `/time` for benchmark/ceiling analysis, `/gauntlet` for frame/process audit, `/council` for a selective evidence-grounded forum, or `/foil` when you want the system to identify and supply the missing complement. Meditate is an orchestrator-invoked grounding form rather than a general user-facing command.

## Repository layout

- `skills/` — source skill specifications
- `research/` — evidence and research basis for FOIL
- `validation/` — current mechanical/specification validation artifacts
- `docs/` — static showcase site for GitHub Pages

## Epistemic rule

The user controls goals and voluntary decisions. Neither the user nor the system controls factual truth by authority alone. Load-bearing factual and technical claims should be tied to proof, measurement, executable checks, or scoped external evidence; unresolved claims remain explicitly unresolved.

## Showcase

The static showcase lives in `docs/`. See [`PAGES_SETUP.md`](PAGES_SETUP.md) for the one-time GitHub Pages setting needed to publish it at the project-site URL.

## License

No repository-wide license has been declared yet. Do not assume permissions beyond GitHub's normal viewing/forking behavior until a license is added.
