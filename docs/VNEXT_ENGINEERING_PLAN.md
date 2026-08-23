# The Gauntlet vNext — typed runtime engineering plan

Baseline: `Kitahl/The-Gauntlet` `main` commit `ba03be52588a81356540611c792726db3f0e874d`, release tree `0b9ecde6df507efc35a4f8c44b91261f755c81d9`, research software `v0.5.0`.

## Goal

Turn the existing research-method specifications into a typed, stateful, evidence-producing, runtime-verifiable control system without weakening the existing evidence boundaries, privacy guarantees, or Gauntlet+FOIL repository boundary.

## Non-negotiable invariants

1. **Specification is not evidence.** A `SKILL.md` can define an obligation but cannot self-certify it.
2. **No raw prompt persistence in the generic runtime.** Generic hooks persist one-way hashes plus small structured metadata only.
3. **No raw generic tool-output persistence.** Engineering/verifier receipts persist output hashes, exit status, timing, tool identity, and named coverage.
4. **Missing capability is explicit.** `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE` are distinct states.
5. **Claim-native verification.** Proof, discovery, synthesis, engineering, evaluation, assurance, preflight, review, and adaptation remain separate obligations.
6. **FOIL may adapt routing; it cannot create factual warrant by itself.**
7. **Mastermind remains external.** No Mastermind package, hook, state, skill, or runtime import is introduced.
8. **Backward compatibility.** Existing Gauntlet hooks/FOIL profiles continue to function; the typed runtime layers around them.
9. **No pseudo-precision.** Meditate uses quantitative VOC only when the caller supplies defensible probabilities/utilities/costs; otherwise it uses labeled ordinal heuristics or returns `UNKNOWN`.
10. **No vote-as-truth.** Council exposes correlation/provenance and requires a direct control before claiming marginal Council value.

## Shared architecture

Every runtime component exposes the same five layers:

1. **SPEC** — the obligation owned by the component.
2. **STATE** — typed, machine-readable state and events.
3. **ACTION/TOOL** — the actual evidence-producing method.
4. **RECEIPT** — content-addressed record of what was done and observed.
5. **VERDICT** — scoped `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE` result.

Core files:

- `tools/egrt_types.py` — canonical enums/dataclasses/hashing.
- `tools/egrt_store.py` — private atomic state/receipt/event store.
- `tools/egrt_hook.py` — privacy-preserving hook event adapter.
- `tools/soul_runtime.py` — obligation routing and release gate.
- `tools/egrt_runtime.py` — status/coverage CLI.

## Build order

### Phase A — freeze pipeline first

1. Define runtime schema and verdict semantics.
2. Define the end-to-end task pipeline.
3. Define per-component current workflow and vNext workflow.
4. Define integration boundaries and failure semantics.
5. Define mechanical tests before empirical benchmarks.

### Phase B — common substrate

Implement types, private store, receipt hashing, event hashing, task/obligation lifecycle, release gate, and hook adapter.

### Phase C — components

- Gauntlet: ten-operation support registry + structured monitors.
- Meditate: explicit DecisionState + VOC/ordinal stopping logic.
- Council: 3–6-seat commit/reveal state machine + provenance overlap + controls.
- Mind: proof-obligation records + exact arithmetic/Z3 adapters.
- Space: multi-index scoped search plan + dedup/saturation/absence boundary.
- Reality: machine-readable candidate + prior-art admission gate + diversity diagnostics.
- Power: explicit verification plan + no-shell command execution + hashed receipts + coverage matrix.
- Time: paired binary analysis + exact McNemar + Wilson intervals + Holm correction + exclusion ledger.

### Phase D — wiring

1. SessionStart initializes typed runtime before Gauntlet/FOIL state.
2. UserPromptSubmit logs only prompt digest/explicit aliases, then FOIL computes relevance.
3. PreTool/PostTool log hashed structured events around existing Gauntlet safety hooks.
4. Stop runs existing Gauntlet boundary check, then the typed Soul release gate when an explicit active task exists.
5. Existing state remains under `.egrt/state/` and gitignored.

### Phase E — verification

Before any efficacy benchmark:

- unit-test schema/state/receipt lifecycle;
- verify permissions and privacy behavior;
- mutation/hazard-test all automatic Gauntlet monitors;
- test Meditate quantitative and ordinal paths;
- test Council commit tampering/reveal/correlation/control requirements;
- test Mind exact arithmetic and missing-tool semantics;
- test Space `NOT_FOUND_WITHIN_SCOPE` boundary without claiming absence;
- test Reality cannot admit without prior-art evidence;
- test Power missing tool/failing tool/passing tool receipts;
- test Time paired statistics against known cases;
- test Soul release gate refuses missing load-bearing receipts;
- run existing repository validation, security and portability gates.

## Migration strategy

This is additive first. Existing `SKILL.md` semantics remain authoritative specifications. New engineering documents define how those specifications are implemented. Only after the typed runtime is stable should old ad-hoc runtime paths be retired or folded into it.

## Empirical phase — explicitly later

After implementation is frozen:

- Gauntlet OFF vs ON with matched model/tool budget;
- Meditate OFF vs ON with computation accounting;
- Council DIRECT vs VOTE vs COUNCIL with matched total budget;
- Gem-specific direct same-tool baseline vs routed Gem;
- whole-system BASE vs typed-runtime pipeline;
- preregister exclusions, contamination, stop rules, analysis, and primary endpoints.
