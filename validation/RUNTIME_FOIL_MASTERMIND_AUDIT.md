# Runtime Assurance + Adaptive FOIL — Mastermind loop audit

Date: 2026-08-21 (America/Vancouver)
Branch: `feature/runtime-assurance-and-adaptive-foil`

This audit applies the Mastermind loop discipline used in the supplied project history: freeze the observed failure, identify the causal mechanism, prefer a general mechanism over a benchmark-specific rule, attack it with negative controls/regression, and preserve unresolved boundaries. The package-level checks below do not establish behavioral efficacy.

## Loop 1 — public/runtime boundary

### Failure

The supplied assurance bundle and portions of the public skill tree mixed reusable mechanisms with private-project/workstation assumptions: absolute workstation paths, project-specific governing files, private keystore conventions, project names/evidence paths, and named internal model routing.

### General mechanism

Separate **specification from runtime**:

- every `skills/<id>/` contains `SKILL.md` only;
- hooks live in `.claude/settings.json`;
- configuration lives in `.gauntlet.json`;
- automation lives in `tools/`;
- state lives in `.egrt/state/`, never `.git/`;
- credentials are environment-only;
- governing files are config-driven;
- optional integrations return `UNAVAILABLE` instead of being assumed.

### Negative controls / regressions

- private-lineage scanner fails on known private-project identifiers/paths;
- skill-layout test fails on any non-`SKILL.md` file inside a skill directory;
- settings test fails if `${CLAUDE_PROJECT_DIR}` disappears or private paths return.

## Loop 2 — hook semantics / false-green runtime

### Failure

Portable prose alone did not make Process Assurance executable, and copied historical hooks would not satisfy current shareability/safety requirements.

### General mechanism

Current Claude Code hook semantics are used:

- exec-form command hooks with `${CLAUDE_PROJECT_DIR}`;
- SessionStart snapshot/reset/context;
- PreToolUse stale-state / optional ledger gate;
- PostToolUse post-commit snapshot;
- Stop turn-boundary evaluator with `stop_hook_active` guard;
- deterministic repeated-tool-loop evidence can trigger `frame` without an LLM;
- semantic precision checks are optional and require an explicitly configured independent model.

### Negative controls / regressions

- Stop hook recursion test with `stop_hook_active=true`;
- configurable governing-file drift test;
- optional ledger defaults to disabled rather than blocking an unrelated repo;
- no API key is required for deterministic monitoring.

## Loop 3 — person-specific FOIL leakage

### Failure

The prior public FOIL specification embedded one person's assessment priors/relative strengths. That makes a public general-purpose FOIL start from the wrong learner state.

### General mechanism

Move personalization to persistent **local saved profiles**:

- no user-specific prior in `skills/foil/SKILL.md`;
- profiles stored in OS user config by default, outside the repository;
- first hooked session creates an empty `default` profile if needed;
- multiple named profiles can be activated for different users;
- raw prompts are not stored by the profile runtime;
- observations store domain/outcome/assistance/confidence/representation metadata.

### Negative controls / regressions

- profile persistence test uses a temporary external profile directory;
- one independent miss stays `INSUFFICIENT_EVIDENCE`;
- two consistent independent misses may become `POSSIBLE_GAP`;
- raw prompt text is absent after prompt-time domain inference.

## Loop 4 — fixed-domain / setup rigidity

### Failure

A fixed questionnaire can miss the domains that actually matter to a new user, while free-text self-report alone cannot establish competence.

### General mechanism

Use a two-layer domain system:

1. a broad cold-start screen of core reasoning/research/engineering capabilities;
2. an open-ended domain registry that adds relevant domains from setup text, explicit custom domains, and later usage.

Prompt-time domain relevance is stored separately from competence. Arbitrary new domains may be created as candidates without changing the public skill.

The current questionnaire contains 20 generated objective items across ten core domains plus open design/UX, creativity, and explanation tasks. Optional domain families include data/ML, physics, chemistry/materials, biology/life sciences, economics/finance, law/policy, hardware/embedded, product management, human factors, and operations/logistics.

### Negative controls / regressions

