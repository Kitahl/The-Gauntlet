# Hermes source adoption ledger

**Ledger ID:** `GAUNTLET-HERMES-SOURCE-001`  
**Fast-build branch:** `work/native-hermes-fastpath`  
**Authority:** `vendor/HERMES_SNAPSHOT.json` is the machine-readable snapshot record.

## 1. Frozen upstream source

| Field | Value |
|---|---|
| Upstream repository | `NousResearch/hermes-agent` |
| Stable release | `v2026.8.27` / Hermes Agent `v0.20.6` |
| Exact commit | `5fc308a70719a83cccdbba4c0e39c23f5a8239d5` |
| License | MIT |
| Upstream license SHA-256 | `821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6` |
| Local destination | `vendor/hermes-agent/` |
| Adoption method | Full source snapshot with only nested `.git` metadata excluded |
| Runtime role | Internal isolated worker implementation; never Gauntlet evidential authority |

## 2. Current phase state

`PREPARED_NOT_MATERIALIZED`

This phase commits the exact pin, the unmodified MIT notice, and a deterministic
materialization/verification command. The full upstream tree is intentionally populated
in the next phase from a networked checkout so that the exact commit can be verified
before any bytes enter `vendor/hermes-agent/`.

## 3. Materialization commands

From the repository root:

```bash
python scripts/vendor_hermes.py --dry-run
python scripts/vendor_hermes.py
python scripts/vendor_hermes.py --verify-only
```

To use an already available clean checkout:

```bash
python scripts/vendor_hermes.py --source /path/to/hermes-agent
```

Replacement of an existing vendored tree requires an explicit reviewed action:

```bash
python scripts/vendor_hermes.py --force
```

## 4. Local modifications inside the vendored tree

None permitted by default.

The source snapshot must remain byte-for-byte faithful to the pinned checkout except for
excluding `.git` metadata. Any future edit under `vendor/hermes-agent/` must be listed here
with the local path, reason, reviewer, and replacement or removal plan.

## 5. Authority boundary

Vendored runtime output is an observation. It cannot directly create a canonical Gauntlet
`Receipt`, change a `Verdict`, clear an `Obligation`, or bypass Soul's `release_gate()`.
