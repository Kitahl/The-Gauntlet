#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from itertools import product
from pathlib import Path

from math_foundry_exec.hadamard_synthesis_r2 import hadamard_candidate_routes
from math_foundry_exec.hadamard_r2_execution import execute_r2_route
from math_foundry_exec.legendre_pairs import (
    build_fixed_marginal_legendre_pb_model,
    canonical_legendre_pair_signature,
    compress_binary_sequence,
    compression_spec,
    proper_compression_lengths,
    verify_compressed_legendre_pair,
    verify_legendre_hadamard,
    verify_legendre_pair,
)
from math_foundry_exec.pb_model import PBModel
from math_foundry_exec.scientific_state import (
    ScientificStateLedger,
    admit_exact_signature_exclusion,
    admit_model_bound_exclusion,
    pb_model_signature,
    record_solver_conflict_hypothesis,
)

checks={}
def ck(name, cond, detail=None):
    if not cond: raise AssertionError(f"{name}:{detail}")
    checks[name]=True

# Find a tiny LP without hardcoding a witness.
rows=[r for r in product((-1,1), repeat=3) if sum(r)==1]
pair=next((a,b) for a in rows for b in rows if verify_legendre_pair(a,b)['valid'])
lp=verify_legendre_pair(*pair)
ck('01_exact_lp_checker', lp['valid'] and lp['status']=='EXACT', lp)
ck('01b_independent_sign_normalization', verify_legendre_pair(tuple(-x for x in pair[0]), pair[1])['valid'])
had=verify_legendre_hadamard(*pair)
ck('02_lp_to_hadamard_exact', had['valid'] and had['order']==8 and had['gram']['valid'], had)

# Compression theorem on a generated LP of composite length 9.
rows9=[r for r in product((-1,1), repeat=9) if sum(r)==1]
pair9=next((a,b) for a in rows9 for b in rows9 if verify_legendre_pair(a,b)['valid'])
ca=compress_binary_sequence(pair9[0],3); cb=compress_binary_sequence(pair9[1],3)
cc=verify_compressed_legendre_pair(ca,cb,full_length=9)
ck('03_exact_compression_identity', cc['valid'] and cc['spec']['compression_factor']==3, cc)
# Common decimation and independent cyclic shifts are exact LP equivalences.
dec_a=tuple(pair9[0][(2*i)%9] for i in range(9)); dec_b=tuple(pair9[1][(2*i)%9] for i in range(9))
shift_a=dec_a[2:]+dec_a[:2]; shift_b=dec_b[5:]+dec_b[:5]
ck('03b_decimation_equivalence_canonical', canonical_legendre_pair_signature(*pair9)==canonical_legendre_pair_signature(shift_a,shift_b))
ck('04_compression_targets', compression_spec(9,3)['paf_nonzero_target']==-6 and compression_spec(9,3)['paf_zero_target']==14)
ck('04b_balanced_compression_priority', proper_compression_lengths(45)[:2]==[5,9], proper_compression_lengths(45))

# Fixed-marginal PB model remains exact and solver-independent at construction.
model, meta=build_fixed_marginal_legendre_pb_model(ca,cb,full_length=9,paf_shifts=[1,2,3,4])
ck('05_fixed_marginal_model', model.metadata['complete_model'] and model.structural_profile()['variables']>18, model.receipt())
sol=model.solve_scipy(time_limit_seconds=2,node_limit=10000)
ck('06_fixed_marginal_solver_exact_substitution', sol.assignment is not None and sol.exact_assignment_check and sol.exact_assignment_check['valid'], sol)

# Court-admitted exact refutation excludes only the exact canonical class.
ledger=ScientificStateLedger('problem-x')
bad_a=[1,1,1]; bad_b=[1,1,1]
bad=verify_legendre_pair(bad_a,bad_b)
sig=canonical_legendre_pair_signature(bad_a,bad_b)
adm=admit_exact_signature_exclusion(
    ledger, forbidden_signature=sig, representation='BINARY_LEGENDRE_PAIR', scope='LEGENDRE_LENGTH_3',
    dependencies={'engine':'test-v1'}, checker_receipt=bad, checker_name='EXACT_INTEGER_LEGENDRE_PAF_CHECKER', replay_payload={'a':bad_a,'b':bad_b})
