"""Portable OpenRouter caller used by optional Process Assurance tools.

Credentials are environment-only. The repository never reads a private keystore.
Supported variables: OPENROUTER_API_KEY and OPENROUTER_API_KEY_1..16.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable

import requests

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    pass


def load_keys() -> list[str]:
    vals: list[str] = []
    for name in ["OPENROUTER_API_KEY", *[f"OPENROUTER_API_KEY_{i}" for i in range(1, 17)]]:
        value = (os.environ.get(name) or "").strip()
        if value and value not in vals:
            vals.append(value)
    return vals


def available() -> bool:
    return bool(load_keys())


def ask(
    system: str,
    user: str,
    *,
    model: str | None = None,
    json_mode: bool = False,
    max_tokens: int = 900,
    temperature: float = 0.0,
    timeout: float = 45.0,
    fetch: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    model = model or os.environ.get("GAUNTLET_JUDGE_MODEL") or os.environ.get("OPENROUTER_MODEL")
    if not model:
        raise OpenRouterError("no model configured; set GAUNTLET_JUDGE_MODEL or OPENROUTER_MODEL")
    keys = load_keys()
    if not keys:
        raise OpenRouterError("no OpenRouter API key configured")
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers_base = {
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "https://github.com/Kitahl/The-Gauntlet"),
        "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "Evidence-Governed Research Toolkit"),
    }
    last: Exception | None = None
    for index, key in enumerate(keys):
        headers = dict(headers_base)
        headers["Authorization"] = f"Bearer {key}"
        try:
            if fetch is not None:
                raw = fetch(BASE_URL, body, headers)
                data = raw if isinstance(raw, dict) else json.loads(str(raw))
            else:
                resp = requests.post(BASE_URL, headers=headers, json=body, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return {"text": text, "model": model, "key_index": index, "usage": data.get("usage")}
        except Exception as exc:
            last = exc
    raise OpenRouterError(f"all configured OpenRouter credentials failed: {last}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model")
    p.add_argument("--system", default="You are a careful research assistant.")
    p.add_argument("--system-file")
    p.add_argument("--input-file")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    system = args.system
    if args.system_file:
        system = open(args.system_file, encoding="utf-8").read()
    user = open(args.input_file, encoding="utf-8").read() if args.input_file else sys.stdin.read()
    try:
        result = ask(system, user, model=args.model, json_mode=args.json)
    except OpenRouterError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
