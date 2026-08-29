"""Prepare, seal, check, and run the active FOIL HLE-10 diagnostic."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
HARNESS = ROOT / "benchmarks" / "harness"
for entry in (TOOLS, HARNESS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from egrt_types import digest  # noqa: E402
from foil_active_runtime_v2 import FoilRuntimePolicyV2  # noqa: E402
from foil_bounded_answer_constructor_v2 import (  # noqa: E402
    ConstructorBoundaryFailure,
    ConstructorDraftV2,
    ConstructorPolicyV2,
)
from foil_evidence_archive import RawEvidenceArchive  # noqa: E402
from foil_evidence_contract import (  # noqa: E402
    AnswerKind,
    AtomicClaim,
    ClaimKind,
    QuestionObligation,
)
from foil_retrieval_claim_comparator import ComparatorPolicy  # noqa: E402
from foil_route_opportunity_v2 import (  # noqa: E402
    QUESTION_SCHEMA_V2,
    RuntimeToolFamily,
    discover_route_opportunity_v2,
)
from foil_runtime_benchmark_integration import run_benchmark_row  # noqa: E402
from foil_runtime_token_ledger import RuntimeTokenLedger  # noqa: E402
from foil_runtime_tools_v2 import (  # noqa: E402
    ExactArithmeticAdapterV2,
    PassageRetrievalAdapterV2,
    RestrictedPythonAdapterV2,
    RetrievedPassageBatch,
    SymbolicLinearAdapterV2,
    ToolBoundaryFailure,
)
from foil_tool_contract_v2 import (  # noqa: E402
    BoundaryFailureCode,
    PassageEvidenceV2,
    ResourceEnvelopeV2,
    RouteValueEstimate,
    TokenUsageV2,
)
from foil_active_runtime_hle10_common import (  # noqa: E402
    A0_SCHEMA,
    CONSTRUCTOR_SCHEMA,
    EFFORT,
    EXPECTED,
    EXPOSURES,
    HLE_REVISION,
    HLE_SHARDS,
    ITEMS,
    MANIFEST,
    MODEL,
    OPPORTUNITIES,
    OUT,
    PREDICTIONS,
    PRIVATE,
    PROTOCOL,
    PROVIDER_EFFECTIVE_CONTEXT,
    RECEIPTS,
    RETRIEVAL_SCHEMA,
    ROOT,
    SEED,
    ProviderError,
    ProtocolError,
    a0_prompt,
    call_codex,
    canonical,
    codex_identity,
    fetch_and_bind,
    now,
    read_json,
    retrieval_prompt,
    sha256_file,
    sha256_text,
    sum_usage,
    usage_from,
    write_json,
)


CORE_COMMIT = "a48b313f72b9c3e31c035cfa7dd380c9306101cd"
INTEGRATION_COMMIT = "2cd98dedf9378cd54fae115d1b7590b39d3fb744"
_ID = re.compile(rb"(?<![0-9a-f])[0-9a-f]{24}(?![0-9a-f])", re.IGNORECASE)
_IMAGE_MARKERS = (
    "attached image", "image above", "image below", "following image", "this image",
    "shown in the image", "pictured", "figure above", "figure below", "attached figure",
    "<img", "![", "data:image", "guess the music", "small part of the flag",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def _ids_in_bytes(payload: bytes) -> set[str]:
    return {match.group(0).decode("ascii").lower() for match in _ID.finditer(payload)}


def exposure_scan() -> dict[str, object]:
    ids: set[str] = set()
    sources: dict[str, int] = {}
    files_scanned = 0
    zip_members = 0
    failures: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        try:
            found = _ids_in_bytes(relative.encode("utf-8"))
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue
                        zip_members += 1
                        found |= _ids_in_bytes(member.filename.encode("utf-8"))
                        found |= _ids_in_bytes(archive.read(member))
            else:
                found |= _ids_in_bytes(path.read_bytes())
            files_scanned += 1
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            failures.append(f"{relative}:{type(exc).__name__}")
            continue
        if found:
            ids |= found
            sources[relative] = len(found)
    if failures:
        raise ProtocolError("exposure scan incomplete: " + ";".join(failures[:10]))
    return {
        "schema": "foil.active-runtime-hle10-exposures.v1",
        "scan_completed": True,
        "files_scanned": files_scanned,
        "zip_members_scanned": zip_members,
        "exposed_ids": sorted(ids),
        "source_hit_counts": dict(sorted(sources.items())),
    }


def _question_rows(data_dir: Path) -> list[dict[str, object]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise ProtocolError("pyarrow is required for pinned HLE selection") from exc
    rows: list[dict[str, object]] = []
    for name, expected in HLE_SHARDS.items():
        path = data_dir / name
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"missing or mismatched pinned shard: {name}")
        table = parquet.read_table(path, columns=["id", "Verified_Classes", "category", "question"])
        rows.extend(table.to_pylist())
    if len(rows) != 668 or len({str(row["id"]) for row in rows}) != 668:
        raise ProtocolError("HLE question projection conservation failed")
    return rows


def _eligible(row: Mapping[str, object], exposed: set[str]) -> bool:
    question = str(row.get("question") or "")
    lowered = question.casefold()
    return bool(
        row.get("Verified_Classes") == "Gold subset"
        and str(row.get("id") or "") not in exposed
        and question.strip()
        and len(question) <= 12_000
        and not any(marker in lowered for marker in _IMAGE_MARKERS)
    )


def prepare(data_dir: Path) -> None:
    if OUT.exists():
        raise ProtocolError("sealed run directory already exists")
    exposure = exposure_scan()
    exposed = set(str(value) for value in exposure["exposed_ids"])
    rows = [row for row in _question_rows(data_dir) if _eligible(row, exposed)]
    rows.sort(key=lambda row: sha256_text(f"{SEED}:FOIL_ACTIVE_RUNTIME_HLE10:{row['id']}"))
    chosen = rows[:EXPECTED]
    if len(chosen) != EXPECTED:
        raise ProtocolError(f"only {len(chosen)} provably fresh eligible rows")
    items: list[dict[str, object]] = []
    opportunities: list[dict[str, object]] = []
    for rank, row in enumerate(chosen, start=1):
        source_id = str(row["id"])
        task_id = f"hle-live-{source_id}"
        question = str(row["question"])
        item = {
            "task_id": task_id,
            "source_id": source_id,
            "category": str(row["category"]),
            "question": question,
            "question_sha256": digest(question),
            "selection_rank": rank,
            "selection_sha256": sha256_text(f"{SEED}:FOIL_ACTIVE_RUNTIME_HLE10:{source_id}"),
            "a0_prompt_sha256": sha256_text(a0_prompt(question)),
            "gold_present": False,
        }
        item["item_sha256"] = sha256_text(canonical(item))
        items.append(item)
        task = {"schema": QUESTION_SCHEMA_V2, "task_id": task_id, "question": question}
        opportunities.append(discover_route_opportunity_v2(task).trace())
    write_json(EXPOSURES, exposure)
    write_json(ITEMS, {"schema": "foil.active-runtime-hle10-items.v1", "gold_present": False, "items": items})
    write_json(OPPORTUNITIES, {"schema": "foil.active-runtime-hle10-opportunities.v1", "diagnostic_only": True, "rows": opportunities})
    frozen = [
        PROTOCOL, A0_SCHEMA, RETRIEVAL_SCHEMA, CONSTRUCTOR_SCHEMA,
        Path(__file__), HARNESS / "foil_active_runtime_hle10_common.py",
        HARNESS / "foil_active_runtime_hle10_score.py",
        HARNESS / "foil_active_runtime_hle10_audit.py",
        HARNESS / "foil_runtime_benchmark_integration.py",
        ROOT / "tools" / "foil_runtime_active.py",
        ITEMS, OPPORTUNITIES, EXPOSURES,
    ]
    write_json(MANIFEST, {
        "schema": "foil.active-runtime-hle10-manifest.v1",
        "classification": "DIAGNOSTIC_UNADMITTED_N10",
        "core_commit": CORE_COMMIT,
        "integration_commit": INTEGRATION_COMMIT,
        "dataset_revision": HLE_REVISION,
        "shards": HLE_SHARDS,
        "selection_seed": SEED,
        "item_count": EXPECTED,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "codex": codex_identity(),
        "prior_receipt_costs": {
            "terra_high_a0_p50": 19513, "terra_high_a0_p90": 21974,
            "terra_high_route_p50": 34246, "terra_high_route_p90": 273355,
        },
        "aggregate_token_ceiling": None,
        "coverage_cancellation": False,
        "retries": 0,
        "files": {path.relative_to(ROOT).as_posix(): sha256_file(path) for path in frozen},
        "gold_opened": False,
        "production_authorized": False,
        "promotion_authorized": False,
    })
    print(f"prepared={EXPECTED} exposed_ids={len(exposed)} opportunity_digest={sha256_file(OPPORTUNITIES)}")


def validate_frozen() -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest = read_json(MANIFEST)
    items = read_json(ITEMS)
    if manifest.get("core_commit") != CORE_COMMIT or manifest.get("integration_commit") != INTEGRATION_COMMIT:
        raise ProtocolError("commit lock mismatch")
    for commit in (CORE_COMMIT, INTEGRATION_COMMIT):
        if _git("merge-base", "--is-ancestor", commit, "HEAD").returncode:
            raise ProtocolError(f"required commit is not an ancestor: {commit}")
    if items.get("gold_present") is not False or len(items.get("items", [])) != EXPECTED:
        raise ProtocolError("gold-free item conservation failed")
    for relative, expected in manifest["files"].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            raise ProtocolError(f"frozen digest mismatch: {relative}")
        if _git("ls-files", "--error-unmatch", relative).returncode:
            raise ProtocolError(f"frozen file is not committed: {relative}")
        if _git("diff", "--quiet", "HEAD", "--", relative).returncode:
            raise ProtocolError(f"frozen file differs from HEAD: {relative}")
    if codex_identity() != manifest["codex"]:
        raise ProtocolError("Codex executable/config identity drift")
    return manifest, list(items["items"])


def _token_usage(call: Mapping[str, object], accounting: list[str]) -> TokenUsageV2:
    usage = usage_from(call.get("usage"))
    if usage is None:
        accounting.append("provider_usage_missing")
        return TokenUsageV2()
    return TokenUsageV2(usage["input_tokens"], usage["cached_input_tokens"], usage["output_tokens"])


def _public_call(call: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in call.items() if key != "output"}


class RetrievalRunner:
    def __init__(self, task_id: str, item_private: Path, accounting: list[str]):
        self.task_id = task_id
        self.item_private = item_private
        self.accounting = accounting
        self.calls: list[dict[str, object]] = []
        self.fetches: list[dict[str, object]] = []

    def __call__(self, question: str, envelope: ResourceEnvelopeV2) -> RetrievedPassageBatch:
        try:
            call = call_codex(self.item_private / "retrieval", retrieval_prompt(question), RETRIEVAL_SCHEMA, search=True)
        except ProviderError as exc:
            self.calls.append(_public_call(exc.call))
            usage = _token_usage(exc.call, self.accounting)
            raise ToolBoundaryFailure(BoundaryFailureCode.PROVIDER_ERROR, exc.reason, usage=usage, latency_ms=int(exc.call.get("wall_ms") or 0)) from exc
        self.calls.append(_public_call(call))
        usage = _token_usage(call, self.accounting)
        tools = list(call.get("tools") or [])
        if any(tool.get("tool_type") != "web_search" for tool in tools if isinstance(tool, Mapping)):
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "retrieval used a non-search tool", usage=usage, tool_calls=len(tools), latency_ms=int(call["wall_ms"]))
        output = call.get("output")
        if not isinstance(output, Mapping) or set(output) != {"status", "sources"} or not isinstance(output.get("sources"), list):
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "retrieval output schema mismatch", usage=usage, tool_calls=len(tools), latency_ms=int(call["wall_ms"]))
        sources = list(output["sources"])
        if len(sources) > 2 or (output.get("status") == "UNRESOLVED" and sources):
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "retrieval source count/status mismatch", usage=usage, tool_calls=len(tools), latency_ms=int(call["wall_ms"]))
        if sources and not tools:
            raise ToolBoundaryFailure(BoundaryFailureCode.MALFORMED_RESULT, "sources returned without a search receipt", usage=usage, latency_ms=int(call["wall_ms"]))
        passages: list[PassageEvidenceV2] = []
        fetch_latency = 0
        for index, source in enumerate(sources):
            if not isinstance(source, Mapping) or set(source) != {"url", "title", "quote"}:
                continue
            try:
                fetched = fetch_and_bind(str(source["url"]), str(source["quote"]))
            except (OSError, ValueError, ProtocolError) as exc:
                fetched = {"requested_url": str(source["url"]), "bound": False, "failure": type(exc).__name__}
            self.fetches.append(fetched)
            fetch_latency += int(fetched.get("latency_ms") or 0)
            if not fetched.get("bound"):
                continue
            content = str(fetched["content"])
            final_url = str(fetched["final_url"])
            passages.append(PassageEvidenceV2(
                f"doc-{digest(final_url)[:16]}", final_url, str(source["title"]) or final_url,
                content, now(), int(fetched["start_offset"]), int(fetched["end_offset"]),
                "UNKNOWN", urllib_parse_host(final_url),
            ))
        write_json(self.item_private / "retrieval_fetches.json", {"fetches": self.fetches})
        return RetrievedPassageBatch(
            tuple(passages), usage, len(tools) + len(sources), int(call["wall_ms"]) + fetch_latency,
        )


def urllib_parse_host(url: str) -> str:
    from urllib.parse import urlparse
    return str(urlparse(url).hostname or "unknown")


class ConstructorRunner:
    def __init__(self, item_private: Path, accounting: list[str]):
        self.item_private = item_private
        self.accounting = accounting
        self.calls: list[dict[str, object]] = []

    def __call__(self, request):  # type: ignore[no-untyped-def]
        evidence = [{"span_id": span.span_id, "text": span.text} for span in request.evidence_packet.spans]
        prompt = (
            "Construct one shortest answer from the admitted evidence for this independent question. "
            "You have no incumbent answer, gold, tools, files, or external context. Bind the answer claim "
            "only to listed evidence span IDs. If the passages do not justify an exact answer, return "
            "NO_CANDIDATE with empty answer, claim, and evidence_span_ids. Do not explain outside JSON.\n\n"
            + canonical({"question": request.question, "evidence": evidence})
        )
        try:
            call = call_codex(self.item_private / "constructor", prompt, CONSTRUCTOR_SCHEMA, search=False)
        except ProviderError as exc:
            self.calls.append(_public_call(exc.call))
            raise ConstructorBoundaryFailure(exc.reason, usage=_token_usage(exc.call, self.accounting), latency_ms=int(exc.call.get("wall_ms") or 0)) from exc
        self.calls.append(_public_call(call))
        usage = _token_usage(call, self.accounting)
        tools = list(call.get("tools") or [])
        if tools:
            raise ConstructorBoundaryFailure("constructor_used_tool", usage=usage, latency_ms=int(call["wall_ms"]))
        output = call.get("output")
        expected = {"status", "answer", "claim", "evidence_span_ids", "reason"}
        if not isinstance(output, Mapping) or set(output) != expected:
            raise ConstructorBoundaryFailure("constructor_output_schema_mismatch", usage=usage, latency_ms=int(call["wall_ms"]))
        if output["status"] == "NO_CANDIDATE":
            return ConstructorDraftV2(None, (), usage, str(output["reason"]) or "no_candidate", sha256_text(prompt), int(call["wall_ms"]))
        answer = str(output["answer"]).strip()
        claim = str(output["claim"]).strip()
        span_ids = tuple(str(value) for value in output["evidence_span_ids"])
        known = {span.span_id for span in request.evidence_packet.spans}
        if not answer or not claim or not span_ids or set(span_ids) - known:
            raise ConstructorBoundaryFailure("constructor_invalid_binding", usage=usage, latency_ms=int(call["wall_ms"]))
        atomic = AtomicClaim(f"claim-{digest({'answer': answer, 'spans': span_ids})[:16]}", claim, ClaimKind.ANSWER, answer, True, span_ids)
        return ConstructorDraftV2(answer, (atomic,), usage, str(output["reason"]) or "evidence_candidate", sha256_text(prompt), int(call["wall_ms"]))


def _route_policy() -> FoilRuntimePolicyV2:
    return FoilRuntimePolicyV2(
        True,
        True,
        ComparatorPolicy(semantic_enabled=False, semantic_route_admitted=False, allow_unadmitted_benchmark_selection=False),
        ConstructorPolicyV2(enabled=True, maximum_claims=3, maximum_output_tokens=None, provider_cap_enforced=False),
        require_raw_archive=True,
    )


def _retrieval_adapter(runner: RetrievalRunner) -> PassageRetrievalAdapterV2:
    envelope = ResourceEnvelopeV2(
        maximum_input_tokens=PROVIDER_EFFECTIVE_CONTEXT,
        maximum_cached_input_tokens=PROVIDER_EFFECTIVE_CONTEXT,
        maximum_output_tokens=PROVIDER_EFFECTIVE_CONTEXT,
        maximum_tool_calls=4,
        maximum_model_passes=2,
        maximum_latency_ms=1_200_000,
        maximum_evidence_characters=200_000,
    )
    value = RouteValueEstimate(800_000, 100_000, 0, 1_000_000, 2_000_000, 50_000)
    return PassageRetrievalAdapterV2(
        runner, envelope=envelope, value=value, tool_id="foil.hle10-passage-retrieval",
        tool_version="1", provider_cap_enforced=True,
    )


def _invalid_row(item: Mapping[str, object], outcome: str, call: Mapping[str, object] | None, reason: str) -> dict[str, object]:
    usage = None if call is None else usage_from(call.get("usage"))
    return {
        "schema": "foil.active-runtime-hle10-row.v1",
        "task_id": item["task_id"], "source_id": item["source_id"],
        "question_sha256": item["question_sha256"], "row_outcome": outcome,
        "row_valid": False, "invalid_reason": reason,
        "original_answer": None, "final_answer": None,
        "original_answer_sha256": None, "final_answer_sha256": None,
        "answer_changed": False, "abstention": False,
        "provider_calls": [] if call is None else [_public_call(call)],
        "provider_usage": usage,
        "ledger_after_spent_usage": None,
        "cost_accounting_complete": usage is not None,
        "accounting_status": "ACCOUNTING_INVALID" if usage is None else "VALID",
        "accounting_invalid_reasons": ["a0_usage_missing"] if usage is None else [],
        "runtime_receipt": None,
        "persisted_at": now(),
    }


def run() -> None:
    _, items = validate_frozen()
    if PREDICTIONS.exists() or RECEIPTS.exists() or PRIVATE.exists():
        raise ProtocolError("predictions/receipts/private attempts already exist; retries are prohibited")
    rows: list[dict[str, object]] = []
    for index, item in enumerate(items, start=1):
        task_id = str(item["task_id"])
        item_private = PRIVATE / task_id
        try:
            a0_call = call_codex(item_private / "a0", a0_prompt(str(item["question"])), A0_SCHEMA, search=False)
            output = a0_call.get("output")
            tools = list(a0_call.get("tools") or [])
            if not isinstance(output, Mapping) or set(output) != {"answer"} or not str(output["answer"]).strip():
                row = _invalid_row(item, "INVALID_A0", a0_call, "a0_output_schema_mismatch")
            elif tools:
                row = _invalid_row(item, "INVALID_A0_TOOL_USE", a0_call, "a0_used_tool")
            else:
                a0 = str(output["answer"])
                accounting: list[str] = []
                if usage_from(a0_call.get("usage")) is None:
                    accounting.append("a0_usage_missing")
                retrieval = RetrievalRunner(task_id, item_private, accounting)
                constructor = ConstructorRunner(item_private, accounting)
                task = {"schema": QUESTION_SCHEMA_V2, "task_id": task_id, "question": str(item["question"])}
                obligation = QuestionObligation(task_id, str(item["question_sha256"]), AnswerKind.EXACT_TEXT)
                final, projection = run_benchmark_row(
                    task, a0, obligation,
                    adapters={
                        RuntimeToolFamily.EXACT_ARITHMETIC: ExactArithmeticAdapterV2(),
                        RuntimeToolFamily.RESTRICTED_PYTHON: RestrictedPythonAdapterV2(),
                        RuntimeToolFamily.SYMBOLIC_COMPUTATION: SymbolicLinearAdapterV2(),
                        RuntimeToolFamily.PASSAGE_RETRIEVAL: _retrieval_adapter(retrieval),
                    },
                    ledger=RuntimeTokenLedger(), policy=_route_policy(),
                    archive=RawEvidenceArchive(item_private / "raw_evidence"),
                    constructor_runner=constructor, semantic_comparator=None,
                )
                runtime = projection["foil_runtime_receipt"]
                provider_calls = [_public_call(a0_call), *retrieval.calls, *constructor.calls]
                provider_usage = sum_usage(provider_calls)
                accounting.extend(str(value) for value in projection["accounting_invalid_reasons"])
                if provider_usage is None:
                    accounting.append("provider_usage_incomplete")
                if projection["accounting_status"] != "VALID":
                    accounting.append("runtime_accounting_invalid")
                row = {
                    "schema": "foil.active-runtime-hle10-row.v1",
                    "task_id": task_id, "source_id": item["source_id"],
                    "question_sha256": item["question_sha256"],
                    "row_outcome": runtime["outcome"], "row_valid": True, "invalid_reason": None,
                    "original_answer": a0, "final_answer": final,
                    "original_answer_sha256": digest(a0), "final_answer_sha256": digest(final),
                    "answer_changed": final != a0,
                    "abstention": final.strip().casefold() in {"abstain", "unknown", "unresolved"},
                    "provider_calls": provider_calls, "provider_usage": provider_usage,
                    "ledger_after_spent_usage": runtime["ledger_after"].get("spent_usage"),
                    "cost_accounting_complete": bool(runtime["cost_accounting_complete"]),
                    "accounting_status": "VALID" if not accounting else "ACCOUNTING_INVALID",
                    "accounting_invalid_reasons": sorted(set(accounting)),
                    "selected_family": runtime["selected_family"],
                    "opportunity": runtime["opportunity"], "probes": runtime["probes"],
                    "tool_contract": runtime["contract"], "tool_receipt": runtime["tool_receipt"],
                    "evidence_packet": runtime["evidence_packet"],
                    "constructor": runtime["constructor"],
                    "a0_assessment": runtime["a0_assessment"], "b_assessment": runtime["b_assessment"],
                    "selection": runtime["selection"],
                    "retrieval_fetches": [
                        {key: value for key, value in fetched.items() if key != "content"}
                        for fetched in retrieval.fetches
                    ],
                    "runtime_receipt": runtime, "persisted_at": now(),
                }
        except ProviderError as exc:
            row = _invalid_row(item, "A0_PROVIDER_ERROR", exc.call, exc.reason)
        except Exception as exc:
            row = _invalid_row(item, "HARNESS_ERROR", None, f"{type(exc).__name__}:{exc}")
        receipt_path = RECEIPTS / f"{task_id}.json"
        write_json(receipt_path, row)
        row["receipt_sha256"] = sha256_file(receipt_path)
        rows.append(row)
        print(f"persisted={index}/{EXPECTED} task={task_id} outcome={row['row_outcome']}")
    if len(rows) != EXPECTED:
        raise ProtocolError("row conservation failed")
    write_json(PREDICTIONS, {
        "schema": "foil.active-runtime-hle10-predictions.v1",
        "classification": "DIAGNOSTIC_UNADMITTED_N10",
        "model": MODEL, "reasoning_effort": EFFORT,
        "rows": rows, "row_count": len(rows),
        "gold_opened": False, "production_authorized": False, "promotion_authorized": False,
    })
    print(f"predictions_frozen={len(rows)} sha256={sha256_file(PREDICTIONS)} commit_before_score=true")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--hle-data", type=Path, required=True)
    sub.add_parser("check")
    sub.add_parser("run")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.hle_data)
    elif args.command == "check":
        manifest, items = validate_frozen()
        print(f"sealed_check=PASS items={len(items)} manifest={digest(manifest)}")
    else:
        run()


if __name__ == "__main__":
    main()
