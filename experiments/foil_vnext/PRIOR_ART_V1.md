# FOIL vNext V1 — External Prior-Art and Code Review

Date reviewed: 2026-08-22

Scope: executable mechanisms relevant to converting evidence/feedback into prompt, workflow, memory, tool-policy, or model changes. The objective here is **not** to copy benchmark optimizers; it is to identify small runtime mechanisms that can transfer without violating FOIL's evidence and assistance semantics.

## DSPy — GEPA

- **Problem solved:** evolve textual components of DSPy programs using execution traces, reflection, and validation metrics.
- **Architecture/mechanism:** candidate program population; full execution traces and predictor-local subtraces; reflective mutation; candidate lineage; Pareto/current-best selection; explicit metric-call/full-eval budgets; optional merge/component selection.
- **Code:** https://github.com/stanfordnlp/dspy and core engine https://github.com/gepa-ai/gepa
- **Important implementation:** `dspy/teleprompt/gepa/gepa.py` (`GEPA`, `GEPAFeedbackMetric`, `DspyGEPAResult`); GEPA core under `src/gepa/gepa_launcher.py`, `src/gepa/core/`, `src/gepa/proposer/`, `src/gepa/strategies/`.
- **License:** DSPy MIT; GEPA MIT.
- **Optimization feedback:** scalar score plus optional textual feedback tied to the full trace or a predictor-local trace; per-instance subscores and candidate lineage are retained.
- **Changes:** prompt/instruction text and, for supported flexible modules, program text/components; not model weights in DSPy's GEPA teleprompter itself.
- **Transfer to FOIL:** trace-local feedback, explicit candidate/state objects, multiple objectives rather than one aggregate score, and hard evaluation budgets.
- **Do not copy:** persistent optimization against the five evaluation items, benchmark-score-only objectives, or any post-exposure mutation of the candidate.

## DSPy — MIPROv2

- **Problem solved:** jointly optimize instructions and few-shot demonstrations for a DSPy program.
- **Architecture/mechanism:** bootstrap demo candidates, summarize program/data, propose instruction candidates, then search prompt/demo combinations with Optuna and minibatch/full validation evaluation.
- **Code:** https://github.com/stanfordnlp/dspy
- **Important implementation:** `dspy/teleprompt/mipro_optimizer_v2.py` (`MIPROv2`, `_bootstrap_fewshot_examples`, `_propose_instructions`, `_optimize_prompt_parameters`).
- **License:** MIT.
- **Optimization feedback:** validation metric scores; proposal context also uses data/program summaries and demos.
- **Changes:** instructions/prompts and demonstrations; not workflow graph or model weights.
- **Transfer to FOIL:** make budgets explicit; separate proposal/discovery from evaluation/verification; preserve a baseline.
- **Do not copy:** metric-driven prompt tuning on the evaluation set or treating better aggregate benchmark score as equivalent to better support calibration.

## DSPy — SIMBA

- **Problem solved:** improve DSPy programs through stochastic introspective minibatch search.
- **Architecture/mechanism:** sample program/model trajectories; score them; prioritize examples with large score dispersion; create candidate programs by appending a successful demo or an introspective rule; retain/evaluate winners.
- **Code:** https://github.com/stanfordnlp/dspy
- **Important implementation:** `dspy/teleprompt/simba.py` (`SIMBA`); `dspy/teleprompt/simba_utils.py` (`append_a_demo`, `append_a_rule`, resampling helpers).
- **License:** MIT.
- **Optimization feedback:** scalar metric per sampled trajectory plus score-gap/variance statistics used to target difficult examples.
- **Changes:** rules/instructions and demonstrations; not model weights.
- **Transfer to FOIL:** allocate effort to cases where outcomes vary; keep explicit candidate pools and resource state.
- **Do not copy:** accumulate benchmark-specific rules or demos across the frozen evaluation; score variance is not evidence of user weakness.

## TextGrad

