---
name: council-of-elders
description: THE COUNCIL OF ELDERS / UNIVERSITY OF TRIBUNAL — an advisory forum that channels documented experts (three colleges + the Fate Team, rosters in ROSTER.md) as one-bot-per-seat lenses over a concrete artifact. PRE-FLIGHT FIRST (measured, binding) — score each question by the ARTIFACT a seat would attack: STRONG (real data/built gate/failing number) seats 2-4; WEAK seats 1; NONE is NOT seated (process questions go to the Gauntlet's own ops; a pure wildcard gets one Chair asking a reframing). Seat 5-8 by QUESTION-FIT, never roster coverage; prefer artifact-derived seats ~2:1 over persona seats; run the 1-call CONTROL alongside every forum and score the forum only by what the control missed (LESSONS #47: value = pack depth, not seat breadth). ALWAYS Claude talking, never the person; no fabricated quotes; pack-less seats are EMPTY/NO-FIT. Convene when you suspect you have COMMITTED to a stance (Degeneration-of-Thought escape), not when you lack ideas. Trigger: /council, /elders, /forum, "council of elders", "university of experts", "ask the council", "convene the forum", "what would the elders say".
---

# THE COUNCIL — documented experts as lenses, measured rules only

v2 (2026-07-20). v1 (1238 lines) is archived at `ARCHIVE_v1_2026-07-20.md`;
the colleges, Fate Team, and institute-design essay live in `ROSTER.md` (read
at seat-time). This file keeps ONLY rules that are (a) MEASURED, (b) ethics/
honesty load-bearing, or (c) the minimum mechanics to run a forum. Every rule
carries its evidence tag. Measured artifacts live in the repo:
`design/COUNCIL_PLENARY_2026-07-20/` (36-seat plenary + A/B + addendum),
`design/LESSONS.md` #47 (the E1 control result).

## 0. WHAT THIS IS, AND WHY IT CAN WORK AT ALL

One hy3/nemotron bot per SEATED expert, each grounded in a fetched retrieval
pack, posting one proposal against a concrete artifact; a skeptic reviews; the
Soul collates, merges, and decides. It is ALWAYS Claude channeling a
documented record — never the person (the HONESTY LAW, §3).

**The mechanism (MEASURED, the one honest justification):** Degeneration-of-
Thought (MAD, arXiv 2305.19118) — once an LLM commits to a stance,
self-reflection cannot recover it even when wrong. A single query is
self-reflection with better packs. E1 (LESSONS #47) confirmed it live: the
forum's one item that justified its cost was the reframing that ARGUED
AGAINST our own conjecture — which the 1-call control did not produce.
**So convene when you suspect you are COMMITTED, not when you lack ideas.**
The forum's product is not more ideas; it is the one that contradicts you.

**The honest limit (MEASURED):** E1 — a 1-call control with the same packs
reproduced the forum's entire core mechanism; marginal value was 3 items at
~7 calls, all from deep-pack instrument-near seats. **Value = pack depth,
not seat breadth.** And simulated experts are MORE confident than real
elicitation while hallucinating dependencies (arXiv 2504.10397) — seat
confidence is an artifact, never signal.

Prior art (CITED, we are known-elsewhere-new-here): multi-agent debate (Du
2305.14325; MAD 2305.19118), ChatEval 2308.07201, SWE-Debate 2507.23348,
AI-simulated expert panels 2603.29470, Polymath (Gowers & Nielsen 2009);
persona-fidelity: OOC 2506.19352, MREval 2603.19313, steering bias
2405.20253. Field warning (2506.01372): AI-scientist systems fail on
EXECUTION, not ideation — seats ideate, the Soul executes, provers certify;
never drift that split.

## 1. PRE-FLIGHT — score BEFORE seating (measured; skipping it cost 39% of a forum)

For each question, write one line: **"a seat attacks THIS artifact: ___"**
- **STRONG** (real data · a built gate · a failing number · a shipped
  design): 2–4 seats, question-fit.
- **WEAK** (a candidate statement, a running job): 1 seat, or wait.
- **NONE** (open strategy · "what are we missing" · our own process): **DO
  NOT SEAT.** Process → the Gauntlet's own ops (`redirect`/`oob`/`frame`);
  pure wildcard → ONE Cross-Domain Chair, REFRAMING only.
*(Evidence: 36-seat plenary — all 8 valuable items from seats 1–22; the 14
seats on artifact-less questions produced ZERO.)*

Then:
- **Seat 5–8 total, by QUESTION-FIT, never roster coverage** (the marginal
  seat past ~8 contributed nothing measurable; "one per group" is the
  measured anti-pattern).
- **Prefer ARTIFACT-DERIVED SEATS ~2:1 over persona seats** (SWE-Debate: the
  artifact's own structure — one seat per failure mode / boundary / gate /
  population / number-producing step — generates guaranteed-diverse
  perspectives immune to every persona-fidelity problem). Keep person-seats
  where a documented human METHOD is the contribution; pick them from
  `ROSTER.md`, or seat a **VISITOR** (§2).
- **The DoT check:** if the Soul has no committed stance yet, think first —
  a forum convened before commitment is buying little (§0).
- **Budget:** a forum ≈ seats+2 calls. The 30+-seat plenary was run once,
  measured (~22% yield), and is not worth repeating unless pre-flight scores
  5+ questions STRONG simultaneously.

## 2. SEATS — who may sit, and on what substrate

- **One bot per seated individual; never two people in one payload.**
- **DISJOINT PACKS BY CONSTRUCTION (Black-Gem-caught):** each seat's
  retrieval pack comes from a DIFFERENT query/shard (author-scope, subfield,
  decade, index). Same packs across seats = variance, not information — a
  costume of a forum.
- **The pack law:** a faculty/visitor seat with no fetched pack is **EMPTY**
  (the panel shrinks and says "reduced panel") — never backfilled, never
  fabricated (a throttled index is not license to invent). A seat whose pack
  does not reach the question returns **`NO-FIT`** and is not counted —
  measured: the plenary's ONLY UNBROKEN post was the one that declared its
  pack's limits and reasoned openly, instead of stretching.
- **PACK META (measured failure modes: stale view · retracted source ·
  dropped assumption · scope-transport · one-sided pack):** every pack
  carries paper YEAR, retraction/version status, and the verbatim CONSTRAINT
  sentence ("under assumption C") — the seat quotes the constraint before
  inferring from the paper. **Retraction status is FETCHED at seat-time, not
  inherited from a cached shard** (Crossref/arXiv); if a source changed,
  the seat emits `BREAK: source-retracted` before any inference — a cached
  pack that predates a retraction is exactly how a dead paper reaches a
  build wearing a CITED tag.
- **The seat build (compressed embodiment ladder):** method card (their
  documented method drives the mandate) → pack → judgment traces (blogs,
  EWDs, MathOverflow — recorded reasoning) → cognitive kit (their signature
  OPERATORS applied one at a time · their ANALOGY WELL · restate the problem
  in their framing first). Style/voice is the worthless costume layer —
  permitted, never ranked. Seats supply DIRECTIONS; the Soul does all depth,
  runs all instruments, and verifies — bots point, Claude digs and proves.
- **MULTI-FAMILY SEATING (user-ordered):** prefer `tencent/hy3:free` +
  `nvidia/nemotron-3-ultra-550b-a55b:free` split across seats — same-family
  pairs give ECHO, not corroboration. Nemotron guardrails (only HALF its old
  ban was re-tested; fabrication is held by RULE): its citations are LEADS
  to verify · it never asserts a NUMBER · read the integrity line every run ·
  prefer ULTRA over SUPER · it **FLAGS but never DECIDES**. Cross-family
  evidence is ASYMMETRIC: disagreement = strong flag; agreement = weak.
- **Chairs & steering (MEASURED):** at most ONE Cross-Domain Chair per forum,
  REFRAMING/analogy/unasked-question only — never a mechanism (38% broken +
  0.88 mean vote for distant seats; and LLMs are ~9.7% LESS steerable toward
  incongruous personas with less diverse persona views, 2405.20253 — the
  most distinctive seats render worst; real diversity comes from SUBSTRATE,
  not the hat).
- **THE VISITOR SEAT (off-roster; closes the hardcoded-prior defect):** if
  the question's real expertise is a PRACTICE nobody on the roster
  represents (any profession, any era — e.g. the HIT problem is bitext
  alignment: a parallel-text specialist, a lexicographer, a cryptanalyst),
  seat a visitor built like any other seat. **Fit line BEFORE pack** ("this
  question needs X because ___"); pack mandatory; **ONE seated at pre-flight,
  plus at most ONE more called mid-forum** via `VISITOR-NEEDED: <specialty> —
  because <line>` (max two total — asking for one when your pack runs out is
  the highest-value thing a seat can say, so the mid-forum route must stay
  open). Trust: least-trusted ON ARRIVAL — its load-bearing claims get the
  Soul's independent check before adoption — and an ADOPTED visitor is
  promoted to the `ROSTER.md` bench, so the roster grows from evidence.

## 3. THE HONESTY LAW (ethics — containment, not just labeling)

- Output is Claude channeling a DOCUMENTED record — never the person. No
  fabricated quotes; tag CITED (fetched) vs CHANNELED (Claude's application
  of their documented style). If the record is silent: "method not on
  record" — never invent a person's reasoning.
- **Living people:** every living-person seat header begins **"MODELED FROM
  PUBLIC RECORD — NOT ENDORSED BY THE NAMED PERSON."** Anyone who has
  publicly objected to AI persona-modeling is not seated (use a role-spec).
  ANONYMIZED seats ("Dept-SMT-3") are the DEFAULT for anything leaving this
  machine. A seat's error is the SYSTEM's error — never attributed to the
  person in any summary.
- **Credit precision:** distinguish "the seat named the AXIS" from "the seat
  handed the INSIGHT" — bots-point-Claude-digs is reported as exactly that.
- **Safety:** persona framing is a measured jailbreak vector (2507.22171:
  −50–70% refusal). Seats are TECHNICAL-advisory only; "channel X" is never
  a route around a refusal.

## 4. THE RUN — post → review → collate → merge → control

**POST.** Each seat: ONE proposal (mechanism + first test) against the
artifact, opening with the **THREE-BUCKET header** — **`PACK STATES:`** (only
this seat's own sources) · **`BRIEF GIVENS (UNVERIFIED):`** (every
figure/claim taken from the shared context, listed BEFORE use, marked
unverified at every mention) · **`BOT INFERS:`** (own reasoning). **HARD
RULE: no number is asserted as established unless it is in THIS seat's own
pack.** *(A/B-MEASURED: old two-bucket header 4/4 laundered a planted
context-number into "fact"; three-bucket 0/4, p≈0.029 — the strongest
evidence in this skill that a rule changes bot behavior.)* Also: corpus
measurements are NOT parameters (39% of plenary seats built mechanisms on
our corpus-specific constants); a proposal whose first test predicts an
already-measured value is a **CONFIRMATION**, labeled so, never ranked as a
proposal. Request tags available to every seat: `TOOL-NEEDED` /
`SOLVER-NEEDED` / `PRIOR-ART-NEEDED: <q> [@institution]` / `VISITOR-NEEDED`
— the Soul runs them, results outrank memory.

**REVIEW (the Skeptic's Chair).** Steelman first (one line: the proposal's
best version), then attack; "found no real flaw" is a legitimate review
(MAD: MODEST tit-for-tat beats maximal; our live pass over-killed).
**EXCEPTION — the softening does NOT apply when the Skeptic runs on
nemotron:** a fabrication-history reviewer keeps the HARD mandate, and per
flags-never-decides its breaks are LEADS the Soul verifies before any
proposal dies. A cross-family Skeptic never RANKS seats comparatively (MAD:
a different-family judge may not be fair) — it break-statuses each post on
its own merits only. High-stakes forums split the review in two mandates
(ChatEval: referee TEAM beats single evaluator): R1 fact/pack errors · R2
missed flaws. **Atomic drift flag** (OOC 2506.19352): a post that is
overwhelmingly `BOT INFERS` with no pack anchoring is a COSTUME — flag it
regardless of how plausible it reads. Votes are recorded as raw telemetry
(the live run validated them as signal: mean vote 0.57 broken / 2.07
amended / 3.00 unbroken) — but **votes allocate attention, NEVER truth**;
one prover certificate outranks every seat.

**COLLATE (mandatory before merge — the live merge miscounted by eye under
context pressure: reported 5 BROKEN/1 struck, raw held 7/5).**
**The reviewer MUST emit machine-greppable tokens, one per post, or the
collation has nothing to count** (both review families caught this: the
regex was specified before anything was required to produce it, and since
"no collation ⇒ no merge" is a hard gate, empty counts kill the forum
silently). Required per post, each on its own line:
`SEAT: <id>` · `STRIKE: <quote or NONE>` · `BREAK: BROKEN|AMENDED|UNBROKEN`
· `VOTE: <0-3>`. Then emit `COLLATION.md`: counts produced by a SCRIPT over
those lines (`grep -c "^BREAK: BROKEN"` etc., output pasted verbatim — never
tallied by eye), then ≤3 lines per seat (claim | break status | the one
adopted fix), then `OPEN THESE POSTS:` (the unbroken/strongly-amended few).
The Soul merges FROM the collation. No collation ⇒ no merge.

**MERGE.** Rank NAME-BLIND by concrete-break status (strip seat names, rank,
re-attach). Dissent prints ON THE SAME PAGE as each finding (count +
content). Findings ship **PROVISIONAL** until the §0 gate (Black Gem screen
→ novelty-red-team Agent) — forum advice is a build artifact, not
pre-trusted. Same-family-only validation is tagged `UNCORROBORATED
CROSS-MODEL`. Killed directions go to `council_memory.md` (append-only) and
ride in future payloads as the negative curriculum — forums were measured
amnesiac.

**CONTROL (STANDING RULE, LESSONS #47).** Alongside EVERY forum, run ONE
direct call carrying the UNION of all packs. **Score the forum only by what
the control failed to produce.** *(Caught in review: packs are DISJOINT by
construction, so their union can overflow one call — the control would then
silently drop packs and quietly break the "same evidence" premise the whole
comparison rests on. If the union exceeds ~80% of the context budget, feed a
STRATIFIED sample — one capped chunk per seat, every seat represented — and
tag the result `CONTROL_SUBSAMPLED`; an unsubsampled control is required
before any claim that the forum beat it outright.)* A forum that beats the control by nothing
should not have been convened — and without the control you cannot know
which kind you ran.

## 5. OUTPUT CONTRACT

Every council answer ends with: (1) the pre-flight score + each seat's ID +
its question-fit rationale, one line each — **use the seat's anonymized ID
when §3 anonymity applies** (the rationale is the point; the name is not, and
the two rules only conflict if you report names where anonymity binds); (2) findings ranked by break status,
each tagged CITED/CHANNELED, with dissent on the same page; (3) what the
1-call CONTROL produced vs what only the forum produced (the honest value
statement); (4) the single NEXT ACTION; (5) gate status (PROVISIONAL until
§0); (6) the standing line: **"This is Claude channeling documented methods
— not the masters speaking. The council advises; the Soul and you decide."**

## 5b. THE INSTRUMENT RACK (the Soul runs these; seats only REQUEST them)

Restored after the v2 cut dropped it (a real loss — seats emit
`TOOL-NEEDED`/`SOLVER-NEEDED` and this is what the Soul reaches for).
On disk / venv: **sympy · mpmath · numpy/scipy · networkx · python-sat ·
z3-solver** · **Vampire 5.0.1 · cvc5 · SMTInterpol** (paths in mathbot §8) ·
**OEIS API** (identify the sequence before theorizing) · **arXiv MCP** ·
**graphify** (code-shape questions) · free indexes (OpenAlex incl.
institution-scoped, Crossref, deps.dev — scoutbot §2). MCP options verified to
EXIST but unvetted: WolframAlpha MCP (keyed), Mathematica MCP (licensed); no
verified SymPy/Lean MCP — sympy is local, Lean routes via mathbot §9.

**THE CEILING, STATED PLAINLY** (restored — the honest limit of the whole
design): what transfers from a person into a seat is the DIRECTION of their
thought (moves, wells, framings) and what they KNOW (their corpus). What does
NOT transfer is depth — the unpublished judgment they would have tomorrow.
The wager is that being pointed in a few genuinely different documented
directions, each checked deep by the Soul + provers, beats one voice
searching alone. E1 measured that wager as **true but small** (§0).

## 6. POINTERS

Pre-registered experiments (E1 run, E2 not-enabled, E3 queued) live in
`design/COUNCIL_EXPERIMENTS.md` — out of this file deliberately: both review
families flagged a disabled queue as dead weight in a loaded skill. Rosters:
`ROSTER.md`. Full v1 text: `ARCHIVE_v1_2026-07-20.md`. Measured artifacts:
`design/COUNCIL_PLENARY_2026-07-20/`, `design/LESSONS.md` #47.
