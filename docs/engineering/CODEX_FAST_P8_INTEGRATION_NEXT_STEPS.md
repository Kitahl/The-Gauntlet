# Codex Next Steps After FAST-P8

**Document ID:** `EGR-CODEX-FAST-P8-CONSUMER-001`  
**Prepared:** `2026-08-29`  
**Repository:** `Kitahl/The-Gauntlet`  
**Producer branch:** `work/native-hermes-fastpath`  
**Status:** `READY_FOR_CONSUMER_FREEZE_AND_ADMISSION_WORK`  
**Execution mode:** phased; stop at every named gate  
**Automatic merge:** prohibited

## 1. Purpose

FAST-P8 completes the bounded Hermes-backed fast-build alpha. The next work is not another
producer feature phase and is not a merge to `main`.

Codex must now treat FAST-P8 as an immutable candidate checkpoint and move through the
consumer-side integration protocol:

```text
freeze exact producer objects
→ verify checkpoint receipt
→ classify every changed path
→ rerun checkpoint-native H1 tests
→ import only the admitted delta into the native-overlay consumer
→ run integrated H2 authority/direct-mode/rollback tests
→ record ADMITTED or REJECTED
```

The producer branch remains a moving source lane. The integration consumer must never use its
floating branch name as evidence after the candidate has been frozen.

## 2. Exact frozen candidate

Use these exact objects unless a later owner instruction explicitly supersedes this document.

### 2.1 FAST-P8 implementation candidate

```text
implementation commit:
6990322a815e46b200d7572544a106607c74343a

implementation tree:
3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6

initial implementation commit:
554ee851996cd363c2e52a6294c3bf478f10a41f

successful implementation run:
33273140981

successful implementation job:
99155128215
```

### 2.2 Publication envelope

The following later commit adds the checkpoint receipt and updated handoff. It is not a
replacement implementation candidate.

```text
publication commit:
b7057dda1b45b7647c0a63c96373c0113c5439f0

publication tree:
c60228d02441ff9277e38b9dc8391630a632b4d9

successful publication run:
33273285506

successful publication job:
99155519987
```

### 2.3 Checkpoint receipt identity

```text
receipt:
docs/engineering/HERMES_FAST_P8_CHECKPOINT.json

receipt content_hash:
c34ef1bb041cdf48d007a282fe3839162a35c88c563bb5972bd77b739c42dcab
```

Recompute the content hash according to the repository's checkpoint convention before trusting
the receipt. Do not trust the recorded string merely because the file exists.

### 2.4 Parent and source baseline

```text
FAST-P7 implementation parent:
9747572e8ca13622b72d8cd3d995fece90e19173

FAST-P7 tree:
0b194a94abf0e9791afeb604c84141325381788f

FAST-P7 publication/base commit:
2c3d5f19fa230bdf3a092c81f587397b4ce2734e

FAST-P7 publication/base tree:
51786c9162cd927a5b4fbb7cff1666bb43ddb4a3

current verified main at handoff:
4f088d688fa9e25b4608f44000a5d9812efa45f9

current verified main tree at handoff:
465d460e9b7f8c61a57ceaf3400907832a6834cc

pinned upstream Hermes:
NousResearch/hermes-agent
v2026.8.27 / v0.20.6
5fc308a70719a83cccdbba4c0e39c23f5a8239d5
```

Refresh the live `main`, integration branches, open PRs, and source manifest before starting.
If live facts differ, record the difference; do not silently substitute new values into this
historical checkpoint.

## 3. Program namespaces must remain separate

Do not confuse these programs:

```text
FAST-P1..FAST-P8
    bounded pinned-runtime alpha

INT-000..INT-800
    three-lane vNext and overlay integration

NATIVE-000..NATIVE-800
    final Gauntlet-owned runtime with no Hermes runtime dependency
```

FAST-P8 is complete as a fast-build alpha. It is not `NATIVE-800`, native-final, production
promotion, or evidence that the whole vNext stack is compatible.

## 4. Branch topology

Preserve three lanes:

```text
work/native-hermes-fastpath
    producer; do not reset, rebase, or consume by floating ref

integration/vnext-core
    stable direct-mode vNext consumer; no required Hermes dependency

integration/vnext-native-stack
    overlay consumer; exact admitted runtime checkpoints only
```

