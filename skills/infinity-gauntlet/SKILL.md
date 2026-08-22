---
name: infinity-gauntlet
description: THE INFINITY GAUNTLET — a portable process-audit skill the orchestrator turns on its own reasoning, evidence, state, and release process. It attacks the frame behind repeated failures, ungated conclusions, inherited numbers, stale authority, hidden assumptions, and false-green verification. Works without repository-specific hooks; optional integrations are feature-detected and never assumed.
---

# THE INFINITY GAUNTLET — portable public edition

The Gauntlet is a **self-audit protocol**. A normal reviewer attacks the candidate it is handed. The Gauntlet also attacks the frame, process, evidence boundary, and session state that produced that candidate.

It is worn by the orchestrator (the **Soul**) and can aim the five specialist stones:

- **MIND / mathbot** — proof, formal reasoning, probability, counterexamples.
- **SPACE / scoutbot** — prior art, existing tools, external evidence.
- **REALITY / novelbot** — genuinely new mechanism search after defaults fail.
- **POWER / codebot** — implementation, execution, tests, software verification.
- **TIME / benchbot** — benchmarks, ceilings, effort/reward, stop/go.

## 0. PUBLIC RUNTIME CONTRACT

This repository must be usable even when no private project runtime is present.

At activation:

1. **Feature-detect integrations before using them.** Never assume a path, hook, bot backend, MCP, CLI, API key, solver, or local project file exists.
2. If an optional integration exists, it may automate detection or verification.
3. If it does not exist, run the corresponding operation **in portable LLM mode** using the evidence and tools actually available.
4. Missing optional machinery is `UNAVAILABLE`, not `PASS`, not `FAIL`, and never a reason to fabricate a result.
5. A public user must never be instructed to execute a repository path that has not first been verified to exist.
6. Historical/private source implementations may have used hooks and helper scripts. They are evidence about the design lineage, **not dependencies of this public skill**.

This section overrides any historical implementation assumptions.

## 1. AUTHORITY AND EVIDENCE

- The user controls goals, constraints, priorities, voluntary actions, and adoption.
- The Soul/Gauntlet is subordinate to those decisions.
- Factual truth is not decided by status. A task-relevant contention from either side is investigated for evidence, counterevidence, assumptions, and scope before it becomes load-bearing.
- `PROVEN`, `MEASURED`, `CITED`, and `DERIVED` describe support type. Confidence is separate.
- Unknown evidence stays `UNKNOWN` or `UNAVAILABLE`.

## 2. THE TEN OPERATIONS

Exactly ten canonical operations exist.

| # | operation | fire when | portable move |
|---|---|---|---|
| 1 | `frame` | repeated attempts share a failure shape | name the shared shape; generate at least one structurally different route |
| 2 | `audit` | a kill/finding is about to be accepted | reconstruct how the verdict was produced; check predeclared criterion and executed evidence |
| 3 | `costume` | one option survives or looks novel | search for the nearest known technique/system and state the differentiator |
| 4 | `derive` | a number/label is about to become a premise | recompute from the nearest raw artifact or show the derivation |
| 5 | `self` | acting on your own load-bearing read | preregister the expected answer/refuter; declare authorship or selection contamination |
| 6 | `redirect` | work is busy but the core claim remains unmeasured | identify the single load-bearing unknown and ask whether current work is upstream of it |
| 7 | `refresh` | a rule/plan/source may be stale | reread the authoritative source or current external source before acting |
| 8 | `boundary` | handing work across contexts or changing shared state | pin assumptions/interfaces/state in an artifact and identify concurrent dependencies |
| 9 | `explain` | system understanding itself is uncertain | explain in plain words, then diff that explanation against the artifacts |
| 10 | `oob` | everything is green | enumerate failure classes not represented in the gate set and add the cheapest independent sensor |

Aliases: `/gauntlet`, `/gauntlet <op>`, “infinity gauntlet”, “gauntlet”, “audit the frame”.

## 3. ROUTING

Do **not** fire all ten operations by ritual. Select the smallest set whose trigger is actually present.

Default routes:

- proof/math uncertainty → `derive` + MIND; add `self` if authored by the evaluator.
- current/external factual uncertainty → `refresh` + SPACE.
- implementation claim → `audit` + POWER; add `oob` before “verified”.
- repeated failed approaches → `frame`; SPACE first for known alternatives, REALITY only after a named constraint defeats them.
- survivor/novelty claim → `costume` + SPACE; REALITY classifies what remains novel.
- lots of activity, unclear progress → `redirect` + TIME.
- handoff / context reset / concurrent build → `boundary` + POWER.
- unclear architecture or documentation → `explain`; use MIND/POWER as appropriate.

FOIL may call the Gauntlet. The Gauntlet may recommend FOIL or specialist lanes. Neither creates independent evidence merely by agreeing with itself.

## 4. OPERATION CONTRACT

Every fired operation produces:

1. **Trigger** — the exact observed condition.
2. **Contention** — the proposition under audit.
3. **Evidence inspected** — artifact/source/run actually seen.
4. **Counterevidence / alternative** — strongest live challenger.
5. **Result** — `CLEARED`, `ISSUE`, `UNKNOWN`, or `UNAVAILABLE`.
6. **Consequence** — what may proceed, what must change, or what remains blocked.
7. **Next cheapest discriminator** — only if unresolved.

No operation may convert missing evidence into a negative verdict.

## 5. FALSE-GREEN DEFENSE

