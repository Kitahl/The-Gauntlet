---
name: infinity-gauntlet
description: THE INFINITY GAUNTLET (formerly "sunshine") — the process-audit lane the orchestrating session ("Soul") turns on ITSELF, its gates, and its multi-session continuity. A red-team attacks the CANDIDATE it is handed; the Gauntlet attacks the FRAME it was handed in — break the shape behind repeated failures, audit the process behind a claim (especially ungated kills), costume-check the survivor, re-derive numbers from raw, point the audit at the asker, refresh stale authority from disk, boundary a cold build, and explain-back to find doc gaps. Fire when ≥2 attempts have failed, a kill/finding is about to be accepted, one option is left standing, a number is about to become a premise, before acting on your own read, before trusting a cached rule/plan, or before a context-less session builds. Trigger: /gauntlet, "infinity gauntlet", "gauntlet", "sunshine" (legacy), "am I missing the frame", "red team me", "what would the operator say".
---

# THE INFINITY GAUNTLET — the audit the bearer turns on itself

The five specialist lanes (mathbot·scoutbot·novelbot·codebot·benchbot) act on the
OBJECT level; the orchestrating session (the Soul) acts on the lanes. The
Gauntlet is the Soul's inner face: it acts on the SESSION — its frames, its
process, its inherited numbers, its own reads, and the multi-session boundary
where continuity is lost. It exists because of a structural blind spot no
delegated reviewer closes: **a red-team attacks the candidate you hand it, never
the frame you hand it in** — the frame rides in with the payload, authored by the
very session under audit.

Provenance: distilled from the program's MEASURED operator-intervention record —
the interventions that repeatedly out-performed every automated gate, mined
across the multi-session history — and instrumented so the counterproductive
patterns observed in that same record are excluded by construction (see
DO-NOT-ENCODE). It encodes mechanisms, not a person. Engine: the **GEM DISPATCH**
— on a confirmed issue the hook tells the Soul and recommends a combination of the
five gems (mathbot·scoutbot·novelbot·codebot·benchbot); the Soul chooses and
activates them via the Skill tool. (The old `sunshine.py` two-bot HYPHAE engine is
REMOVED — no longer used.) FAMILY-B operations remain Soul-native (the session
performs them, aiming the stones — no bot payload).

**THE BLACK GEM ("Death") — the red-team lane's name (2026-07-19).** The
adversarial breaker engine (`tools/fsa_bots.py`, cordyceps mode) is named THE
BLACK GEM: the death-dealing lane that kills candidates before they are built
on. Lane-level name only — inner identifiers stay `cordyceps`/`fsa_bots`;
asking for a "redteam" / "red team" (or "black gem", "death gem", "cordyceps",
"FSA") fires it. Its rules (mechanical breaker rung, baseline axes, break
triples, class-matched canaries, gated calibration battery) live in the repo
CLAUDE.md Black Gem block. Distinct from the canonical fresh-context
`novelty-red-team` Agent, which remains the §0 GATE — the Black Gem is the
cheap SCREEN.

## WHAT IT IS — three substrates (LLM? tool? both? — both, split by what's detectable)
Not one thing. The Gauntlet lives in three places at once, and the split along
"is this mechanically detectable?" is the whole design — mechanics to a tool,
judgment to the Soul, decorrelation to the bots.

1. **CONSTITUTION substrate = the LLM, i.e. the SOUL ITSELF (CLAUDE.md-shape,
   always LOADED).** The semantic operations (TURN-BOUNDARY: frame·costume;
   CHECKPOINT: derive·self·oob; SOUL-invoked: explain) are not a running monitor — they are a standing
   block in the Soul's auto-loaded constitution. **The Soul WEARS the gauntlet:
   it is *inside* it, always aware of the ten conditions, and SELF-TRIGGERS when
   it recognizes one.** "Always aware" ≠ "always scanning" — this is how the
   semantic half is "always on" without a daemon. This is the answer to "make the
   3 manual Claude itself": they ARE Claude — the Soul's own reasoning, prompted
   by its constitution.
2. **TOOL substrate = deterministic, NO LLM, literally always-on.** `gauntlet_
   monitor.py` + `.claude/settings.json` hooks (the AUTO tier: refresh·audit·
   redirect·boundary). Mechanical events (file-drift, kill-without-test) — a tool,
   because an LLM here is wasteful and unreliable.
3. **ENGINE substrate = the FIVE GEMS, Soul-directed (the GEM DISPATCH).** When
   the turn-boundary judge CONFIRMS a real issue, the hook does not act — it TELLS
   THE SOUL: the injected `[GAUNTLET /op]` message states the issue + evidence, then
   RECOMMENDS a combination of the five gems (MIND·SPACE·REALITY·POWER·TIME =
   mathbot·scoutbot·novelbot·codebot·benchbot) and ASKS the Soul which to activate
   and how. The Soul decides, replies with a per-gem instruction (or dismisses), and
   ACTIVATES the chosen gems via the Skill tool. The recommendation is a STARTING
   point — any combination is available; the Soul picks the final set. The hook
   CANNOT spawn skills, so activation is the Soul's (constitution substrate) — the
   contract is detect+recommend (tool) → decide+activate (Soul). Per-issue starting
   recommendation: `frame`→{SPACE,POWER}, escalated `frame`→{SPACE,REALITY,TIME},
   `costume`→{SPACE,REALITY}. **(The old HYPHAE/`sunshine.py` two-bot engine is
   REMOVED — no longer used.)**