Rules:

1. Do not merge or push `main`.
2. Do not force-update the producer branch.
3. Do not build the overlay directly on the producer branch.
4. Create or update `integration/vnext-native-stack` only from an exact admitted
   `integration/vnext-core` head.
5. Keep the overlay's runtime mode `OFF` by default.
6. Open a stacked overlay PR against `integration/vnext-core`, not directly against `main`.
7. Keep any Hermes-dependent overlay PR labeled `INTERIM_ALPHA / DRAFT`.

## 5. Immediate Codex work order

Execute the following phases in order. Stop and report at the end of each phase.

---

# Phase C0 — Live discovery and immutable freeze

## Goal

Establish current repository facts and freeze one consumer candidate without changing source
behavior.

## Required reads

Read first:

```text
AGENTS.md, if present
docs/engineering/GAUNTLET_FAST_BUILD_HANDOFF.md
docs/engineering/HERMES_FAST_P8_CHECKPOINT.json
docs/engineering/PHASE8_USER_CLI_BOOT.md
docs/engineering/CODEX_FAST_P8_INTEGRATION_NEXT_STEPS.md
the audited whole-stack concurrent-integration plan
GNR-PLAN-004, when available in the workspace
```

## Required commands

```bash
git fetch --all --tags --prune
git status --short --branch
git rev-parse work/native-hermes-fastpath
git rev-parse work/native-hermes-fastpath^{tree}
git show --no-patch --format=fuller 6990322a815e46b200d7572544a106607c74343a
git rev-parse 6990322a815e46b200d7572544a106607c74343a^{tree}
git show --no-patch --format=fuller b7057dda1b45b7647c0a63c96373c0113c5439f0
git rev-parse b7057dda1b45b7647c0a63c96373c0113c5439f0^{tree}
git ls-tree 6990322a815e46b200d7572544a106607c74343a vendor/hermes-agent
git submodule status
```

Verify that the gitlink resolves to:

```text
5fc308a70719a83cccdbba4c0e39c23f5a8239d5
```

Inspect:

```text
integration/VNEXT_NATIVE_SOURCE_MANIFEST.json
integration/imports/
integration/conflicts/
integration/requests/
```

Do not assume these paths or consumer branches already exist.

## Freeze decision

Record both identities:

```text
SOURCE_IMPLEMENTATION_SHA = 6990322a815e46b200d7572544a106607c74343a
SOURCE_IMPLEMENTATION_TREE = 3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6
PUBLICATION_SHA = b7057dda1b45b7647c0a63c96373c0113c5439f0
PUBLICATION_TREE = c60228d02441ff9277e38b9dc8391630a632b4d9
```

The implementation SHA is the executable candidate. The publication SHA is its receipt
envelope. Do not import publication-only documentation as though it changed runtime behavior.

## Exit gate C0

Produce a report containing:

```text
live main SHA/tree
live core-consumer SHA/tree or ABSENT
live overlay-consumer SHA/tree or ABSENT
last_admitted_hermes_sha or NONE
frozen implementation SHA/tree
publication SHA/tree
checkpoint receipt hash verification result
gitlink SHA and cleanliness
candidate validation class
```

Stop if any recorded object is missing, the receipt hash fails, or the gitlink differs.

---

# Phase C1 — Determine the correct delta base

## Goal

Avoid duplicate or incomplete imports.

## Algorithm

1. Read the integration source manifest.
2. If `last_admitted_hermes_sha` exists:
   - verify that it is an ancestor of the FAST-P8 implementation;
   - use the last admitted exact checkpoint as the incremental delta base.
3. If no Hermes checkpoint has been admitted:
   - compute the merge base between the producer and the exact current/core baseline;
   - verify ancestry;
   - treat FAST-P8 as a cumulative candidate from that verified base.
4. If ancestry fails:
   - do not auto-import;
   - create a range-diff and manual delta reconstruction report.

Commands:

