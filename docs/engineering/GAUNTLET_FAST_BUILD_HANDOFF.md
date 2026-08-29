# Gauntlet Fast Build — Session-to-Codex Handoff Ledger

**Handoff ID:** `GAUNTLET-FAST-HANDOFF-001`  
**Repository:** `Kitahl/The-Gauntlet`  
**Branch:** `work/native-hermes-fastpath`  
**Baseline commit:** `4f088d688fa9e25b4608f44000a5d9812efa45f9`  
**Governing plan:** `docs/engineering/GAUNTLET_FAST_BUILD_HERMES_INTERNAL_RUNTIME_2026-08-28.md`

## 1. Frozen implementation decision

The fast build vendors the pinned Hermes Agent `v0.20.6` source and runs it as an isolated
internal subprocess. Gauntlet remains the sole authority over obligations, receipts, verdicts,
and release. Same-process imports between the two top-level package trees are prohibited.

## 2. Phase ledger

| Phase | Scope | State | Commit |
|---:|---|---|---|
| 1 | Pin, provenance, license, vendoring command, governing plan | `COMPLETE` | `60bb6f22d7c13a25fee204fbc17798c6c55cb19f` |
| 2 | Materialize and verify the exact `vendor/hermes-agent/` snapshot | `COMPLETE` | `a24a952133d03c43872dbec034a5a8ba5515a32f` |
| 3 | Constants, typed JSONL IPC, isolated worker bootstrap | `COMPLETE` | `98db935f56155ea1f446c10eb6aa5f00384e5d3d` |
| 4 | Launcher, runtime profile, Gauntlet-owned runtime home, one agent turn | `COMPLETE` | `c40b5b93d67e76e2d5e7153fc886c58142bd6f49` |
| 5 | Status/release plugin tools and subprocess module adapter | `NEXT` | — |
| 6 | Observation bridge and Soul finalizer | `PENDING` | — |
| 7 | FOIL advisory route and single `gauntlet` entry point | `PENDING` | — |
| 8 | Eight-item manual boot verification and Codex transfer | `PENDING` | — |

## 3. Phase 1 outputs

1. Exact upstream repository, tag, commit, and license pin.
2. Exact upstream MIT license notice under `third_party/`.
3. Machine-readable snapshot manifest under `vendor/`.
4. `scripts/vendor_hermes.py`, which:
   - verifies the exact Git commit and tag;
   - rejects a dirty or wrong checkout;
   - verifies the MIT license hash;
   - copies the source while excluding only nested `.git` metadata;
   - records deterministic file count and tree digest;
   - supports an independent `--verify-only` pass;
   - requires `--force` before replacing an existing snapshot.
5. The governing fast-build engineering plan stored in the repository.
6. No changes to `tools/egrt_types.py`, `tools/soul_runtime.py`, FOIL authority ceilings,
   receipt formats, or direct module behavior.

## 4. Phase 2 verification receipt

| Field | Result |
|---|---|
| GitHub Actions run | `33223968298` — `SUCCESS` |
| Upstream repository | `NousResearch/hermes-agent` |
| Upstream release | `v2026.8.27` / Hermes Agent `v0.20.6` |
| Upstream commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| Snapshot commit | `a24a952133d03c43872dbec034a5a8ba5515a32f` |
| Vendored files | `10488` |
| Deterministic tree SHA-256 | `5a87f74ab782bfda8dcaed7938ac216d3fd6063e897f67dc0e27cb4c4d4b1dca` |
| License SHA-256 | `821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6` |
| Materialized at | `2026-08-29T00:35:28.082238+00:00` |
| Local modifications | `0` |
| Excluded content | nested `.git` metadata only |

Executed successfully:

```bash
python scripts/vendor_hermes.py --dry-run
python scripts/vendor_hermes.py
python scripts/vendor_hermes.py --verify-only
```

The independent verification pass reproduced the same file count, license hash, upstream
commit, and deterministic tree digest as the materialization pass. Upstream whitespace was
preserved rather than rewritten because Phase 2 required an exact source snapshot.

## 5. Phase 3 implementation receipt

| Field | Result |
|---|---|
| Implementation commit | `98db935f56155ea1f446c10eb6aa5f00384e5d3d` |
| GitHub Actions run | `33225470731` — `SUCCESS` |
| Verification environment | Ubuntu `24.04.4`; CPython `3.12.14` |
| Host files added | `4` |
| Vendored Hermes files modified | `0` |
| JSONL schema | `gauntlet.worker.v1` |
| Request type | `worker.request` |
| Result type | `worker.result` |
| Maximum JSONL record | `1048576` bytes |
| Namespace proof event | `worker.imports_verified` |

