# FOIL v5 / Mirror 0.6.0-rc4 validation report

Date: 2026-08-24
Implementation freeze: `82cb73d2af2ed50ab8e7f893bbf8bbde2bf4c4e3`

## Completed software boundary

RC4 closes the remaining latest-plan implementation seams without changing
FOIL's authority ceiling:

- `foil_v5_pipeline.py` provides the reusable strict-compiler → deterministic-
  scanner → adaptive-shadow-route → optional observational-ledger path and
  binds the existing pure host finalizer to the exact A0.
- `foil_formalization_admission.py` and `foil_formalization_routing.py` admit an
  externally generated obligation spec only after exact route/schema/spec
  binding, fresh route-scoped calibration, conservative fidelity and extraction-
  recall bounds, complete mutation controls, independent per-instance checks,
  mechanical equivalence, and measured error correlation.
- `foil_promotion_gates.py` turns an exact candidate-bound, preregistered
  partition/domain/metric matrix into fail-closed Gate 1/2/3 receipts. It does
  not collect data.
- `foil_later_studies.py` freezes and validates the required arms for profile P0,
  RQ-26, the model-strength ladder, history policy, and human complementarity.
  Contract completeness is explicitly non-efficacy and non-promotion.

The core compiler still never reads prose. No NL-to-obligation generator is
included. The normal adaptive controller still rejects unadmitted generated
obligations. Every new surface is host-invoked, digest-bound, A0-preserving,
non-executing, and separate from Gauntlet and Mastermind.

## Executed verification

| Check | Result |
|---|---|
| New focused suites | **18/18 passed** |
| Complete repository suite | **729 tests passed in 59.174 s** |
| Python compile-all | **passed** |
| Staged whitespace check | **passed** |
| RC4 small pilot | **6/6 passed** |

The preregistered pilot was committed before execution. Its report SHA-256 is
`df30671e506d5e7f352cd4cd42cced2fd1683827ce3ba732fa2f17efb66dcf53` and its
protocol SHA-256 is
`4e2699477e8893757bd6524cc90df71b5455135b80e027331da0e48cb82b3849`.

The six cases cover host-declared defect routing, correct-answer stand-down,
admitted generated-origin retention, incomplete-mutation rejection,
development-gate non-promotion, and development-study non-promotion. Recorded
provider calls, network calls, token spend, candidate generations, and answer
mutations were all zero.

## Evidence status

This validates software structure and executable integration only. The small
formalization calibration is a three-row synthetic fixture. It is not an audit,
does not estimate a production fidelity floor, and does not open any generated
route.

The following remain correctly **UNRUN / NOT PROMOTED** because their external
data do not exist in this repository:

- Gate 1B lock evaluation and Gate 1C prospective confirmation;
- Gate 2 repair benefit/damage and Gate 3 Ditto execution efficacy;
- real formalization fidelity, extraction recall, and real-claim coverage;
- profile P0 efficacy and P1/P2 activation;
- RQ-26, model-ladder, history-policy, and human-complement outcomes;
- smart-monitor behavioral benefit.

Those are empirical research tasks, not missing software wiring. Their evaluators
now fail closed on incomplete or development-only evidence rather than allowing a
green unit test to masquerade as promotion.
