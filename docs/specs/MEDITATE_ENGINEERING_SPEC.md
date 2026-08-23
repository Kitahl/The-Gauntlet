# Decision Preflight / Meditate — engineering specification

## Obligation

Prevent execution from outrunning the represented decision/evidence state. Meditate is a metareasoning controller, not a ceremonial delay or extra opinion.

## Current workflow

`STILL -> GROUND -> ORIENT -> WEIGH -> RELEASE`

Current implementation is primarily specification-level.

## vNext state

`DecisionState` contains:

- goal and success condition;
- authoritative artifacts;
- supported facts;
- assumptions and refuters/cost-if-wrong;
- unknowns and decision sensitivity;
- candidate actions;
- one shared `current_best_eu` baseline when quantitative VOC is used;
- current blocker;
- explicit trigger flags.

## Triggers

Run only when one or more is explicitly represented: high stakes, irreversibility, stale authority, repeated failure, decision-sensitive unknowns, major disagreement.

## Decision rule

### Quantitative mode

Only when the caller supplies defensible probabilities, outcome utilities and computation costs against one shared current best expected utility:

`VOC(a) = E[max_d EU(d | O_a)] - max_d EU(d) - C(a)`.

- best positive VOC -> perform that computation;
- maximum VOC <= 0 -> RELEASE.

### Ordinal mode

When numeric quantities are not justified, compare explicit ordinal ranks for information gain, progress, risk reduction and cost. A unique dominating action may be recommended as `HEURISTIC`; otherwise return `UNKNOWN`.

## vNext workflow

1. STILL: freeze uncontrolled action generation for one control pass.
2. GROUND: register authoritative artifacts/versions/hashes.
3. ORIENT: define decision, success, constraints, stakes, reversibility.
4. WEIGH: represent facts/assumptions/unknowns/actions and run quantitative VOC or ordinal dominance.
5. RELEASE: ACT, RELEASE, or CONTINUE/UNKNOWN.
6. Emit a Meditate receipt; do not convert heuristic ranking into factual evidence.

## Runtime

`tools/meditate_runtime.py`

## Mechanical tests

- no trigger -> skip;
- probabilities must sum to one;
- positive VOC selects action;
- non-positive max VOC releases;
- incomplete model returns UNKNOWN;
- ordinal ties stay UNKNOWN;
- no pseudo-numeric VOC is invented.
