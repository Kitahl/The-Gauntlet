# FOIL Codex dose-response — three-item development pilot

**Date:** 2026-08-24
**Status:** preregistered before scored calls
**Scope:** development smoke evidence only

## Question

Across a deliberately broad six-configuration Codex ladder, does the frozen FOIL
prompt contract produce any visible BASE-vs-FOIL transition pattern on three hard,
short, closed-book GPQA items?

This pilot does not estimate a dose-response curve, calibrate the adaptive
controller, certify a route, or test safe default activation. Three items are
chosen because the operator requested a small run before financing a larger one.

## Frozen selection

Use GPQA-Diamond at repository revision
`56686c06f5e19865c153de0fdb11be3890014df7`. Apply these deterministic filters:

- expert validator accuracy at most 0.50;
- non-expert validator accuracy at most 0.34;
- canonical source difficulty of hard undergraduate level or harder;
- normalized question length below 900 characters;
- item absent from the 2026-08-23 development manifest.

The pinned inputs produce 25 eligible rows. Sort by expert accuracy, normalized
question length, and source index; take the first **three**. Seed `20260824`
controls answer-option shuffling and global unit order. Item IDs, public content, the source-archive digest, the exclusion-manifest
digest, and all configuration SHA-256 digests are frozen before calls. Gold
remains closed. The protocol, runner, public skill, schema, items, condition map,
manifest, lock, and exclusion manifest must all exist in one immutable pre-call
Git commit; that commit is recorded in every receipt.

## Matrix and hard cap

    3 items × 6 configurations × 2 arms × 1 replicate = 36 scored calls
    6 positive controls                                      =  6 calls
    hard maximum model executions                            = 42 calls

Configurations are Luna, Terra, and Sol at low and high reasoning effort. They
are configurations, not a validated one-dimensional ability scale.

BASE receives only the common closed-book question and answer schema. FOIL
receives `/foil solve`, the frozen public FOIL skill contract, and the identical
question. No profile, repository context, network, tool grant, or persistent
state is available to either arm.

Calls are ephemeral, read-only, ignore user configuration/rules, use a fresh
empty directory, and require `{"answer":"A|B|C|D"}`. There are no retries or
model substitutions. Six trivial schema controls run first, one per
configuration. Any failed control, unknown JSONL event/item shape, tool event, malformed
response, timeout, transport error, call-cap breach, or frozen-hash mismatch
stops the run. Raw streams remain local under an ignored private directory.
Resume accepts a completed call only when its model, effort, prompt digest,
pre-call commit, CLI version, raw-stream hashes, kind, and call ID match exactly.
Git checks and CLI version probes are auxiliary local subprocesses, not model
executions and not part of the 42-call model-execution cap.

## Analysis

After every prediction and the exact 42-receipt public inventory is tracked,
committed, and clean, verify each prediction against its frozen unit, receipt,
and ignored raw stream. Scoring derives answers from the validated receipts,
verifies the downloaded archive digest, then—and only then—reconstructs gold and
reports:

- the six raw paired tables: both correct, FOIL only, BASE only, both wrong;
- BASE and FOIL accuracy per configuration and overall;
- paired difference per configuration and overall;
- raw input/cached/output token and wall-time summaries;
- every invalid/missing cell without pooling or retry.

Exact McNemar and item-cluster sign-flip values may be emitted as diagnostics,
but they are not a promotion test. Do not fit the draft same-run
`arm × p_hat_config` mixed model: `p_hat_config` is outcome-derived and three
items provide no useful fitted dose-response evidence. Do not estimate a route
fidelity floor from this run.

## Permitted outcomes and nonclaims

The only completion labels are:

- `UNSAFE`: a hard authority/isolation/tool boundary failed;
- `INCONCLUSIVE`: the frozen matrix did not complete validly;
- `OBSERVED_IN_THIS_PILOT`: the matrix completed and raw results are reported.

`OBSERVED_IN_THIS_PILOT` is not support for general FOIL superiority, a model
ranking, calibration, certification, formalization fidelity, extraction recall,
production cost savings, personalization benefit, causal rescue/damage, or safe
default activation. The three items are development data forever.