Before saying `verified`, `fixed`, `safe`, `complete`, `all green`, or equivalent:

- state what the checks actually observe;
- name at least one relevant failure class outside that observation boundary, or show why the declared scope is exhaustive;
- use an independent verifier where one is available;
- do not count same-model agreement, repeated prose, or multiple correlated agents as independent verification.

A verification must not define its own scope.

## 6. REPETITION / FRAME CHECK

When two or more attempts fail:

1. List the failed attempts in one line each.
2. Abstract the common representation, assumption, dependency, or search space.
3. Ask what all failed attempts were **forbidden from changing**.
4. Generate one route that changes that invariant.
5. Prefer a known method from another field before inventing a new mechanism.
6. If the attempts are actually progressing on different subproblems, do not falsely call them repetition.

## 7. COSTUME CHECK

For a surviving or “new” design:

1. Write the mechanism without project-specific names.
2. Search/recall the closest established class.
3. Compare mechanism, assumptions, input/output contract, and failure modes.
4. If the delta is only renaming, packaging, or parameter choice, call it adaptation rather than novelty.
5. If evidence is insufficient, output `NOVELTY UNKNOWN`.

## 8. DERIVE CHECK

For every load-bearing number or label:

- identify the rawest accessible source;
- recompute with code/calculator/solver when feasible;
- preserve units, denominator, exclusions, and uncertainty;
- report disagreements instead of averaging them away;
- label inherited summaries as inherited until checked.

## 9. SELF CHECK

Before relying on your own interpretation:

- freeze your current prediction or interpretation;
- name a concrete observation that would refute it;
- declare whether you authored, selected, filtered, or summarized the object being judged;
- seek a verifier with a different failure mode when the claim is important.

## 10. REDIRECT CHECK

Ask:

> What is the one unresolved quantity, behavior, or proposition on which the decision actually depends?

Then classify current work:

- **UPSTREAM** — directly changes/estimates the load-bearing unknown.
- **SUPPORTING** — necessary prerequisite with a clear dependency edge.
- **COSMETIC** — improves presentation/robustness without reducing the key uncertainty.
- **OFF-PATH** — no evidence of a dependency edge.

Stop polishing when the core uncertainty remains untouched.

## 11. REFRESH CHECK

Currentness is a claim.

- For mutable local work: reread the authoritative file/state before acting.
- For software versions, policies, prices, schedules, public figures, releases, and other volatile facts: use a current source.
- For research claims: inspect the paper/source rather than relying on remembered summaries.
- Record the retrieval date or state version when it matters.

## 12. BOUNDARY CHECK

Before work crosses contexts:

- pin goal, inputs, outputs, invariants, interfaces, and unresolved assumptions in an artifact;
- state what is safe to mutate and what another live process/session may depend on;
- do not rely on chat-only memory for a cold build;
- if concurrency ownership is unknown, stop the conflicting mutation until ownership is resolved.

## 13. EXPLAIN CHECK

Explain the system in plain language from memory, then inspect the artifacts and diff:

- missing component;
- wrong dependency;
- wrong status;
- obsolete behavior;
- unclear ownership.

A mismatch can indicate either misunderstanding or a documentation defect; investigate which.

## 14. OUT-OF-BAND CHECK

Build a two-column table:

| gate observes | plausible failure it cannot see |
|---|---|
| unit tests | integration/environment behavior |
| static checks | runtime resource exhaustion |
| model judge | shared-model bias / hidden evaluator mismatch |
| benchmark average | subgroup or tail failure |
| source citation | source does not entail exact claim |

Add only the cheapest sensor needed for the high-impact unwatched failure.

## 15. OPTIONAL INTEGRATIONS

Optional automation is allowed only after existence is verified.

Examples include hooks, test runners, formal solvers, browser/search tools, code execution, telemetry, or an adversarial model backend. Their names and paths are environment-specific.

When an integration is absent:

- do not emit a shell command to a nonexistent file;
- do not silently substitute fake output;
- use portable mode or mark the step `UNAVAILABLE`;
- continue only if the remaining evidence is sufficient for the scoped claim.

## 16. SNAP — PORTABLE CONTRACT

`SNAP: <hard issue>` means an **intensive solve**, not an automatic multi-agent backend.

Public behavior:

1. Freeze the target and success condition.
2. Generate diverse independent candidate mechanisms.
3. Attack candidates with counterexamples and known-method search.
4. Execute/mechanically verify load-bearing steps where possible.
5. Maintain a kill list and do not recycle dead mechanisms without new evidence.
6. Return `SOLVED` only with claim-native verification; otherwise `STALLED` or `UNKNOWN`.

If an environment provides a multi-agent backend, it may accelerate these steps. No backend is assumed.

## 17. RELEASE GATE

The Gauntlet clears release only when:

- the relevant trigger set has been considered;
- all load-bearing claims have appropriate support or are explicitly unresolved;
- every required external integration was either verified present or treated as unavailable;
- no dead path is required for the stated behavior;
- the verification scope is explicit;
- unresolved high-impact issues are carried forward rather than hidden.

## 18. OUTPUT

Use this compact form:

**GAUNTLET**
- Fired: `<ops>`
- Claim/frame: `<what is being audited>`
- Evidence: `<what was actually checked>`
- Counterevidence: `<strongest live alternative>`
- Result: `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`
- Consequence: `<decision implication>`
- Next discriminator: `<only if needed>`

The Gauntlet is an audit instrument, not an authority oracle.
