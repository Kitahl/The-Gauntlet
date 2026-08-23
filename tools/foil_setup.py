#!/usr/bin/env python3
"""`foil setup` — bring your own model.

Writes `.foil/models.json`: the list of models FOIL may use, which roles each one
fills, and nothing secret. Secrets stay in the environment; the config records
only the variable name.

    python tools/foil_setup.py detect                     # what looks usable here
    python tools/foil_setup.py init --auto                # write a config from detection
    python tools/foil_setup.py add --preset openai --model gpt-4.1 --id primary
    python tools/foil_setup.py add --preset ollama --model qwen3:8b --id local
    python tools/foil_setup.py add --id box --family cli --command "ssh gpu llm -m {model} {prompt}"
    python tools/foil_setup.py add --id agent --preset claude_cli --model <model-id>
    python tools/foil_setup.py roles --primary primary --reviewer local
    python tools/foil_setup.py probe --live
    python tools/foil_setup.py capabilities --out .foil/capability-manifest.json
    python tools/foil_setup.py doctor

Roles
-----
FOIL asks for a role, never a vendor. The core roles are:

    primary     does the work
    reviewer    independent critique; should be a *different* model where possible
    verifier    claim-native checking, often cheap and deterministic
    benchmark   the model under test in a controlled evaluation

An unfilled role is reported as unfilled. FOIL degrades explicitly rather than
silently substituting the primary for a reviewer, because a model reviewing its
own output is not independent evidence.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from foil_models import (  # noqa: E402
    OUTPUT_PARSERS,
    PRESETS,
    Determinism,
    ModelError,
    ProviderStatus,
    complete,
    detect_environment,
    probe,
    redacted,
    spec_from_row,
)

CONFIG_SCHEMA = "egrt.foil-model-config.v1"
DEFAULT_CONFIG = Path(".foil/models.json")
ROLES = ("primary", "reviewer", "verifier", "benchmark")


# --------------------------------------------------------------------------- #
# config io                                                                    #
# --------------------------------------------------------------------------- #

def empty_config() -> dict[str, Any]:
    return {"schema": CONFIG_SCHEMA, "models": [], "roles": {},
            "notes": "Secrets are never stored here; api_key_env names an environment variable."}


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_config()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != CONFIG_SCHEMA:
        raise SystemExit(f"{path}: unexpected schema {data.get('schema')!r}")
    return data


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def specs(config: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for row in config.get("models", []):
        spec = spec_from_row(row)
        out[spec.id] = spec
    return out


def spec_for_role(config: dict[str, Any], role: str):
    """Resolve a role to a spec, or None. Never silently substitutes."""
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}; roles are {list(ROLES)}")
    model_id = config.get("roles", {}).get(role)
    if not model_id:
        return None
    table = specs(config)
    if model_id not in table:
        raise SystemExit(f"role {role!r} points at unknown model id {model_id!r}")
    return table[model_id]


# --------------------------------------------------------------------------- #
# commands                                                                     #
# --------------------------------------------------------------------------- #

def cmd_detect(args: argparse.Namespace) -> int:
    found = detect_environment()
    print(json.dumps({"detected": found,
                      "boundary": "A detected preset is a candidate, not a verified provider. "
                                  "Run `probe --live` before relying on one."},
                     indent=2))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    path = Path(args.config)
    if path.is_file() and not args.force:
        raise SystemExit(f"{path} already exists; pass --force to overwrite")
    config = empty_config()
    if args.auto:
        for hit in detect_environment():
            if hit.get("unverified") and not args.include_local:
                continue
            row = {"id": hit["preset"], "preset": hit["preset"]}
            config["models"].append(row)
    if not config["models"]:
        config["models"].append({"id": "mock", "preset": "mock",
                                 "notes": "offline placeholder; replace with a real model"})
    config["roles"] = {"primary": config["models"][0]["id"]}
    save_config(path, config)
    print(json.dumps({"written": str(path),
                      "models": [row["id"] for row in config["models"]],
                      "roles": config["roles"],
                      "next": ["python tools/foil_setup.py add --preset <preset> --model <name>",
                               "python tools/foil_setup.py roles --primary <id> --reviewer <id>",
                               "python tools/foil_setup.py probe --live"]}, indent=2))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    path = Path(args.config)
    config = load_config(path)
    row: dict[str, Any] = {"id": args.id}
    if args.preset:
        row["preset"] = args.preset
    for key, value in (("family", args.family), ("model", args.model),
                       ("base_url", args.base_url), ("api_key_env", args.api_key_env),
                       ("determinism", args.determinism), ("notes", args.notes),
                       ("output_parser", args.output_parser)):
        if value:
            row[key] = value
    if args.command:
        row["command"] = shlex.split(args.command)
    decoding = {}
    for item in args.decoding or []:
        key, _, raw = item.partition("=")
        try:
            decoding[key] = json.loads(raw)
        except json.JSONDecodeError:
            decoding[key] = raw
    if decoding:
        row["decoding"] = decoding
    spec = spec_from_row(row)  # validates before writing
    config["models"] = [r for r in config.get("models", []) if r.get("id") != spec.id]
    config["models"].append(row)
    config.setdefault("roles", {})
    if not config["roles"].get("primary"):
        config["roles"]["primary"] = spec.id
    save_config(path, config)
    print(json.dumps({"added": spec.id, "family": spec.family,
                      "determinism": spec.determinism,
                      "requires_replicates": spec.determinism_class.requires_replicates,
                      "config": str(path)}, indent=2))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    path = Path(args.config)
    config = load_config(path)
    before = len(config.get("models", []))
    config["models"] = [r for r in config.get("models", []) if r.get("id") != args.id]
    config["roles"] = {k: v for k, v in config.get("roles", {}).items() if v != args.id}
    save_config(path, config)
    print(json.dumps({"removed": args.id, "models_before": before,
                      "models_after": len(config["models"]), "roles": config["roles"]}, indent=2))
    return 0


def cmd_roles(args: argparse.Namespace) -> int:
    path = Path(args.config)
    config = load_config(path)
    table = specs(config)
    for role in ROLES:
        value = getattr(args, role, None)
        if value:
            if value not in table:
                raise SystemExit(f"unknown model id {value!r}; known: {sorted(table)}")
            config.setdefault("roles", {})[role] = value
    save_config(path, config)
    unfilled = [r for r in ROLES if not config.get("roles", {}).get(r)]
    same = (config.get("roles", {}).get("primary")
            and config["roles"].get("primary") == config.get("roles", {}).get("reviewer"))
    print(json.dumps({
        "roles": config.get("roles", {}),
        "unfilled": unfilled,
        "independence_warning": (
            "primary and reviewer are the same model; its critique of its own output "
            "is not independent evidence" if same else None),
    }, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    print(json.dumps({"models": [redacted(s) for s in specs(config).values()],
                      "roles": config.get("roles", {})}, indent=2))
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    table = specs(config)
    ids = [args.id] if args.id else list(table)
    rows = [probe(table[i], live=args.live) for i in ids if i in table]
    ready = [r for r in rows if r["status"] == ProviderStatus.READY.value]
    result = {
        "checked_live": args.live,
        "providers": rows,
        "ready": len(ready),
        "unavailable": [r["id"] for r in rows if r["status"] == ProviderStatus.UNAVAILABLE.value],
        "boundary": ("Without --live this reports configuration only. Configured is not "
                     "available, and available is not used."),
    }
    print(json.dumps(result, indent=2))
    return 0 if not args.require_ready or ready else 1


def cmd_test(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    table = specs(config)
    if args.id not in table:
        raise SystemExit(f"unknown model id {args.id!r}; known: {sorted(table)}")
    try:
        response = complete(table[args.id], args.prompt,
                            max_tokens=args.max_tokens, temperature=args.temperature)
    except ModelError as exc:
        print(json.dumps({"id": args.id, "status": "FAILED", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"id": args.id, "status": "OK", "text": response.text,
                      "receipt": response.to_receipt()}, indent=2))
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    """Emit the manifest `foil_tool_policy` consumes, so models join capability routing."""
    config = load_config(Path(args.config))
    providers = []
    for index, spec in enumerate(specs(config).values()):
        status = probe(spec, live=args.live)["status"]
        mapped = "READY" if status == ProviderStatus.READY.value else status
        for capability in ("TEXT_GENERATION", "REASONING"):
            providers.append({
                "name": spec.id, "capability": capability, "status": mapped,
                "priority": index, "write_allowed": False,
                "metadata": {"family": spec.family, "model": spec.model,
                             "determinism": spec.determinism},
            })
    manifest = {"schema": "egrt.foil-capability-manifest.v2", "providers": providers}
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    path = Path(args.config)
    config = load_config(path)
    table = specs(config)
    rows = [probe(spec, live=args.live) for spec in table.values()]
    roles = config.get("roles", {})
    findings: list[str] = []
    if not table:
        findings.append("no models configured; run `init --auto` or `add`")
    if not roles.get("primary"):
        findings.append("no primary role assigned")
    if roles.get("primary") and roles.get("primary") == roles.get("reviewer"):
        findings.append("primary and reviewer are the same model; critique is not independent")
    if not roles.get("reviewer"):
        findings.append("no reviewer role; independent critique is unavailable and must be "
                        "reported as NOT-MEASURED rather than assumed")
    nondet = [r["id"] for r in rows if r["requires_replicates"]]
    if nondet:
        findings.append(f"models without seed control: {nondet}; any benchmark cell using them "
                        f"needs replicates, and a single sample measures noise")
    only_mock = table and all(spec.family == "mock" for spec in table.values())
    if only_mock:
        findings.append("only the mock adapter is configured; no real model is reachable")
    print(json.dumps({
        "config": str(path), "models": len(table), "roles": roles,
        "providers": rows, "findings": findings,
        "verdict": "OK" if not findings else "ATTENTION",
    }, indent=2))
    return 0 if not findings else 1


# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FOIL model setup — bring your own LLM")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("detect", help="report presets that look usable in this environment"
                   ).set_defaults(func=cmd_detect)

    init = sub.add_parser("init", help="write a starter config")
    init.add_argument("--auto", action="store_true", help="seed from detection")
    init.add_argument("--include-local", action="store_true",
                      help="include unverified localhost endpoints")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    add = sub.add_parser("add", help="add or replace a model")
    add.add_argument("--id", required=True)
    add.add_argument("--preset", choices=sorted(PRESETS))
    add.add_argument("--family")
    add.add_argument("--model", default="")
    add.add_argument("--base-url")
    add.add_argument("--api-key-env")
    add.add_argument("--command",
                     help="cli family; {prompt} and {model} are substituted into argv. "
                          "Omit {prompt} and the prompt is delivered on stdin instead, "
                          "which is the safe default for long prompts on Windows. "
                          "Per-call knobs such as effort are ordinary argv tokens.")
    add.add_argument("--output-parser", choices=[p for p in OUTPUT_PARSERS if p],
                     help="cli family; how to read stdout (default: raw text)")
    add.add_argument("--determinism", choices=[d.value for d in Determinism])
    add.add_argument("--decoding", action="append", metavar="KEY=JSON")
    add.add_argument("--notes")
    add.set_defaults(func=cmd_add)

    remove = sub.add_parser("remove")
    remove.add_argument("--id", required=True)
    remove.set_defaults(func=cmd_remove)

    roles = sub.add_parser("roles", help="assign models to roles")
    for role in ROLES:
        roles.add_argument(f"--{role}")
    roles.set_defaults(func=cmd_roles)

    sub.add_parser("list").set_defaults(func=cmd_list)

    probe_cmd = sub.add_parser("probe", help="report availability")
    probe_cmd.add_argument("--id")
    probe_cmd.add_argument("--live", action="store_true", help="contact the endpoint")
    probe_cmd.add_argument("--require-ready", action="store_true",
                           help="exit 1 unless at least one provider is live-verified")
    probe_cmd.set_defaults(func=cmd_probe)

    test = sub.add_parser("test", help="one real completion")
    test.add_argument("--id", required=True)
    test.add_argument("--prompt", default="Reply with the single word: ready.")
    test.add_argument("--max-tokens", type=int, default=64)
    test.add_argument("--temperature", type=float, default=0.0)
    test.set_defaults(func=cmd_test)

    caps = sub.add_parser("capabilities", help="export a capability manifest")
    caps.add_argument("--out")
    caps.add_argument("--live", action="store_true")
    caps.set_defaults(func=cmd_capabilities)

    doctor = sub.add_parser("doctor", help="config health and independence check")
    doctor.add_argument("--live", action="store_true")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Piping into `head` should truncate, not raise.
    try:
        import signal

        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):  # pragma: no cover - non-POSIX
        pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
