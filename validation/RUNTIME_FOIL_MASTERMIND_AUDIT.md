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

## Release boundary

This candidate is intended to establish:

- portable hook wiring;
- public/private boundary hygiene;
- saved profile mechanics;
- questionnaire mechanics;
- conservative classification/update rules;
- automatic domain-relevance adaptation.

It does **not** establish:

- psychometric validity of the questionnaire;
- calibrated learner-state probabilities;
- causal improvement in user learning;
- superiority of profile-driven FOIL over a matched strong non-profile baseline;
- universal correctness of LLM-based turn-boundary judgment.

Those remain prospective research obligations in `research/FOIL_PERSONALIZATION_BASIS.md`.
