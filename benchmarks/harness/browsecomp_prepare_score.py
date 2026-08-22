from __future__ import annotations
import base64,csv,hashlib,io,json,random,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'benchmark_runs'/'2026-08-22'; OUT.mkdir(parents=True,exist_ok=True)
URL='https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv'; SEED=20260824

def get(u):
 r=urllib.request.Request(u,headers={'User-Agent':'The-Gauntlet-benchmark/0.1'}); return urllib.request.urlopen(r,timeout=60).read()
def key(password,length):
 h=hashlib.sha256(password.encode()).digest(); return h*(length//len(h))+h[:length%len(h)]
def decrypt(value,password):
 raw=base64.b64decode(value); k=key(password,len(raw)); return bytes(a^b for a,b in zip(raw,k)).decode()
def norm(x): return re.sub(r'[^a-z0-9]+',' ',str(x).casefold()).strip()
def prepare():
 rows=list(csv.DictReader(io.StringIO(get(URL).decode('utf-8-sig')))); rng=random.Random(SEED); selected=rng.sample(rows,20)
 qs=[]; gold={}
 for i,row in enumerate(selected):
  qid=f'bc-{i:02d}-{hashlib.sha256(row["problem"].encode()).hexdigest()[:8]}'
  problem=decrypt(row['problem'],row['canary']); answer=decrypt(row['answer'],row['canary'])
  qs.append({'id':qid,'benchmark':'BrowseComp-official-test-subset','condition':'BASE' if i%2==0 else 'FOIL_MM','question':problem,'instruction':'Use web browsing. Return one succinct exact answer.'}); gold[qid]=answer
 (OUT/'browsecomp_questions.json').write_text(json.dumps({'schema':'foil-browsecomp-questions/v1','selection_seed':SEED,'source':URL,'conditions':{'BASE':'straightforward browsing with the same web access','FOIL_MM':'FOIL evidence routing + counterevidence + exact-answer audit with the same web access'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
 return qs,gold
def main():
 qs,gold=prepare(); p=OUT/'browsecomp_predictions.json'
 if p.exists():
  preds={x['id']:x.get('answer') for x in json.loads(p.read_text()).get('predictions',[])}; items=[]; summary={'BASE':[0,0],'FOIL_MM':[0,0]}; review=[]
  for q in qs:
   pred=str(preds.get(q['id'],'')).strip(); ref=str(gold[q['id']]).strip(); exact=norm(pred)==norm(ref); c=q['condition']; summary[c][1]+=1; summary[c][0]+=int(exact); items.append({'id':q['id'],'condition':c,'exact_normalized_match':exact}); review.append({'id':q['id'],'condition':c,'prediction':pred,'reference':ref,'exact_normalized_match':exact})
  result={'schema':'foil-browsecomp-results/v1','selection_seed':SEED,'summary':[{'condition':c,'correct_exact':v[0],'n':v[1],'accuracy_exact':v[0]/v[1]} for c,v in summary.items()],'items':items,'validity_boundary':'Official BrowseComp questions, exploratory disjoint-subset in-session A/B. Exact-normalized scoring is stricter/different from the official LLM judge; nonmatches require post-commit semantic adjudication.'}
  (OUT/'browsecomp_results.json').write_text(json.dumps(result,indent=2)+'\n'); (OUT/'browsecomp_review_private.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
 print(f'prepared {len(qs)} blinded BrowseComp questions')
if __name__=='__main__': main()
