# Adapt — Adaptive Reasoning Complement

**Adapt** is the Strong Inference public name for the adaptive-complement system implemented under the stable **FOIL** protocol/runtime namespace.

The product rename changes the human-facing concept, not the compatibility contract.

## Disambiguation

Adapt is a task/user complement module, not a persona-cloning system, a generic self-reflection product, or an additional source of factual authority. The technical identifier `foil` remains the stable implementation namespace.

The previous public label **Mirror — Adaptive Reasoning Complement** is retired from the Strong Inference product surface. It remains here only as migration vocabulary because older documentation and validation receipts used it.

## What Adapt does

Adapt exists to make a large toolset easier to use without turning personalization into a fixed trait model.

For the current task it asks:

1. What capabilities does this task actually require?
2. Which capabilities are already well covered by the user/current context?
3. Which load-bearing capability is missing, uncertain, or unsupported?
4. What is the smallest useful complement that fills that gap?
5. Which existing Strong Inference module, verifier, search tool, runtime, model, or external capability should provide it?
6. Did that help, was it redundant, or did it take over work unnecessarily?

Adapt is **complementary**, not automatically contrarian. It does not manufacture evidence. The specialist modules still produce claim-native evidence and receipts.

A complement may be missing knowledge, a procedure, prior art, evidence, a verifier, a representation change, a tool, execution support, a counterexample search, or a check against a plausible error.

## Mechanism

```text
CURRENT TASK REQUIREMENTS
          ×
CURRENT USER / CONTEXT EVIDENCE
          ↓
MISSING LOAD-BEARING COMPLEMENT
          ↓
MINIMUM USEFUL ASSISTANCE
```

The FOIL protocol underneath Adapt maintains competing local gap hypotheses, routes the minimum useful complement, separates assisted success from independent performance, and updates persistent evidence only under its admissibility rules.

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

Those names are **technical/protocol identifiers**, not the Strong Inference public module name.

## Evidence boundary

Adapt may decide which complement to request. That routing decision is not factual warrant.

A proof still requires proof/derivation or an appropriate prover. A software claim still requires execution. A current-fact claim still requires current sources. A benchmark claim still requires measurement. A novelty claim still requires scoped prior-art work.

Assisted success is also kept separate from later independent performance and transfer.

## Canonical technical specification

The compatibility protocol contract remains at [`skills/foil/SKILL.md`](../skills/foil/SKILL.md). Runtime ownership is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md).