```bash
git merge-base --is-ancestor "$FUNCTIONAL_BASE" "$SOURCE_IMPLEMENTATION_SHA"
git merge-base "$FUNCTIONAL_BASE" "$SOURCE_IMPLEMENTATION_SHA"
git log --oneline --decorate "$FUNCTIONAL_BASE..$SOURCE_IMPLEMENTATION_SHA"
git diff --stat "$FUNCTIONAL_BASE" "$SOURCE_IMPLEMENTATION_SHA"
git diff --raw --find-renames --find-copies \
  "$FUNCTIONAL_BASE" "$SOURCE_IMPLEMENTATION_SHA"
```

## Required output

Set and record:

```text
FUNCTIONAL_BASE_SHA
FUNCTIONAL_BASE_TREE
DELTA_KIND = INCREMENTAL | CUMULATIVE | MANUAL_RECONSTRUCTION_REQUIRED
```

Do not use `2c3d5f...` automatically. It is the FAST-P7 publication base for the FAST-P8
increment, but it may not be the last checkpoint admitted by the integration consumer.

## Exit gate C1

The delta base, ancestry, and non-duplication decision are explicit and reproducible.

---

# Phase C2 — Create the source-manifest entry

## Goal

Represent FAST-P8 as an exact candidate in the integration manifest before importing code.

## Required source entry

Create a new append-only source entry such as:

```text
source_id: HERMES-FAST-P8
producer_ref: work/native-hermes-fastpath
source_head: 6990322a815e46b200d7572544a106607c74343a
source_tree: 3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6
publication_head: b7057dda1b45b7647c0a63c96373c0113c5439f0
publication_tree: c60228d02441ff9277e38b9dc8391630a632b4d9
checkpoint_receipt: docs/engineering/HERMES_FAST_P8_CHECKPOINT.json
checkpoint_content_hash: c34ef1bb041cdf48d007a282fe3839162a35c88c563bb5972bd77b739c42dcab
upstream_hermes_commit: 5fc308a70719a83cccdbba4c0e39c23f5a8239d5
functional_base: <C1 result>
functional_base_tree: <C1 result>
authority_ceiling: OBSERVATION_ONLY
runtime_required: true
admission_state: FROZEN
```

Do not call this source `ADMITTED` yet.

## Delta artifact

Create:

```bash
git diff \
  --binary \
  --full-index \
  --find-renames \
  --find-copies \
  "$FUNCTIONAL_BASE_SHA" \
  "$SOURCE_IMPLEMENTATION_SHA" \
  > integration/patches/HERMES-FAST-P8.patch

sha256sum integration/patches/HERMES-FAST-P8.patch
```

Record modes, renames, copies, deletes, and the mode-`160000` gitlink.

## Exit gate C2

The manifest entry and patch digest exist, are internally consistent, and remain `FROZEN`.

---

# Phase C3 — Classify every changed path

## Goal

Prevent a wholesale producer-branch merge.

Generate the complete path list from the exact delta, not from the checkpoint's short
`changed_paths` array alone.

Use these initial classes:

```text
NATIVE_PORT_CANDIDATE
DERIVED_PORT_CANDIDATE
INTERIM_ALPHA
REFERENCE_ONLY
REFERENCE_ONLY_REQUIRED
VALIDATION_ONLY
MIXED_SHARED
REJECTED
```

## Expected classification direction

These are starting hypotheses, not automatic admission decisions:

### Native or derived candidates

```text
gauntlet_host/module_cli.py
    preserve read-only adapter semantics; retest against the current Soul/store

gauntlet_host/ipc.py
gauntlet_host/observation_bridge.py
gauntlet_host/finalizer.py
    candidates for extraction into Gauntlet-owned contracts after authority review
```

### Interim alpha

```text
gauntlet_host/cli.py
gauntlet_host/__main__.py
gauntlet_host/launcher.py
gauntlet_host/worker_main.py
gauntlet_host/phase7_worker.py
gauntlet_host/runtime_profile.py
gauntlet_host/gauntlet_plugin.py
gauntlet_host/foil_bridge.py
```

These paths still depend on the pinned Hermes runtime or Hermes plugin/runtime semantics.

### Reference-only

```text
vendor/hermes-agent
vendor/HERMES_SNAPSHOT.json
scripts/vendor_hermes.py
third_party/HERMES_LICENSE.txt
third_party/HERMES_SOURCE_LEDGER.md
```

Preserve attribution and source identity. Do not make the core branch depend on the gitlink.

### Validation-only

