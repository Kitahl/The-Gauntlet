from __future__ import annotations
import io,json,random,re,urllib.request,zipfile
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'benchmark_runs'/'2026-08-22'; OUT.mkdir(parents=True,exist_ok=True)
SEED=20260822
HLE='https://raw.githubusercontent.com/ustc-ai4science/Science-Star/4abe1db2d6d0920aa0a6236ee2f81de872adafa5/data/HLE/subset/hle_subset_50.jsonl'
ARC='https://github.com/fchollet/ARC-AGI/archive/refs/heads/master.zip'
BAD=('attached image','image above','image below','following image','this image','shown in the image','shown in this image','pictured','figure above','figure below','attached figure','this knot','guess the music','small part of the flag')
def get(u):
 r=urllib.request.Request(u,headers={'User-Agent':'The-Gauntlet-benchmark/0.1'}); return urllib.request.urlopen(r,timeout=60).read()
def norm(x): return re.sub(r'\s+',' ',str(x).strip()).casefold()
def hle():
 rows=[json.loads(x) for x in get(HLE).decode().splitlines() if x.strip()]; elig=[]
 for r in rows:
  q=str(r.get('question','')); low=q.casefold()
  if r.get('answer_type')=='multipleChoice' and not any(x in low for x in BAD) and len(q)<=6500: elig.append(r)
 if len(elig)<10: raise RuntimeError(f'need >=10 HLE items, found {len(elig)}')
 rng=random.Random(SEED); by=defaultdict(list)
 for r in elig: by[str(r.get('category') or 'Other')].append(r)
 for v in by.values(): rng.shuffle(v)
 sel=[]
 while any(by.values()):
  for k in sorted(by):
   if by[k]: sel.append(by[k].pop())
 rng.shuffle(sel); qs=[]; gold={}
 for i,r in enumerate(sel):
  qid='hle-'+r['id']; qs.append({'id':qid,'benchmark':'HLE-public-subset','condition':'BASE' if i%2==0 else 'FOIL_MM','category':r.get('category'),'answer_type':'multipleChoice','question':r['question']}); gold[qid]=r['answer']
 return qs,gold
def arc():
 z=zipfile.ZipFile(io.BytesIO(get(ARC))); cand=[]
 for n in z.namelist():
  if '/data/evaluation/' not in n or not n.endswith('.json'): continue
  raw=z.read(n)
  if len(raw)>7000: continue
  t=json.loads(raw)
  if len(t.get('test',[]))!=1 or 'output' not in t['test'][0]: continue
  inp=t['test'][0]['input']
  if len(inp)<=20 and max(map(len,inp),default=0)<=20: cand.append((Path(n).stem,t))
 rng=random.Random(SEED+1); rng.shuffle(cand); qs=[]; gold={}
 for i,(tid,t) in enumerate(cand[:12]):
  qid='arc-'+tid; x=t['test'][0]; qs.append({'id':qid,'benchmark':'ARC-AGI-1-evaluation','condition':'BASE' if i%2==0 else 'FOIL_MM','train':t['train'],'test_input':x['input'],'instruction':'Infer the transformation and return only the output grid.'}); gold[qid]=x['output']
 return qs,gold
def main():
 hq,hg=hle(); aq,ag=arc(); qs=hq+aq; gold={**hg,**ag}
 (OUT/'benchmark_questions.json').write_text(json.dumps({'schema':'foil-benchmark-questions/v1','selection_seed':SEED,'conditions':{'BASE':'direct answer; no FOIL/Mastermind','FOIL_MM':'Frontier-Exam FOIL + Mastermind final defect pass; no gold'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
 p=OUT/'predictions.json'
 if p.exists():
  preds={x['id']:x.get('answer') for x in json.loads(p.read_text()).get('predictions',[])}; rows=[]; agg=defaultdict(list)
  for q in qs:
   ok=norm(preds.get(q['id']))==norm(gold[q['id']]) if q['benchmark'].startswith('HLE') else preds.get(q['id'])==gold[q['id']]
   rows.append({'id':q['id'],'benchmark':q['benchmark'],'condition':q['condition'],'correct':bool(ok)}); agg[(q['benchmark'],q['condition'])].append(int(ok))
  summary=[{'benchmark':b,'condition':c,'correct':sum(v),'n':len(v),'accuracy':sum(v)/len(v)} for (b,c),v in sorted(agg.items())]
  (OUT/'benchmark_results.json').write_text(json.dumps({'schema':'foil-benchmark-results/v1','selection_seed':SEED,'summary':summary,'items':rows,'validity_boundary':'Exploratory in-session disjoint-subset pilot; not an official submission. Same-item causal A/B requires isolated executions.'},indent=2)+'\n')
 print(f'prepared {len(qs)} blinded questions: HLE={len(hq)}, ARC={len(aq)}')
if __name__=='__main__': main()
