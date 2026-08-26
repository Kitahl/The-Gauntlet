# FOIL SKILL contract audit

`tools/foil_contract_audit.py` converts the current 19-section
`skills/foil/SKILL.md` into a closed, drift-detecting map. Every source line that
contains the normative words `must` or `never` has exactly one entry in
`docs/FOIL_SPEC_CONTRACT_MAP.json`. Adding an unmapped modal line, moving a
mapped clause, deleting named evidence, or assigning evidence to an
`UNTESTABLE_AS_WRITTEN` clause fails closed.

Current static result (2026-08-26):

| Item | Count |
|---|---:|
| Sections | 19 |
| Normative modal lines | 35 |
| Modal word occurrences | 36 |
| `TESTED` | 25 |
| `PARTIAL` | 9 |
| `UNTESTABLE_AS_WRITTEN` | 1 |
| Unmapped / extra lines | 0 / 0 |

The 36-to-35 difference is the phrase `must never`, which is one normative line
containing both modal words. The single untestable clause is the semantic claim
that a citation entails a claim at its stated scope. Software can enforce typed
source and claim records, but that unrestricted semantic relation is not
machine-testable as currently written.

This report is a topology and evidence-link audit. Existing test-file paths are
not proof that every behavior is correct, and the map makes no efficacy claim.

Reproduce with:

```powershell
python -m unittest tests.test_foil_contract_audit
python tools/foil_contract_audit.py
```
