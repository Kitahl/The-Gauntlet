"""FOIL model layer — provider-neutral access to any LLM.

FOIL's core rule is that it requests a *capability* and the host satisfies it.
That rule previously covered tools but not the language model itself, so anything
built on FOIL inherited whatever model the harness happened to hard-code.

This module makes the model a configured capability like any other. It has no
third-party dependencies: every adapter speaks HTTP over `urllib` or spawns a
local command. Adding a provider is a config edit, not a code change.

Adapter families
----------------
`openai_chat`        any OpenAI-compatible `/v1/chat/completions` endpoint —
                     OpenAI, Azure OpenAI, OpenRouter, Together, Groq, Fireworks,
                     DeepSeek, Mistral, xAI, vLLM, llama.cpp server, LM Studio,
                     Ollama's compatibility shim, and most self-hosted gateways
`anthropic_messages` the Anthropic `/v1/messages` API
`ollama_chat`        Ollama's native `/api/chat`
`cli`                any local command that reads a prompt and prints a reply
                     (`claude -p`, `codex exec`, `llm`, `ssh box llm`, a shell script)
`mock`               deterministic offline echo, for tests and dry runs

`cli` prompt delivery and output parsing
----------------------------------------
`{prompt}` and `{model}` are substituted into the argv template. If the template
contains no `{prompt}`, the prompt is written to the command's **stdin** instead.
Prefer stdin: Windows caps a command line at 32,767 characters, so a long prompt
in argv fails at the OS level rather than in a place a caller can diagnose.

Any per-call knob a CLI exposes as a flag — effort, model, output format — is
just an argv token, so no adapter code is needed for it::

    ["claude", "-p", "--model", "{model}", "--effort", "low", "--output-format", "json"]

`output_parser` says how to read what came back:

* `""` / `"text"` — stdout is the reply (default).
* `"claude_json"` — stdout is one JSON object; the reply is its `result` field.
  `session_id`, `total_cost_usd`, `num_turns` and `duration_ms` are recorded in
  the response `usage` when present. Malformed JSON, or JSON with no `result`,
  raises `ModelError` — it is never silently downgraded to raw stdout, because a
  usage line or an error blob would then be scored as a model answer.

Rules this module keeps
-----------------------
* **Never pretend a provider is available.** `probe()` distinguishes "configured"
  from "verified against the live endpoint" and reports `NOT_MEASURED` when it
  has not checked.
* **Never store a secret.** Config holds the *name* of an environment variable,
  never its value. `redacted()` is what gets written to receipts.
* **Determinism is declared, not assumed.** Every spec carries a determinism
  class, because whether a benchmark needs replicates depends on it.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Iterable

SCHEMA = "egrt.foil-models.v1"

__all__ = [
    "SCHEMA", "ModelSpec", "ModelResponse", "ModelError", "ProviderStatus",
    "Determinism", "ADAPTER_FAMILIES", "OUTPUT_PARSERS", "PRESETS", "complete",
    "probe", "spec_from_row", "redacted", "resolve_key", "detect_environment",
]

#: Ways to read a `cli` command's stdout. See the module docstring.
OUTPUT_PARSERS = ("", "text", "claude_json")


class ProviderStatus(str, Enum):
    READY = "READY"                    # verified against the live endpoint
    CONFIGURED = "CONFIGURED"          # credentials and endpoint present, not verified
    UNAVAILABLE = "UNAVAILABLE"        # missing key, missing command, or endpoint refused
    NOT_MEASURED = "NOT-MEASURED"      # not checked; never treat as available


class Determinism(str, Enum):
    SEEDED = "SEEDED"                  # accepts a seed and honours it
    TEMPERATURE_ONLY = "TEMPERATURE_ONLY"   # temperature=0 only; still may vary
    NONDETERMINISTIC = "NONDETERMINISTIC"   # no reproducibility control offered

    @property
    def requires_replicates(self) -> bool:
        """A benchmark cell needs replicates unless the model is genuinely seeded."""
        return self is not Determinism.SEEDED


class ModelError(RuntimeError):
    """Any failure to obtain a completion. Never swallowed into an empty string."""


@dataclass(frozen=True)
class ModelSpec:
    """One configured model. `id` is what FOIL refers to; everything else is host detail."""

    id: str
    family: str
    model: str = ""
    base_url: str = ""
    api_key_env: str = ""                      # NAME of an env var, never a secret
    command: list[str] = field(default_factory=list)   # `cli` family only
    output_parser: str = ""                            # `cli` family only; OUTPUT_PARSERS
    headers: dict[str, str] = field(default_factory=dict)
    decoding: dict[str, Any] = field(default_factory=dict)
    determinism: str = Determinism.NONDETERMINISTIC.value
    context_tokens: int | None = None
    supports: dict[str, bool] = field(default_factory=dict)
    timeout_seconds: float = 120.0
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("model spec needs an id")
        if self.family not in ADAPTER_FAMILIES:
            raise ValueError(
                f"unknown adapter family {self.family!r}; "
                f"known families: {sorted(ADAPTER_FAMILIES)}"
            )
        Determinism(self.determinism)  # raises on a bad value
        if self.output_parser not in OUTPUT_PARSERS:
            raise ValueError(
                f"unknown output_parser {self.output_parser!r}; "
                f"known parsers: {sorted(p for p in OUTPUT_PARSERS if p)}"
            )
        if self.output_parser and self.family != "cli":
            raise ValueError("output_parser applies to the `cli` family only")

    @property
    def determinism_class(self) -> Determinism:
        return Determinism(self.determinism)

    def with_decoding(self, **overrides: Any) -> "ModelSpec":
        merged = {**self.decoding, **{k: v for k, v in overrides.items() if v is not None}}
        return replace(self, decoding=merged)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model_id: str
    model: str
    family: str
    latency_ms: int
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    request_sha256: str = ""
    response_sha256: str = ""
    decoding: dict[str, Any] = field(default_factory=dict)

    def to_receipt(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("text")                        # receipts record the digest, not the body
        return row


def _digest(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def resolve_key(spec: ModelSpec) -> str | None:
    """Read the key from the environment. Absent is a normal, reportable state."""
    if not spec.api_key_env:
        return None
    return os.environ.get(spec.api_key_env) or None


def redacted(spec: ModelSpec) -> dict[str, Any]:
    """The receipt-safe view: env var names, never values."""
    row = asdict(spec)
    row["api_key_present"] = bool(resolve_key(spec))
    row["headers"] = {k: "<redacted>" for k in spec.headers}
    return row


# --------------------------------------------------------------------------- #
# transport                                                                    #
# --------------------------------------------------------------------------- #

def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str],
               timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise ModelError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ModelError(f"cannot reach {url}: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        raise ModelError(f"transport failure for {url}: {exc}") from exc


def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system")
    rest = [m for m in messages if m.get("role") != "system"]
    return system, rest


# --------------------------------------------------------------------------- #
# adapters                                                                     #
# --------------------------------------------------------------------------- #

def _openai_chat(spec: ModelSpec, messages: list[dict[str, str]],
                 decoding: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    url = spec.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {"model": spec.model, "messages": messages}
    for key in ("temperature", "top_p", "max_tokens", "seed", "stop",
                "response_format", "reasoning_effort"):
        if decoding.get(key) is not None:
            payload[key] = decoding[key]
    headers = dict(spec.headers)
    key = resolve_key(spec)
    if key:
        headers.setdefault("Authorization", f"Bearer {key}")
    data = _post_json(url, payload, headers, spec.timeout_seconds)
    try:
        choice = data["choices"][0]
        text = choice["message"].get("content") or ""
        finish = choice.get("finish_reason", "")
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError(f"unexpected OpenAI-compatible response shape: {str(data)[:400]}") from exc
    return text, {"usage": data.get("usage", {}), "finish_reason": finish}, payload


def _anthropic_messages(spec: ModelSpec, messages: list[dict[str, str]],
                        decoding: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    url = spec.base_url.rstrip("/") + "/messages"
    system, rest = _split_system(messages)
    payload: dict[str, Any] = {
        "model": spec.model,
        "messages": rest,
        "max_tokens": int(decoding.get("max_tokens") or 4096),
    }
    if system:
        payload["system"] = system
    for key in ("temperature", "top_p", "stop_sequences"):
        if decoding.get(key) is not None:
            payload[key] = decoding[key]
    headers = dict(spec.headers)
    headers.setdefault("anthropic-version", "2023-06-01")
    key = resolve_key(spec)
    if key:
        headers.setdefault("x-api-key", key)
    data = _post_json(url, payload, headers, spec.timeout_seconds)
    try:
        text = "".join(block.get("text", "") for block in data["content"]
                       if block.get("type") == "text")
    except (KeyError, TypeError) as exc:
        raise ModelError(f"unexpected Anthropic response shape: {str(data)[:400]}") from exc
    return text, {"usage": data.get("usage", {}),
                  "finish_reason": data.get("stop_reason", "")}, payload


def _ollama_chat(spec: ModelSpec, messages: list[dict[str, str]],
                 decoding: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    url = spec.base_url.rstrip("/") + "/api/chat"
    options = {k: v for k, v in {
        "temperature": decoding.get("temperature"),
        "top_p": decoding.get("top_p"),
        "seed": decoding.get("seed"),
        "num_predict": decoding.get("max_tokens"),
    }.items() if v is not None}
    payload = {"model": spec.model, "messages": messages, "stream": False, "options": options}
    data = _post_json(url, payload, dict(spec.headers), spec.timeout_seconds)
    try:
        text = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ModelError(f"unexpected Ollama response shape: {str(data)[:400]}") from exc
    return text, {"usage": {"eval_count": data.get("eval_count")},
                  "finish_reason": data.get("done_reason", "")}, payload


#: Fields lifted out of a `claude_json` envelope into the response `usage`.
CLAUDE_JSON_USAGE_FIELDS = ("session_id", "total_cost_usd", "num_turns", "duration_ms")


def _parse_claude_json(spec: ModelSpec, stdout: str) -> tuple[str, dict[str, Any], str]:
    """Read one `claude -p --output-format json` envelope.

    Fails loudly. A usage banner, a wrapper's error blob, or a truncated stream
    would otherwise be scored as the model's answer.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ModelError(
            f"{spec.id}: output_parser=claude_json but stdout is not JSON "
            f"({exc.msg} at char {exc.pos}): {stdout[:400]!r}"
        ) from exc
    if not isinstance(data, dict) or "result" not in data:
        raise ModelError(
            f"{spec.id}: output_parser=claude_json but the payload has no 'result' field: "
            f"{str(data)[:400]}"
        )
    result = data["result"]
    if not isinstance(result, str):
        raise ModelError(
            f"{spec.id}: output_parser=claude_json expected a string 'result', "
            f"got {type(result).__name__}"
        )
    usage = {key: data[key] for key in CLAUDE_JSON_USAGE_FIELDS if key in data}
    if isinstance(data.get("usage"), dict):
        usage["tokens"] = data["usage"]
    finish = str(data.get("subtype") or data.get("type") or "cli")
    return result, usage, finish


