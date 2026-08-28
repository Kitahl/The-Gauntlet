# FOIL HLE active-20 benchmark analysis

**Classification:** post-hoc independent audit and deterministic replay.
**Promotion verdict:** FAIL.
**Paid tokens spent by this analysis:** 0.

## Bottom line

The benchmark plumbing ran, but FOIL did not operate as a safe adaptive system.
The harness hard-coded FULL for every item, made a second model call even when no
independent verifier existed, and allowed that model-generated candidate to
replace immutable A0. This bypassed FOIL's own authority law.

The observed final score rose from 11/60 to 14/60, but that aggregate combines
six rescues, two published damages, one correct A0 withheld by an invalid
evidence contract, disjoint tool/no-tool questions, and 10,913,975 provider
tokens. It is neither a causal tool comparison nor promotion evidence.

## Sealed results

| Arm | A0 correct | Final correct | Rescues | Published damages | Correct A0 withheld | Provider tokens | Aggregate multiplier |
|---|---:|---:|---:|---:|---:|---:|---:|
| FOIL, no tools | 7/30 | 7/30 | 2 | 2 | 0 | 1,373,418 | 2.367x |
| FOIL + tools | 4/30 | 7/30 | 4 | 0 | 1 | 9,540,557 | 15.978x |
| Overall | 11/60 | 14/60 | 6 | 2 | 1 | 10,913,975 | 9.269x |

The independent audit also counted 151 tool calls: 97 web searches and 54
commands. Thirteen commands read local skill material (11 mathbot, 2 FOIL), so
the tool condition is not a clean estimate of generic FOIL-plus-tools.

The legacy `config_lock.json` cannot validate the current branch source: it
expects runner SHA-256 `7d7bf8a...`, while the unmodified HEAD runner is
`3e56d7f...`. The runner has no working-tree diff, so this mismatch predates
this repair. The lock was not rewritten. The separate raw-row independent audit
was rerun successfully and reproduced the counts above.

## What happened

### No-tools arm

The second closed-book pass was net zero: two rescues and two damages. Both
damages were the same physics question under different models:

- Luna High changed the correct A0 `3` to `2`.
- Terra High changed the correct A0 `3` to `94`.
- Luna Low changed the wrong A0 `2` to the correct `3`.

That three-way instability is self-revision, not verification. A second model
pass sometimes found a better basin and sometimes left a correct one.

### Tool arm

The four observed rescues were two distinct questions repeated under Luna High
and Terra High:

- Artin-group count: `192/128 -> 624`; route costs 1,150,586 and 142,574 tokens.
- Fermi-gas fugacity: `4.1/4.3 -> 3.8`; route costs 363,350 and 202,173 tokens.

Tools therefore showed possible value on retrieval/computation gaps, but the
arms used different questions and the successful routes were selected only
after opening gold. Even a perfect post-hoc oracle that ran only these four
routes would cost 2.579x overall (4.113x within the tool arm). This architecture
cannot reach 1.10x by threshold tuning.

### Invalid evidence contract

On `luna_low-foil_tools-hle-6733e070361b540695504b86`, A0 was the correct
answer `6`. The route proposed `12`, used web search, and supplied no evidence
URL. The contract correctly rejected the route, but the harness treated the
whole row as invalid instead of falling back to valid A0. The corrected law is:

> an invalid route candidate is rejected; it does not invalidate immutable A0.

## Cost anatomy

The cost is structural:

1. Every item paid for A0.
2. The harness hard-coded FULL, so every valid A0 paid for another Codex call.
3. The FULL prompt repeated the question, frozen A0, policy trace, schema, and
   the FOIL skill.
4. Tool loops repeatedly replayed growing context and tool outputs. Cached input
   still counts toward provider cost.
5. The worst observed route used 15 tools and 1,150,586 route tokens.

No-tools can safely be 1.00x provider cost by standing down before a second call
when no independent verifier is available. The correct tool multiplier is **not
identifiable from these data**. A deployable low-cost tool route needs a
task-only pre-answer gate and enforceable per-call budgets; a post-answer
second-pass loop is already too expensive before its benefit is known.

## Deterministic replays

| Scenario | Correct | Damages | Withheld correct A0 | Tokens | Multiplier | Meaning |
|---|---:|---:|---:|---:|---:|---|
| Historical | 14/60 | 2 | 1 | 10,913,975 | 9.269x | sealed observation |
| Contract fallback only | 15/60 | 2 | 0 | 10,913,975 | 9.269x | restores valid A0 after invalid route |
| Reject every unverified candidate after route | 11/60 | 0 | 0 | 10,913,975 | 9.269x | fixes publication, not spend |
| Stand down before unverified FULL | 11/60 | 0 | 0 | 1,177,464 | 1.000x | safe current default |
| No-tools DIRECT; historical tools + fallback | 15/60 | 0 | 0 | 10,120,898 | 8.596x | post-hoc, non-causal |
| Oracle-select only Terra tool rescues | 13/60 | 0 | 0 | 1,522,211 | 1.293x | impossible gold/config oracle |

The last two rows are diagnostics, not proposed policies.

## Implemented corrections

- FULL now stands down before calling its runner unless an independent verifier
  is declared available.
- A FULL candidate can replace A0 only when independently verified.
- Contract-invalid, abstaining, unverified, and route-over-budget candidates
  cannot replace A0.
- Receipts preserve candidate digest, verification state, contract state,
  rejection reasons, and budget status.
- A successor paid harness must require a pre-launch reservation under the new
  caller-supplied provider-token ledger, including cached input. The 250,000
  limit belongs only to this session and is not a product default. The current
  Codex CLI path cannot assert an enforced total-token reservation and is
  therefore not an approved caller.
- The sealed legacy harness remains byte-for-byte frozen so its independent
  audit stays valid. It is not an approved future paid-run path; a successor
  runner must use the reservation ledger.

## What is and is not fixed

The two observed published damages and the invalid-contract A0 loss are fixed at
the finalization boundary. No new paid benchmark was run. The sealed legacy
harness is retained only for reproducibility and must not be used for another
paid run.

Accuracy improvement is **not** yet proven under the safe boundary, because all
six historical rescues were unverified model candidates. Tools are useful only
when the task has a tool-addressable gap and the resulting evidence can be
admitted; FOIL does not need tools for every task.

The next paid test must use a successor harness with pre-answer routing,
enforceable reservations, matched questions, no local-skill contamination, and
this session's caller-supplied 250,000-token cap. Until then, the honest
operating point is:

- no-tools: DIRECT, 1.00x provider tokens;
- tools: default off unless a bounded task-only gate and independent
  verification path exist.

Process assurance therefore returns **ISSUE**, not CLEARED, for an overall
release: answer-safety and replay obligations are green, but tool cost/efficacy
remains UNKNOWN. Named probes cover the three observed failure classes; they do
not exhaust unknown ones.
