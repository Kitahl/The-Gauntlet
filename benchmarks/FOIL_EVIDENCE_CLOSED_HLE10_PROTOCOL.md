# FOIL evidence-closed HLE-10 Terra-High diagnostic protocol

**Date:** 2026-08-28
**Status:** preregistered diagnostic; default-off; unadmitted

## Question

On the same ten text-only HLE questions previously assigned to the Terra-High
tools arm, can the new evidence-closed FOIL route improve the frozen Terra-High
direct answers without damage, while remaining below a caller-supplied session
ceiling of 250,000 newly consumed tokens?

This is not a fresh DIRECT-vs-FOIL efficacy benchmark. DIRECT is the already
frozen historical Terra-High A0. Reusing it avoids approximately 204,000 new
tokens. Provider nondeterminism and exposure to these public questions make the
result a historical frozen-A0 diagnostic only.

## Frozen design

1. Prepare exactly the ten `FOIL_TOOLS` questions and Terra-High A0 answers
   from the committed 2026-08-26 receipts. The prepare path never reads gold.
2. One Terra-High/high batch call receives all ten questions, no A0, and no
   gold. It may use web search only and must return at most one candidate, one
   HTTPS URL, and one verbatim quote per question.
3. The host rejects any non-web tool event, more than ten tool events, unsafe
   URL, non-text response, or quote not found in a host-fetched source page.
4. Two separate Terra-High/high comparison batches receive the same frozen
   question/evidence pairs. One receives only A0 claims; the other receives
   only candidate claims. Neither receives candidate origin, counterpart, or
   gold. Comparator calls may use no tools.
5. FOIL's existing evidence packet, claim comparator, and strict answer
   selector perform the final benchmark-only decision. B requires full support
   and A0 requires a critical contradiction at confidence at least 95%.
6. If any boundary fails, preserve A0. Production and promotion authority stay
   false. Raw fetched pages are never persisted.
7. Predictions and public receipts must be committed before the scorer opens
   the historical gold artifact.

## Cost law

The 250,000 figure is a caller-supplied ceiling for this session, not a product
constant and not a per-call output cap. The CLI exposes no trustworthy
mid-generation total-token limiter, so the harness stops before launching a
later batch when the remaining allowance is below the prelaunch reserve. A
single provider call can still overshoot; this limitation is explicit.

New token accounting is provider-reported `input_tokens + output_tokens`.
Cached input is reported separately and is not double-counted. Historical A0
tokens are reported but excluded from newly consumed tokens.

## Primary outputs

- frozen-A0 correct, final correct, net rescues, damages;
- answer changes and abstentions/fallbacks;
- quote-bind success and comparator-support counts;
- search/tool event counts;
- per-stage and total newly consumed tokens;
- exact provenance and digest conservation.

No score threshold promotes this route. Ten reused public questions cannot
calibrate semantic entailment, estimate generalized HLE lift, or establish the
22/60 target.
