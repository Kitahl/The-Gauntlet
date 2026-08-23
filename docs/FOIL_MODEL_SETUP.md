# FOIL setup — bring your own model

FOIL asks for a **role**, never a vendor. You tell it once which models fill which
roles, and everything downstream — the skill, the tool router, the benchmark — works
against whatever you configured.

No third-party packages. Every adapter is `urllib` over HTTP or a local subprocess.

## 60 seconds

```bash
python tools/foil_setup.py detect                  # what looks usable here
python tools/foil_setup.py init --auto             # write .foil/models.json
python tools/foil_setup.py probe --live            # actually contact the endpoints
python tools/foil_setup.py doctor                  # health + independence check
```

## Adding models

```bash
# hosted, OpenAI-compatible
python tools/foil_setup.py add --id primary --preset openai --model gpt-4.1 \
    --decoding temperature=0 --decoding seed=20260822

# Anthropic
python tools/foil_setup.py add --id reviewer --preset anthropic --model claude-sonnet-4-6

# fully local
python tools/foil_setup.py add --id local --preset ollama --model qwen3:8b
python tools/foil_setup.py add --id served --preset vllm --model llama-3.3-70b

# anything with an OpenAI-compatible endpoint
python tools/foil_setup.py add --id gw --family openai_chat --model my-model \
    --base-url https://gateway.internal/v1 --api-key-env GATEWAY_TOKEN

# any command at all — agentic CLIs, remote boxes, wrapper scripts
python tools/foil_setup.py add --id box --family cli --model mixtral \
    --command "ssh gpu-box llm -m {model} {prompt}"
python tools/foil_setup.py add --id codex --preset codex_cli

python tools/foil_setup.py roles --primary primary --reviewer reviewer \
    --verifier local --benchmark primary
```

`{prompt}` and `{model}` are substituted in `cli` argv. Omit `{prompt}` and the
prompt arrives on stdin instead — prefer that, because Windows caps a whole
command line at 32,767 characters and a long benchmark prompt in argv fails at
the OS level rather than anywhere a caller can diagnose.

Per-call knobs are ordinary argv tokens. The adapter has no vendor flag logic, so
effort, model and output format are just words in the command:

```bash
python tools/foil_setup.py add --id agent --family cli --model <model-id>     --command "claude -p --model {model} --effort low --output-format json"     --output-parser claude_json
```

`--output-parser claude_json` reads one JSON object from stdout and takes its
`result` field as the reply, recording `session_id`, `total_cost_usd`,
`num_turns` and `duration_ms` in the response usage when present. Malformed JSON,
or JSON without a `result`, raises `ModelError`; it is never downgraded to raw
stdout, because a usage banner or an error blob would otherwise be scored as a
model answer. The `claude_cli` preset ships this shape already and stays
`NONDETERMINISTIC`: the CLI offers no seed, so every benchmark cell using it
needs replicates.

## Adapter families

| family | covers |
|---|---|
| `openai_chat` | OpenAI, Azure, OpenRouter, Together, Groq, Fireworks, DeepSeek, Mistral, xAI, Gemini's OpenAI shim, vLLM, SGLang, TGI, llama.cpp, LM Studio, most internal gateways |
| `anthropic_messages` | Anthropic `/v1/messages` |
| `ollama_chat` | Ollama native `/api/chat` |
| `cli` | `claude -p`, `codex exec`, `llm`, SSH to a GPU box, any script |
| `mock` | deterministic offline echo for CI and dry runs |

Presets are **data** in `foil_models.PRESETS`, not logic. A provider nobody has heard
of yet needs a config row, not a patch.

## Roles

| role | used for |
|---|---|
| `primary` | does the work |
| `reviewer` | independent critique — should be a *different* model |
| `verifier` | claim-native checking; often cheap and deterministic |
| `benchmark` | the model under test in a controlled evaluation |

An unfilled role stays unfilled. FOIL reports `NOT-MEASURED` rather than quietly
promoting the primary into the reviewer slot, because a model critiquing its own
output is not independent evidence. `doctor` exits 1 and says so if you point both
roles at one model.

## Three rules the layer enforces

**Never pretend a provider is available.** `probe()` returns `CONFIGURED` when the
pieces are present and only returns `READY` after a live completion succeeded.
`UNAVAILABLE` names the reason — missing env var, command not on PATH, endpoint
refused. Configured is not available; available is not used.

**Never store a secret.** Config holds the *name* of an environment variable. The
receipt view records `api_key_present: true/false` and redacts custom headers. There
is a test asserting a real key never reaches the config file or a receipt.

**Determinism is declared, not assumed.** Every model carries a class:

| class | meaning | replicates |
|---|---|---|
| `SEEDED` | accepts and honours a seed | not forced |
| `TEMPERATURE_ONLY` | `temperature=0` only | required |
| `NONDETERMINISTIC` | no reproducibility control | required |

This is load-bearing, not decoration. `benchmarks/harness/bench_foil_session.py design` reads it and
changes the plan:

```
mixed pool (one cli model)  -> items = 75,  replicates = 3
all-seeded pool             -> items = 150, replicates = 1
```

Fewer replicates means more items to reach the same power. The harness will not let
you claim one sample per cell while a nondeterministic model is in the pool.

## Models as a routed capability

```bash
python tools/foil_setup.py capabilities --out .foil/capability-manifest.json
```

emits a manifest `foil_tool_policy` already consumes. `TEXT_GENERATION` and
`REASONING` are now capabilities alongside `WEB_SEARCH` and `FORMAL_PROOF`, with
claim routes `model_generation`, `model_reasoning`, and `independent_review`. Both
carry `writes: False`, so the write guard applies to them like everything else.

Their authority ceilings are written down: model output *carries no evidential
authority of its own*, and model reasoning *still needs a claim-native verifier*.
Swapping in a better model does not upgrade a claim.

## Using it in code

```python
import foil_setup as fs, foil_models as fm

config = fs.load_config(Path(".foil/models.json"))
spec = fs.spec_for_role(config, "reviewer")
if spec is None:
    ...  # NOT-MEASURED. Do not fall back to the primary.
else:
    response = fm.complete(spec, [{"role": "user", "content": prompt}],
                           temperature=0, max_tokens=1024)
    receipt.append(response.to_receipt())   # digests and decoding, never the body
```

`complete()` raises `ModelError` on any failure. It never returns an empty string
that a caller might mistake for a real answer.

## Benchmarking any model

```bash
python benchmarks/harness/bench_foil_session.py all \n    --model-config .foil/models.json --live
```

The `invariants` and `power` sections are model-free by construction — the policy
kernel is a pure function and the power arithmetic is arithmetic. The `models`
section reports the pool, and `design` sizes the behavioural arm against it. No
condition in the design names a vendor: conditions differ only in the policy text
supplied, and the receipt records the resolved model id and decoding so a result is
attributable to a model without the design depending on one.
