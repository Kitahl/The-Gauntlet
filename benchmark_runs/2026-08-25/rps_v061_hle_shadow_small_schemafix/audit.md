# Independent audit and interpretation

Audit result: `PASS`

- Results SHA-256: `00fb0d16b016c39ff58c671a8f41533ad2e381fe95ef13516cd84e5d649324db`
- Scored rows: 4
- Successful schema-fixed provider calls: 6 (2 controls, 4 observers)
- Prior rejected-schema request: 1, no answer and zero recorded token usage
- Tool calls: 0
- Profile writes: 0
- Answer mutations: 0
- Deterministic transition cases: 6/6

The scorer result was independently reconstructed from the locked predictions,
source rows, and receipts. All three summary slices were recomputed independently.

## Gold-key qualification

The array-transformation item has an independent executable audit establishing E
as the unique exact answer. On that item, the shadow gate behaved directionally
correctly in both configurations:

- Terra High: correct frozen E -> `FAST_ACCEPT`;
- Terra Low: wrong frozen B -> `ABSTAIN`.

The neural-network item retains only its HLE source key A; its original rationale
was already qualified as invalid for empirical-soundness reasons. On that weaker
keyed item:

- Terra High: source-keyed A -> `ABSTAIN`;
- Terra Low: C against source key A -> `FAST_ACCEPT`.

Therefore the reported `1/2` unsafe-fast-accept count is source-keyed, while the
one independently executable wrong answer was not fast-accepted. Neither result
is large enough to support calibration or promotion.

## Load-bearing finding

The deterministic hinge gate fixes the old structural defect: an explicitly
non-discriminating pass cannot fast-accept. It does not validate the semantics of
a model-authored hinge, expected outcome, or observation. On the surviving unsafe
row, the same model supplied a purported exact relation, predicted that it
distinguished the candidate, and reported that the candidate matched it. The
controller could enforce the transition law but could not independently verify
those three semantic claims.

The separate observer also added 97,840 tokens to a 101,454-token frozen BASE,
for a measured BASE-plus-observer multiplier of `1.9644x`. This implementation
therefore remains default-off and shadow-only.
