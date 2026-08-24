# FOIL Codex dose-response benchmark — development report

**Evidence label:** `OBSERVED_IN_THIS_PILOT`  
**Pairs:** 18 across 3 items and six configurations  
**Boundary:** exploratory matched prompt-contract evidence, not a superiority or deployment claim.

| Configuration | BASE | FOIL | FOIL only | BASE only | Paired difference | McNemar p |
|---|---:|---:|---:|---:|---:|---:|
| LUNA_LOW | 66.7% | 33.3% | 0 | 1 | -33.3% | 1.0000 |
| LUNA_HIGH | 66.7% | 100.0% | 1 | 0 | +33.3% | 1.0000 |
| TERRA_LOW | 66.7% | 66.7% | 0 | 0 | +0.0% | 1.0000 |
| TERRA_HIGH | 66.7% | 66.7% | 0 | 0 | +0.0% | 1.0000 |
| SOL_LOW | 100.0% | 66.7% | 0 | 1 | -33.3% | 1.0000 |
| SOL_HIGH | 66.7% | 66.7% | 0 | 0 | +0.0% | 1.0000 |

## Overall

- BASE accuracy: 72.2%
- FOIL accuracy: 66.7%
- Paired risk difference: -5.6%
- Discordant pairs: 3 (FOIL only 1, BASE only 2)
- Exact McNemar p: 1.0000
- Exact item-cluster sign-flip p: 1.0000

## Interpretation boundary

Three-item development observation of a bundled FOIL prompt-contract effect under independent stochastic calls. No general superiority, causal rescue/damage, validated dose, calibration, certification, personalization, controller, or deployment claim.

The draft same-run p-hat mixed model was not run because it uses an outcome-derived regressor and three items cannot support a fitted dose-response claim. Configuration order is descriptive only.
