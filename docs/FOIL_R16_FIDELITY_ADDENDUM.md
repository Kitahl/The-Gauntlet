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

R1.6 also preserves the central scope boundary: explicit annotated arithmetic is
not free-form prose-to-obligation transformation. `PARTIAL`, `ABSTAIN`, and
`UNSUPPORTED` are first-class outcomes, and omissions outside the supported
annotation grammar are not counted as covered claims.