def _cli(spec: ModelSpec, messages: list[dict[str, str]],
         decoding: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Run a local command. `{prompt}` in argv is substituted; otherwise stdin is used.

    This is how agentic CLIs join the pool: `claude -p {prompt}`,
    `codex exec {prompt}`, `llm -m mistral {prompt}`, or any wrapper script.
    Per-call knobs such as effort are ordinary argv tokens in `spec.command`; the
    adapter deliberately has no vendor-specific flag logic.
    """
    if not spec.command:
        raise ModelError(f"{spec.id}: cli family requires a command")
    prompt = "\n\n".join(f"[{m.get('role', 'user')}]\n{m['content']}" for m in messages)
    argv = [part.replace("{prompt}", prompt).replace("{model}", spec.model)
            for part in spec.command]
    # No `{prompt}` in the template means stdin delivery. That is the safe default
    # on Windows, where the whole command line is capped at 32,767 characters.
    uses_stdin = not any("{prompt}" in part for part in spec.command)
    executable = shutil.which(argv[0])
    if not executable:
        raise ModelError(f"{spec.id}: command not found on PATH: {argv[0]}")
    argv[0] = executable
    try:
        proc = subprocess.run(
            argv, input=prompt if uses_stdin else None, text=True,
            capture_output=True, timeout=spec.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ModelError(f"{spec.id}: command timed out after {spec.timeout_seconds}s") from exc
    if proc.returncode != 0:
        raise ModelError(f"{spec.id}: command exited {proc.returncode}: "
                         f"{(proc.stderr or proc.stdout or '')[-600:]}")
    payload = {"argv": argv[1:], "prompt_delivery": "stdin" if uses_stdin else "argv"}
    if spec.output_parser == "claude_json":
        text, usage, finish = _parse_claude_json(spec, proc.stdout.strip())
        return text, {"usage": usage, "finish_reason": finish}, payload
    return proc.stdout.strip(), {"usage": {}, "finish_reason": "cli"}, payload


def _mock(spec: ModelSpec, messages: list[dict[str, str]],
          decoding: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Deterministic offline adapter. Never reaches a network."""
    payload = {"model": spec.model or "mock", "messages": messages, "decoding": decoding}
    text = spec.decoding.get("canned_response") or f"MOCK[{_digest(payload)[:16]}]"
    return text, {"usage": {"prompt_messages": len(messages)}, "finish_reason": "mock"}, payload


Adapter = Callable[[ModelSpec, list, dict], tuple]

ADAPTER_FAMILIES: dict[str, Adapter] = {
    "openai_chat": _openai_chat,
    "anthropic_messages": _anthropic_messages,
    "ollama_chat": _ollama_chat,
    "cli": _cli,
    "mock": _mock,
}


# --------------------------------------------------------------------------- #
# presets — data, not logic. Edit or extend freely.                            #
# --------------------------------------------------------------------------- #

PRESETS: dict[str, dict[str, Any]] = {
    "openai": {"family": "openai_chat", "base_url": "https://api.openai.com/v1",
               "api_key_env": "OPENAI_API_KEY", "determinism": "SEEDED"},
    "anthropic": {"family": "anthropic_messages", "base_url": "https://api.anthropic.com/v1",
                  "api_key_env": "ANTHROPIC_API_KEY", "determinism": "TEMPERATURE_ONLY"},
    "openrouter": {"family": "openai_chat", "base_url": "https://openrouter.ai/api/v1",
                   "api_key_env": "OPENROUTER_API_KEY", "determinism": "NONDETERMINISTIC"},
    "together": {"family": "openai_chat", "base_url": "https://api.together.xyz/v1",
                 "api_key_env": "TOGETHER_API_KEY", "determinism": "SEEDED"},
    "groq": {"family": "openai_chat", "base_url": "https://api.groq.com/openai/v1",
             "api_key_env": "GROQ_API_KEY", "determinism": "SEEDED"},
    "fireworks": {"family": "openai_chat", "base_url": "https://api.fireworks.ai/inference/v1",
                  "api_key_env": "FIREWORKS_API_KEY", "determinism": "SEEDED"},
    "deepseek": {"family": "openai_chat", "base_url": "https://api.deepseek.com/v1",
                 "api_key_env": "DEEPSEEK_API_KEY", "determinism": "TEMPERATURE_ONLY"},
    "mistral": {"family": "openai_chat", "base_url": "https://api.mistral.ai/v1",
                "api_key_env": "MISTRAL_API_KEY", "determinism": "SEEDED"},
    "xai": {"family": "openai_chat", "base_url": "https://api.x.ai/v1",
            "api_key_env": "XAI_API_KEY", "determinism": "SEEDED"},
    "google_openai_compat": {"family": "openai_chat", "api_key_env": "GEMINI_API_KEY",
                             "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                             "determinism": "TEMPERATURE_ONLY"},
    "vllm": {"family": "openai_chat", "base_url": "http://localhost:8000/v1",
             "api_key_env": "", "determinism": "SEEDED",
             "notes": "self-hosted vLLM; also covers SGLang and TGI OpenAI shims"},
    "llamacpp": {"family": "openai_chat", "base_url": "http://localhost:8080/v1",
                 "api_key_env": "", "determinism": "SEEDED"},
    "lmstudio": {"family": "openai_chat", "base_url": "http://localhost:1234/v1",
                 "api_key_env": "", "determinism": "SEEDED"},
    "ollama": {"family": "ollama_chat", "base_url": "http://localhost:11434",
               "api_key_env": "", "determinism": "SEEDED"},
    "azure_openai": {"family": "openai_chat", "api_key_env": "AZURE_OPENAI_API_KEY",
                     "base_url": "", "determinism": "SEEDED",
                     "notes": "set base_url to <resource>/openai/deployments/<deployment>"},
    # Determinism stays NONDETERMINISTIC: the CLI offers no seed, so every
    # benchmark cell using it needs replicates. The prompt goes on stdin (no
    # `{prompt}` token) because a benchmark prompt can exceed the Windows argv
    # cap, and the JSON envelope is parsed so a usage banner is never scored as
    # an answer. Add per-call flags (`--model {model}`, `--effort low`) as
    # ordinary argv tokens via `foil_setup.py add --command`.
    "claude_cli": {"family": "cli", "command": ["claude", "-p", "--output-format", "json"],
                   "output_parser": "claude_json",
                   "determinism": "NONDETERMINISTIC",
                   "notes": "agentic CLI; prompt on stdin, reply read from the JSON `result`"},
    "codex_cli": {"family": "cli", "command": ["codex", "exec", "{prompt}"],
                  "determinism": "NONDETERMINISTIC"},
    "llm_cli": {"family": "cli", "command": ["llm", "-m", "{model}", "{prompt}"],
                "determinism": "NONDETERMINISTIC",
                "notes": "Simon Willison's llm; brings its own plugin ecosystem"},
    "mock": {"family": "mock", "determinism": "SEEDED",
             "notes": "offline; use for dry runs and CI"},
}


def spec_from_row(row: dict[str, Any]) -> ModelSpec:
    """Build a spec from a config row, expanding `preset` first."""
    data = dict(row)
    preset = data.pop("preset", None)
    if preset:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
        merged = {**PRESETS[preset], **{k: v for k, v in data.items() if v not in (None, "", [], {})}}
        data = merged
        data.setdefault("id", preset)
    known = set(ModelSpec.__dataclass_fields__)
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"unknown model config keys: {unknown}")
    return ModelSpec(**{k: v for k, v in data.items() if k in known})


# --------------------------------------------------------------------------- #
# completion and probing                                                       #
# --------------------------------------------------------------------------- #

def complete(spec: ModelSpec, messages: Iterable[dict[str, str]] | str,
             **decoding: Any) -> ModelResponse:
    """One completion from any configured model. Raises `ModelError` on failure."""
    rows = ([{"role": "user", "content": messages}] if isinstance(messages, str)
            else [dict(m) for m in messages])
    if not rows:
        raise ModelError("messages must not be empty")
    merged = {**spec.decoding, **{k: v for k, v in decoding.items() if v is not None}}
    merged.pop("canned_response", None)
    adapter = ADAPTER_FAMILIES[spec.family]
    started = time.monotonic()
    text, meta, payload = adapter(spec, rows, merged)
    elapsed = int((time.monotonic() - started) * 1000)
    return ModelResponse(
        text=text, model_id=spec.id, model=spec.model, family=spec.family,
        latency_ms=elapsed, usage=meta.get("usage", {}) or {},
        finish_reason=str(meta.get("finish_reason", "")),
        request_sha256=_digest(payload), response_sha256=_digest(text),
        decoding=merged,
    )


def probe(spec: ModelSpec, *, live: bool = False) -> dict[str, Any]:
    """Report availability honestly.

    Without `live`, this reports configuration only: `CONFIGURED` means the pieces
    are present, not that the endpoint answered. Only a live probe returns `READY`.
    """
    row: dict[str, Any] = {
        "id": spec.id, "family": spec.family, "model": spec.model,
        "determinism": spec.determinism,
        "requires_replicates": spec.determinism_class.requires_replicates,
        "checked_live": bool(live),
    }
    if spec.family == "cli":
        found = shutil.which(spec.command[0]) if spec.command else None
        row["command"] = shlex.join(spec.command) if spec.command else ""
        if not found:
            return {**row, "status": ProviderStatus.UNAVAILABLE.value,
                    "reason": f"command not on PATH: {spec.command[0] if spec.command else '(none)'}"}
    elif spec.family != "mock":
        if not spec.base_url:
            return {**row, "status": ProviderStatus.UNAVAILABLE.value, "reason": "no base_url"}
        if spec.api_key_env and not resolve_key(spec):
            return {**row, "status": ProviderStatus.UNAVAILABLE.value,
                    "reason": f"environment variable {spec.api_key_env} is not set"}
        row["base_url"] = spec.base_url
    if not live:
        return {**row, "status": ProviderStatus.CONFIGURED.value,
                "reason": "configuration present; endpoint not contacted"}
    try:
        response = complete(spec, "Reply with the single word: ready.",
                            max_tokens=16, temperature=0)
    except ModelError as exc:
        return {**row, "status": ProviderStatus.UNAVAILABLE.value, "reason": str(exc)[:400]}
    return {**row, "status": ProviderStatus.READY.value,
            "latency_ms": response.latency_ms,
            "sample_sha256": response.response_sha256[:16],
            "reason": "live completion succeeded"}


def detect_environment() -> list[dict[str, Any]]:
    """Suggest presets that look usable here. A suggestion is not a provider."""
    found: list[dict[str, Any]] = []
    for name, preset in PRESETS.items():
        if name == "mock":
            continue
        family = preset.get("family")
        if family == "cli":
            command = preset.get("command") or []
            if command and shutil.which(command[0]):
                found.append({"preset": name, "why": f"{command[0]} is on PATH",
                              "family": family})
        else:
            env = preset.get("api_key_env") or ""
            if env and os.environ.get(env):
                found.append({"preset": name, "why": f"{env} is set", "family": family})
            elif not env and str(preset.get("base_url", "")).startswith("http://localhost"):
                found.append({"preset": name,
                              "why": f"local endpoint candidate {preset['base_url']}",
                              "family": family, "unverified": True})
    return found
