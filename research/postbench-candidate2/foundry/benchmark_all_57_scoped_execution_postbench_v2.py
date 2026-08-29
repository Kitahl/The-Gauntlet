#!/usr/bin/env python3
from __future__ import annotations
import json, os, subprocess, sys, time, signal
import psutil
from pathlib import Path

from math_foundry_exec.method_backend_registry import full_backend_report
from math_foundry_exec.strategy import method_spec

ROOT = Path(__file__).resolve().parent
def _kill_process_tree(pid: int) -> None:
    try:
        parent=psutil.Process(pid)
        children=parent.children(recursive=True)
    except psutil.Error:
        children=[]; parent=None
    for child in reversed(children):
        try: child.kill()
        except psutil.Error: pass
    if parent is not None:
        try: parent.kill()
        except psutil.Error: pass
    try: os.killpg(pid,signal.SIGKILL)
    except (ProcessLookupError,PermissionError): pass

OUT = ROOT / 'MATH_FOUNDRY_ALL57_SCOPED_EXECUTION_RESULT.json'
WORKER = ROOT / 'benchmark_all_57_scoped_execution_postbench_worker.py'
methods = sorted(json.loads((ROOT / 'method_atlas.json').read_text())['methods'])
rows=[]
start_all=time.perf_counter()
for mid in methods:
    print('ISOLATED START', mid, flush=True)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','MATH_FOUNDRY_SINGLE_METHOD':mid}
    t=time.perf_counter()
    with __import__('tempfile').TemporaryFile(mode='w+t',encoding='utf-8') as out_f, __import__('tempfile').TemporaryFile(mode='w+t',encoding='utf-8') as err_f:
        # GNU timeout proved reliable for nested solver processes that may create
        # their own process/session structure. 124/137 are recorded as bounded
        # qualification timeout, never as mathematical success.
        cp=subprocess.run(['timeout','--kill-after=5s','60s',sys.executable,'-B',str(WORKER)],cwd=ROOT,env=env,stdout=out_f,stderr=err_f,text=True)
        out_f.flush(); err_f.flush(); out_f.seek(0); err_f.seek(0)
        stdout=out_f.read(); stderr=err_f.read()
        elapsed=time.perf_counter()-t
        if cp.returncode in (124,137):
            rows.append({'method_id':mid,'status':'TIMEOUT','elapsed_seconds':elapsed,'error':'OUTER_60S_QUALIFICATION_TIMEOUT','stdout_tail':stdout[-4000:], 'stderr_tail':stderr[-4000:]})
            print('ISOLATED DONE',mid,'TIMEOUT',round(elapsed,3),flush=True)
            continue
        if cp.returncode!=0:
            rows.append({'method_id':mid,'status':'ERROR','elapsed_seconds':elapsed,'worker_returncode':cp.returncode,'stdout_tail':stdout[-4000:],'stderr_tail':stderr[-4000:]})
            print('ISOLATED DONE',mid,'ERROR',round(elapsed,3),flush=True)
            continue
        one=json.loads(OUT.read_text())
        if len(one.get('cases',[])) != 1 or one['cases'][0].get('method_id') != mid:
            rows.append({'method_id':mid,'status':'ERROR','elapsed_seconds':elapsed,'error':'WORKER_RESULT_IDENTITY_MISMATCH'})
            print('ISOLATED DONE',mid,'ERROR_IDENTITY',round(elapsed,3),flush=True)
            continue
        row=one['cases'][0]
        row['isolated_worker_elapsed_seconds']=elapsed
        rows.append(row)
        print('ISOLATED DONE',mid,row.get('status'),round(elapsed,3),flush=True)


report=full_backend_report(methods)
summary={
 'schema':'mathfoundry/all57-scoped-execution-postbench-v2',
 'status':'PASS' if len(rows)==57 and all(r.get('status')=='PASS' for r in rows) else 'FAIL',
 'passed':sum(r.get('status')=='PASS' for r in rows),
 'total':len(rows),
 'autonomous_scoped_method_count':sum(method_spec(ROOT,m).autonomy_class=='AUTONOMOUS_SCOPED_EXECUTION' for m in methods),
 'backend_registry_methods_with_available_backend':report['methods_with_available_backend'],
 'cases':rows,
 'elapsed_seconds':time.perf_counter()-start_all,
 'qualification_isolation':'ONE_FRESH_PYTHON_SUBPROCESS_PER_METHOD; OUTER_TIMEOUT_60S; SAME_CASES_AND_VALIDATORS_AS_V1',
 'authority':'EXECUTION_QUALIFICATION_ONLY',
 'claim_boundary':'PASS means the same 57 v1 scoped cases each passed in a separate bounded qualification process. Production runtime semantics are unchanged; this does not imply full general backend parity.'
}
OUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2,sort_keys=True))
raise SystemExit(0 if summary['status']=='PASS' else 1)
