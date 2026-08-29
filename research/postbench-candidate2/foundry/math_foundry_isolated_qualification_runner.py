#!/usr/bin/env python3
"""Qualification runner with fresh-root isolation and explicit artifact staging.

A suite may declare:
  "produces": ["RESULT.json", ...]
  "requires_artifacts": ["RESULT.json", ...]

Produced artifacts are copied into a run-private store with their hashes. A later
suite gets only the artifacts it explicitly requires. Generated artifacts present
in the source root are excluded from fresh copies, preventing accidental hidden
shared-state dependencies.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time, signal
import psutil
from pathlib import Path


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(text: str) -> str:
    return _sha_bytes(text.encode("utf-8", errors="replace"))


def _kill_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
        parent = None
    for child in reversed(children):
        try:
            child.kill()
        except psutil.Error:
            pass
    if parent is not None:
        try:
            parent.kill()
        except psutil.Error:
            pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_one(cmd: list[str], cwd: Path, timeout: float | None):
    # File-backed capture avoids a subtle subprocess timeout failure: solver
    # grandchildren can inherit PIPE descriptors and keep communicate() blocked
    # even after the direct child is killed. wait() is tied only to the direct
    # process; output remains inspectable from the temporary files.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as out_f, tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err_f:
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=out_f, stderr=err_f, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"},
            start_new_session=True,
        )
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        out_f.flush(); err_f.flush(); out_f.seek(0); err_f.seek(0)
        stdout = out_f.read(); stderr = err_f.read()
        if timed_out:
            return ("TIMEOUT", None, stdout, stderr)
        return ("PASS" if proc.returncode == 0 else "FAIL", proc.returncode, stdout, stderr)


def run_manifest(*, root: Path, manifest_path: Path, out_path: Path, log_dir: Path, force_isolation: bool | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text())
    isolate = bool(manifest.get("suite_isolation_required", False)) if force_isolation is None else bool(force_isolation)
    log_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    overall = True
    artifact_ledger: dict[str, dict] = {}
    # Exclude only generated artifacts that are absent from the pristine source root.
    # Some suites deliberately regenerate files that are ALSO manifested baseline fixtures
    # (for example semantic/adaptive routing results). Those pristine fixtures must remain
    # available to independent package-verification suites; explicit staging overwrites them
    # only for suites that declare a generated dependency.
    produced_names = {str(name) for suite in manifest["suites"] for name in suite.get("produces", [])}
    generated_names = {name for name in produced_names if not (root / name).is_file()}

    with tempfile.TemporaryDirectory(prefix="mfq_artifacts_") as artifact_tmp:
        artifact_store = Path(artifact_tmp)
        for index, suite in enumerate(manifest["suites"], 1):
            cmd = [sys.executable if x == "python" else str(x) for x in suite["command"]]
            timeout_raw = suite.get("timeout_seconds")
            timeout = None if timeout_raw is None else float(timeout_raw)
            required = [str(x) for x in suite.get("requires_artifacts", [])]
            produces = [str(x) for x in suite.get("produces", [])]
            staged: list[dict] = []
            captured: list[dict] = []
            start = time.monotonic()

            if isolate:
                with tempfile.TemporaryDirectory(prefix=f"mfq_{index:02d}_") as tmp:
                    run_root = Path(tmp) / "root"
                    ignored_names = {log_dir.name, out_path.name, "__pycache__", ".git"} | generated_names
                    shutil.copytree(
                        root,
                        run_root,
                        ignore=lambda _p, names: [n for n in names if n in ignored_names or n.endswith(".pyc")],
                    )
                    missing = []
                    for name in required:
                        entry = artifact_ledger.get(name)
                        if entry is None:
                            missing.append(name)
                            continue
                        src = artifact_store / entry["store_name"]
                        dst = run_root / name
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                        data = dst.read_bytes()
                        if _sha_bytes(data) != entry["sha256"]:
                            raise RuntimeError(f"staged artifact hash mismatch: {name}")
                        staged.append({"name": name, "sha256": entry["sha256"], "producer_suite": entry["producer_suite"]})
                    if missing:
                        status, rc, stdout, stderr = (
                            "FAIL",
                            None,
                            "",
                            "Missing explicitly required qualification artifacts: " + ", ".join(missing),
                        )
                    else:
                        status, rc, stdout, stderr = _run_one(cmd, run_root, timeout)
                    if status == "PASS":
                        for name in produces:
                            produced = run_root / name
                            if not produced.is_file():
                                status = "FAIL"
                                rc = None
                                stderr += f"\nDeclared qualification artifact was not produced: {name}\n"
                                break
                            data = produced.read_bytes()
                            digest = _sha_bytes(data)
                            store_name = f"{index:02d}_{Path(name).name}"
                            shutil.copy2(produced, artifact_store / store_name)
                            entry = {
                                "name": name,
                                "sha256": digest,
                                "bytes": len(data),
                                "producer_suite": suite["name"],
                                "producer_index": index,
                                "store_name": store_name,
                            }
                            artifact_ledger[name] = entry
                            captured.append({k: v for k, v in entry.items() if k != "store_name"})
            else:
                # Shared-root mode remains diagnostic only. Requirements are checked
                # against the run-private ledger to keep dependency declarations honest.
                missing = [name for name in required if name not in artifact_ledger]
                if missing:
                    status, rc, stdout, stderr = (
                        "FAIL", None, "", "Missing explicitly required qualification artifacts: " + ", ".join(missing)
                    )
                else:
                    status, rc, stdout, stderr = _run_one(cmd, root, timeout)
                if status == "PASS":
                    for name in produces:
                        produced = root / name
                        if not produced.is_file():
                            status = "FAIL"; rc = None
                            stderr += f"\nDeclared qualification artifact was not produced: {name}\n"
                            break
                        data = produced.read_bytes(); digest = _sha_bytes(data)
                        store_name = f"{index:02d}_{Path(name).name}"
                        shutil.copy2(produced, artifact_store / store_name)
                        entry = {"name": name, "sha256": digest, "bytes": len(data), "producer_suite": suite["name"], "producer_index": index, "store_name": store_name}
                        artifact_ledger[name] = entry
                        captured.append({k: v for k, v in entry.items() if k != "store_name"})

            elapsed = time.monotonic() - start
            (log_dir / f"{index:02d}_{suite['name']}.stdout.txt").write_text(stdout, encoding="utf-8")
            (log_dir / f"{index:02d}_{suite['name']}.stderr.txt").write_text(stderr, encoding="utf-8")
            row = {
                "index": index,
                "name": suite["name"],
                "command": suite["command"],
                "status": status,
                "returncode": rc,
                "timeout_seconds": timeout_raw,
                "elapsed_seconds": elapsed,
                "stdout_sha256": _sha(stdout),
                "stderr_sha256": _sha(stderr),
                "stdout_bytes": len(stdout.encode()),
                "stderr_bytes": len(stderr.encode()),
                "isolation_mode": "FRESH_ROOT_COPY_WITH_EXPLICIT_ARTIFACT_STAGING" if isolate else "SHARED_ROOT_DIAGNOSTIC",
                "required_artifacts": staged,
                "produced_artifacts": captured,
            }
            rows.append(row)
            overall &= status == "PASS"
            progress = {
                "schema": "mathfoundry/isolated-qualification-result/2",
                "candidate": manifest.get("candidate", ""),
                "authority": manifest.get("authority", ""),
                "claim_boundary": manifest.get("claim_boundary", ""),
                "qualification_dependency_policy": manifest.get("qualification_dependency_policy", ""),
                "suite_isolation_required": bool(manifest.get("suite_isolation_required", False)),
                "suite_isolation_enforced": isolate,
                "status": "RUNNING" if index < len(manifest["suites"]) else ("PASS" if overall else "FAIL"),
                "suite_count": len(manifest["suites"]),
                "completed": len(rows),
                "passed": sum(r["status"] == "PASS" for r in rows),
                "artifact_ledger": [{k: v for k, v in e.items() if k != "store_name"} for e in artifact_ledger.values()],
                "suites": rows,
            }
            out_path.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n")
    return json.loads(out_path.read_text())


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--manifest", default="MATH_FOUNDRY_FORMAL_PLANE_CANDIDATE_QUALIFICATION_MANIFEST.json")
    p.add_argument("--out", default="MATH_FOUNDRY_FORMAL_PLANE_ISOLATED_QUALIFICATION_RESULT.json")
    p.add_argument("--log-dir", default="isolated_qualification_logs")
    p.add_argument("--shared-root", action="store_true", help="Diagnostic only; disables isolation even if manifest requests it")
    a = p.parse_args(argv)
    root = Path(a.root).resolve()
    result = run_manifest(
        root=root,
        manifest_path=root / a.manifest,
        out_path=root / a.out,
        log_dir=root / a.log_dir,
        force_isolation=False if a.shared_root else None,
    )
    print(json.dumps({"status": result["status"], "passed": result["passed"], "suite_count": result["suite_count"], "suite_isolation_enforced": result["suite_isolation_enforced"]}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
