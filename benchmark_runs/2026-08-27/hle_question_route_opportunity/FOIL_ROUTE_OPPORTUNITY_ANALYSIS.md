# FOIL HLE question-only route-opportunity diagnostic

**Classification:** historical development diagnostic; not efficacy, calibration,
or promotion evidence

## Outcome

FOIL's frozen question-only predictor found at least one plausible registered
evidence route for **17/20 distinct HLE questions**. Those 17 questions account
for **40/49 historical A0-wrong configuration rows** and **6/6 historical
rescues**. The other 3 questions account for 9 A0-wrong rows and no historical
rescues.

This rejects the narrow hypothesis that *question-level route opportunity* is
near zero on this development set. It does **not** establish that a named tool
can execute, that its output can adjudicate the claim, or that routing would
improve accuracy.

| Frozen status | Questions | Audit rows | A0-wrong rows | Historical rescues |
|---|---:|---:|---:|---:|
| `FOUND` | 17 | 51 | 40 | 6 |
| `UNSUPPORTED` | 3 | 9 | 9 | 0 |
| **Total** | **20** | **60** | **49** | **6** |

The 60 rows are three model/configuration observations over 20 questions; they
are not 60 independent questions.

## Overlapping capability hypotheses

| Capability | Questions flagged | A0-wrong rows | Historical rescues |
|---|---:|---:|---:|
| `CODE_EXECUTION` | 13 | 30 | 6 |
| `SYMBOLIC_COMPUTATION` | 11 | 26 | 6 |
| `FORMAL_PROOF` | 7 | 16 | 3 |
| `SCHOLARLY_SEARCH` | 7 | 17 | 5 |
| `WEB_SEARCH` | 3 | 7 | 0 |

These buckets overlap and must not be summed. They are positive structural
signatures, not verified applicability labels. In particular, the broad math
signature can nominate symbolic computation for a problem that a bounded
symbolic parser will later decline.

## Information and authority audit

- Prediction input used only `id` and `question`.
- A0, gold, expected output, correctness, answer labels, and unknown runtime
  fields are rejected by the closed question-input schema.
- Predictions were written and content-hashed before the scorer read the audit.
- Prediction SHA-256 (canonical artifact body):
  `bfcea1456ce893fa25618af90232116c3d661849b805b7cb3b84741699f06168`.
- Prediction file SHA-256:
  `cd1eb28ce3af78ea936df23fc923b2e008f92c987aadeedbdec7109c3cde7728`.
- Report SHA-256 (canonical artifact body):
  `2f3b86b97104d7b708d27e246878f920471ff6d20c3578555058bdcb50eaa05a`.
- Report file SHA-256:
  `2fd0167f2d5f7f2ab030c16a890e91fb5d9e44468c55f2e2650f2d10c7981c26`.
- Provider calls, model calls, tool calls, token spend, answer mutations,
  execution authorizations, and promotion changes: **all zero**.

## Known limitation found before scoring

The frozen v1 predictor missed the DFT overlap-add/overlap-save operation-count
question because it contains a numeric computation request without one of v1's
math-structure signatures. The artifact was not changed after this was noticed;
moving the rule after looking at outcomes would invalidate the freeze. Any v2
signature change must be versioned and evaluated on a new holdout.

## Decision

Do not run another broad model benchmark yet. Build and measure the smallest
runtime applicability probes behind the frozen candidates:

1. executable-language availability and bounded execution for code questions;
2. parseability plus exact-result checks for numeric/symbolic questions;
3. source-retrieval availability and receipt quality for current/legal and
   scholarly facts, without treating retrieval as answer correctness;
4. explicit decline for unsupported languages, unparseable mathematics, and
   semantic disputes.

Only a new holdout can estimate precision, coverage, rescue, damage, and token
value. The current diagnostic chooses what to test next; it cannot promote a
route.
