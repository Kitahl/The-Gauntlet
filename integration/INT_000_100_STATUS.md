# INT-000 / INT-100 status

## Current stable consumer

- Branch: `integration/vnext-core`
- Base main: `4f088d688fa9e25b4608f44000a5d9812efa45f9`
- Imported exact source checkpoint: `7fcfd259a6b103a464061c1d30f2a48fa1ff7f52`
- Native/Hermes dependency: absent
- Core default mode: direct

## Exact ancestry retained

```text
main 4f088d6
  → Mind af8dc26
  → Council vNext 1321729
  → Council v3 7fcfd25
```

The exact source commits were retained by non-force fast-forward. Their current state is
`AUDITED`, not `ADMITTED`, because binary/full-index patch digests and integrated exact-head
qualification remain pending.

## Open blockers

- `BLOCKER-TIME-IDENTITY`
- `BLOCKER-TIME-ARTIFACT-DIVERGENCE`
- `BLOCKER-INT100-PATCH-DIGESTS`
- `BLOCKER-INT100-H2`

No claim of complete vNext integration, Time admission, Hermes checkpoint compatibility,
or native-runtime completion is made.
