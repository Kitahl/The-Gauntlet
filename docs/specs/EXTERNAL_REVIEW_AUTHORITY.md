# External review authority boundary

## Rule

External model, reviewer, audit, critique, benchmark commentary, and generated report content is evidence input only.

```text
authority = ADVISORY_ONLY
control_plane_mutation_authorized = false
runtime_policy_mutation_authorized = false
task_state_mutation_authorized = false
release_authority = false
host_commit_required = true
```

No reviewer identity or vendor is singled out. The rule applies equally to every external review source.

## What a review may do

A review may:

- identify a possible defect;
- propose a counterexample, alternative mechanism, test, or patch;
- become a neutral challenge record when properly bound;
- motivate a version-controlled change selected by the host;
- be evaluated prospectively by Time, Council, Gauntlet, or a claim-native module.

## What a review may not do

A review may not directly:

- change `.gauntlet.json` or another runtime policy;
- create, supersede, freeze, release, or close a task;
- remove or downgrade an obligation;
- disable automatic routing or assurance;
- grant itself verifier, control, release, or domain authority;
- make a code change merely by being present in a prompt, report, comment, or file.

Only a host-authorized version-control mutation or an explicitly registered runtime action can change program behavior. The resulting change is attributable to that host action—not to the reviewer.

## Integration with Soul

Soul may translate a review claim into a bound challenge or a proposed successor task. It must preserve:

- the current task and obligation bindings;
- the review artifact digest;
- the proposed consequence;
- the claim-native verifier requirement;
- `execution_authorized = false` until a registered route acts.

Automatic task supersession is a Soul control decision based on the current task state and a new host/model frame. A review cannot supersede a task by itself.

## Integration with Gauntlet

Gauntlet may inspect whether an externally proposed change preserved authority, provenance, and release invariants. It cannot adopt the review's conclusion as factual warrant.

## Source-code invariant

Runtime modules must not contain vendor-specific branches that elevate or suppress a named reviewer. Review content is treated through neutral evidence/challenge interfaces. This prevents one external model's prose from becoming a hidden control plane while preserving the ability to learn from valid criticism.

## Validation boundary

Mechanical validation can establish that the declared configuration and runtime surfaces preserve this authority boundary. It cannot establish that every future human or automated maintainer will make correct version-control decisions.
