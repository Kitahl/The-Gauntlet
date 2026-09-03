# Hermes source adoption ledger

**Ledger ID:** `GAUNTLET-HERMES-SOURCE-001`  
**Fast-build branch:** `work/native-hermes-fastpath`  
**Authority:** `vendor/HERMES_SNAPSHOT.json` is the machine-readable source record.

## 1. Frozen upstream source

| Field | Value |
|---|---|
| Upstream repository | `NousResearch/hermes-agent` |
| Stable release | `v2026.8.27` / Hermes Agent `v0.20.6` |
| Exact commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| License | MIT |
| Upstream license SHA-256 | `821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6` |
| Local destination | `vendor/hermes-agent/` |
| Adoption method | Git submodule-style gitlink pinned to the exact upstream commit |
| Runtime role | Internal isolated worker implementation; never Gauntlet evidential authority |

## 2. Current source state

`GITLINK_VERIFIED`

Gauntlet records the upstream Hermes tree as a Git gitlink rather than copying the full
third-party source tree into Gauntlet history. This preserves exact source identity while
preventing upstream documentation, test fixtures, public OAuth client identifiers, and
secret-shaped examples from being misclassified as first-party Gauntlet credentials by the
repository-wide full-history secret scan.

The remediation does **not** add a Gitleaks allowlist and does **not** weaken the first-party
secret scanner. The pinned upstream source must be initialized through Git submodules before
the native Hermes worker is executed.

| Verification field | Value |
|---|---|
| Gitlink commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| Upstream tag | `v2026.8.27` |
| License SHA-256 | `821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6` |
| Local modifications | `0` |

## 3. Checkout and verification

From the repository root:

```bash
git submodule update --init --depth 1 -- vendor/hermes-agent
python scripts/vendor_hermes.py --verify-only
```

Or initialize and verify in one bounded command:

```bash
python scripts/vendor_hermes.py --init
```

`vendor/hermes-agent` must remain a mode-`160000` gitlink to the exact pinned commit. A
copied source tree at that path is rejected by the verifier.

## 4. Local modifications inside the upstream tree

None.

Do not edit the submodule worktree as part of Gauntlet. A future Hermes upgrade must update
the gitlink, the machine-readable source record, and this ledger together after license,
security, and behavior qualification.

## 5. Authority boundary

Hermes runtime output is an observation. It cannot directly create a canonical Gauntlet
`Receipt`, change a `Verdict`, clear an `Obligation`, or bypass Soul's `release_gate()`.