```text
.github/phase5_verify.py
.github/phase6_verify.py
.github/phase7_verify.py
.github/phase8_verify.py
.github/workflows/fastpath-checkpoint.yml
```

Extract permanent assertions before removing any producer harness.

### Mixed/high-risk

```text
pyproject.toml
.gauntlet.json
.github/workflows/*
tools/egrt_types.py
tools/egrt_store.py
tools/soul_runtime.py
```

Any touched shared path requires an invariant-based conflict record. Never select `ours` or
`theirs` without semantic review.

## Required classification record

For every changed path record:

```text
path
change type
mode before/after
blob before/after
owner
classification
runtime dependency
authority impact
import action
required tests
rollback action
```

## Exit gate C3

Every path is classified. No unclassified path may enter the consumer branch.

---

# Phase C4 — H1 checkpoint-native requalification

## Goal

Independently reproduce the producer checkpoint before integration.

Run at the exact implementation SHA, with the publication receipt available separately.

Minimum H1:

```bash
git checkout --detach 6990322a815e46b200d7572544a106607c74343a
git submodule update --init --recursive
python scripts/vendor_hermes.py --verify-only

python -m venv .venv-fast-p8-h1
. .venv-fast-p8-h1/bin/activate
python -m pip install --upgrade pip
python -m pip install -e vendor/hermes-agent
python -m pip install -e . --no-deps

PYTHONPATH=. python .github/phase8_verify.py
```

Also run the existing producer checkpoint workflow against the exact source SHA when the
workflow supports an exact-SHA dispatch. If it does not, record the limitation and use a
content-identical detached checkout receipt.

## H1 assertions

At minimum prove again:

```text
gauntlet starts
isolated worker starts
model responds against deterministic fixture
runtime tool executes
gauntlet_task_status returns read-only canonical status
OBSERVATION_ONLY record is written
parent-owned Soul gate runs
UNKNOWN is not accepted as CLEARED
canonical receipts created = 0
ordinary ~/.hermes created = false
FAST-P7 route remains SHADOW / ADAPTATION_ONLY
```

## Exit gate C4

Set:

```text
admission_state = H1_PASS
validation_class = EXACT_HEAD
```

only when exact-source qualification succeeds. Preserve every failed run in history.

---

# Phase C5 — Build the overlay consumer

## Goal

Apply only the reviewed candidate delta onto the exact core consumer.

## Branch creation

If `integration/vnext-native-stack` does not exist:

```bash
git switch --detach "$EXACT_CORE_HEAD"
git switch -c integration/vnext-native-stack
```

If it exists:

```bash
git switch integration/vnext-native-stack
git pull --ff-only
```

Verify that the overlay base is the exact intended `integration/vnext-core` head. Do not
silently rebase onto a moving core.

## Import strategy

Use one of:

```text
exact source blobs for conflict-free owned paths
git cherry-pick -n for one clean isolated delta
hashed binary/full-index patch with git apply --3way --index
manual invariant-based union for shared files
```

Never merge `work/native-hermes-fastpath`.

Create:

```text
integration/imports/HERMES-FAST-P8.json
```

Bind:

```text
source head/tree
publication head/tree
functional base
patch SHA-256
applied paths
rejected paths
reference-only paths
validation-only paths
conflict records
resulting import commit/tree
operator/tool versions
```

## Default mode

The imported overlay must default to:

```text
OFF
```

`OBSERVE` and `SHADOW` require explicit opt-in. Do not introduce an unqualified `ENABLED`
mode.

## Exit gate C5

The import commit is narrow, reproducible, rollbackable, and contains no unclassified path.

---

# Phase C6 — H2 integrated qualification

## Goal

Prove that the exact imported candidate is compatible with the current vNext consumer without
weakening direct mode or authority.

Create permanent tests:

```text
tests/integration/test_native_overlay_firewall.py
tests/integration/test_vnext_core_stack.py
```

Do not rely only on `.github/phase*_verify.py`.

## H2 job A — DIRECT_MODE

Run with:

```text
Hermes gitlink uninitialized
Hermes dependencies absent
native/fastpath mode OFF
HERMES_HOME unset
```

Prove:

1. current public direct module APIs and CLIs still work;
2. no host starts automatically;
3. no extra model or network calls occur;
4. canonical task/receipt behavior is unchanged;
5. deleting operational runtime state cannot change canonical state;
6. direct release decisions depend only on canonical receipts and registered authority.

## H2 job B — FASTPATH_SHADOW

Run in an isolated environment with the exact gitlink initialized.

Prove:

1. runtime operational `OK` cannot become `CLEARED`;
2. forged `verdict` or receipt-like fields in an observation are rejected;
3. plugins cannot self-grant authority;
4. workers cannot write canonical receipts;
5. general execution cannot clear `ENGINEERING`;
6. task identity is explicit and cannot be inferred from prompt text;
7. status tools are read-only;
8. host unavailability leaves direct mode functional;
9. an uninitialized gitlink leaves direct mode functional;
10. deleting the operational DB leaves canonical task/receipt state unchanged;
11. observation replay under another task fails;
12. duplicate retries produce zero duplicate canonical effects;
13. FAST-P7 remains proposal-only;
14. unresolved tasks remain unresolved;
15. rollback to `OFF` succeeds without rewriting receipts.

## Shared-file conflicts

For every shared path touched, create:

```text
integration/conflicts/<path-slug>.md
```

Record all source invariants, rejected behaviors, resulting blob hash, and dedicated
regressions.

## Exit gate C6

Set `H2_PASS` only after both jobs pass on the exact overlay head/tree.

---

# Phase C7 — Admission decision

## ADMIT only when

```text
checkpoint head/tree frozen
receipt hash verified
H1 exact-head tests pass
every changed path classified
exact import receipt exists
H2 direct and shadow jobs pass
runtime authority remains OBSERVATION_ONLY
FOIL remains ADAPTATION_ONLY
default mode remains OFF
rollback passes
core remains independently green
```

Then:

```text
admission_state = ADMITTED
last_admitted_hermes_sha = 6990322a815e46b200d7572544a106607c74343a
```

Record the resulting overlay commit and tree.

## REJECT when

Any authority, direct-mode, rollback, provenance, or compatibility invariant fails.

On rejection:

1. preserve the previous admitted checkpoint;
2. retain all failure evidence;
3. mark this source entry `REJECTED`;
4. report the exact failing invariant to the producer;
5. repair forward on a new producer commit;
6. do not destabilize `integration/vnext-core`.

## Pull request

After `ADMITTED`, open or update:

```text
head: integration/vnext-native-stack
base: integration/vnext-core
state: DRAFT while Hermes runtime is still required
label/status: INTERIM_ALPHA
```

Do not merge it automatically.

---

# Phase C8 — Native-runtime continuation after admission

FAST-P8 is a bridge, not the final architecture. After consumer admission, continue the
separate `GNR-PLAN-004` program under Gauntlet-owned namespaces.

Priority sequence:

```text
NATIVE-000
    freeze direct-mode APIs, receipts, performance, cost, and source-adoption baseline

NATIVE-100
    host-neutral contracts, ToolObservation, CapabilitySpec, sealed AuthorityRule,
    module adapters, receipt firewall, OFF/OBSERVE/SHADOW

NATIVE-200
    Gauntlet-owned provider profiles and transports

NATIVE-300
    Gauntlet-owned tools, MCP, approvals, plugin ABI

NATIVE-400
    Gauntlet-owned context engine and operational session database

NATIVE-500
    execution, interruption, retry, idempotency, scheduler, recovery

NATIVE-600
    executable Soul DAG and FOIL proposal integration

NATIVE-700
    governed skills, memory, session search, observation-only delegation

NATIVE-800
    security, fuzzing, cross-platform, non-inferiority, rollback, canary
```

The final native completion claim requires no Hermes runtime or package dependency. Preserve
the fastpath as a regression/reference lane until the native replacement has demonstrated
feature-specific parity and the required authority gates.

## Immediate native work after checkpoint admission

Begin with `NATIVE-000`, not a provider rewrite:

1. create `NON_REGRESSION_MANIFEST.json`;
2. inventory public APIs, CLIs, task/receipt schemas, and direct-mode commands;
3. freeze deterministic normalized receipt fixtures;
4. measure direct-mode latency, memory, network calls, and complete cost;
5. create or migrate the Hermes source-adoption ledger and notices;
6. select and version-lock static type, coverage, mutation, and fuzz tools;
7. publish the native-host threat model;
8. stop for owner scope approval before `NATIVE-100`.