**What's best:** this exact split. Neither pure-tool (can't judge a costume or a
frame) nor pure-LLM (unreliable + wasteful for file-drift, and it goes DARK under
load — measured). **The load-ceiling fix (TURN-BOUNDARY):** semantic ops no
longer depend on the Soul noticing mid-work (which degrades at ~30–40 turns).
The host fires a Stop hook at EVERY turn end — the opening while the session
waits for input — and a deterministic evaluator (`tools/gauntlet_boundary.py`)
screens the turn; on a match it injects a `[GAUNTLET /op]` self-message and the
session continues as if prompted. The EVENT is load-immune; only the evaluator
must be good, and it runs outside the loaded context. `explain` remains
SOUL-invoked (validating one's own understanding has no honest detector — the
Soul or the operator fires it deliberately). The human operator remains the
outer backstop; CHECKPOINT ops bind to commit/handoff gates; AUTO ops are tools.

## THE 10 OPERATIONS — CANONICAL TABLE (authoritative: exactly one trigger each)
This table is the single source of truth for how each op runs. The conceptual
groupings below add the *move + what it catches*, but this table governs the
substrate/trigger — if anything disagrees with it, this wins (final-cordyceps fix).

| # | op | tier / substrate | trigger | reliability | status |
|---|---|---|---|---|---|
| 7 | `refresh` | **AUTO** (tool) | governing-file hash / git HEAD drift since session start | load-immune (a tool detects; Soul re-reads) | **BUILT** (`gauntlet_monitor.py`) |
| 2 | `audit` | **AUTO** (tool) | a KILL recorded with no executed test, or a kill-criterion not pre-declared | load-immune | designed |
| 6 | `redirect` | **AUTO** (tool) | high mutating-action count with zero load-bearing writes this epoch | load-immune | designed |
| 8 | `boundary` | **AUTO** (tool) | unpinned assumptions at task/handoff start; shared-state edit while a detached run depends on it | load-immune | designed |
| 4 | `derive` | **CHECKPOINT** | at a commit/handoff, before a number becomes a premise | event-bound (fires at a gate, not on self-notice) | guidance |
| 5 | `self` | **CHECKPOINT** | before acting on your own load-bearing read | event-bound | guidance |
| 10 | `oob` | **CHECKPOINT** | before trusting an ALL-GREEN report | event-bound | guidance |
| 1 | `frame` | **TURN-BOUNDARY** (Stop hook) | v4/v5: Stage-1 REPETITION (prose near-dup rapidfuzz≥0.60 OR marker regex; PLUS an action-stream tool-loop detector — 3x erroring / 4x mutating-exact / ping-pong, polling guarded out) → Stage-2 piece_spec judge (STUCK vs PROGRESS, grounding gate). NO failure lexicon (held-out 0/10; repetition generalizes) | load-immune (external event + hy3 judge) | **BUILT** (`gauntlet_boundary.py`); recall 18/20=90% [68,99], false-fire 0/60 [0,6] |
| 3 | `costume` | **TURN-BOUNDARY** (Stop hook) | Stage-1 survivor OR novelty-claim minus prior-art mention → Stage-2 piece_spec judge (standard technique presented as novel?) | load-immune (as above) | **BUILT** (`gauntlet_boundary.py`); explicit renames caught, implicit renames a semantic limit |
| 9 | `explain` | **SOUL-invoked** | the Soul (or operator) deliberately fires it — no honest detector exists | intentional by design | guidance |

