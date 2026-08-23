# SESSION 4 — SCORE, DEEP RESEARCH, AND DESIGN FOIL vNEXT V2

Run this only after Sessions 1–3 are complete.

Before using it, replace:

- `<PASTE_SELECTION_FREEZE_SHA>`
- `<PASTE_BASE_RECEIPT_SHA>`
- `<PASTE_VNEXT_SPEC_SHA>`
- `<PASTE_VNEXT_RECEIPT_SHA>`
- `<PASTE_VNEXT_MM_RECEIPT_SHA>`

with the real values from `experiments/foil_vnext5/PROGRESS.md`.

Then copy everything below into a new ChatGPT session.

---

You are running the analysis stage of the FOIL vNext5 development experiment for The Gauntlet.

Repository:
`https://github.com/Kitahl/The-Gauntlet`

Frozen references:

- selection: `<PASTE_SELECTION_FREEZE_SHA>`
- BASE receipts: `<PASTE_BASE_RECEIPT_SHA>`
- vNext V1 specification: `<PASTE_VNEXT_SPEC_SHA>`
- vNext V1 receipts: `<PASTE_VNEXT_RECEIPT_SHA>`
- vNext V1 + Mastermind receipts: `<PASTE_VNEXT_MM_RECEIPT_SHA>`

This is an analysis/design session. All three conditions are now frozen, so you may inspect all three result branches and benchmark references.

Follow normal ChatGPT policies and connected-tool rules.

## 1. Verify experiment integrity

Confirm:

- the same five item IDs were used in all three conditions;
- the selection commit preceded the condition executions;
- vNext V1 was committed before the five item contents were read in Session 2;
- Session 3 used exactly the same frozen vNext V1 specification;
- the benchmark-specific tool regimes were matched;
- all 15 receipts exist;
- no condition silently changed its treatment during execution.

Report any integrity problem before interpreting scores.

## 2. Score the 15 runs

Use benchmark-native scoring where practical.

For each of the five items report:

- benchmark;
- reference answer/output;
- BASE answer and correctness;
- FOIL_VNEXT_V1 answer and correctness;
- FOIL_VNEXT_V1_MM answer and correctness;
- confidence by condition;
- tool cost by condition;
- vNext task regime;
- whether Mastermind changed the vNext candidate;
- whether that change helped, hurt, or was neutral.

Then report totals:

- BASE correct / 5;
- vNext correct / 5;
- vNext + Mastermind correct / 5;
- paired item-by-item wins/losses/ties.

Do not make significance or general-efficacy claims from n=5.

## 3. Classify failures by mechanism

For every incorrect result assign the most defensible primary category:

- DISCOVERY_FAILURE
- EVIDENCE_SELECTION_FAILURE
- REASONING_ERROR
- STATE_OR_REPRESENTATION_ERROR
- VERIFIER_SELECTION_FAILURE
- PREMATURE_COMMITMENT
- EXCESSIVE_VERIFICATION
- EXCESSIVE_ABSTENTION
- UNNECESSARY_CRITIQUE
- PROFILE_ROUTING_ERROR
- EXACT_OUTPUT_ERROR
- TOOL_OR_EXECUTION_ERROR
- OTHER

Distinguish:

A. current FOIL implementation defect;
B. missing runtime-policy mechanism;
C. weak/noisy profile evidence;
D. Mastermind interaction effect;
E. benchmark/harness artifact;
F. insufficient evidence to justify a change.

## 4. Audit current FOIL code

Inspect current FOIL source, tests, validation, calibration, and research files.

At minimum:

- `tools/foil_profile.py`
- `tools/foil_hook.py`
- `tools/foil_assessment.py`
- `tools/foil_layer2.py`
- `tools/foil_calibration.py`
- `tools/foil_domains.py`
- all relevant FOIL tests
- `research/FOIL_PERSONALIZATION_BASIS.md`
- `validation/FOIL_LAYER2_MASTERMIND_AUDIT.md`
- benchmark receipts and methodology docs

Map:

`observed failure -> current mechanism -> earliest missing/incorrect mechanism -> smallest possible repair`.

