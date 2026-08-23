# Mirror — Adaptive Reasoning Complement

**Mirror** is the public name for the adaptive complement system historically named **FOIL**.

The rename changes the human-facing concept, not the compatibility contract.

## Disambiguation

This project's **Mirror — Adaptive Reasoning Complement** is not the 2025 research framework **MIRROR: Multi-agent Intra- and Inter-Reflection for Optimized Reasoning in Tool Learning**, and it is not a persona-cloning or self-reflection product. No novelty claim is made for the word "Mirror" itself.

Here, **Mirror** specifically means the task/user complement mechanism described below. The technical identifier `foil` is retained as a stable disambiguating implementation name.

## What Mirror does

Mirror exists to make a large toolset easier to use.

For the current task it asks:

1. What capabilities does this task actually require?
2. Which of those capabilities are already well covered by the user/current context?
3. Which load-bearing capability is missing, uncertain, or unsupported?
4. What is the smallest useful complement that fills that gap?
5. Which existing Gem, verifier, search tool, runtime, model, or external capability should provide it?
6. Did that help, was it redundant, or did it take over work unnecessarily?

Mirror is **complementary**, not automatically contrarian. It is not a sixth Gem and it does not manufacture evidence. The existing specialist modules still produce claim-native evidence and receipts.

A complement may be missing knowledge, a procedure, prior art, evidence, a verifier, a representation change, a tool, execution support, a counterexample search, or a check against a plausible error.

## Why the name fits

The core mechanism is a dynamic comparison between:

```text
CURRENT TASK REQUIREMENTS
          ×
CURRENT USER / CONTEXT EVIDENCE
          ↓
MISSING LOAD-BEARING COMPLEMENT
          ↓
MINIMUM USEFUL ASSISTANCE
```

It "mirrors" the task against what is already covered and supplies what is missing rather than applying the same fixed workflow to everyone.

## Compatibility

The following identifiers remain unchanged so existing installations, profiles, tests, benchmark receipts, and links do not break:

- skill directory: `skills/foil/`
- technical skill name: `foil`
- slash command: `/foil`
- runtime modules: `tools/foil_*`
- environment variables such as `FOIL_TASK_RUN`
- `.foil/` runtime/config paths
- historical benchmark condition names such as `FOIL`, `FOIL_PROFILE`, and `FOIL_MM`
- existing FOIL-named research, validation, and onboarding files

Those names are now **legacy technical identifiers**, not the public product/concept name.

## Evidence boundary

Mirror may decide which complement to request. That routing decision is not factual warrant.

A proof still requires proof/derivation or an appropriate prover. A software claim still requires execution. A current-fact claim still requires current sources. A benchmark claim still requires measurement. A novelty claim still requires scoped prior-art work.

Assisted success is also kept separate from later independent performance and transfer.

## Canonical technical specification

The compatibility skill contract remains at [`skills/foil/SKILL.md`](../skills/foil/SKILL.md). Runtime ownership is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md).