Files added:

```text
gauntlet_host/__init__.py
gauntlet_host/constants.py
gauntlet_host/ipc.py
gauntlet_host/worker_main.py
```

The Phase 3 worker:

1. verifies the pinned snapshot manifest before runtime import;
2. rejects preloaded non-vendored `tools` modules;
3. removes Gauntlet repository paths from the worker import path;
4. sets worker `PYTHONPATH` and cwd to `vendor/hermes-agent`;
5. verifies both `find_spec("tools")` and imported `tools.__file__`;
6. emits a structured namespace proof;
7. accepts strict typed JSONL requests and emits deterministic JSONL results;
8. rejects duplicate JSON keys, unknown fields, invalid types, and unsupported operations;
9. exposes no `Verdict`, `EvidenceClass`, `Receipt`, or release field.

The successful run proved:

```text
tools_origin = vendor/hermes-agent/tools/__init__.py
cwd = vendor/hermes-agent
sys.path[0] = vendor/hermes-agent
PYTHONPATH = vendor/hermes-agent
upstream_commit = 5fc308a70719a83cccdbba4c0e39c23f5a8239d5
```

Negative checks also passed:

| Check | Required result |
|---|---|
| Root Gauntlet `tools` preloaded | `TOOLS_NAMESPACE_PRELOADED` |
| Duplicate JSON key | `DUPLICATE_JSON_KEY`; process exit `2` |
| Premature `run` request | `UNAVAILABLE`; process exit `3` |
| Runtime authority fields present | none |

The first temporary Phase 3 run, `33225379537`, stopped before worker execution because its
shallow checkout did not contain `HEAD^` for a harness-only diff command. The repaired harness
removed that invalid precondition. Run `33225470731` then completed every Phase 3 worker check.

## 6. Phase 4 implementation receipt

| Field | Result |
|---|---|
| Implementation commit | `c40b5b93d67e76e2d5e7153fc886c58142bd6f49` |
| Successful GitHub Actions run | `33226703542` — `SUCCESS` |
| Verification environment | Ubuntu `24.04.4`; CPython `3.12.14` |
| Host files added | `2` |
| Existing host files extended | `3` |
| Vendored Hermes files modified | `0` |
| Runtime home | `~/.gauntlet/runtime` |
| Upstream engine instantiated | `run_agent.AIAgent` from the vendored snapshot |
| Provider path exercised | upstream custom OpenAI-compatible provider resolution |
| Model call count | `1` |
| Worker completion event | `worker.turn_completed` |
| Mock final response | `phase4 mock response` |
| Input / output / total tokens | `12 / 4 / 16` |
| Session persistence | `state.db` created under the Gauntlet runtime home |
| Ordinary `~/.hermes` created | `NO` |
| Runtime authority fields in result | `0` |

Files added:

```text
gauntlet_host/launcher.py
gauntlet_host/runtime_profile.py
```

Files extended:

```text
gauntlet_host/constants.py
gauntlet_host/ipc.py
gauntlet_host/worker_main.py
```

### 6.1 Launcher boundary

The parent-side launcher:

1. prepares the Gauntlet-owned runtime profile;
2. never imports vendored `run_agent.py` in the parent interpreter;
3. starts the worker by absolute file path with cwd and `PYTHONPATH` set to the vendor root;
4. passes one typed JSONL request over stdin and expects exactly one JSONL result on stdout;
5. correlates request and task IDs;
6. binds worker status to process exit status;
7. applies a bounded launcher timeout;
8. returns typed `ERROR` or `UNAVAILABLE` operational failures;
9. removes inherited `HERMES_YOLO_MODE`, `HERMES_ACCEPT_HOOKS`, and
   `HERMES_INTERACTIVE` values before process launch;
10. does not perform Soul finalization or claim task release.

The working Phase 4 command shape is:

```bash
python -m gauntlet_host.launcher \
  "Return the configured mock response." \
  --task-id task-phase4-live \
  --model phase4-mock \
  --provider custom \
  --timeout 90 \
  --json
```

### 6.2 Runtime profile

Before upstream runtime imports or construction, the profile manager creates:

