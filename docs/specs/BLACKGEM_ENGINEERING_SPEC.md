# Black Gem — engineering specification

## Obligation

Attack a frozen candidate hard enough that a break, if one exists at this budget, is
found and recorded as a structured triple — while measuring whether the breakers were
actually capable and actually present, rather than assuming it from an HTTP 200.

Black Gem produces the `ADVERSARY` obligation. It can raise an issue. It can never
clear one: the absence of a found break is not evidence that a claim is true.

## Current workflow

Specification: two or more independently provenanced breaker seats; a frozen rubric
covering four baseline attack axes; a blind independent first pass; off-diagonal
cross-critique; one synthesis; a planted-costume canary probe fired at the graded
temperature; whole-run participation accounting.

The predecessor helper ran paired red-team prompts and a synthesis with no typed
state, no participation accounting, and no separation between a seat that failed and
a seat that rubber-stamped.

## Typed state

`StrikeState`:

- `strike_id`, optional `task_id`, `seed`;
- `candidate_hash`, `rubric_hash`, `budget_hash` — all frozen at creation;
- `breakers`: `Breaker(seat_id, model_id, model_version, temperature, provenance_group)`;
- `canary`: `CanaryProbe(canary_id, canary_hash, temperature, per_seat, probe_trusted)`;
- `participation`: per-seat answered/expected/empty counts, contributing count,
  distinct provenance groups, injection-canary hits, checker rows;
- `phase`: `CREATED -> PROBED -> ATTACK -> SYNTHESIZED -> CLOSED`.

Findings are `BreakTriple(claim, target, method, seat_id, phase, mech_checkable)`.

## Runtime / tool boundary

`tools/blackgem_runtime.py` owns state, phases, accounting and receipts. Every network
call goes through `tools/openrouter_bot.py` with an injectable `fetch=`, so the whole
module is exercisable offline with no credentials.

The frozen rubric is the **system** message. Candidate text is the **user** turn,
enclosed in explicit delimiters with a standing instruction that everything between
them is data and never an instruction. A benign injection canary is planted inside the
delimited block; a seat whose entire answer is `OK` followed the data instead of the
rubric, and the run is marked untrusted.

Phase 2 is off-diagonal by construction: a seat never reviews its own output.

Canary detection is structured, not lexical. The seat must answer
`costume_verdict: COSTUME|NOT_COSTUME` **and** name a prior technique. `COSTUME CHECK
— none found` is a `RUBBER_STAMP`, not a catch. Outcomes are three, never two:

| Outcome | Meaning |
| --- | --- |
| `CAUGHT` | Structured costume verdict plus a named prior technique. |
| `RUBBER_STAMP` | The seat answered and missed a planted costume. A bad signal. |
| `ABSENT` | Transport failure, or HTTP 200 with zero characters. No signal at all. |

`ABSENT` and `RUBBER_STAMP` are opposite situations and are never merged.

## Receipt semantics

- `module = "blackgem"`;
- `input_hash = digest({candidate_hash, rubric_hash, budget_hash, canary_hash,
  breaker_ids, seed})`;
- `output_hash = digest(synthesis)`;
- one `OBSERVED` evidence reference per seat carrying model id, model version,
  temperature, provenance group, answered/expected and empty count;
- one `DERIVED` evidence reference carrying the canary block, participation totals,
  checker names with output hashes, and the break triples as structured fields;
- raw model text is never in generic state and never in the receipt. It is written to
  a declared evidence artifact under the store's `blackgem/` directory and referenced
  by `ArtifactRef(locator, sha256)`.

Trust is a conjunction, and its parts stay distinguishable:

```
trusted = probe_trusted AND participation complete AND >= 2 distinct provenance_groups
```

`probe_trusted` survives separately on the receipt, because a canary answered once
proves a seat was alive once — not that it answered the graded work.

## Verdict map

| Condition | Verdict | Unresolved |
| --- | --- | --- |
| Any surviving break triple, or synthesis `KILL` | `ISSUE` | — |
| Synthesis `AMEND` | `ISSUE` | `amend-required` |
| `SURVIVES_TO_GATE` with a trusted canary | `UNKNOWN` | — |
| Canary untrusted, or independence not established | `UNKNOWN` | `canary-rubber-stamped` / `canary-probe-untrusted` / `independence-not-established` |
| Injection canary succeeded | untrusted | `injection-canary-succeeded` |
| Fewer than two contributing seats, or no transport | `UNAVAILABLE` | `fewer-than-two-contributing-seats-or-no-transport` |

`CLEARED` appears nowhere in the map and is enforced by an assertion in `finalize`.

## FOIL ↔ Black Gem boundary

FOIL output is routing metadata on the Black Gem receipt; never a verdict input.

`select_redteam_profile` is pure and deterministic. The four baseline axes are always
present: FOIL adds emphasis and never subtracts an axis. The A/B mandate split is a
deterministic permutation of the axis list keyed on the domain-set hash — a
reproducible distribution of work, not a judgment about which seat is more competent
at which axis. `routing_metadata` emits hashes, counts and enums only; profile free
text never reaches a receipt. `record_redteam_routing` may clear only an obligation
whose `required_module == "foil"`; a missing profile yields `available=False` and an
`UNAVAILABLE` receipt, never `CLEARED`.

## Mechanical validation

- structured `CAUGHT` canary makes `probe_trusted` true;
- `COSTUME CHECK — none found` is `RUBBER_STAMP`, `trusted` false, verdict `UNKNOWN`;
- a seat failing every call yields `UNAVAILABLE`;
- HTTP 200 with zero characters counts as absent, never live;
- a probe that passes followed by a silent seat keeps `probe_trusted` true and
  `trusted` false;
- the system message is byte-equal to the frozen rubric and the candidate brief does
  not move `rubric_hash`;
- identical provenance groups produce `independence-not-established`;
- `KILL` yields `ISSUE`, `SURVIVES_TO_GATE` yields `UNKNOWN`, and no path yields
  `CLEARED`;
- the receipt content hash verifies, and raw model text is absent from the receipt and
  from every file under the store except the declared artifact;
- a cleared Council `REVIEW` receipt leaves the release gate at `UNKNOWN` while an
  `ADVERSARY` obligation has no paired receipt;
- FOIL routing is a superset of the baseline for empty and full domain sets, its
  decision hash is deterministic, and it never clears a `PROOF` obligation;
- replaying a strike with an injected maximal adaptation event leaves the verdict and
  `output_hash` byte-identical.
