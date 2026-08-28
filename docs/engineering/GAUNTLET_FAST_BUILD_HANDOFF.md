# Gauntlet Fast Build — Session-to-Codex Handoff Ledger

**Handoff ID:** `GAUNTLET-FAST-HANDOFF-001`  
**Repository:** `Kitahl/The-Gauntlet`  
**Branch:** `work/native-hermes-fastpath`  
**Baseline commit:** `4f088d688fa9e25b4608f44000a5d9812efa45f9`  
**Governing plan:** `docs/engineering/GAUNTLET_FAST_BUILD_HERMES_INTERNAL_RUNTIME_2026-08-28.md`

## 1. Frozen implementation decision

The fast build vendors the pinned Hermes Agent `v0.20.6` source and runs it later as an
isolated internal subprocess. Gauntlet remains the sole authority over obligations,
receipts, verdicts, and release. Same-process imports between the two top-level package
trees are prohibited.

## 2. Phase ledger

| Phase | Scope | State | Commit |
|---:|---|---|---|
| 1 | Pin, provenance, license, deterministic vendoring command, governing plan | `COMPLETE` | this commit |
| 2 | Materialize and verify `vendor/hermes-agent/` at the exact commit | `NEXT` | — |
| 3 | Add `gauntlet_host` constants, typed JSONL IPC, isolated worker bootstrap | `PENDING` | — |
| 4 | Add launcher, runtime profile, Gauntlet-owned runtime home | `PENDING` | — |
| 5 | Add status/release plugin tools and subprocess module adapter | `PENDING` | — |
| 6 | Add observation bridge and Soul finalizer | `PENDING` | — |
| 7 | Add FOIL advisory route and single `gauntlet` entry point | `PENDING` | — |
| 8 | Perform the eight-item manual boot verification and prepare Codex transfer | `PENDING` | — |

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

## 4. Continue instruction

Continue with **Phase 2 only**:

1. run `python scripts/vendor_hermes.py --dry-run`;
2. materialize the exact pinned source;
3. run `python scripts/vendor_hermes.py --verify-only`;
4. update this ledger with the resulting file count, tree SHA-256, and commit SHA;
5. stop before implementing `gauntlet_host/`.