## Native hard prohibitions

```text
no model/tool/plugin/scheduler writes canonical verdicts
no ToolObservation Verdict field
no operational DB as authority storage
no memory or skill to receipt conversion
no same-process import of conflicting top-level tools packages
no permanent Hermes runtime/package dependency
no silent provider, model, tool, route, context, or backend substitution
no task release outside Soul
```

## 6. Time and core blockers

The concurrent-integration plan recorded Time identity and artifact-divergence blockers. Codex
must refresh their live state.

Do not claim:

```text
VNEXT_CORE_INTEGRATED
INT-400 complete
INT-450 complete
whole-stack complete
core PR ready
```

until one exact Time candidate has been selected, published, and validated, and all required
core integration gates pass.

FAST-P8 overlay admission may proceed independently in its consumer worktree when the exact
core base is suitable, but it cannot bypass unresolved core blockers.

## 7. Required Codex reports

At the end of every phase report:

```text
phase ID
exact branch
before SHA/tree
after SHA/tree
source checkpoint SHA/tree
functional base SHA/tree
files changed
path classifications
commands run
exact exit codes
tests passed/failed/skipped
workflow run and job IDs
authority invariants checked
canonical receipts created
canonical task mutations
remaining blockers
next permitted phase
```

Never report success from intention, code inspection alone, or a model/tool self-report.

## 8. Ready-to-paste Codex execution prompt

```text
PROJECT: The Gauntlet — FAST-P8 Consumer Freeze and Integration Admission
REPOSITORY: https://github.com/Kitahl/The-Gauntlet

PRIMARY HANDOFF:
docs/engineering/CODEX_FAST_P8_INTEGRATION_NEXT_STEPS.md

PRODUCER LANE:
work/native-hermes-fastpath

FROZEN IMPLEMENTATION CANDIDATE:
commit 6990322a815e46b200d7572544a106607c74343a
tree   3aba1c6263eaca953d92c6f71f2f5b4f9c7996d6

PUBLICATION ENVELOPE:
commit b7057dda1b45b7647c0a63c96373c0113c5439f0
tree   c60228d02441ff9277e38b9dc8391630a632b4d9

CHECKPOINT RECEIPT:
docs/engineering/HERMES_FAST_P8_CHECKPOINT.json
content_hash c34ef1bb041cdf48d007a282fe3839162a35c88c563bb5972bd77b739c42dcab

UPSTREAM PIN:
NousResearch/hermes-agent
v2026.8.27 / v0.20.6
5fc308a70719a83cccdbba4c0e39c23f5a8239d5

ROLE:
Act as the consumer/integration operator, not the producer.

START WITH PHASE C0 ONLY.

1. Read AGENTS.md if present, the current handoff ledger, FAST-P8 checkpoint,
   Phase-8 engineering note, this Codex plan, the audited concurrent-integration
   plan, and GNR-PLAN-004 if available.
2. Refresh live main, producer, core-consumer, overlay-consumer, PR, workflow,
   manifest, and Time-blocker state.
3. Verify every exact commit/tree above and the mode-160000 Hermes gitlink.
4. Independently recompute and verify the FAST-P8 checkpoint content hash.
5. Record whether a previous Hermes checkpoint is already ADMITTED.
6. Determine but do not yet apply the correct cumulative or incremental delta base.
7. Produce the C0 freeze report with exact command output.
8. Do not modify source behavior.
9. Do not merge or push main.
10. Do not reset, rebase, or force-update work/native-hermes-fastpath.
11. Stop after C0 and wait for the next instruction.

AUTHORITY INVARIANT:
runtime execution
→ ToolObservation
→ claim-native Gauntlet module
→ canonical Receipt
→ Soul release gate

FAST-P8 IS:
a validated pinned-runtime interim alpha candidate.

FAST-P8 IS NOT:
NATIVE-800, native-final, a release candidate, integrated compatibility proof,
or permission to merge.
```

## 9. Final stop condition

This document authorizes Codex to begin **Phase C0 only**. Later phases are fully specified
for continuity, but each requires an explicit continuation after the previous exit report.
