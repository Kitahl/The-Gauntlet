# FOIL safe-finalization small pilot result

This is deterministic software-contract evidence, not behavioral-efficacy or promotion evidence.

- Overall: **7/7 passed**
- Rescue cases: **3/3**
- Preservation/rejection cases: **4/4**
- Unauthorized answer changes: **0**
- Model/network calls: **0 / 0**
- Token cost: **0**

| Case | Result | State | Reason | Elapsed (ms) |
|---|---:|---|---|---:|
| arithmetic-rescue | PASS | CANDIDATE_SELECTED | explicit_host_approval_and_content_bindings_matched | 3.313 |
| json-rescue | PASS | CANDIDATE_SELECTED | explicit_host_approval_and_content_bindings_matched | 4.125 |
| tolerance-rescue | PASS | CANDIDATE_SELECTED | explicit_host_approval_and_content_bindings_matched | 3.014 |
| correct-clear-stand-down | PASS | BASE_PRESERVED | no_defect_reported | 0.028 |
| semantic-route-stand-down | PASS | BASE_PRESERVED | HOST_ROUTE_UNAVAILABLE | 0.373 |
| same-provenance-rejection | PASS | BASE_PRESERVED | structural_semantic_provenance_overlap | 1.149 |
| tampered-candidate-rejection | PASS | BASE_PRESERVED | candidate_digest_mismatch | 2.002 |

The three positive cases use host-supplied candidate fixtures and synthetic gate receipts.
They establish wiring and fail-closed selection behavior only; they do not establish that FOIL can discover repairs or improve real tasks.
