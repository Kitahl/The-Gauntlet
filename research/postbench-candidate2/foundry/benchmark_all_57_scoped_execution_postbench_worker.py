from __future__ import annotations
import json,time,statistics,os
from pathlib import Path
from math_foundry_exec.runtime import run_method
from math_foundry_exec.strategy import method_spec
from math_foundry_exec.method_backend_registry import full_backend_report

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'MATH_FOUNDRY_ALL57_SCOPED_EXECUTION_RESULT.json'

P=lambda **kw: kw
imp=lambda a,b:{'op':'imp','left':a,'right':b}

CASES={
'ALG-01':({'variables':['x','y'],'polynomials':['x+y-3','x*y-2']},lambda x:x.get('basis_size')==2),
'ALG-02':({'n':4,'generators':[[1,0,3,2]]},lambda x:x.get('orbits')==[[0,1],[2,3]]),
'ALG-03':({'maximal_simplices':[[0,1,2]]},lambda x:x.get('betti_numbers')==[1,0,0]),
'ALG-04':({'integer':72,'p':2,'power':4},lambda x:x.get('valuation')==3 and x.get('residue')==8),
'COMB-01':({'left':['a','b'],'right':['x','y'],'incidences':[['a','x'],['a','y'],['b','y']]},lambda x:x.get('double_count_identity') and x.get('incidence_count')==3),
'COMB-02':({'bad_event_probability':[1,100],'max_dependency_degree':10},lambda x:x.get('existence_certified') is True),
'COMB-03':({'coefficients':[-1,0,1],'p':5},lambda x:x.get('roots')==[1,4]),
'COMB-04':({'factors':[[1,1],[1,1]]},lambda x:x.get('coefficients')==[1,2,1]),
'COMB-05':({'family':[[2,3],[1,3],[3,4]],'i':1,'j':3},lambda x:x.get('cardinality_preserved') and x.get('uniformity_preserved')),
'COMB-06':({'adjacency':[[0,1],[1,0]]},lambda x:x.get('characteristic_polynomial_coefficients')==[1,0,-1]),
'DISC-01':({'values':[1,2,3,4],'predicate':{'op':'le','value':3}},lambda x:x.get('status')=='COUNTEREXAMPLE' and x.get('witness')==4),
'DISC-02':({'x':[0,1,2],'y':[1,3,5]},lambda x:x.get('exact_fit') and x.get('slope')=={'num':2,'den':1}),
'DISC-03':({'n':3,'edges_a':[[0,1],[1,2]],'edges_b':[[0,2],[2,1]]},lambda x:x.get('isomorphic') is True),
'DISC-04':({'values':[1,2,3,4],'predicate':{'op':'divisible','by':2}},lambda x:x.get('witness')==1),
'DISC-05':({'expression':'sin(x)/x','variable':'x','point':0},lambda x:x.get('limit')=='1'),
'DISC-06':({'x':[0,1,2],'y':[1,2,5]},lambda x:x.get('verified_on_data') and x.get('degree')==2),
'FORM-01':({'domains':{'x':[0,1,2]},'constraints':[{'coefficients':{'x':1},'op':'>=','rhs':1}]},lambda x:x.get('feasible_count')==2),
'FORM-02':({'coefficients':[-6,-12,18]},lambda x:x.get('equivalent') and x.get('normalized_coefficients')==[1,2,-3]),
'FORM-03':({'universe':[0,1,2],'statement_a_true':[0],'statement_b_true':[0,1]},lambda x:x.get('relation')=='A_STRONGER_THAN_B'),
'FORM-04':({'universe':[0,1,2],'left_true':[0,2],'right_true':[0,2]},lambda x:x.get('equivalent') is True),
'FORM-05':({'cnf':[[1,2],[-1,2],[1,-2]]},lambda x:x.get('status')=='SAT'),
'IMP-01':({'source_labels':{'a':True,'b':False},'target_labels':{'x':True,'y':False},'mapping':{'a':'x','b':'y'}},lambda x:x.get('valid_reduction') is True),
'IMP-02':({'diagonal_predictions':[True,False,True]},lambda x:x.get('differs_from_each_on_own_index') is True),
'IMP-03':({'observations':['same','same','other'],'labels':['YES','NO','YES']},lambda x:x.get('perfect_classification_possible') is False and len(x.get('indistinguishable_conflicts',[]))==1),
'OPT-01':({'values':[10,7,12,8],'weights':[5,3,6,4],'capacity':10},lambda x:x.get('upper_bound')=={'num':21,'den':1}),
'OPT-02':({'n':3},lambda x:x.get('integer_optimum')==2 and x.get('sdp_bound')=={'num':9,'den':4}),
'OPT-03':({'values':[10,7,12,8],'weights':[5,3,6,4],'capacity':10},lambda x:x.get('objective')==20),
'OPT-04':({'nodes':['s','a','t'],'edges':[['s','a',1],['a','t',2],['s','t',5]],'source':'s','target':'t'},lambda x:x.get('reachable') and x.get('distance')=={'num':3,'den':1} and x.get('dual_feasible')),
'OPT-05':({'values':[10,7,12,8],'weights':[5,3,6,4],'capacity':10},lambda x:x.get('objective')==20),
'OPT-06':({'ground_size':3,'weights':[3,2,1],'independent_sets':[[],[0],[1],[2],[0,1],[0,2],[1,2]]},lambda x:x.get('matroid_axioms_verified') and x.get('greedy_optimal') and x.get('exact_optimum_weight')=={'num':5,'den':1}),
'OPT-07':({'cost_matrix':[[3,5],[4,4],[2,6]]},lambda x:x.get('selected_action')==1 and x.get('robust_value')=={'num':4,'den':1}),
'OPT-08':({'Q':[[2,0],[0,4]],'c':[-2,-8]},lambda x:x.get('positive_definite') and x.get('stationarity_verified') and x.get('objective')=={'num':-9,'den':1}),
'PROOF-01':({'a':30,'b':18},lambda x:x.get('gcd')==6 and x.get('identity_verified')),
'PROOF-02':({'cnf':[[1],[-1]]},lambda x:x.get('contradiction') and not x.get('satisfiable')),
'PROOF-03':({'summand':'n','closed_form':'n*(n+1)/2'},lambda x:x.get('proved_by_induction_schema') is True),
'PROOF-04':({'states':[0,1,2],'initial_states':[0],'transitions':[[0,1],[1,2],[2,2]],'invariant_states':[0,1,2],'monovariant':{'0':2,'1':1,'2':0}},lambda x:x.get('initial_invariant') and x.get('preserved') and x.get('monovariant_verified')),
'PROOF-05':({'n':4,'implications':[[0,1],[1,2],[2,3]],'bottom':1},lambda x:x.get('least_fixed_point')==15 and x.get('fixed')),
'PROOF-06':({'a_labels':{'a':True,'b':False},'b_labels':{'x':True,'y':False},'a_to_b':{'a':'x','b':'y'},'b_to_a':{'x':'a','y':'b'}},lambda x:x.get('equivalent_under_declared_reductions') is True),
'PROOF-07':({'left':['a','b'],'right':['x','y'],'edges':[['a','x'],['b','y']]},lambda x:x.get('exists') and x.get('unique')),
'REP-01':({'A':[[1,1],[1,-1]],'b':[3,1],'projection_indices':[0]},lambda x:x.get('feasible') and x.get('projected_solution')==['2']),
'REP-02':({'n':4,'generators':[[1,0,3,2]],'transitions':[[0,2],[1,3]]},lambda x:x.get('quotient_state_count')==2 and x.get('quotient_transitions')==[[0,1]]),
'REP-03':({'values':[10,7,12,8],'weights':[5,3,6,4],'capacity':10},lambda x:x.get('strong_duality_verified') is True and x.get('primal_value')==x.get('dual_value')),
'REP-04':({'values':[1,2,3,4],'prime':17,'primitive_root':3},lambda x:x.get('roundtrip_verified') is True),
'REP-05':({'A':[[1,1],[0,1]],'b':[1,0],'x':[2,3]},lambda x:x.get('roundtrip_verified') is True),
'REP-06':({'matrix':[[1,2],[2,4]]},lambda x:x.get('rank')==1 and x.get('factorization_verified')),
'REP-07':({'residuals':[[1,2,3],[2,4,6]]},lambda x:x.get('rank')==1 and x.get('rank_one_hidden_structure',{}).get('verified')),
'REP-08':({'universe_size':16,'bitset':0b101011,'mask':0b111100},lambda x:x.get('result_bitset')==(0b101011&0b111100) and x.get('materialized_members') is False),
'SEARCH-01':({'states':['a','b','c'],'transitions':[['a','b'],['b','c']],'targets':['c'],'initial_states':['a']},lambda x:x.get('reachable_from_any_initial') and x.get('winning_preimage')==['a','b','c']),
'SEARCH-02':({'values':[3,5,7,10],'target':15},lambda x:x.get('found') and x.get('sum')==15),
'SEARCH-03':({'nodes':['0','1','2'],'edges':[['0','1',1],['1','2',3]],'thresholds':[1,3]},lambda x:len(x.get('levels',[]))==2 and len(x['levels'][0]['components'])==2 and len(x['levels'][1]['components'])==1),
'SEARCH-04':({'A0':[[1]],'A1':[[1]],'b0':[1],'b1':[0],'parameters':[0,1]},lambda x:x.get('all_nonsingular') and x.get('path',[{}])[1].get('solution')==[{'num':1,'den':2}]),
'SEARCH-05':({'variables':['a','b','c'],'factors':[['a','b']]},lambda x:x.get('decomposable') and len(x.get('components',[]))==2),
'SEARCH-06':({'required_capabilities':['SAT'],'solvers':[{'id':'s1','capabilities':['SAT'],'cost':2},{'id':'s2','capabilities':['SAT','PB'],'cost':1}]},lambda x:x.get('selected_solver')=='s2'),
'VER-01':({'premises':['P',imp('P','Q')],'steps':[{'rule':'premise','formula':'P'},{'rule':'premise','formula':imp('P','Q')},{'rule':'modus_ponens','antecedent_step':0,'implication_step':1,'formula':'Q'}],'conclusion':'Q'},lambda x:x.get('proof_valid') and x.get('conclusion_verified')),
'VER-02':({'cnf':[[1,2],[-1,2],[1,-2]]},lambda x:x.get('status') in {'SAT','UNSAT'}),
'VER-03':({'states':['a','b','c'],'initial_states':['a'],'transitions':[['a','b'],['b','c']],'bad_states':['c']},lambda x:x.get('safe') is False and x.get('counterexample_trace')==['a','b','c']),
'VER-04':({'coefficients':[1,1],'interval':[0,1]},lambda x:x.get('lower')=={'num':1,'den':1} and x.get('upper')=={'num':2,'den':1}),
}

