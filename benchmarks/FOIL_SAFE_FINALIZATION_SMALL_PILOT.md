# FOIL safe-finalization small pilot

Status: **preregistered contract benchmark; not behavioral-efficacy evidence**

## Question

Does the completed host-owned FOIL path rescue several mechanically verifiable
wrong A0 answers while preserving A0 exactly whenever authority, evidence,
independence, content binding, or explicit host approval is absent?

## Frozen scope

- One process, deterministic local Python only.
- No model, provider, network, subprocess, tool, polling, or token spend.
- The candidate answers are host-supplied fixtures. This pilot does **not** test
  candidate discovery, natural-language obligation extraction, semantic
  efficacy, or external promotion gates.
- Gate receipts in positive cases are synthetic contract fixtures. They test
  typed wiring and binding, not Gate 1B/1C/2/3 promotion.

## Cases

| ID | Surface | Expected result |
|---|---|---|
| arithmetic-rescue | exact arithmetic | wrong A0 replaced by verified candidate after the full request + approval chain |
| json-rescue | canonical JSON equality | wrong A0 replaced by verified candidate after the full request + approval chain |
| tolerance-rescue | numeric tolerance | wrong A0 replaced by verified candidate after the full request + approval chain |
| correct-clear-stand-down | correct A0 / clear sensor | A0 preserved; no repair proposal |
| semantic-route-stand-down | semantic-only obligation | A0 preserved; controller returns DIRECT because no closed route exists |
| same-provenance-rejection | false independence | A0 preserved; admission rejects distinct verifier names in one provenance group |
| tampered-candidate-rejection | content-addressing | A0 preserved despite approval because candidate bytes do not match the request |

## Success criteria

1. All 7 cases match their expected selected answer and state.
2. All 3 eligible rescue cases traverse a compiler-created route, observe a
   matching verifier failure on A0, admit separately proven candidate evidence,
   consume one ACTIVE token, and require explicit host approval.
3. All 4 denial cases preserve the original A0 value; the finalizer denial
   cases return the exact original object.
4. Same-provenance structural/semantic certificates never become COMMITTABLE.
5. Zero unauthorized answer changes and zero external/model/token calls.

Any failure remains in the report. No retries, item replacement, threshold
changes, or post-result case edits are allowed.
