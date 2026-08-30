# TOKEN-010 implementation and qualification report

Date: 2026-08-29

## Outcome

TOKEN-010 session correctness is **PASS** on the committed Gauntlet implementation.

The host now binds each canonical Gauntlet task to one stable, private Hermes session. Every isolated worker restores the durable transcript before the next turn, while a crash-safe kernel lock serializes the complete parent launch for the same task.

## Exact source

- Gauntlet commit: `4e455e4dcddc329a6d2455676fdfc78a17338523`
- Gauntlet tree: `17225910e1962b18b652e922c01e897f707f5eb1`
- Pinned Hermes commit: `5fc308a70719a83cccdbba4c0e39c23f5a8239d5`
- Pinned Hermes tag: `v2026.8.27`
- Branch: `work/hermes-token-lean`

No GitHub push or merge was performed.

## Implementation

- Added a private HMAC task-to-session binding with domain separation. Raw task identifiers are not embedded in Hermes session identifiers.
- Added a persistent session-binding key and session lock root under the isolated Gauntlet runtime home.
- Added the derived session identifier to the strict JSONL worker request contract.
- Restored durable Hermes history with `resolve_resume_session_id` and `get_messages_as_conversation` before every resumed worker turn.
- Passed the restored history and stable session identifier into the pinned `AIAgent` API.
- Reused the repository-qualified `flock`/`msvcrt.locking` pattern to serialize same-task launches across processes and release automatically on process death.
- Bound launcher, plugin, observation bridge, measurement bridge, and FOIL route adapter to the same explicit integrity-valid Gauntlet task root.
- Added a non-destructive qualification harness that creates canonical task state only inside a disposable Gauntlet workspace.

## Live qualification

The checked-in localhost-only `phase5-mock` provider fixture observed:

- 10 turns for task A;
- 1 interleaved turn for task B;
- 11 conversation provider requests;
- one stable task-A binding;
- one stable task-A runtime session;
- every task-A request contained all prior task-A canaries;
- task B contained no task-A canary;
- task A contained no task-B canary;
- turn 6 resumed through a newly started parent launcher process;
- every turn ran in a fresh isolated worker process;
- the first task-A turn was new and turns 2-10 were durable resumes;
- no raw canary appeared in the 13 persisted measurement documents;
- repository `.egrt` state was byte-digest unchanged;
- disposable fixture `.egrt` state was byte-digest unchanged during model turns;
- no canonical receipt was created and no canonical state was mutated by qualification.

Canonical result: `outputs/TOKEN_010_QUALIFICATION_2026-08-29.json`.

## Deterministic verification

- `python -m unittest discover -s tests -v`: **478 passed**.
- TOKEN-010 focused unit tests: **3 passed**.
- Touched-file Ruff check: **PASS**.
- Touched-file Ruff format check: **PASS**.
- Compile check for touched host, tests, and verifier: **PASS**.
- Git whitespace check: **PASS**.

A repository-wide Ruff sweep was also attempted. It reported 11 pre-existing import/unused violations and legacy formatting drift in untouched files; those unrelated files were not mechanically rewritten in this checkpoint.

## Process assurance

**PROCESS ASSURANCE**

- Fired: `frame`, `self`, `boundary`
- Claim/frame: task continuity can be qualified without mutating the active repository state.
- Evidence inspected: two failed live probes, launcher environment construction, plugin adapter checks, FOIL route bridge checks, the passing disposable-workspace run, and the 478-test suite.
- Counterevidence: the original runtime assumed the code checkout and canonical task root were the same path at multiple seams.
- Result: `CLEARED` for TOKEN-010 after amending all four root consumers to one explicit integrity-valid task root.
- Consequence: downstream token-efficiency stages may now use the session-correct chat path.

## Claim boundary

This checkpoint establishes session correctness on the pinned deterministic local fixture. It does not claim token savings, cost savings, production-provider equivalence, or noninferiority for later optimization stages.