```text
~/.gauntlet/runtime/
├── config.yaml
├── state.db                 # created by the upstream SessionDB during the turn
├── memories/
├── skills/
├── cache/
├── logs/
└── pending/
    ├── memory/
    └── skills/
```

It preserves other provider/model settings while forcing the alpha governance values:

```yaml
auxiliary:
  background_review:
    enabled: false
memory:
  write_approval: true
skills:
  write_approval: true
```

It rejects `~/.hermes` as the requested Gauntlet runtime home, writes `config.yaml` atomically,
and sets `HERMES_HOME` to the dedicated directory. The worker also passes
`skip_background_review=True` to upstream `AIAgent`.

The successful verification deliberately began with the opposite three profile values and
with the three inherited bypass flags set. The resulting profile contained the required
Gauntlet values, while the worker completed through the isolated subprocess boundary.
This verifies profile enforcement and launch sanitization for the tested path; it is not a
claim that every upstream memory or skill mutation path has been behaviorally qualified.

### 6.3 One real upstream turn

The successful verification installed dependencies from the pinned vendored tree for the CI
job, started a local OpenAI-compatible endpoint, and executed one actual upstream `AIAgent`
conversation turn. The endpoint received exactly one `/chat/completions` request for
`phase4-mock`. The worker returned:

```text
status = OK
event = worker.turn_completed
provider = custom
model = phase4-mock
final_response = phase4 mock response
api_calls = 1
input_tokens = 12
output_tokens = 4
total_tokens = 16
completed = true
failed = false
partial = false
```

The returned namespace proof still bound `tools` to:

```text
vendor/hermes-agent/tools/__init__.py
```

and the result contained none of:

```text
verdict
evidence_class
receipt
release
```

This proves the bounded engine path with a deterministic local endpoint. It does not yet prove
operation against a paid external provider or any particular production model.

### 6.4 Negative and harness checks

| Check | Result |
|---|---|
| Python compile of `gauntlet_host` | `PASS` |
| Source line-shape check | `PASS` |
| Launcher imports vendored `run_agent` | `NO` |
| Request JSONL round trip | `PASS` |
| Result JSONL round trip | `PASS` |
| Invalid profile root `[]` | `RUNTIME_CONFIG_INVALID`; exit `2` |
| Missing authority fields in worker result | `PASS` |
| Session DB outside Gauntlet runtime home | `NO` |

Temporary run `33226562129` reached upstream `AIAgent` but stopped at its minimum-context guard
because the deterministic mock declared `16384` tokens while the upstream runtime requires at
least `64000`. The worker returned a typed `UNAVAILABLE` result rather than fabricating success.
Only the mock fixture was corrected to `131072`; run `33226703542` then passed every Phase 4
check. The temporary Phase 4 workflow was removed after the successful receipt was recorded.

## 7. Authority and scope state after Phase 4

Implemented and verified:

```text
parent launcher
→ Gauntlet-owned runtime profile
→ bounded JSONL subprocess
→ pinned snapshot and namespace verification
→ upstream provider resolution
→ upstream AIAgent construction
→ one model conversation turn
→ upstream session persistence under ~/.gauntlet/runtime
→ transport-level worker result
```

Not implemented and therefore not claimed:

```text
Gauntlet runtime plugin
Gauntlet status/release tools
subprocess module adapter
runtime tool lifecycle observations
observation store
Soul finalizer
FOIL route
single user-facing gauntlet entry point
external-provider qualification
runtime tool execution
end-to-end task release
```

A transport-level `OK` means only that the worker turn completed. It is not a Gauntlet verdict,
receipt, evidence clearance, or task release.

## 8. Continue instruction

Continue with **Phase 5 only**:

1. create `gauntlet_host/gauntlet_plugin.py` and the minimum tool definitions;
2. register at least `gauntlet_task_status` and `gauntlet_release_status` through the existing
   vendored plugin/tool registry rather than a new registry;
3. create `gauntlet_host/module_cli.py` as the Gauntlet-side subprocess adapter;
4. keep Gauntlet's repository root as the adapter process import root;
5. pass task identity only through `GAUNTLET_TASK_ID`, never conversation inference;
6. make worker-side Gauntlet calls execute the adapter by exact file/module command;
7. return canonical status data without allowing a plugin or worker to create receipts,
   change verdicts, clear obligations, or release a task;
8. prove one agent-visible status call through the isolated runtime;
9. stop before tool-lifecycle observation recording, Soul finalization, FOIL routing, or the
   final product CLI.
