# Governed Full-Hermes Runtime Handoff

**Branch:** `work/hermes-token-lean`

**Pinned Hermes:** `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` (`v2026.8.27`)

## Outcome

The host now has two explicit, isolated runtime profiles:

- `gauntlet-lean.v1` remains the frozen compatibility/evaluation profile. It exposes only the four compiled Gauntlet tools and retains the qualified sparse-context behavior.
- `gauntlet-governed.v1` restores the normal pinned Hermes CLI surface while retaining task/session binding, Gauntlet status tools, module-owned receipts, and Soul's fail-closed release gate.

Governed mode is opt-in:

~~~powershell
python -m gauntlet_host.cli run --profile governed --root . "your task"
python -m gauntlet_host.cli chat --profile governed --root .
~~~

Use `--profile lean` (the compatibility default) for the TOKEN-700-qualified surface.

## Codex plugin

The repository includes `plugins/hermes-gauntlet` version `0.2.0`. The plugin exposes two Codex skills:

- `governed-hermes` diagnoses, starts, resumes, or opens the full governed runtime. Persistent privacy-bounded FOIL/Mirror profile adaptation remains active on every governed prompt.
- `hermes-foil` creates explicit adaptation work through the helper's `foil` command. That command forces `--kind ADAPTATION` and a `/foil` prompt so the receipt is bound to the correct task rather than a global active-task pointer.

After the plugin has been registered in a local or shared Codex marketplace, invoke `$hermes-gauntlet:governed-hermes` for ordinary governed work or `$hermes-gauntlet:hermes-foil` for explicit adaptation work. The helper remains usable without skill invocation:

~~~powershell
python plugins\hermes-gauntlet\scripts\hermes_gauntlet.py doctor --json
python plugins\hermes-gauntlet\scripts\hermes_gauntlet.py foil --prompt "adapt to what I am missing"
python plugins\hermes-gauntlet\scripts\hermes_gauntlet.py continue --task-id "task-..." --prompt "/foil continue the adaptation"
~~~

The public resume handle is always the Gauntlet task ID. The internal Hermes session ID remains private, and neither plugin skill performs canonical release automatically.

## Governed capabilities

The governed profile enables:

- persistent Hermes memory and user-profile stores in a dedicated named profile;
- persistent privacy-bounded FOIL/Mirror adaptation on every governed prompt;
- explicit FOIL task binding, so concurrent tasks cannot misattribute adaptation receipts through the global active-task pointer;
- project context files and trusted project-local/external skill discovery;
- all repository Gem skills, including Soul and Infinity Gauntlet's Black Gem path;
- normal coding-context detection against the requested project working directory;
- environment probing, execution guidance, stall guards, completion guidance, parallel-tool guidance, and verify-on-stop;
- the pinned `hermes-cli` toolset, including terminal/process, files, web, browser (when installed), vision/image (when configured), skills, todo, memory, session search, code execution, and `delegate_task`;
- bounded pre-agent MCP discovery plus native between-turn MCP refresh and dynamic plugin/MCP tool assembly;
- up to 64 agent iterations within the existing wall-clock run budget;
- normal post-turn memory/skill review with a 60,000-input-token cap and paid auxiliary fallback disabled;
- clean persisted user messages: task/status/FOIL context remains a volatile API sidecar.

The profile inherits normal Hermes `config.yaml` values (including model, MCP definitions, and enabled-plugin policy), then applies the governed safety/capability overrides. It uses Hermes' standard named-profile path so provider authentication can use Hermes' read-only root-auth fallback. Sessions, memory, skills, pending writes, measurements, and plugins remain isolated from the default Hermes profile.

## Authority boundary

Autonomy applies to detection, routing, tool use, delegation, Gem execution, verification, and receipt production. It does not collapse evidence authority:

- model prose and raw tool output are not canonical receipts;
- each obligation is clearable only by the module dictated by its kind;
- FOIL can clear only an explicitly requested `ADAPTATION` obligation;
- Black Gem never emits `CLEARED`;
- Gems do not self-certify;
- Soul remains the only canonical release gate.

The parent finalizer automatically evaluates Soul's release gate after every completed turn. Canonical task release remains an explicit operator mutation:

~~~powershell
python tools/soul_runtime.py --root . release <task-id>
~~~

Automatic release was deliberately not enabled. A `CLEARED` finalization reports eligibility but does not silently set the task's `released` flag.

## Verification notes

The no-model pinned-runtime probe exposed all required core governed tools and all four Gauntlet tools. Optional tools whose local executables or credentials were absent correctly failed their Hermes `check_fn` and were omitted for that turn.

The current host Python environment lacks the pinned optional `snowballstemmer` dependency, so Hermes logs that progressive tool-search indexing is skipped. This does not block MCP discovery or tool registration: the assembly path catches the optional-index failure and returns the full filtered tool list. No dependency was downloaded because this retrofit was constrained to repository-local code.

User-installed executable plugin bundles are profile-isolated by Hermes. Governed mode inherits the normal enabled/disabled plugin policy and bundled/project plugins, but it does not copy arbitrary executable bundles from the default profile. Install a user plugin into the governed Hermes profile if that plugin must execute there.

## Token boundary

The governed profile is a capability profile, not a TOKEN-700 replacement result. The frozen lean profile remains the only measured token-efficiency option. Governed mode intentionally pays for broader tools, memory/profile context, project context, and verification. It retains the verified no-title-call saving and caps background review, but it has not been benchmarked against TOKEN-700 thresholds.
