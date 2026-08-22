from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import prepare_and_score_v2 as v

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'benchmark_runs'/'2026-08-22'; OUT.mkdir(parents=True,exist_ok=True)
# 673a... was exposed with its gold answer earlier in this conversation.
# 673832... is the deterministic balancing drop: highest lexical BASE id among the frozen HLE selection.
DROP={'hle-673a76559e89466aa6433f66','hle-67383288f2df805520bc86b5'}

def main():
 hq,hg=v.hle(); hq=[q for q in hq if q['id'] not in DROP]; hg={k:x for k,x in hg.items() if k not in DROP}
 aq,ag=v.arc(); qs=hq+aq; gold={**hg,**ag}
 (OUT/'benchmark_questions.json').write_text(json.dumps({'schema':'foil-benchmark-questions/v2','selection_seed':v.SEED,'excluded_hle_ids':sorted(DROP),'conditions':{'BASE':'direct answer; no FOIL/Mastermind','FOIL_MM':'Frontier-Exam FOIL + Mastermind final defect pass; no gold'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
 p=OUT/'predictions.json'
 if p.exists():
  preds={x['id']:x.get('answer') for x in json.loads(p.read_text()).get('predictions',[])}; rows=[]; agg=defaultdict(list)
  for q in qs:
   ok=v.norm(preds.get(q['id']))==v.norm(gold[q['id']]) if q['benchmark'].startswith('HLE') else preds.get(q['id'])==gold[q['id']]
   rows.append({'id':q['id'],'benchmark':q['benchmark'],'condition':q['condition'],'correct':bool(ok)}); agg[(q['benchmark'],q['condition'])].append(int(ok))
  summary=[{'benchmark':b,'condition':c,'correct':sum(z),'n':len(z),'accuracy':sum(z)/len(z)} for (b,c),z in sorted(agg.items())]
  (OUT/'benchmark_results.json').write_text(json.dumps({'schema':'foil-benchmark-results/v2','selection_seed':v.SEED,'summary':summary,'items':rows,'validity_boundary':'Exploratory in-session disjoint-subset pilot; not an official submission. Same-item causal A/B requires isolated executions.'},indent=2)+'\n')
 print(f'prepared {len(qs)} blinded questions: HLE={len(hq)}, ARC={len(aq)}')
if __name__=='__main__': main()
