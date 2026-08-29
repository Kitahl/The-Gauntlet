"""Shared sealed-run utilities for the active FOIL HLE-10 diagnostic."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "benchmark_runs" / "2026-08-28" / "active_runtime_hle10"
PRIVATE = OUT / "private"
RECEIPTS = OUT / "receipts"
ITEMS = OUT / "items.json"
OPPORTUNITIES = OUT / "opportunities.json"
EXPOSURES = OUT / "exposure_manifest.json"
MANIFEST = OUT / "manifest.json"
PREDICTIONS = OUT / "predictions.json"
RESULTS = OUT / "results.json"
REPORT = OUT / "report.md"

MODEL = "gpt-5.6-terra"
EFFORT = "high"
EXPECTED = 10
SEED = 20260828
TIMEOUT_SECONDS = 600
MAX_SOURCE_BYTES = 1_000_000
MAX_DOCUMENT_CHARACTERS = 100_000
PROVIDER_EFFECTIVE_CONTEXT = 258_400
HLE_REVISION = "0bc83643672d4f68a5f89998617a639d85e7318b"
HLE_SHARDS = {
    "Gold_subset.part01.parquet": "0f9347730c0b9a7b690931bfe38f748d2b142be8b4b3318e16d23844b18af98b",
    "Gold_subset.part02.parquet": "9661a90148056d7d39e0fef058159e72532119aa8ee30a26f06dfa27b61d015f",
    "Gold_subset.part03.parquet": "ace18833057f09e9071be632239b255a1cd23a3a602dddd524b88e573bf427aa",
    "Gold_subset.part04.parquet": "f09e14efe051a8a5af54e5f14f0bb2231ddb4b68cbba8886afb2f0a2995e3737",
    "Gold_subset.part05.parquet": "23211a403e2c013b01dd8634ffa982b9f6dfcb6a4c126a3223c2a18913030ee2",
}

A0_SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_active_runtime_hle10_a0.schema.json"
RETRIEVAL_SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_active_runtime_hle10_retrieval.schema.json"
CONSTRUCTOR_SCHEMA = ROOT / "benchmarks" / "protocols" / "foil_active_runtime_hle10_constructor.schema.json"
PROTOCOL = ROOT / "benchmarks" / "FOIL_ACTIVE_RUNTIME_HLE10_PROTOCOL.md"


class ProtocolError(RuntimeError):
    pass


class ProviderError(RuntimeError):
    def __init__(self, reason: str, call: Mapping[str, object]):
        super().__init__(reason)
        self.reason = reason
        self.call = dict(call)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(pretty(value), encoding="utf-8", newline="\n")
    temporary.replace(path)


def read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def codex_executable() -> str:
    if shutil.which("codex.cmd"):
        shim = Path(shutil.which("codex.cmd") or "")
        package = shim.resolve().parent / "node_modules" / "@openai" / "codex" / "node_modules" / "@openai"
        matches = sorted(package.glob("codex-win32-*/vendor/*/bin/codex.exe"))
        if len(matches) == 1:
            return str(matches[0])
    executable = shutil.which("codex.exe") or shutil.which("codex")
    if not executable:
        raise ProtocolError("native Codex executable is unavailable")
    return executable


def codex_identity() -> dict[str, object]:
    executable = Path(codex_executable())
    proc = subprocess.run([str(executable), "--version"], capture_output=True, text=True, timeout=20, check=False)
    if proc.returncode != 0:
        raise ProtocolError("codex --version failed")
    return {
        "path_basename": executable.name,
        "sha256": sha256_file(executable),
        "version": proc.stdout.strip(),
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "effective_context_tokens": PROVIDER_EFFECTIVE_CONTEXT,
    }


def usage_from(raw: object) -> dict[str, int] | None:
    if not isinstance(raw, Mapping):
        return None
    result: dict[str, int] = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        result[key] = value
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


_NON_TOOLS = {"reasoning", "agent_message"}


def parse_stream(text: str) -> dict[str, object]:
    usage: dict[str, int] | None = None
    tools: dict[str, dict[str, object]] = {}
    errors = 0
    for index, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue
        if not isinstance(event, dict):
            errors += 1
            continue
        if event.get("type") == "turn.completed":
            usage = usage_from(event.get("usage"))
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        kind = str(item.get("type") or "")
        if kind and kind not in _NON_TOOLS:
            key = str(item.get("id") or f"event-{index}")
            action = item.get("action") if isinstance(item.get("action"), dict) else {}
            query = item.get("query") if isinstance(item.get("query"), str) else action.get("query", "")
            prior = tools.get(key, {})
            tools[key] = {
                "tool_id": key,
                "tool_type": kind,
                "query": str(query or ""),
                "started": bool(prior.get("started")) or event.get("type") == "item.started",
                "completed": bool(prior.get("completed")) or event.get("type") == "item.completed",
            }
    return {"usage": usage, "tools": list(tools.values()), "parse_errors": errors}


def call_codex(stage_dir: Path, prompt: str, schema: Path, *, search: bool) -> dict[str, object]:
    if stage_dir.exists():
        raise ProtocolError(f"provider stage already exists: {stage_dir.name}")
    stage_dir.mkdir(parents=True)
    prompt_path = stage_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8", newline="\n")
    last = stage_dir / "last.json"
    argv = [codex_executable()]
    if search:
        argv.append("--search")
    argv.extend([
        "exec", "--json", "-m", MODEL,
        "-c", f'model_reasoning_effort="{EFFORT}"',
        "-s", "read-only", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--ignore-rules",
        "--output-schema", str(schema), "-o", str(last),
    ])
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="foil-live-hle10-") as directory:
            proc = subprocess.run(
                [*argv, "-C", directory, "-"], input=prompt, capture_output=True,
                text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS, check=False,
            )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
        wall_ms = int((time.monotonic() - started) * 1000)
        (stage_dir / "events.jsonl").write_text(stdout, encoding="utf-8", newline="\n")
        (stage_dir / "stderr.txt").write_text(stderr, encoding="utf-8", newline="\n")
        stream = parse_stream(stdout)
        call = {
            "returncode": None, "wall_ms": wall_ms, "usage": stream["usage"],
            "tools": stream["tools"], "parse_errors": stream["parse_errors"],
            "prompt_sha256": sha256_text(prompt), "output_sha256": None,
            "raw_persisted": True, "search_enabled": search, "timed_out": True,
        }
        write_json(stage_dir / "call.json", call)
        raise ProviderError("provider_timeout", call) from exc
    wall_ms = int((time.monotonic() - started) * 1000)
    (stage_dir / "events.jsonl").write_text(proc.stdout, encoding="utf-8", newline="\n")
    (stage_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8", newline="\n")
    output = last.read_text(encoding="utf-8") if last.exists() else ""
    stream = parse_stream(proc.stdout)
    call = {
        "returncode": proc.returncode,
        "wall_ms": wall_ms,
        "usage": stream["usage"],
        "tools": stream["tools"],
        "parse_errors": stream["parse_errors"],
        "prompt_sha256": sha256_text(prompt),
        "output_sha256": sha256_text(output),
        "raw_persisted": True,
        "search_enabled": search,
    }
    write_json(stage_dir / "call.json", call)
    if proc.returncode != 0:
        raise ProviderError(f"provider_returncode_{proc.returncode}", call)
    if not output:
        raise ProviderError("provider_missing_output", call)
    return {**call, "output": read_json(last)}


def a0_prompt(question: str) -> str:
    return (
        "Produce the closed-book baseline answer for exactly one Humanity's Last Exam question. "
        "Use no tools, web search, files, shell, code, or external resources. Return only the shortest "
        "answer the question requests inside the JSON answer field. For multiple choice, return only "
        "the option letter. Do not explain.\n\nQUESTION:\n" + question
    )


def retrieval_prompt(question: str) -> str:
    return (
        "For this one independent question, use web search only, at most two searches, and no shell, "
        "code, files, skills, or other tools. Return up to two authoritative public HTTPS source URLs "
        "and a verbatim quote from each source that directly bears on the answer. A search snippet is "
        "not evidence: quote text you believe is present on the fetched page. If you cannot identify a "
        "fetchable direct passage, return UNRESOLVED with an empty sources array. Do not mention any "
        "incumbent answer; none is available.\n\nQUESTION:\n" + question
    )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data)


def _public_https(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProtocolError("source URL must be credential-free HTTPS")
    if parsed.port not in (None, 443):
        raise ProtocolError("source URL uses a non-HTTPS port")
    addresses = {row[4][0] for row in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ProtocolError("source URL did not resolve exclusively to public addresses")
    return parsed


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str, headers: Any, newurl: str):  # type: ignore[no-untyped-def]
        _public_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_and_bind(url: str, requested_quote: str) -> dict[str, object]:
    _public_https(url)
    request = urllib.request.Request(url, headers={"User-Agent": "FOIL-active-runtime-HLE10/1.0"})
    started = time.monotonic()
    with urllib.request.build_opener(_SafeRedirect()).open(request, timeout=30) as response:
        final_url = response.geturl()
        _public_https(final_url)
        payload = response.read(MAX_SOURCE_BYTES + 1)
        content_type = str(response.headers.get("Content-Type") or "")
    if len(payload) > MAX_SOURCE_BYTES:
        raise ProtocolError("source exceeded byte bound")
    charset = "utf-8"
    match = re.search(r"charset=([^;\s]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1).strip('"\'')
    decoded = payload.decode(charset, errors="replace")
    if "html" in content_type.casefold() or "<html" in decoded[:1000].casefold():
        parser = _TextExtractor()
        parser.feed(decoded)
        content = "\n".join(parser.parts)
    else:
        content = decoded
    content = html.unescape(content)[:MAX_DOCUMENT_CHARACTERS]
    quote = html.unescape(str(requested_quote)).strip()
    start = content.find(quote)
    if start < 0 and quote:
        tokens = re.split(r"\s+", quote)
        pattern = r"\s+".join(re.escape(token) for token in tokens if token)
        found = re.search(pattern, content)
        if found:
            start, quote = found.start(), content[found.start():found.end()]
    bound = bool(quote and start >= 0)
    return {
        "requested_url": url,
        "final_url": final_url,
        "content_type": content_type,
        "content": content,
        "content_sha256": sha256_text(content),
        "requested_quote": requested_quote,
        "bound": bound,
        "start_offset": None if not bound else start,
        "end_offset": None if not bound else start + len(quote),
        "passage": None if not bound else quote,
        "passage_sha256": None if not bound else sha256_text(quote),
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


def sum_usage(calls: list[Mapping[str, object]]) -> dict[str, int] | None:
    usages = [call.get("usage") for call in calls]
    if any(not isinstance(value, Mapping) for value in usages):
        return None
    result = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for usage in usages:
        assert isinstance(usage, Mapping)
        parsed = usage_from(usage)
        if parsed is None:
            return None
        for key in result:
            result[key] += parsed[key]
    return result