- **Problem solved:** optimize text-valued variables through natural-language feedback treated as textual gradients.
- **Architecture/mechanism:** computation graph/backward feedback produces contextual textual gradients; `TextualGradientDescent` aggregates gradients and constraints, optionally remembers prior gradients, and asks an LLM for a revised variable.
- **Code:** https://github.com/zou-group/textgrad
- **Important implementation:** `textgrad/optimizer/optimizer.py` (`get_gradient_and_context_text`, `TextualGradientDescent`, momentum variant); variable/autograd graph modules.
- **License:** MIT.
- **Optimization feedback:** free-form textual criticism plus the context in which that criticism was produced; optional gradient memory.
- **Changes:** text variables such as prompts, solutions, or code text; not model weights in TGD itself.
- **Transfer to FOIL:** bind feedback to a specific target/claim and preserve hard constraints separately from soft feedback.
- **Do not copy:** universal self-critique/backprop on every task, or treating same-model criticism as an independent verifier.

## metaTextGrad

- **Problem solved:** automatically improve the optimizer used to improve LLM pipelines, including optimizer content and structure.
- **Architecture/mechanism:** LLM rewrites/combines optimizer source code; candidate optimizer classes are executed and evaluated; the best-scoring code is retained across epochs. Separate content/structure optimizer variants exist.
- **Code:** https://github.com/zou-group/metatextgrad
- **Important implementation:** `meta_optimization.py`; modified `textgrad/textgrad/optimizer/optimizer.py` (`MetaOptimizer`, `MetaContentOptimizer`, pipeline optimizers).
- **License:** MIT.
- **Optimization feedback:** task/dataset evaluation score plus optimizer source and task examples; best-score/best-code state.
- **Changes:** optimizer source/workflow structure and optimizer task descriptions; downstream TextGrad still changes textual program variables.
- **Transfer to FOIL:** represent the runtime controller as explicit executable policy rather than prose, and freeze it as an auditable object.
- **Do not copy:** self-modifying code during evaluation, dynamic benchmark-specific code generation, or selecting candidate code after seeing evaluation performance.

## AgentSquare

- **Problem solved:** automatically search modular LLM-agent designs.
- **Architecture/mechanism:** explicit modules for planning, reasoning, tool use, and memory; module evolution generates code; recombination forms agents; a performance predictor can screen combinations; benchmark execution supplies performance.
- **Code:** https://github.com/tsinghua-fib-lab/AgentSquare
- **Important implementation:** `search/agent_search.py` (`Agent`, `ModuleInfo`, benchmark/evolution loop); `search/module_evolution.py`; `search/module_predictor.py`; `search/recombination.py`; module pools in `search/*_modules.json`; `workflow.py`.
- **License:** README declares Apache-2.0. The inspected repository root did not expose a `LICENSE` file, so the badge is recorded rather than treated as a vendoring grant.
- **Optimization feedback:** measured benchmark performance attached to agents/modules; predictor/evolution/recombination use the archive of designs and scores.
- **Changes:** workflow/module structure and generated module code spanning planning, reasoning, tool use, and memory; not primarily model weights.
- **Transfer to FOIL:** make routing dimensions explicit and modular; keep the set small enough to attribute failures causally.
- **Do not copy:** open-ended module/code search during evaluation or a reward definition that collapses calibrated assistance, evidence quality, and independent capability into one accuracy score.

## AFlow

- **Problem solved:** automatically generate and improve agentic workflows represented as executable graphs/code.
- **Architecture/mechanism:** predefined operators (generation, review/revision, ensemble, testing/programming); an optimizer samples prior high-scoring rounds, incorporates experience/logs, asks an optimization LLM for a graph modification, validates the modification, evaluates the new graph, records score/experience, and can stop on convergence.
- **Code:** https://github.com/FoundationAgents/AFlow
- **Important implementation:** `run.py` (`ExperimentConfig`, `Optimizer` entry); `scripts/optimizer.py` (`Optimizer`, `_optimize_graph`, `GraphOptimize`); workflow/operator implementations under `workspace/*/workflows` and supporting scripts.
- **License:** MIT.
- **Optimization feedback:** benchmark validation score plus structured experience/logs describing prior graph modifications and outcomes.
- **Changes:** workflow graph/code and prompts; not model weights.
- **Transfer to FOIL:** explicit operator repertoire, experience/state separated from executor, and convergence/early-stop logic.
- **Do not copy:** graph search on the held-out evaluation items, repeated generic review nodes, or adding workflow complexity merely because it improves a scalar development score.

## Agent Lightning