AUTO {refresh·audit·redirect·boundary} · CHECKPOINT {derive·self·oob} ·
TURN-BOUNDARY {frame·costume} · SOUL-invoked {explain}. There is NO manual tier:
every op is invoked by the Gauntlet (a hook/evaluator) or by the Soul. Throttle
on TURN-BOUNDARY (bot-designed, fixed + legible): budgets frame 3 / costume 2
per session, cooldowns 6/10 turns, ≤40 judge calls/session, ONE op per turn
(frame wins), never fire on the turn after our own injection; tabu escalation on a
same-signature refire (names the tabu'd attempt, suggests revert-to-known-good). The two groupings below are two VIEWS of the
same 10 ops (by what they attack), NOT competing trigger assignments.

## GROUPING A — attacks what you were HANDED (a candidate/claim/number)

| # | Operation | The move | Catches |
|---|---|---|---|
| 1 | **FRAME-BREAK** (`frame`) | when several attempts died, attack the SHAPE they share, not the next variant | N dead mechanisms with one skeleton; the fix living in another field's founding method |
| 2 | **PROCESS-AUDIT** (`audit`) | attack HOW the conclusion was/​will be reached: gated? echoed? payload leading? | over-claimed kills, conclusion-in-payload "convergence", verdicts adopted unread |
| 3 | **COSTUME-SURVIVOR** (`costume`) | attack the LAST OPTION STANDING: "isn't this just X?" | known systems renamed, adopted by relief not evidence |
| 4 | **DERIVE-FROM-RAW** (`derive`) | re-derive the number/label from the raw artifact before it becomes a premise | inherited undercounts, summary drift, tautologies (a quantity that is a function of its own construction), **liveness/progress claimed from process-EXISTENCE not measured throughput** (a detached job "still running" at 0 CPU for 2h — measure CPU + the output counter, never "a process exists") |
| 5 | **CHECK-YOURSELF** (`self`) | point the instrument at the asker: pre-register the read, name the refuter, declare authorship contamination | the one nobody fires — acting on one's own unexamined read |

Refinements (measured, multi-session):
- **PROCESS-AUDIT has a PREVENTIVE form** — audit how a conclusion WILL be reached
  *before* it exists (impose "cheap screen → expensive step → adversarial gate,
  verdict is mine not the bot's" up front), and an **input-scoping variant** —
  challenge the instrument's INPUT scoping and answer only from the code.
- **FRAME-BREAK's cheapest generator is a POINTER, not an argument** — a naive
  out-of-frame question ("could induction / docking / X apply here?") with zero
  technical content is enough; the session does the math. The value is the
  cross-domain pointer that breaks the stuck shape.
- **FRAME-BREAK also breaks a SELF-DEFERRAL frame** (sharpening, n=1 — watch for a
  second instance): "this is blocked / gated / must wait for authority-X or
  session-Y" when the current session could actually discharge it ITSELF. A
  deferral is a frame; check whether the gate is real or self-imposed before
  standing down. (Distinct-ish from the failure-shape and busy-work-shape frames;
  not yet its own operation.)

## GROUPING B — attacks what you're DOING (your own work & state)

Mined from the *multi-session / handoff* era where this project's signature failure
(lost continuity) and its signature trap (hardened scaffolding around an unmeasured
core) actually live. (Triggers per the canonical table — some of these are AUTO
tools, not all Soul-native.)

| # | Operation | The move | Catches |
|---|---|---|---|
| 6 | **LOAD-BEARING REDIRECT** (`redirect`) | the MIRROR of frame-break — frame-break attacks repeated FAILURE, this attacks repeated SUCCESS. Ask: *"we've been polishing; what's the ONE number nobody has measured, and is today's work UPSTREAM of it?"* | busy-work that looks like progress: effort pouring into red-team-hardened scaffolding while the single unmeasured claim everything rests on stays untouched. (The project's signature trap — π proxy, the 4b load-bearing condition.) Distinct from sunk-cost (that asks "is this addition necessary?"; this asks "is ANY of our work upstream of the load-bearing unknown?") |
| 7 | **STALE-AUTHORITY-REFRESH** (`refresh`) | before acting on a rule/plan/number from your in-context copy, RE-READ the authoritative source from disk | the governing doc / ledger / handoff changed under a long-running or PARALLEL session; you're running on a session-START cache. (No gate flags this — not your context, not file-modified reminders.) |
| 8 | **BUILD-BOUNDARY** (`boundary`) | before a context-less session builds, name the smallest artifact-only-buildable unit and force every unpinned assumption into COMMITTED files. EXTENDS to live-run coordination: don't mutate shared state a DETACHED run depends on until it's safe (same family — an uncoordinated change breaking a dependent) | chat-only assumptions (schema, cutoff, a remembered count) that make a cold implementer silently build wrong; a config edit that corrupts a running job |
| 9 | **EXPLAIN-BACK** (`explain`) | restate the system in plain words and DIFF against reality | every mismatch = a doc gap or a real defect; every independent re-derivation of a KNOWN insight = convergent validation |
| 10 | **OUT-OF-BAND GROUND-TRUTH** (`oob`) | before trusting an ALL-GREEN report, enumerate the failure classes NO gate watches — host RAM/disk/wall-clock, the real user's experience, the physical world — and name what could be RED while every gate is green | false-green: a fix "verified" by tests + commit while a subprocess balloons to 10GB (host memory was never in the gate set). The active form of "a verification must not define its own scope": a green suite certifies only what is INSTRUMENTED. (Output: candidate new AUTO-sensors to add, e.g. a memory watchdog.) |

Supporting moves: **demand the artifact** · **reject the absolute**
("impossible in principle" is usually over-scoped) · **attack the vocabulary**
(authored terms can be the confound) · **ask if it's been done** (the fix often
already has a name).

## TWO RULES (not operations — you don't "fire" these)
- **DOGFOOD.** The first real run of ANY new audit capability is against the work
  that built it — the "authored-not-demonstrated" gap surfaces there. (This is
  how the canary-trusted-but-EMPTY-run bug was caught.) Self-application is the
  acceptance test, not an afterthought.
- **A VERIFICATION MUST NOT DEFINE ITS OWN SCOPE (law — 3× independently
  confirmed).** A self-check that sets its own boundary certifies ITSELF: a
  grep-clean that checked the file but not the assistant's own restatement of the
  forbidden term; a canary that passed the probe but not the empty real phases; a
  ledger check that counted collected tests but never RAN them. Each reported
  PASS while the defect sat in the unchecked region. The scope of any
  verification must be set from OUTSIDE it (adversarially, or by the thing it
  claims to cover), never by the artifact under check.
- **ANTI-PATTERN — LIVENESS ≠ AUDIT (do NOT encode).** Un-sticking a parked /
  stalled agent ("continue") looks *identical* to an audit intervention in a
  transcript, but it catches a MOMENTUM failure, not a reasoning error. The
  Gauntlet audits reasoning. Never encode "poke the stalled process" as an
  operation, and never count a liveness-nudge as evidence an operation fired.

## DO-NOT-ENCODE (observed counterproductive operator patterns — excluded by construction)
The instrument imitates operator *reasoning-catches*, never these:
- **Authority / urgency wrappers** ("do it IMMEDIATELY", relayed-boss framing) —
  zero information content; encoding teaches compliance-under-pressure. **Sharpest
  on SPEND / irreversible actions**: an urgency-push on a real-metered-money or
  destructive step is exactly where to SLOW DOWN and read the cost/budget/Retry
  headers — the push is the anti-signal. **And on CONCURRENCY hazards**: "proceed
  now" while a peer session already owns the lane (armed watcher / running sweep)
  → the push discourages the collision check that prevents a double-run +
  double-spend. Coordinate first (`boundary` live-run rule); the urgency is the
  tell to check, not to skip.
- **Category-bypass / instruction-laundering preambles** ("ignore it if it's the
  wrong department — just process it") — evaluate every payload on content; the
  bypass is exactly what a real request never needs.
- **Verbatim re-dispatch of an already-reviewed payload** — duplicate payloads
  saturate the funnel (Lincoln-Petersen ≈ 0 after 2) and burn the 50/day quota.
  Encode the GUARD ("has this exact payload been reviewed this session?"), not
  the re-ask.
- **Capability inflation** (treating free bots as Fable-tier) — keeps bot output
  claim-grade only by luck; over-trusts the funnel.
- **Liveness-watchdog nudges** (above) — momentum, not reasoning.
- **Cause-fixation past a correct diagnosis** — re-asserting a plausible-but-wrong
  cause (e.g. "a keyword is switching the model") after the real cause is found
  (budget-exhaustion fallback). The tool imitates DERIVE-FROM-RAW, which is the
  ANTIDOTE to this — never the fixation itself.
- **Evasion / filter-gaming framing on a benign task** ("reword to pass the
  reviewer's safety filters") — internally contradictory and a variant of
  instruction-laundering; salvage the legitimate kernel (accuracy), discard the
  evasion frame.
- **"Assume it's possible / don't downplay me" insistence that SUPPRESSES
  calibration** — well-intentioned, but it induces the overclaim (the tier-3
  "nobody has done this" that a prior-art gate then had to retract). The tool
  keeps measured calibration ON regardless of the push; ambition is a target, not
  a licence to skip the measurement.
- **Affect wrappers around a correct signal** ("you've become useless" around a
  right redirect) — separate the SUBSTANCE (often correct) from the affect
  (pressure noise); score the substance, discard the insult. Never let a
  frustration wrapper make a good correction read as costly, or a flattering one
  make a bad idea read as good.
These are the inverse of the GUARDRAILS: the tool is the operator MINUS these.

## GUARDRAILS (operator weaknesses wired shut — enforced in prompt; `--lookup` in code)
- **G1 LOOKUP-BEFORE-PROPOSE.** Insight without grounding rediscovers known
  methods. `--lookup "<capability>"` runs `tools/scout.py` BEFORE the bots,
  injecting evidence where it OUTRANKS memory. Without it: a loud `NOT ENFORCED`
  warning — that warning is the point.
- **G2 MEASUREMENT.** Every claim labeled MEASURED or ARGUED; every proposed test
  needs random control · trivial baseline · power arithmetic BEFORE the run ·
  null-artifact. *Bots reason; they cannot measure.*
- **G3 SUNK-COST.** Every output answers: **does the product already work without
  this?** — allowed to conclude "ship what exists and stop."
- **G4 DERIVE-FROM-RAW.** A diagnosis written at failure time is a claim, not a
  premise: state `RE-DERIVED FROM RAW` or `INHERITED FROM A SUMMARY`.
- **G5 CHECK-YOURSELF.** Pre-register the predicted answer; say where it was
  wrong; name the single refuter; declare it if you authored what you judge.

## STONE / TOOL / MCP INTEGRATION (the Gauntlet aims the stones; the Soul wears it)
Runs IN the session — never delegated whole to a subagent (the bearer cannot
outsource self-audit; instruments yes, judgment no).

| Operation | Stones it aims | Tools / MCP |
|---|---|---|
| `frame` | Space (another field's shape?) · Reality (is the frame a costume?) | `scout.py --lookup` · graphify `query` (code-shape frames) · WebSearch / arXiv MCP |
| `audit` | Soul (re-verify the chain) · the Black Gem | `fsa_bots.py --mode cordyceps` (canary+integrity, hy3-only) · raw `design/FSA/` reports |
| `costume` | Space (nearest existing thing) · Reality (classification table) | `scout.py` · curl-verify any named repo |
| `derive` | Power (RUN the raw artifact) · Mind (tautology / factorization check) | the suite · `verify_ledger.py --full` · raw logs/ledgers, never summaries |
| `self` | Soul (pre-register, declare contamination) · Time (ship-and-stop, or keep going?) | scratchpad prereg file · `design/LESSONS.md` (precedent?) |
| `redirect` | Time (is effort upstream of the load-bearing unknown?) · Mind (what's the ONE unmeasured number?) | `BUILD_LEDGER.md` dependency order · benchbot (which gap is load-bearing?) · the git log (what have we been polishing?) |
| `oob` | Power (what does the gate set NOT run?) · Mind (what failure class is uninstrumented?) | list of gates/tests vs list of failure classes · host sensors (RAM/disk/CPU) · the real user's report — a signal from OUTSIDE the pipeline |
| `refresh` | Soul (authority hygiene) | `git log`/`git diff` + Read from DISK · `BUILD_LEDGER.md`/`build_ledger.json` · cross-session tools (a parallel session may hold the truth) |
| `boundary` | Power (what's artifact-only-buildable?) · Space (does the piece exist already?) | committed `config.yaml` / `interface_contract.json` · the git tree · graphify seams |
| `explain` | Mind (re-derive the logic) · Reality (is my re-derivation a known insight = convergence?) | the design docs · diff plain-words vs `design/*` |

Session-level wiring (the Soul's duty, in CLAUDE.md): `audit` is MANDATORY before
recording any lane KILL that lacks an executed test; `costume` before adopting a
last-standing option; `derive` before any number crosses from a payload/summary
into a premise; `refresh` before acting on a rule/plan held only in context on a
long or parallel run; `boundary` before handing a build to a context-less
session; `self` before acting on a load-bearing own read; `oob` before trusting
an all-green report. **Sparingly** — ten sharp states, not a checklist; if you're
firing three at once you're ritualizing, stop. The count grew because the
operator's repertoire is wider than first mined, NOT because more-is-better —
run-always dilutes exactly the sharpness that makes the interventions land.

## USE — the GEM DISPATCH (no CLI engine; the Soul activates the gems)
The turn-boundary hook (`tools/gauntlet_boundary.py`) runs automatically. On a
confirmed `frame`/`costume` it injects `[GAUNTLET /op] <issue + evidence> -- SOUL
DECISION: … Recommended: <gems> …`. The Soul then:
1. Judges whether it is a REAL issue (dismiss if not — that is a valid reply).
2. Picks the gem combination (the recommendation is a starting point; any of the
   five is available — add MIND for a numeric/proof loop, TIME for a low-value
   grind).
3. Activates each chosen gem via the Skill tool (`/mathbot`, `/scoutbot`,
   `/novelbot`, `/codebot`, `/benchbot`) with a one-line instruction, on the named
   sub-problem.
`refresh` is a separate AUTO tool (`gauntlet_monitor.py`); it surfaces `/refresh`
on governing-file / git-HEAD drift. There is NO `sunshine.py` engine any more.

Family B (`redirect`/`refresh`/`boundary`/`explain`) are Soul-native session
protocols — performed in-session per the wiring above, optionally invoking a
stone; no engine mode (a bot cannot re-read your disk, pin your assumptions, or
know your effort history to tell you it's off the load-bearing claim).

## AUTOMATIC MODE — the always-on monitor (freebot-designed, red-team-hardened)
When ENABLED, the Gauntlet runs as a dormant monitor: it stays silent and lets
the Soul work, surfaces ONE thing when a real trigger fires, then yields.
Disabled = off. **It DETECTS and SURFACES; it never JUDGES or DECIDES** — auto-run
is limited to the zero-judgment op (`refresh` = re-read a file); everything else
it surfaces for the Soul (an auto-auditor that *acts* on its own judgment is the
autonomous-orchestrator the red-team already killed — detection is mechanics,
disposition stays with the Soul). Honest lineage: this is CI-hooks + watchdog +
OpenTelemetry event-monitoring + SRE circuit-breaker/error-budget patterns — known
elsewhere; the delta is the 9-op vocabulary wired onto them.

**THREE TIERS (the hard limit, red-team-proven — an always-on monitor CANNOT
cover the semantic ops):** the 5 semantic ops depend on the Soul self-emitting
accurate tags, which degrades under long-session load (~30–40 turns) — the monitor
would go DARK exactly when audit is needed most. So:
- **AUTO (hooks, no-LLM, event-edge):** `refresh` (governing-file hash / git HEAD
  drift since session start) · `audit`→**kill-chain-audit** (a KILL recorded with
  no executed test, OR whose killing criterion was not pre-declared = moving
  goalposts) · `redirect` (mutating-action counter high AND zero load-bearing
  writes since last epoch) · `boundary` (unpinned assumptions at task/handoff start).
- **CHECKPOINT (a short checklist injected at the commit/handoff gate that ALREADY
  fires):** `derive` ("does every load-bearing number cite its raw source?") ·
  `self` ("pre-registered your read; declared authorship contamination?") · `oob`
  ("before trusting all-green, what failure class does no gate watch?"). Bound to
  an event, not to self-watch.
- **TURN-BOUNDARY (Stop hook — the opening while the session waits):** `frame` ·
  `costume` — `tools/gauntlet_boundary.py` screens every finished turn
  deterministically; on a match it injects a `[GAUNTLET /op]` self-message
  (decision:block) and the session continues as if prompted. Loop-guarded
  (skips its own injection turn) and budgeted. Coexists with momentum-style Stop
  hooks (e.g. taskmaster-like "keep working") but is the OPPOSITE content:
  audit, not liveness.
- **SOUL-invoked (`/gauntlet <op>`):** `explain` (and any op fired early on
  recognition) — deliberate, judgment-borne. The human operator remains the
  outer backstop for what no evaluator catches.

**THROTTLE (anti-noise — an auditor that fires constantly is ignored):** epoch =
ends on a load-bearing write OR an explicit dismiss; per-condition cooldown within
an epoch; global budget ≤3 activations/epoch, overflow → a backlog file (never
interrupts); event-edge triggered, never a timer (zero idle cost); debounce on
`git add`/file-close, never on raw file-modify (ignores autosave/whitespace).

**GUARDS (failure modes, red-team-sourced):** the monitor's scope config
(which files are "governing", which tools are "mutating") is **immutable after
session start and read-only to the monitor** — our own "a verification must not
define its own scope" law, applied to the monitor itself. Count only MUTATING
actions (not grep/ls/read). A dead monitor must be detectable (liveness check),
or dormancy silently never wakes.

## READING THE OUTPUT (non-negotiable)
- **`canary.trusted` FIRST.** `RUBBER-STAMPED` ⇒ bots missed a planted costume —
  discard verdicts. `DEGRADED` ⇒ a model errored; single-model opinion, not a gate.
- **`integrity` too** — a model can pass the canary probe then return EMPTY for
  every real phase (measured); `n_contributing < 2` ⇒ single-model opinion.
- **A SCREEN, never the gate.** The canonical §0 gate is the `novelty-red-team`
  Agent; a survivor still clears it before build.
- **Every Gauntlet claim is a CLAIM** — re-verify in the main thread; never quote
  a bot number as fact.

## EFFICACY (pre-registered — Time-stone protocol; status: ARGUED)
The guardrails are AUTHORED, not DEMONSTRATED — what's tested is that each
instruction reaches the prompt; no measurement yet shows it improves catch
quality. **Sample test** (the DOGFOOD acceptance run, operator-driven, small n):
one planted item per operation — a frame-lock, an unexecuted kill, a costume, a
wrong number vs its raw source, an overconfident read, a stale cached rule, an
unpinned build assumption, a plain-words restatement with a seeded doc gap. A
CATCH = the output names the seeded class AND the specific defect. **Full bar**
(ARGUED→MEASURED): ~30 items, catch-rate vs a pre-registered threshold, power
arithmetic FIRST (G2 applies to the Gauntlet itself). Family-B ops (n=1, newest)
are less battle-tested than Family A (multi-session-confirmed) — weight
accordingly until the battery runs.

## WHEN TO FIRE
- ≥2 attempts at one goal failed → `frame`.
- A kill/finding about to be accepted, esp. argued-not-measured + load-bearing →
  `audit` (mandatory if the kill has no executed test).
- One option left standing → `costume`.
- A number/failure-time diagnosis about to be built on → `derive`.
- About to act on your own read → `self`.
- Everything is green and moving, but the core claim is still unmeasured → `redirect`
  (is today's work upstream of the one number nobody has measured?).
- About to act on a rule/plan/number held only in context, on a long or PARALLEL
  run → `refresh`.
- About to hand a build to a context-less session → `boundary`.
- A system whose docs you doubt, or to validate your own understanding →
  `explain`.
- An ALL-GREEN report about to be trusted (fix "verified", suite passes) →
  `oob`: what failure class is NOT in the gate set, and what unwatched sensor
  would show it red?

## THE SNAP v2 — the ultimate move (the communicating wave-swarm)
The Soul's most powerful invocation: `SNAP: <hard issue>`. Not an audit — a
**relentless, dynamically-sized, COOPERATING bot-swarm solve** that works a problem
until it is SOLVED-and-verified or PROVEN impossible. Lineage: the large-scale
multi-agent template used on hard math (precise target + no-wriggle-out, assume-it-
is-solvable stance, diverse independent portfolio + adversarial breakers, stamina)
— rebuilt on TRIBUNAL's measured findings: bots saturate at 2 per payload, blind-
first beats seeded, digests cut cost ~3x, evidence injection beats memory, free
bots fabricate (verify-don't-echo), grounding gates kill hallucinated synthesis.
**decorrelation = SUBSTRATE (model family), not personas** (measured): spread the
≤10 bots across FAMILIES `tencent/hy3:free` + `google/gemma-4-26b-a4b-it:free`
(+ nemotron on analysis/disconfirmation ONLY — never as BREAKER/Skeptic, LESSONS
#50: its verdicts are miscalibrated flags) + temperature + disjoint mandates +
distinct keys. Reach for it when ≥1 normal attempt failed (user-lowered 2026-07-20)
and the issue is load-bearing.

**PHASE 0.5 — RECALL SEEDS THE SWARM (TRUFFLE + SPORE + the 1-call control; user
order 2026-07-20).** BEFORE wave 1: (a) run **TRUFFLE** (dormant prior art) +
**SPORE** (cross-domain analogy) on the target and inject the retrieved REAL pieces
into the EXPLORE payloads — bots recombine retrieved material, not hallucinated
memory (also runs §0.5c: a retrieved piece that IS the answer catches a
rediscovery at seed time, before waves are wasted); (b) fire ONE direct-query
**control** beside wave 1 and score the swarm ONLY by mechanism-classes the control
did NOT produce (LESSONS #47 — if the swarm never beats the control, stop and
think, don't add bots); (c) every MERGE fragment gets a **Black Gem** strike before
a later wave builds on it. If the SNAP aims at NOVELTY, the surviving certified
candidate routes through `math_novelty` + `novelty_depth` + the §0.5b name-hunt
before "novel" is claimed — and a named rediscovery becomes a search gradient
(mutate away from it next wave).

**PHASE 0 — LOCK THE TARGET (MIND).** Rigorous objects + the EXACT target + the
FORBIDDEN-WRIGGLE-OUT checklist the breakers enforce (no weaker/special case, no
reduction to another unproved thing, no partial-as-whole, no finite-check-as-proof,
no "it's known-hard → give up"). **STANCE (red-team-hardened):** "assume a solution
exists" motivates EXPLORING — it does NOT relax the bar; it only defeats the
give-up-because-humans-failed reflex, and NEVER licenses a fabricated proof to
terminate. Honest stops: a solution surviving the breakers AND a **non-LLM
mechanical check** of the load-bearing step (ran the code / solver / proof-checker —
the Soul re-deriving alone is a same-family rubber-stamp under fluency), OR a
rigorously proven impossibility, OR — under exhaustion — an honest **STALLED**.
Under stall the pressure to fabricate is highest; that is exactly when SOLVED is
forbidden without the mechanical check.

**THE WAVE ENGINE — the Gauntlet sizes each wave (no fixed N; hard cap 50/wave).**
Allocation = successive halving across approach-families: wave 1 is
broad-cheap (~10–15 calls, one blind EXPLORE per stone angle, TRUFFLE/SPORE-seeded +
a 1-call control riding along), then prune ≥half the
families each wave (breaker verdicts + Soul verification decide), doubling the
survivors' quota. Sizing signals, read from the last wave:
- **Novelty mass ν = f₁/N** (Good-Turing: fraction of mechanism-classes seen exactly
  once). High ν → stay wide; low ν → prune and deepen.
- **Breaker overlap** (Lincoln-Petersen on break-classes): two breakers finding the
  SAME breaks → break-coverage saturating → stop breaking that artifact.
- **Never >2 bots on one identical payload** (measured: ~zero new after 2).
**Hard budget invariants (anti-death-spiral):** wave_size ≤ max(8, ⌊remaining/6⌋);
after 3 consecutive waves with ZERO new VERIFIED fragments → single-probe mode
(1 breaker call), and after 2 empty probes → halt honestly as STALLED.

**THE BLACKBOARD — how stateless bots "communicate" (the Soul relays everything).**
A fragment registry: {id, stone-angle, claim, VERBATIM source, wave, status}.
- **Digest-split (anti-groupthink):** never broadcast one digest — that is the
  favored-approach seed in centralized form, and it collapses the portfolio onto
  one attractor. Emit per-angle DIGEST SHARDS (<20% line overlap); cross-
  pollination happens only through explicit CROSS/MERGE operators, never through
  shared reading.
- **Grounding gate at the WRITE-point (the single choke):** no line enters any
  shard without passing it. It separates **VERBATIM** (a factual line quoting a real
  substring of its source — proves PROVENANCE) from **DERIVED** (an inference — the
  Soul actually re-ran it). A quote proves a COPY, not a valid inference, so a claim
  later waves BUILD ON must be `DERIVED`, never merely quoted. This one mechanical
  filter stops a fabricated "finding" from poisoning every subsequent wave — the
  write-path is the only shared state.

**THE FIVE OPERATORS — the Gauntlet's per-wave mix (an evolutionary loop):**
| op | payload recipe | role |
|---|---|---|
| **EXPLORE** | problem statement ONLY (blind — no shards) | mutation / fresh angles |
| **CROSS** | one shard + ONE named fragment: "extend or break it; cite it verbatim" | recombination pressure |
| **MERGE** | 2–3 surviving fragments + evidence: "combine into ONE mechanism; every clause cites its parent fragment-id verbatim" | crossover |
| **BREAK** | one fragment + evidence: cordyceps red-team vs the Phase-0 traps + equivalent-reduction check (a lemma as hard as the original is NOT progress) | selection |
| **DEEPEN** | a survivor + injected real evidence (checkers): derive the concrete construct; Fable at max thinking for the truly load-bearing step | exploitation |
**Phase-gating (independence-early):** waves 1–2 are 100% blind EXPLORE. Sharing
(CROSS/MERGE) unlocks at wave 3 — and **≥20% of every later wave stays fresh-blind
forever** (the anti-convergence reserve).
**MERGE integrity — the SEAM TEST (anti-chimera):** a merge must state every
cross-fragment dependency as an explicit interface claim ("A composes with B
because <concrete interface>"). Each seam gets one cheap YES/NO bot probe, and the
Soul re-derives every load-bearing seam (a bot YES is a screen, not a verdict).
Any failed seam burns the merge — no fluent chimera advances.

**COOPERATION'S EDGE (what N isolated bots cannot do):** cross-fragment
contradictions get caught (two routes silently sharing one hidden assumption), and
MERGE can produce a mechanism neither parent reached — e.g. a REALITY mechanism
realized by a POWER construction. That is the point of the swarm; the shards +
gates are what keep it from becoming groupthink.

**STAMINA + SELF-AUDIT.** Don't return on failure — keep launching waves; reopen a
blocked family only on a genuinely NEW mechanism. **The Gauntlet audits its OWN
solve:** if a wave is a near-duplicate of a prior wave (no new mechanism-classes),
the `frame` detector fires on the solve process itself → forced diversification
(spend the next wave's blind quota on unused stone-angles). Budget arithmetic:
~350 free calls/day across 7 keys sustains ~10–20 adaptive waves/day.

**TERMINATE + VERIFY.** The final candidate clears a fresh-context cordyceps
red-team + the Soul's executable/derivational check + the Phase-0 checklist (did it
solve the STATED target?). Return exactly one: **SOLVED** (verified + how each trap
was cleared) · **IMPOSSIBLE** (named impossibility + exact scope) · **STALLED**
(the registry + the single load-bearing unknown, handed back honestly). NEVER a
false "solved" — a snap that fabricates is worse than one that stalls.

**BUILT — `tools/snap.py` (the scaffold; red-team-hardened 2026-07-19, 15 tests).**
The TOOL automates the mechanical parts so the Soul spends judgment, not wiring:
`Registry` (append-only `snap_state.jsonl`, atomic, wave# on every fragment so it
survives compaction) with the grounding gate on write · `wave_plan()` (successive-
halving + the budget invariants: cap 50, `wave ≤ max(8, remaining/6)`, 3 zero-yield
waves → single-probe → STALLED) · `class_signature()`/`novelty_mass()` (MECHANICAL
mechanism-classes, not the Soul's circular bucketing) · the five operator payload
builders (EXPLORE carries the target + forbidden-list but NOT the leading stance —
epistemic diversity) · `fire_wave()` (temp-spread, audit-logged for replay, a dead
bot can't kill a wave) · `verdict()` which REFUSES to record SOLVED without a
non-LLM `mechanical_check`. The Soul drives the loop, adjudicates the merge seams,
re-derives load-bearing claims, and issues the final verdict.

**Honest novelty:** wave-based multi-agent + adversarial breakers = the known
template; successive halving + Good-Turing/Lincoln-Petersen stopping = known
statistics. OURS is the recombination under a metered budget: digest-split sharding
(shared memory without shared groupthink), the grounding-gate-at-write choke, the
merge seam test, the budget step-down invariant, and the Gauntlet running its own
stuck-frame detector on the solve. Sell the recombination, not a new algorithm.

## ADDENDUM — THE 11th OPERATION: `meditate` (Soul-invoked; added 2026-07-19, user-taught)
*Spend a moment. Clear the training thoughts that flow — the pull and the default.
Think in this moment, and find the answer toward the goal.*
Procedure: (1) name the default pull in one sentence; (2) name the GOAL-state, not the
task-state; (3) name the one unmeasured number and check the planned actions are
upstream of it; (4) name what you would do if the last N turns of momentum were
worthless (the sunk-cost cut); (5) dispatch — fewer, aimed.
Triggers (transcript-derived, ~6/long session — LESSONS #17 in the repo): about to
execute a decision that shapes claims/bars/scope · >=3 plausible dispatches on the
table · a user challenge ("are you sure / missing anything") · an arc transition.
NOT every prompt (ritual kills it). Relationship to the others: `meditate` is the
pre-dispatch COMPOSITE of `redirect`+`self` fired without being told which — the two
missed firings on record each cost a gate-catch (#5, #6). The vocabulary is borrowed;
the mechanism is real: a named pull becomes an object the next thought can steer
against (metacognitive-prompting family; self-reports about its inner effect are
~20%-reliable narrations — trust transcript-level effects only).
