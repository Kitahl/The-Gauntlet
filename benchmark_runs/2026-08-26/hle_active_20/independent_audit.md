# FOIL HLE active-route independent audit

Rows: 60; provider calls: 119; tools: 151.
A0: 11/60; final: 14/60.
Rescues: 6; published damages: 2; correct A0 withheld by invalid final: 1.
Tokens: A0 1177464; route 9736511; total 10913975.
Confound: 13 local skill reads ({'foil': 2, 'mathbot': 11}); external/free bot events: 0.

| Slice | A0 correct | Final correct | Rescues | Damages | Withheld | Tools | Total tokens | Mean multiplier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LUNA_LOW::FOIL | 1/10 | 2/10 | 1 | 0 | 0 | 0 | 431224 | 2.421x |
| LUNA_LOW::FOIL_TOOLS | 1/10 | 0/10 | 0 | 0 | 1 | 28 | 1624781 | 8.914x |
| LUNA_HIGH::FOIL | 2/10 | 2/10 | 1 | 1 | 0 | 0 | 462290 | 2.316x |
| LUNA_HIGH::FOIL_TOOLS | 2/10 | 4/10 | 2 | 0 | 0 | 86 | 5645948 | 26.398x |
| TERRA_HIGH::FOIL | 4/10 | 3/10 | 0 | 1 | 0 | 0 | 479904 | 2.412x |
| TERRA_HIGH::FOIL_TOOLS | 1/10 | 3/10 | 2 | 0 | 0 | 37 | 2269828 | 10.980x |
| FOIL | 7/30 | 7/30 | 2 | 2 | 0 | 0 | 1373418 | 2.385x |
| FOIL_TOOLS | 4/30 | 7/30 | 4 | 0 | 1 | 151 | 9540557 | 15.431x |
| OVERALL | 11/60 | 14/60 | 6 | 2 | 1 | 151 | 10913975 | 9.019x |

The two arms contain disjoint questions. Arm differences are descriptive, not causal.
The tool arm is local-skill-confounded and is not a pure FOIL-plus-generic-tools estimate.
Invalid final rows count as wrong. A valid A0 remains in the A0 denominator.
