# FOIL HLE active-route 20-item pilot

Status: **PREREGISTERED SMALL HISTORICAL-CORPUS PILOT**
Date: 2026-08-26

## Question

On twenty previously unused, public, text-only HLE subset items, what does active
FOIL do under (a) reasoning-only execution and (b) execution with read-only web
search and sandboxed computation available?  When tools are available, when are
they actually used, which type is used, how many times, and where do their tokens
enter the run?

## Dataset and selection

- Source: Science-Star HLE subset at pinned repository commit
  `4abe1db2d6d0920aa0a6236ee2f81de872adafa5`.
- Expected source SHA-256:
  `7e6deb84eafffaea128823ae53f9d7ee9ebfa7aaf77ff465f5d7df595606a361`.
- Exclude every HLE ID already named by the earlier public and HLE-Verified
  pilots, image-dependent rows, malformed rows, and questions over 6,500
  characters.
- Rank remaining items by descending question length, with SHA-256 of
  `20260826:HLE_ACTIVE_20:<id>` as the tie-break.  Take the first twenty.
- Alternate the ranked rows between `FOIL` and `FOIL_TOOLS`, producing ten
  distinct items per arm.  The arms are disjoint; their accuracy difference is
  descriptive and **not** a same-item causal estimate.

Gold is not written during preparation and is not supplied to model calls.
Predictions and public receipts must be committed before scoring refetches gold.

## Configurations

Every selected item is run once with each configuration:

1. `TERRA_HIGH`: `gpt-5.6-terra`, high reasoning effort;
2. `LUNA_LOW`: `gpt-5.6-luna`, low reasoning effort;
3. `LUNA_HIGH`: `gpt-5.6-luna`, high reasoning effort.

This is sixty result rows.  The provider is nondeterministic and there are no
replicates, so per-configuration differences are smoke evidence only.

## Active routing

This experiment does not mutate `foil_adaptive_route` or pretend its shadow
signal already carries production authority. A separate benchmark-only executor
consumes a frozen `ShadowRouteDecision` and actively executes its `FULL` route.
For HLE, the host uses `foil_policy.RuntimePolicyV2` over task properties:

- `FOIL`: closed-book technical reasoning; host execution route `FULL`;
- `FOIL_TOOLS`: external-retrieval uncertainty; host execution route `FULL`,
  with retrieval enabled inside that route.

The resulting policy trace and host route are frozen in every unit.  The model
must follow that route; a mismatched route is invalid.  This activates the
recommended work in the benchmark while leaving production authority off.

## Tools

- `FOIL`: no tools.  Any observed tool event invalidates the row.
- `FOIL_TOOLS`: read-only native `web_search` and sandboxed
  `command_execution` are available.  Other tool types invalidate the row.
- Tools are available, not mandatory.  FOIL must use the minimum sufficient
  capability.  A no-tool decision remains informative.
- The harness derives tool use from Codex JSONL events.  It does not trust the
  response's self-report.  Public receipts retain query/command metadata,
  ordering, status, output size and output digest; full tool output stays in the
  ignored private run directory.

## Tokens

Each result unit first freezes one closed-book, tool-free A0 and then executes
one active FOIL FULL-route call over that A0. The tool arm differs only in its
read-only tool capability. Therefore 60 result units plan 120 provider calls:
60 A0 calls and 60 active-route calls. If an A0 call is invalid, its dependent
route is not launched, the row remains invalid, and the lower actual count is
reported without retry.

There is no artificial model-output or reasoning-token cap in either arm.  The
harness passes no `max_tokens`, `token_budget`, or equivalent option.  It records
provider-reported input, cached-input, cache-write-input, output, and
reasoning-output tokens, plus wall time, per row.  Total means input plus output;
cached input is reported separately and is not added a second time.

## Metrics

- strict whitespace/case-normalized exact-match accuracy;
- route counts and route validity;
- tool-use rate, calls per row, tool types, search queries, commands, ordering,
  completion/failure state, output characters and hashes;
- tool-use by category, configuration, correctness, and route;
- A0, active-route, and combined input/cached/cache-write/output/reasoning-output
  tokens and wall time;
- accuracy and token summaries by arm and configuration.

No semantic model judge is used.  This may undercount equivalent mathematical
answers and is reported as a scoring limitation.

## Authority and non-claims

- Benchmark answer selection is active.  It is not shadow replay.
- Production activation, profile writes, external write tools, promotion, and
  calibration remain unauthorized.
- The run does not establish HLE population accuracy, a causal tool benefit,
  frontier-model recall, or a production token target.
