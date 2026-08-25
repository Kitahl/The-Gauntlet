# FOIL R1.7 provenance repair — results

Verdict: **FAIL_NOISY; route remains default-off and unadmitted**

## Frozen receipts

- Scanner/protocol commit: `aa377ad7381e580e1be0e3bf55b465caf6f7c8ac`.
- Label freeze commit: `6a5ee21195a8ec68f5eb091d134a6e8562f05f12`.
- Source SHA-256: `4bc62db838f8418365d51c627bd66294cbdca9fb7f01519cb13f0dce8c51580b`.
- Final report SHA-256:
  `f8c0c6f0b92ef9d9e0bc7bab35524b3966bca78e30d123e86cc0a1e4f9baf28d`.
- Runtime provider, model, bot, token, profile-write, answer-mutation,
  execution-authority, and promotion counts: all zero.

The first generated report used a syntactically valid but nonexistent commit
string (`aa377adf84e...`) and had digest `1718dcf4...`. It was rejected before
acceptance. Scanner outcomes were already exposed, so blindness was not
restored; only the receipt binding was regenerated with the actual frozen
commit. The runner now rejects any commit other than that exact value.

## Preregistered outcomes

| Measure | Result | Wilson two-sided 95% |
|---|---:|---:|
| Mutant detection | 27/28 (96.4%) | [82.3%, 99.4%] |
| Natural-miss detection | 2/6 (33.3%) | [9.7%, 70.0%] |
| Official-correct control flags | 7/20 (35.0%) | [18.1%, 56.7%] |

The preregistered decision is `FAIL_NOISY` because 7 false-fire controls exceed
the 4/20 failure threshold. The route remains `GENERATED_UNADMITTED`; nothing
was promoted and no answer was changed.

Natural detection by class was:

| Class | Detected |
|---|---:|
| `RESULT` | 1/1 |
| `OPERAND` | 1/1 |
| `SWAPOP` | 0/1 |
| `DROPSTEP` | 0/1 |
| `CONSISTENT_LOCAL` | 0/1 |
| `CONSISTENT_GLOBAL` | 0/1 |
| `FINAL` | no fresh support |

The six-class association was estimable but uninformative: Spearman `0.3162`,
exact two-sided permutation `p = 1.0` over 720 permutations; Pearson was also
`0.3162`. At this scale, high mutation kill again did not predict useful natural
detection.

## Failure analysis

All seven flagged official controls were provenance failures. Five had clean,
coherent rationales and expose fresh unsupported normalization classes:

- calendar conversion (`one week` to `7` days);
- word-number normalization (`two`, `four`, `seven`, `five`);
- inflectional scale language (`tripled` to factor `3`);
- written percentage language (`percent` to denominator `100`); and
- compound lexical fractions (`two thirds` to `2/3`).

Two official `is_correct` controls had the right final answer but defective
rationales: one reached six carrot sticks through unrelated operations, and one
mixed seven- and fourteen-day candy calculations while landing on the correct
difference. They are contaminated as clean-rationale false-alarm controls. A
strict sensitivity analysis removing both still leaves 5/18 clean false fires
(27.8%, Wilson [12.5%, 50.9%]), so the failure verdict is unchanged.

The recall loss is structural. V2 widened admissible numeric sources but still
checks only exact local arithmetic, source membership/derivation, and final
consistency. The four missed natural errors used internally exact, sourced
numbers inside the wrong transformation or omitted a required transformation.
This route cannot discover those semantic obligations, and widening provenance
cannot make it do so.

## Licensed conclusion

The v2 repair successfully removes all seven known R1.6 provenance false-fire
shapes in development tests. That improvement did not generalize enough to the
fresh sample, and recall fell sharply on structural natural errors. R1.7 is a
useful negative result: literal/derivation provenance is not a sufficient
standalone discovery route, and the near-perfect mutant score remains a poor
proxy for historical natural-miss detection.

No v3 tuning is performed on these now-exposed rows. Any successor must first
define a new non-overlapping sample and should separate lexical normalization
from semantic transformation coverage. This result is historical-model smoke,
not calibration, route admission, frontier recall, or a prevalence estimate.
