# FOIL evidence-closed HLE-10 Terra-High diagnostic

- Frozen A0: **1/10**
- Final: **1/10**
- Rescues / damages: **0 / 0**
- Answer changes: **0**
- Exact quote-bound rows: **0**
- Newly consumed tokens: **184099**
- Historical A0 tokens (excluded): **204224**
- Added-token overhead versus frozen A0: **90.15%** (combined **1.9015x**)

Constructor audit: one Terra-High call made 4 web-search events containing
10 queries, then returned ABSTAIN for all 10 items. It emitted no candidate,
URL, or quote, so the host had no quote-binding attempt to perform and launched
no semantic-comparison calls.

Classification: `HISTORICAL_FROZEN_A0_LIVE_ROUTE_DIAGNOSTIC`. No production or promotion authority.
