# FOIL certified arithmetic rule-bank small pilot — results

Verdict: **PASS_SYNTHETIC_INTEGRATION; route remains default-off and unadmitted**

The frozen 12-case pilot matched all expected outcomes:

| Outcome | Result |
|---|---:|
| Correct controls | 4/4 passed |
| Control false fires | 0/4 |
| Synthetic defects | 4/4 detected |
| Unsupported shapes | 4/4 stood down as `PARTIAL` |
| Attempt conservation | 12 = 8 executed + 4 stood down |

The four executed rule shapes were frozen `certified-v2`, separately versioned
numeric powers, complete raw numeric-equality lines, and joint trace-constraint
consistency. Provider calls, tokens, profile writes, actions, execution
authority, answer mutation, and promotion were all zero. A0 identity and
`GENERATED_UNADMITTED` origin were preserved in every raw row.

Report SHA-256:
`8171068f029c8da7c0f85ca8d455e0f4cfa216e8a01ee9059a308b0ba9f998a6`.
The report binds the exact parser, generator, verifier, compiler, admission
bridge, protocol, runner, and auditor files by SHA-256. The independent audit
rederived all summary counts, file bindings, and the report hash from 12 raw
rows.

This result is deliberately classified `SYNTHETIC_INTEGRATION_ONLY`. It is not
a false-fire probability estimate, natural-error recall, extraction recall,
fresh ProcessBench certification, calibration, admission, promotion, or
frontier-model evidence.
