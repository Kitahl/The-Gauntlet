# FOIL R1.6 fidelity addendum

Status: **one execution-class generator implemented; calibration absent**

The general fidelity contract in `FOIL_FORMALIZATION_FIDELITY.md` remains in
force. R1.6 changes only the earlier statement that no generator is shipped.

`gsm8k.annotated-arithmetic.v1` has small translation distance because it reads
explicit, machine-like calculation annotations. That does not make its
extraction faithful by assertion. Its first evidence is therefore a small,
no-oracle historical-model smoke pilot with:

- mutation controls covering seven named defect classes;
- natural misses independently labelled before scanner execution;
- correct-response false-fire controls;
- separate mutation and natural per-class rates;
- typed non-identifiability when common support or variance is absent; and
- no admission or promotion consequence.

The pilot does not establish route fidelity, extraction recall, real-traffic
coverage, production prevalence, frontier-model behavior, or independence of
future formalizers. It cannot open the admission gate. A future production route
must still satisfy the existing route-scoped calibration, mutation completeness,
extraction-recall, freshness, instance-check, and conservative-bound policies.


R1.7 treats every R1.6 row as development evidence. It does not tune v2 and
rescore the same rows as held out. The v2 grammar and decision thresholds are
committed first; fresh hash-selected source rows exclude the complete R1.6
curation/control/mutation question universe, and labels freeze before scanner
execution. This is a dose-response smoke rerun, not calibration. A favorable
result can justify a larger independent study but cannot admit or promote v2.
R1.6 also preserves the central scope boundary: explicit annotated arithmetic is
not free-form prose-to-obligation transformation. `PARTIAL`, `ABSTAIN`, and
`UNSUPPORTED` are first-class outcomes, and omissions outside the supported
annotation grammar are not counted as covered claims.

The certified arithmetic rule bank does not change that boundary. P0.5's 3,400
ProcessBench rows are development evidence used to select `certified-v2`;
zero observed false fires on those rows is not a fresh per-split certificate.
The rule-bank small pilot contains only 12 frozen synthetic integration cases.
Its purpose is parser/verifier/admission plumbing, not a probability, recall, or
coverage estimate. Every rule remains default-off and
`GENERATED_UNADMITTED` until fresh route-specific evidence passes the existing
admission contract.
