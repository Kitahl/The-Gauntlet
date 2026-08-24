# FOIL formalization fidelity and extraction recall

Status: **admission seam implemented; external generator and calibrated routes absent**

## Current boundary

FOIL v5 does not transform free-form prose into obligations. The host supplies a
strict versioned declarative task spec; `foil_obligation_compiler.py` validates and
binds it but never extracts checks from prose.

Consequently, current decidable coverage measures only a supplied obligation
universe. It does not measure FOIL's ability to find decidable structure in prose,
does not prove that the universe faithfully represents the source, and cannot be
read as global semantic correctness.

Closed fields, versions, digests, enums, and a closed verifier registry establish
structural validity and integrity. They do not establish semantic faithfulness or
extraction recall.

Any external component that generates obligations from natural language must pass
this gate before its output can feed the existing compiler.

## Implemented admission seam

`foil_formalization_admission.py` implements the fail-closed boundary. It binds
the exact route, formalizer identities, task regime, compiler schema, source,
generated spec, calibration, policy, and per-instance evidence. Admission uses
a conservative one-sided Clopper-Pearson lower bound for both route fidelity and
separately adjudicated extraction recall; it also requires freshness, a complete
predeclared mutation suite, instance checks, and—on translation routes—dual
formalization, mechanical equivalence, and a measured error-correlation ceiling.

`foil_formalization_routing.py` preserves the core controller's closed verifier
routes while keeping `ADMITTED_GENERATED` visible in the outer trace. Admission
never grants execution or answer-mutation authority. No generator is shipped, no
real route has earned calibration, and the host-supplied route remains distinct.

## The 21-point contract

1. Keep the current host-supplied route distinct from every generated route.
2. Version the generator, prompt/contract, model, task regime, and output schema.
3. Bind the source artifact and every generated obligation by digest.
4. Define route scope narrowly; no global fidelity scalar is permitted.
5. Separate execution-class routes from genuine semantic-translation routes.
6. Treat arithmetic, schema, repository query, and executable-test routes as
   near-zero translation only after their mutation controls pass.
7. Give prose-to-logic, quantifier/scope, and theorem-formalization routes the
   full semantic-fidelity gate.
8. Never let a formalizer judge its own faithfulness as load-bearing evidence.
9. Use independent dual formalizations only when their comparison is a mechanical
   equivalence check over a shared, frozen semantics.
10. Treat A/B disagreement as a sound defect signal: at least one formalization is
    unfaithful or outside the comparison contract.
11. Do not treat A/B agreement as proof; measure correlated error and common
    wrong-agreement on held-out audited items.
12. Require a versioned mutation suite with planted omission, scope, quantifier,
    unit, sign, boundary, and predicate defects.
13. A check is unvalidated until it catches every predeclared planted defect class;
    this never means every conceivable defect.
14. Maintain a route-specific posterior from independently audited outcomes, not
    from self-reports or proxy-check agreement counted as Bernoulli truth.
15. Gate on a conservative lower bound or calibrated per-instance risk score, not
    a point estimate.
16. Fail closed and abstain outside the exact validated route/version/scope.
17. Report a held-out risk-coverage curve so abstention cost is visible.
18. Measure extraction recall separately: load-bearing claims omitted before
    formalization are invisible to fidelity checks.
19. Measure extraction precision separately from declared-universe coverage.
20. Measure real-claim routable coverage, observed-error coverage, detection yield,
    human audit time, runtime cost, and abstention before financing a large gate.
21. Generated obligations may never raise certificate class, action authority, or
    answer-mutation authority beyond the evidence independently admitted for that
    exact route and instance.

## Dual formalization: what it buys

Mechanical disagreement is decisive about consistency, not about which side is
faithful. Mechanical agreement is useful only to the extent the two formalizers'
errors are decorrelated and the equivalence checker covers the intended semantics.
Same-family formalizers may echo the same omission or scope error. Correlation
alone is not a complete error model; common wrong-agreement and checker
`UNKNOWN`/timeout rates must also be measured. `UNKNOWN` is abstention, never
agreement.

The mechanical comparison is what avoids a semantic-judge regress. Asking a model
whether its own translation is faithful does not.

## Extraction recall is a separate gate

Round-trip checks, bidirectional entailment, dual formalization, and mutation
testing can assess only claims that were extracted. None can detect a load-bearing
claim that was never proposed.

A future extraction study therefore requires a separately adjudicated source
claim inventory and reports:

- recall of load-bearing claims;
- precision of extracted claims;
- routable share of all load-bearing claims;
- share of observed errors inside the routable subset;
- unresolved/omitted/undecidable mass without pooling;
- human and runtime cost.

Failure to meet the extraction floor means abstain from any completeness claim,
even when declared-universe coverage is 100%.

## Pilot policy

The RC4 integrated pilot ran only three synthetic calibration rows to exercise
the admission wiring. It does not estimate a certification floor, measure real
fidelity or extraction recall, or open a generated-obligation route. No large
audit budget is authorized by this document.

The admission rule remains:

> Narrow routes with earned bounds, independent per-instance checks, abstention
> outside validated scope, a mutation suite that catches every predeclared defect
> class, separately floored extraction recall, and measured real-claim coverage
> sufficient to justify the audit cost.