Do not assume more code is better.

## 5. Deep prior-art and GitHub code research

Search current papers and executable repositories.

At minimum inspect:

- DSPy GEPA
- DSPy MIPROv2
- DSPy SIMBA
- TextGrad
- metaTextGrad
- AgentSquare
- AFlow
- Agent Lightning
- Reflexion
- SiriuS

Also search for newer directly relevant systems.

For each candidate record:

- exact problem solved;
- algorithm/mechanism;
- repository URL;
- license;
- concrete relevant source files/classes/functions;
- feedback signal consumed;
- what is optimized: prompt, workflow, module selection, memory, tool policy, or weights;
- evaluation/train-dev-test separation;
- mechanism potentially transferable to FOIL;
- reason transfer may be inappropriate.

Pay special attention to:

- adaptive test-time compute;
- verifier routing;
- stopping rules;
- conditional critique;
- overthinking/degradation from extra reasoning;
- trajectory feedback and credit assignment;
- experience libraries/memory;
- stale-memory/profile interference;
- routing under uncertainty;
- optimization without contaminating held-out evaluation.

Create:

`research/FOIL_VNEXT_PRIOR_ART.md`

## 6. Run three Mastermind design loops

### Loop 1 — earliest causal defect

Find the earliest runtime/design defect best supported by:

- the 15 execution receipts;
- current FOIL source;
- prior art.

State the smallest test that could distinguish this explanation from alternatives.

### Loop 2 — attack the proposed repair

Construct a task class where the proposed fix could make FOIL worse.

Add a regression/adversarial test demonstrating the risk where possible.

### Loop 3 — minimal supported repair

Design the smallest repair that:

- addresses the supported defect;
- survives Loop 2;
- preserves FOIL's evidence/personalization boundaries;
- does not add universal critique, retrieval, or tool usage without evidence.

## 7. Decide what changes are supported

Produce these sections explicitly:

### SUPPORTED FIXES
Changes supported by multiple pieces of evidence.

### LIKELY BUT UNCONFIRMED HYPOTHESES
Plausible changes that need more data.

### DO NOT CHANGE
Current FOIL mechanisms that the evidence does not justify altering.

### BENCHMARK / HARNESS ISSUES
Problems in measurement rather than FOIL.

### NEW DATA REQUIRED
Experiments needed to resolve uncertainty.

## 8. Design FOIL_VNEXT_V2_CANDIDATE

Only if supported by the evidence, create:

- `experiments/foil_vnext_candidate_v2/SPEC.md`
- experimental implementation under `experiments/foil_vnext_candidate_v2/`
- matching automated tests

Prefer explicit components only where supported, such as:

- TaskState
- UncertaintyLedger
- RuntimePolicy
- EffortBudget
- VerifierPolicy
- ProfileInfluenceGate
- StopPolicy
- OutcomeTrace

For every proposed component state:

- problem fixed;
- evidence;
- input;
- output;
- state transition;
- failure modes;
- tests;
- status: REQUIRED, EXPERIMENTAL, or DEFERRED.

Do not silently replace production FOIL.

## 9. Preserve the evaluation boundary

The five vNext5 tasks are now DEVELOPMENT DATA.

Do not use them as held-out evidence for V2.

Create a fresh preregistered V2 evaluation protocol using new unseen items:

`benchmarks/FOIL_VNEXT_V2_HELDOUT_PROTOCOL.md`

## 10. Final deliverables

Create:

- `validation/FOIL_VNEXT5_ANALYSIS.md`
- `research/FOIL_VNEXT_PRIOR_ART.md`
- `experiments/foil_vnext_candidate_v2/SPEC.md` if supported
- experimental V2 code/tests if supported
- `benchmarks/FOIL_VNEXT_V2_HELDOUT_PROTOCOL.md`

The final response should summarize:

1. BASE vs vNext vs vNext+MM results;
2. strongest supported failure mechanism;
3. supported code changes;
4. changes explicitly rejected/deferred;
5. V2 held-out test plan;
6. commit SHA(s) containing the analysis and any experimental V2 code.