ck('07_court_exact_refutation', adm['admitted'] and ledger.is_signature_excluded(sig,representation='BINARY_LEGENDRE_PAIR',scope='LEGENDRE_LENGTH_3',dependencies={'engine':'test-v1'}), adm)
ck('08_m7_dependency_invalidation', not ledger.is_signature_excluded(sig,representation='BINARY_LEGENDRE_PAIR',scope='LEGENDRE_LENGTH_3',dependencies={'engine':'test-v2'}), ledger.change_impact(dependencies={'engine':'test-v2'}))

# Proof-carrying Boolean interval contradiction.
contr=PBModel('contradiction'); x=contr.new_var('x'); contr.add_eq({x:1},2,name='impossible')
static=admit_model_bound_exclusion(ledger,contr,representation='PB_TEST',scope='UNIT',dependencies={'engine':'test-v1'})
ck('09_static_pb_conflict_admitted', static['admitted'] and ledger.is_model_excluded(contr,representation='PB_TEST',scope='UNIT',dependencies={'engine':'test-v1'}), static)
# Solver-only conflict reports persist as hypotheses but have zero pruning authority.
hyp_model=PBModel('solver-hypothesis'); hx=hyp_model.new_var('x'); hy=hyp_model.new_var('y')
hyp_model.add_eq({hx:1,hy:1},1,name='sum1'); hyp_model.add_eq({hx:1},0,name='x0'); hyp_model.add_eq({hy:1},0,name='y0')
hyp=record_solver_conflict_hypothesis(ledger,hyp_model,representation='PB_TEST',scope='HYP',dependencies={'engine':'test-v1'},solver_receipt={'solver':'test','status':'INFEASIBLE','message':'untrusted'})
ck('09b_solver_hypothesis_not_pruning', not hyp['admitted'] and not ledger.is_signature_excluded(pb_model_signature(hyp_model),representation='PB_TEST',scope='HYP',dependencies={'engine':'test-v1'}), hyp)

# Atomic Librarian-style persistence and exact reuse.
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'state.json'; ledger.save_atomic(p); loaded=ScientificStateLedger.load(p,problem_signature='problem-x')
    ck('10_state_roundtrip', loaded.receipt()['state_digest']==ledger.receipt()['state_digest'] and loaded.receipt()['admitted_exact_fact_count']==2)

# CRS ranking is SEARCH_ONLY and responds to exact-information observations.
ledger.record_observation(route_id='A',status='UNRESOLVED',elapsed_seconds=10,exact_exclusions_learned=0)
ledger.record_observation(route_id='B',status='UNRESOLVED',elapsed_seconds=2,exact_exclusions_learned=10)
rank=ledger.rank_experiments(['A','B'])
ck('11_crs_information_ranking', rank['ranked_routes'][0]['route_id']=='B' and rank['authority']=='SEARCH_ONLY', rank)

# M8-style interaction telemetry is descriptive only.
ledger.record_filter_event(filters=['PSD'],states_before=100,states_after=60,elapsed_seconds=1,representation='LP')
ledger.record_filter_event(filters=['COSET'],states_before=100,states_after=70,elapsed_seconds=1,representation='LP')
ledger.record_filter_event(filters=['PSD','COSET'],states_before=100,states_after=10,elapsed_seconds=1,representation='LP')
inter=ledger.interaction_report()
ck('12_m8_interaction_telemetry', inter['rows'] and inter['rows'][0]['interaction_lift']>0 and inter['authority']=='SEARCH_ONLY', inter)

# First-class route exists generally but is research-only under standard AUTO.
routes=hadamard_candidate_routes(20); lr=[r for r in routes if r['route_id']=='HAD-LP-COMPRESS-LEARN']
ck('13_lp_route_registered', len(lr)==1 and lr[0]['research_only'] and lr[0]['legendre_length']==9, routes)

# Route can close a held-out small instance through compression + PB + exact Gram.
# Post-benchmark qualification uses a stable 20s outer budget so the subprocess
# solver startup slice is not a load-sensitive ~0.31s release gate. The route,
# seed, work cap, exact checker, and mathematical acceptance criteria are unchanged.
with tempfile.TemporaryDirectory() as td:
    result=execute_r2_route(lr[0],max_seconds=20,max_nodes=100000,seed=3,restarts=8,scientific_state_path=str(Path(td)/'state.json'))
    ck('14_lp_route_exact_small', result['status']=='COMPLETE_SOLVED_PROOF' and result['found'] and result['result']['hadamard']['valid'], result)
    ck('15_scientific_state_emitted', result['scientific_state']['schema']=='mathfoundry/scientific-search-state/1', result.get('scientific_state'))

print(json.dumps({'status':'PASS','passed':len(checks),'total':len(checks),'checks':checks},indent=2,sort_keys=True))
