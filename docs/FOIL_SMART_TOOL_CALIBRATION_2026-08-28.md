# FOIL smart-tool calibration — 2026-08-28

Status: **implemented development calibration; no promotion authorized**.

## Outcome

FOIL now derives smart-tool utility from the benchmark owner's requested score
and token envelope. It does not contain a product-wide token cap. For the
current HLE development target:

- rows: 60;
- baseline: 11 correct;
- target: 22 correct;
- caller envelope: 250,000 total provider tokens;
- required net rescues: 11;
- break-even token value per net rescue: `floor(250000 / 11) = 22,727`.

Damage is priced at twice a rescue because the existing promotion law permits
at most 0.5 damages per rescue. Invalid evidence is priced at half a rescue. A
route must clear a 5% conservative-utility margin using a 95% Jeffreys interval,
not a model confidence score.

The cost side remains route-specific. Each `ToolContract` declares its maximum
input, cached-input, output, latency, monetary, and privacy cost before launch.
A harder route may ask for a larger envelope, but its larger cost directly
reduces its prelaunch utility. The outer `BenchmarkTokenLedger` still enforces
the caller's total session envelope.

## Frozen-evidence decisions

| Route | Evidence | Calibrated decision |
|---|---:|---|
| no-tools second pass | 30 attempts, 2 rescues, 2 damages, 793,077 added tokens | **STAND_DOWN**; conservative utility −36,727 tokens/launch |
| unrestricted retrieval second pass | 30 attempts, 4 reported rescue rows | **UNCALIBRATED**; none of the four rescues is cleanly attributable to saved tool evidence |
| deterministic active verify on HLE replay | 3 applications, 0 tokens | benchmark use remains enabled; production admission is unearned |

The four historical tool-arm rescue rows reduce to two distinct questions:

- Artin-group count: both traces searched or cited a copy of the HLE benchmark;
  the result is leakage-contaminated and cannot calibrate scholarly retrieval.
- Fermi-gas fugacity: both traces claimed a numerical solve, but every saved
  computation attempt was rejected and no search-result passage was retained.
  The answer may be correct, but the route cannot be mechanically credited.

See the hashed raw-trace audit and calibration reports in
`benchmark_runs/2026-08-28/hle_rescue_trace_audit/report.json` and
`benchmark_runs/2026-08-28/smart_tool_target_calibration/report.json`.

## No-tools interjection boundary

Without tools, FOIL can ask the model for a blind rival, a different method, or
a narrow counter-check. That can move the model into a better reasoning basin;
the historical no-tools arm did this twice. It also damaged two correct answers.

The current RPS v0.6.2 policy therefore preserves A0:

- agreement can support A0 but is not proof;
- disagreement causes abstention;
- B cannot replace A0 without an independent discriminator;
- factual information absent from the model context cannot be retrieved without
  a retrieval tool.

Consequently, no-tools interjection is useful for uncertainty signaling and for
deterministically checkable contradictions. It is not admitted as a general HLE
answer-repair route.

## Remaining gate

Before a retrieval candidate may replace A0, FOIL still needs admissible evidence
that a retained source passage supports the candidate claim. A model-only
entailment judgment remains `SUPPORT_ONLY` under the current evidence law. The
next retrieval experiment must therefore preserve source passages, exclude the
benchmark corpus and answer-bearing queries, execute any claimed computation,
and freeze the candidate before scoring.
