# Counterform — Adaptive Reasoning Complement

**Counterform** is BASTION-01's public name for the adaptive complement system
implemented under the stable technical identifier **FOIL**. **Mirror** was an
earlier public display name and remains only as a compatibility locator.

The public rename changes no profile, command, receipt, evidence rule, or release
authority.

## What Counterform does

Counterform exists to make a large specialist system adapt to the current task
without pretending to diagnose a person.

For the current task it asks:

1. What capabilities does this task actually require?
2. Which capabilities are already well covered by the user and current context?
3. Which load-bearing capability is missing, uncertain, or unsupported?
4. What is the smallest useful complement that fills that gap?
5. Which existing module, verifier, search tool, runtime, model, or external
   capability should provide it?
6. Did that assistance help, repeat work, or take over work unnecessarily?

Counterform is complementary, not automatically contrarian. It is not an extra
evidence producer and does not manufacture warrant. BASTION-01's specialist
modules still produce claim-native evidence and receipts.

A complement may be missing knowledge, a procedure, prior art, evidence, a
verifier, a representation change, a tool, execution support, a counterexample
search, or a check against a plausible error.

## Why the name fits

In design, a counterform is the shape defined by the form around it. The mechanism
compares the current task's requirements with the capabilities and evidence
already present, then supplies the smallest load-bearing part that is absent:

```text
CURRENT TASK REQUIREMENTS
          ×
CURRENT USER / CONTEXT EVIDENCE
          ↓
MISSING LOAD-BEARING COMPLEMENT
          ↓
MINIMUM USEFUL ASSISTANCE
```

## Compatibility

The following identifiers remain unchanged so existing installations, profiles,
tests, benchmark receipts, and links do not break:

- skill directory: `skills/foil/`
- technical skill name: `foil`
- slash command: `/foil`
- runtime modules: `tools/foil_*`
- environment variables such as `FOIL_TASK_RUN`
- `.foil/` runtime/config paths
- historical benchmark condition names such as `FOIL`, `FOIL_PROFILE`, and `FOIL_MM`
- existing FOIL- and Mirror-named research, validation, onboarding, and link paths

Those are compatibility identifiers, not the public concept name.

## Evidence boundary

Counterform may decide which complement to request. That routing decision is not
factual warrant. Proof still requires proof or an appropriate prover; software
claims require execution; current-fact claims require current sources; benchmark
claims require measurement; novelty claims require scoped prior-art work.

Assisted success remains separate from later independent performance and transfer.

## Canonical technical specification

The compatibility skill contract remains at
[`skills/foil/SKILL.md`](../skills/foil/SKILL.md). Runtime ownership is documented
in [`ARCHITECTURE.md`](ARCHITECTURE.md), and the complete public naming contract is
in [`BRAND_ARCHITECTURE.md`](BRAND_ARCHITECTURE.md).
