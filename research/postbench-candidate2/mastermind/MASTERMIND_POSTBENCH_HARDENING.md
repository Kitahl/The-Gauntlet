# Mastermind post-benchmark hardening

Authority: `PRE_REVIEW_ONLY`. Promotion authority: `NONE`.

This source tree is a descendant of `4.4.11-research-integration-candidate.1`. The blind benchmark continues to use the frozen candidate-1 ZIP; this post-benchmark hardening does not alter that arm.

Added mechanism:

- `mastermind_lib/repair_minimality.py` enumerates every repair plan induced by a frozen finite primitive-edit universe up to a declared edit-count cap. A global-minimum claim is emitted only when every policy-valid plan has an independently identified execution outcome and none is `UNKNOWN`. Selection is then exact over successful plans using the existing semantic-delta/touched-lines/edit-count ordering.

The scope is intentionally finite. This does not claim universal fault localization, an unbounded globally minimum repair, or causal certainty.
