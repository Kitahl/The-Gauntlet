# FOIL RPS v0.6.2 frozen shadow policy

Status: `DEFAULT-OFF / SHADOW-ONLY / NOT PROMOTED`

The host-verifier outcome is the sole blind-rival gate. The answer generator
must not choose or adjudicate the host check.

| Host outcome | Shadow transition |
|---|---|
| `CONFIRMED` | `STAND_DOWN` |
| `CONTRADICTED` | `ABSTAIN` |
| `NOT_APPLICABLE` | `REQUEST_BLIND_RIVAL` |
| `UNCERTAIN` | `REQUEST_BLIND_RIVAL` |

After one admitted blind rival:

- matching answer digests produce `CORRELATED_AGREEMENT`;
- different answer digests produce `ABSTAIN`.

The blind-rival envelope contains no incumbent-answer field. One rival is the
maximum. Answer mutations, execution authority, promotion authority, provider
calls from the deterministic host verifier, and profile writes are all zero.

Total cost means input plus output tokens. Output-only cost is diagnostic.
Abstention is a primary result, not a hidden failure mode.
