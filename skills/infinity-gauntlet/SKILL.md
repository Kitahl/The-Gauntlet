---
name: infinity-gauntlet
description: Process Assurance Framework. Trigger: /gauntlet, repeated failed attempts, ungated kill/finding, last-surviving option, inherited number, stale authority, cross-context handoff, unclear architecture, or an all-green verification claim. Audits the frame and process behind a result, not only the result.
---

# Process Assurance Framework

The framework is a self-audit layer worn by the Research Orchestrator.

Runtime automation is external to this skill:

- `.claude/settings.json`
- `.gauntlet.json`
- `tools/gauntlet_boundary.py`
- `tools/gauntlet_monitor.py`
- `tools/gauntlet_hook.py`
- `tools/verify_ledger.py`
- optional `tools/scout.py`, `tools/fsa_bots.py`, `tools/snap.py`

See `docs/RUNTIME_SETUP.md`.

## Ten operations

| operation | trigger | action |
|---|---|---|
| `frame` | repeated attempts share a failure shape | identify the shared invariant and change representation/assumption/method |
| `audit` | a kill/finding is about to be accepted | reconstruct criterion, evidence, and decision path |
| `costume` | last survivor or novelty framing | classify nearest prior art and actual delta |
| `derive` | inherited number/label becomes a premise | recompute from the nearest raw artifact |
| `self` | relying on your own load-bearing read | preregister expectation/refuter and declare authorship/selection contamination |
| `redirect` | much work, core claim still unknown | identify the load-bearing unknown and whether current work is upstream |
| `refresh` | governing state may be stale | reread current authoritative source/state |
| `boundary` | handoff/concurrent mutation | pin assumptions/interfaces/ownership in artifacts |
| `explain` | understanding/docs uncertain | explain plainly and diff against artifacts |
| `oob` | everything is green | enumerate relevant failure classes no current gate observes |

Use the smallest relevant set; do not ritualize all ten.

## Runtime contract

- optional integrations are feature-detected;
- missing integrations are `UNAVAILABLE`, not fabricated pass/fail;
- no machine-specific path is assumed;
- state lives under the configured project runtime directory, not `.git/`;
- OpenRouter credentials are environment-only;
- the Stop hook honors `stop_hook_active` to avoid recursive continuation;
- deterministic strong tool-loop evidence can trigger `frame` without an LLM judge; semantic precision checks may use an independently configured model when available.

## Output

**PROCESS ASSURANCE**
- Fired: `<operations>`
- Claim/frame: `<target>`
- Evidence inspected: `<actual artifacts/runs>`
- Counterevidence: `<strongest live challenger>`
- Result: `CLEARED | ISSUE | UNKNOWN | UNAVAILABLE`
- Consequence: `<what can proceed>`
- Next discriminator: `<only if unresolved>`