all_methods=sorted(json.loads((ROOT/'method_atlas.json').read_text())['methods'])
assert set(CASES)==set(all_methods),(sorted(set(all_methods)-set(CASES)),sorted(set(CASES)-set(all_methods)))
methods=([os.environ['MATH_FOUNDRY_SINGLE_METHOD']] if os.environ.get('MATH_FOUNDRY_SINGLE_METHOD') else all_methods)
assert all(m in CASES for m in methods)
rows=[]
for mid in methods:
    print("START", mid, flush=True)
    inp,validator=CASES[mid]
    full={**inp,'problem_statement':f'{mid} scoped execution qualification','claim_statement':f'{mid} scoped execution qualification','wall_seconds':30,'evaluation_context_id':'ALL57-SCOPED-V1'}
    t=time.perf_counter()
    try:
        r=run_method(ROOT,mid,full); elapsed=time.perf_counter()-t
        results=r.get('results',[])
        # DISC-01's mathematical result is the final counterexample step; most scoped methods use one step.
        target=results[-1] if mid=='DISC-01' else (results[0] if results else {})
        ok=(r.get('status')=='COMPLETED_SEARCH_ONLY' and r.get('execution_semantic_status')=='AUTONOMOUS_EXECUTABLE' and r.get('progress',{}).get('verified_progress_count',0)>=1 and bool(validator(target)))
        rows.append({'method_id':mid,'status':'PASS' if ok else 'FAIL','elapsed_seconds':elapsed,'execution_status':r.get('status'),'execution_semantic_status':r.get('execution_semantic_status'),'verified_progress_count':r.get('progress',{}).get('verified_progress_count',0),'result':target,'all_results':results,'receipt_results':[x.get('result') for x in r.get('receipts',[])]})
        print("DONE", mid, rows[-1]["status"], round(elapsed,3), flush=True)
    except Exception as exc:
        rows.append({'method_id':mid,'status':'ERROR','elapsed_seconds':time.perf_counter()-t,'error':f'{type(exc).__name__}:{exc}'})

report=full_backend_report(methods)
summary={
 'schema':'mathfoundry/all57-scoped-execution-v1',
 'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
 'passed':sum(r['status']=='PASS' for r in rows),
 'total':len(rows),
 'autonomous_scoped_method_count':sum(method_spec(ROOT,m).autonomy_class=='AUTONOMOUS_SCOPED_EXECUTION' for m in methods),
 'backend_registry_methods_with_available_backend':report['methods_with_available_backend'],
 'cases':rows,
 'authority':'EXECUTION_QUALIFICATION_ONLY',
 'claim_boundary':'PASS means the Method Atlas card has a concrete scoped executor and exact replay on its declared finite/exact benchmark. It does not mean full general implementation parity with Lean/Sage/SCIP-class systems.'
}
OUT.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2,sort_keys=True))
for r in rows:
    if r['status']!='PASS': print(json.dumps(r,indent=2,sort_keys=True))
raise SystemExit(0 if summary['status']=='PASS' else 1)
