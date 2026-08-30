# FOIL Shadow Authority Kernel

Status: `IMPLEMENTED_SHADOW_ONLY / BEHAVIORAL_EFFICACY_NOT_MEASURED`

This additive kernel is the first executable slice of the FOIL v4.2 restricted-
authority design. It leaves the existing FOIL V2 routing policy and capability
registry unchanged. It does not execute tools, mutate an answer, or authorize a
write.

## Two independent decisions

1. `decide_authority` maps a trusted sensor registration, an untrusted sensor
   report, and explicit owner/calibration context to one shadow action.
2. `decide_admission` evaluates a proposed answer delta against a structurally
   bound patch certificate and a separately represented semantic verification.
   A successful result is only `COMMITTABLE`; a host still has to make the final
   commit decision.

Certificate success never admits a repair by itself.

## Fixed safety invariants

- Sensor reports contain no authority field. Authority comes only from a trusted
  registration.
- Prompt and person evidence cannot receive escalation or repair-proposal
  authority.
- Evidence strength and action authority are separate axes.
- Unknown applicability, unknown outcomes, mismatched sensor identity, and
  mismatched target scope fail closed.
- Repair proposals require all three explicit prerequisites: proposal mode is
  enabled, calibration is current, and owner risk policy permits a proposal.
- All authority decisions are shadow-only, preserve the base answer, and deny
  execution. These fields cannot be overridden through normal construction.
- Candidate, structural certificate, and semantic verification are bound to the
  same base, candidate, scope, and obligation-set digests.
- Verifier authority resolves through a closed host registry. Registration binds
  authority ID, role, version, implementation digest, authorized scope,
  environment digest, and the complete registration digest.
- Every certificate carries canonical verifier input plus the observed result.
  Admission recomputes the evidence digest, reruns the closed deterministic
  verifier, and compares the complete result. Caller-selected PASS values and
  syntactically valid arbitrary hashes have no authority.
- The repair producer cannot certify or semantically verify its own candidate.
  Producer, structural verifier, and semantic verifier implementation digests
  must be distinct; verifier names alone never establish independence.
- Missing, failed, or unknown checks never make a candidate committable.
- Even `COMMITTABLE` candidates preserve the base answer, deny execution, and
  require a host commit.
- Public input is strictly typed; strings such as `"FAIL"` and truthy values such
  as `"false"` cannot bypass enum or boolean checks.

## Deliberately absent

The default registry currently authorizes only closed deterministic structural
verifiers. It contains no independently authorized semantic verifier, so a
caller cannot reach `COMMITTABLE` by relabeling a built-in result. Adding a real
semantic authority requires a separately implemented and registered verifier,
not a runtime string or provenance edit.

This slice does not provide production sensors, a repair generator, an executor,
a host integration, calibration data, efficacy measurements, or proof that FOIL
selects the minimum correct residual complement. Those require the staged
experiments and RQ-26 evaluation described in the audited research docket.

FOIL remains separate from Gauntlet and Mastermind. This module imports neither
system and grants neither system control authority.