- 500 generated seeds: each objective item has a unique option set and exactly one derived answer;
- generated session payloads contain no direct answer/correct/key fields;
- unanswered items stay `INSUFFICIENT_EVIDENCE`;
- fully assisted correct answers do not create `PROMISING_STRENGTH`;
- custom setup domains remain unscored until evidence exists;
- open tasks remain `NEEDS_RUBRIC_REVIEW` rather than receiving fabricated objective precision.

## Loop 5 — profile-to-runtime adaptation

### Failure

A saved questionnaire result is useless if it does not alter future routing, and automatic adaptation is dangerous if mere topic mention is mistaken for capability.

### General mechanism

`UserPromptSubmit` now:

- infers only **current domain relevance**;
- updates the active profile with relevance metadata, not competence evidence;
- injects a compact profile/current-task context;
- never stores the raw prompt.

FOIL itself records performance evidence only after a diagnostic observation and conditions it on assistance. Newer task-diagnostic evidence overrides stale onboarding evidence.

### Negative controls / regressions

- prompt-hook test verifies domain creation for new task areas;
- prompt text is not present in saved profile JSON;
- relevance does not change competence classification;
- skill specification explicitly forbids one-miss permanent weakness updates.

## Loop 6 — cold-path entrypoint and profile semantics

### Failure

The first integrated path revealed two classes of defect that unit-level component checks can miss: command/entrypoint behavior and over-broad profile promotion. Blank self-estimate fields could be mistaken for declared relevance, while setup-inferred domains needed an explicit persistence path into the saved profile.

### General mechanism

- only an actually supplied self-rating can become self-estimate evidence;
- setup text and explicit custom domains are persisted as **relevance metadata only**;
- cold-start/profile creation is exercised through the same public entrypoints used by hooks.

### Regression

- blank self-estimates do not declare competence or relevance;
- setup-derived custom domains persist without being scored;
- profile bootstrap remains blank/provisional.

## Loop 7 — validator drift after architecture change

### Failure

The old showcase validator treated any reference to runtime helper paths as a defect because the previous public release was specification-only. After adding real portable helpers, that gate became anti-diagnostic: it rejected the intended architecture.

### General mechanism

Validation now distinguishes:

- **required public runtime paths** — must exist and may be referenced;
- **machine-specific/private paths** — must not appear;
- **optional integrations** — may be absent and return `UNAVAILABLE`.

Decision Preflight is checked by its current orchestrator-owned contract instead of a stale historical phrase.

## Loop 8 — privacy validator self-leak

### Failure

A production validator itself listed the private names it was intended to ban. The privacy check therefore introduced the exact private lineage it was supposed to prevent.

### General mechanism

Separate sensitive sentinels from production validation:

- private-name/path sentinels live only in `tests/test_private_leaks.py`;
- production validators use generic portability checks such as machine-specific absolute-path patterns;
- the leak test excludes its own sentinel source while scanning the candidate.

### Regression

The exact CI candidate passed the private-lineage scan after this separation.

## Loop 9 — state-isolation validator specificity

### Failure

Runtime state was correctly configured as `.egrt/state` and the repository correctly ignored the broader `.egrt/` directory, but the showcase validator required the literal `.egrt/state/` line in `.gitignore` and produced a false negative.

### General mechanism

Validate the relationship semantically:

1. read `.gauntlet.json` and obtain the configured `state_dir`;
2. require it to lie under `.egrt/` and not `.git/`;
3. require `.gitignore` to ignore `.egrt/`;
4. require the public Process Assurance contract to state that runtime state is outside Git metadata.

This tests the actual invariant rather than one spelling of the configuration.

## Release boundary

This candidate is intended to establish:

- portable hook wiring;
- public/private boundary hygiene;
- saved profile mechanics;
- questionnaire mechanics;
- conservative classification/update rules;
- automatic domain-relevance adaptation;
- release validators that track the actual runtime architecture rather than historical implementation details.

It does **not** establish:

- psychometric validity of the questionnaire;
- calibrated learner-state probabilities;
- causal improvement in user learning;
- superiority of profile-driven FOIL over a matched strong non-profile baseline;
- universal correctness of LLM-based turn-boundary judgment.

Those remain prospective research obligations in `research/FOIL_PERSONALIZATION_BASIS.md`.