- **Problem solved:** decouple arbitrary agent execution from trainable optimization so prompts, policies, or weights can be improved from rollout traces.
- **Architecture/mechanism:** runners/tracers emit structured events/spans and rewards; a central store coordinates rollouts/resources; training algorithms consume traces and publish updated resources. The current executable schema makes model requests, rewards, rollout state, and metadata first-class typed objects.
- **Code:** https://github.com/microsoft/agent-lightning
- **Important implementation:** `agentlightning/schemas.py` (`Event`, `ModelRequestData`, `RewardData`, `Rollout*`); `agentlightning/client.py` store clients; controllers under `agentlightning/controller/`; runnable training examples under `examples/`.
- **License:** MIT.
- **Optimization feedback:** structured rollout events/spans plus scalar reward and optional human/machine-readable reward explanation.
- **Changes:** depending on algorithm, resources may be prompt templates/configuration or model/policy weights.
- **Transfer to FOIL:** decouple runtime traces from later learning; use a typed, minimal public trace as the causal record of what policy ran.
- **Do not copy:** reinforcement learning/fine-tuning in this experiment, reward-only attribution, or any resource update after item exposure.

## Reflexion

- **Problem solved:** improve repeated agent attempts by converting failure/outcome feedback into verbal reflection kept in episodic memory.
- **Architecture/mechanism:** after a failed/halted attempt, `CoTAgent`/`ReactReflectAgent` can store the last trace, generate a reflection, or use both; the reflection is inserted into the next attempt's prompt. ReAct variants expose search/lookup actions and a finite step/token halt rule.
- **Code:** https://github.com/noahshinn/reflexion
- **Important implementation:** `hotpotqa_runs/agents.py` (`ReflexionStrategy`, `CoTAgent`, `ReactAgent`, `ReactReflectAgent`, reflection/prompt builders).
- **License:** MIT.
- **Optimization feedback:** correctness/environment outcome plus the previous scratchpad; a reflection LLM converts that into verbal memory.
- **Changes:** task-local/persistent episodic memory and subsequent prompt context; not model weights.
- **Transfer to FOIL:** explicit finite stop rules and conditional reflection only after a demonstrated failure/uncertainty.
- **Do not copy:** automatic repeated reflection, storing private reasoning in FOIL receipts, or treating self-reflection as independent evidence.

## SiriuS

- **Problem solved:** self-improve multi-agent systems by building an experience library from successful trajectories and repairing failed trajectories, then training specialized agents from that library.
- **Architecture/mechanism:** generate multi-agent trajectories; separate wrong cases; critic generates targeted feedback using the ground-truth answer; regenerate improved trajectories; merge/filter them into fine-tuning data; fine-tune agents.
- **Code:** https://github.com/zou-group/sirius
- **Important implementation:** `Problem_solving/PhyChem/agent.py`; `get_a_sol.py`; `get_b_feedback.py` (`generate_critic_feedback`, `get_feedback`); `get_c_regenerate.py`; `get_finetune_data.py`; `fine_tune.py`.
- **License:** MIT.
- **Optimization feedback:** correctness/ground truth, full multi-agent trajectories, and critic-generated textual feedback.
- **Changes:** experience library and ultimately specialized model weights through supervised fine-tuning.
- **Transfer to FOIL:** keep assisted trajectories conceptually separate from independent capability and analyze failure modes after evaluation from minimal traces.
- **Do not copy:** ground-truth-dependent repair during evaluation, private trajectory storage, benchmark-specific experience libraries, or fine-tuning/model-weight updates.

## Design conclusion for V1

The prior art contains powerful mechanisms for **learning a persistent agent/program**. FOIL vNext V1 instead needs a smaller per-task controller whose objective is conditional support quality and evidence discipline. The transferable subset is therefore:

1. explicit typed state and trace-local attribution (GEPA, Agent Lightning);
2. a fixed modular action repertoire (AgentSquare, AFlow);
3. discovery/evaluation separation and fixed budgets (MIPROv2, GEPA, AFlow);
4. target-specific textual/evidential feedback rather than generic critique (TextGrad, Reflexion);
5. finite stopping and no-op paths when obligations are already satisfied (AFlow, Reflexion);
6. strict separation between assisted performance and independent capability (required by FOIL; especially important not to inherit SiriuS-style trajectory-training semantics).

Accordingly `FOIL_vNEXT_CANDIDATE_V1` performs no prompt evolution, workflow search, memory accumulation, code mutation, or weight update during the five-item evaluation.
