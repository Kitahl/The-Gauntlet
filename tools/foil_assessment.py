"""Adaptive FOIL onboarding questionnaire.

The assessment creates a provisional profile, not an IQ/personality diagnosis.
It mixes context/self-report with generated objective probes, confidence, and
open-ended production tasks. Setup text selects relevant optional domains.
"""
from __future__ import annotations

import argparse
import json
import random
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from foil_profile import ensure_domain, load as load_profile, observe, save as save_profile

SCHEMA = "egrt.foil-assessment.v1"
CORE = ["quantitative_reasoning", "formal_reasoning", "probability_statistics", "software_engineering", "research_evidence", "scientific_method", "security_privacy", "planning_decision_making"]
DOMAIN_HINTS = {
    "data_ml": ["machine learning", "ml", "model training", "data science", "neural", "embedding"],
    "causal_inference": ["causal", "causality", "confound", "intervention", "counterfactual"],
    "design_ux": ["design", "ux", "ui", "accessibility", "interface", "product design"],
    "creativity_ideation": ["creative", "creativity", "ideation", "brainstorm", "fiction", "art"],
    "communication_writing": ["writing", "communication", "paper", "essay", "documentation", "presentation"],
    "teaching_explanation": ["teach", "tutor", "explain", "learning", "education"],
    "systems_reliability": ["distributed", "reliability", "concurrency", "database", "network", "systems"],
}
STYLE = [
    ("mechanism_first", "I prefer understanding why a method works before memorizing steps."),
    ("examples_first", "Concrete examples help me more than abstract definitions at the beginning."),
    ("independent_first", "When stakes allow, I prefer making an independent attempt before seeing a worked solution."),
    ("verification_depth", "For important claims, I prefer explicit evidence and independent checks even when slower."),
    ("visual_spatial", "Diagrams or spatial representations often help me think."),
    ("option_breadth", "I prefer seeing several plausible approaches before committing to one."),
]
CONTEXT = [
    ("goal", "What do you most want FOIL to help you become better at?"),
    ("work_domains", "What fields or kinds of problems do you work on most?"),
    ("experience", "Briefly describe your practical experience in those areas."),
    ("tools", "What tools/languages/workflows do you already use comfortably?"),
    ("constraints", "What constraints matter most: time, cost, compute, risk, accessibility, or something else?"),
    ("help_mode", "When stuck, do you prefer a hint, checklist, worked example, direct solution, or choice?"),
    ("learning_goal", "Do you prioritize fastest completion, independent learning, or a balance?"),
]
OPEN = [
    {"id": "design", "domain": "design_ux", "prompt": "Design a compact phone+desktop research status panel that shows current state, one next action, evidence/uncertainty, and details. Include keyboard and low-vision accessibility. Explain two tradeoffs.", "rubric": ["constraint coverage", "information hierarchy", "accessibility", "tradeoffs", "validation plan"]},
    {"id": "creativity", "domain": "creativity_ideation", "prompt": "List 10 common single nouns that are as semantically different from one another as possible. Avoid proper nouns, jargon, and near-synonyms.", "rubric": ["validity", "uniqueness", "semantic breadth"]},
    {"id": "explanation", "domain": "teaching_explanation", "prompt": "Explain to a bright beginner why checking an answer with the same method that produced it can miss errors. Use one concrete example and one practical rule.", "rubric": ["correctness", "clarity", "example quality", "actionable rule"]},
]


def infer_domains(text: str) -> list[str]:
    low = text.lower()
    return [domain for domain, words in DOMAIN_HINTS.items() if any(w in low for w in words)]


def options(rng: random.Random, correct: str, wrong: list[str]) -> list[str]:
    vals = [correct]
    for x in wrong:
        if x != correct and x not in vals:
            vals.append(x)
    while len(vals) < 4:
        filler = f"none-{len(vals)}"
        if filler not in vals:
            vals.append(filler)
    vals = vals[:4]
    rng.shuffle(vals)
    return vals


def q_quant(rng: random.Random, i: int) -> dict:
    if i == 0:
        rate, mins, target = rng.randint(3, 9), rng.randint(4, 10), rng.randint(6, 14)
        done = rate * mins
        ans = str(rate * target)
        return {"kind": "rate", "prompt": f"A process completes {done} units in {mins} minutes at a constant rate. How many in {target} minutes?", "options": options(rng, ans, [str(rate*(target+1)), str(done+target), str(max(1, rate*(target-1)))]), "params": [done, mins, target]}
    a, x, b = rng.randint(2, 8), rng.randint(-8, 12), rng.randint(-10, 10)
    c = a*x+b
    ans = str(x)
    sign = "+" if b >= 0 else "-"
    return {"kind": "linear", "prompt": f"Solve: {a}x {sign} {abs(b)} = {c}", "options": options(rng, ans, [str(x+1), str(x-1), str(c-b)]), "params": [a,b,c]}


def q_formal(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"modus_tollens","prompt":"If P implies Q and Q is false, what follows?","options":["P is false","P is true","Nothing about P follows","Q is true"],"params":[]}
    return {"kind":"counterexample","prompt":"A claim says every even integer greater than 2 is divisible by 4. What is the strongest response?","options":["Give 6 as a counterexample","Give 8 as an example","Ask for more samples","The claim is true by definition"],"params":[]}


def q_prob(rng: random.Random, i: int) -> dict:
    r,b = rng.randint(2,7),rng.randint(2,7)
    total=r+b
    if i == 0:
        f=Fraction(r,total)
        ans=f"{f.numerator}/{f.denominator}"
        return {"kind":"simple_prob","prompt":f"A bag has {r} red and {b} blue tokens. P(red)?","options":options(rng,ans,[f"{b}/{total}",f"{r}/{b}",f"1/{total}"]),"params":[r,b]}
    f=Fraction(b,total-1)
    ans=f"{f.numerator}/{f.denominator}"
    return {"kind":"conditional_prob","prompt":f"A bag has {r} red and {b} blue tokens. A red is removed. P(next is blue)?","options":options(rng,ans,[f"{b}/{total}",f"{r-1}/{total-1}",f"1/{total-1}"]),"params":[r,b]}


def q_software(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"complexity","prompt":"A program loops over n records and, for each, loops over all n records again. Dominant complexity?","options":["O(1)","O(n)","O(n log n)","O(n²)"],"params":[]}
    return {"kind":"false_green","prompt":"Unit tests pass but production fails only under load. Strongest next check?","options":["Rerun the same unit tests","Measure production-like load/resource behavior","Rewrite docs","Assume users are wrong"],"params":[]}


def q_evidence(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"fresh_source","prompt":"You need the current stable version of a package. Strongest evidence?","options":["Model memory","An old tutorial","Current official release/documentation","Undated forum comment"],"params":[]}
    return {"kind":"scope","prompt":"A paper reports +20% on one benchmark, but a claim says +20% in all domains. What is warranted?","options":["The all-domain claim is proved","Only the benchmark-specific result is supported","The method fails elsewhere","Citation count decides"],"params":[]}


def q_science(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"control","prompt":"A treatment group improves after an intervention, but there is no control group. What is the central limitation?","options":["Improvement alone does not identify the intervention as the cause","The sample must be exactly 100","The outcome must be binary","A control is unnecessary"],"params":[]}
    return {"kind":"preregister","prompt":"You will try many analyses and report the best-looking one. What most directly reduces selective-analysis bias?","options":["Pre-register the primary analysis/decision rule","Increase font size","Run fewer software tests","Use more citations"],"params":[]}


def q_security(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"secret","prompt":"Where should an API key for a public repository normally live?","options":["Committed in source","Environment/secret store outside tracked files","README example with the real key","Issue comment"],"params":[]}
    return {"kind":"least_privilege","prompt":"A tool only needs read access to one directory. Best default permission?","options":["Administrator access","Read access only to the required scope","Full disk access","Disable authentication"],"params":[]}


def q_planning(rng: random.Random, i: int) -> dict:
    if i == 0:
        return {"kind":"critical_path","prompt":"A project has many polish tasks but one unmeasured condition determines whether the approach works. What should be prioritized?","options":["Measure the load-bearing condition","Polish everything equally","Add branding","Increase meeting count"],"params":[]}
    return {"kind":"reversible","prompt":"Two actions have similar expected value; one is cheap/reversible and one is costly/irreversible. With high uncertainty, what is generally preferable first?","options":["The cheap reversible probe","The costly irreversible action","Choose randomly","Avoid collecting evidence"],"params":[]}


GEN: dict[str, Callable[[random.Random,int],dict]] = {
    "quantitative_reasoning": q_quant,
    "formal_reasoning": q_formal,
    "probability_statistics": q_prob,
    "software_engineering": q_software,
    "research_evidence": q_evidence,
    "scientific_method": q_science,
    "security_privacy": q_security,
    "planning_decision_making": q_planning,
}


def answer(item: dict) -> str:
    k=item["kind"]
    p=item.get("params",[])
    if k=="rate": return str((p[0]//p[1])*p[2])
    if k=="linear": return str((p[2]-p[1])//p[0])
    if k=="modus_tollens": return "P is false"
    if k=="counterexample": return "Give 6 as a counterexample"
    if k=="simple_prob":
        f=Fraction(p[0],p[0]+p[1]); return f"{f.numerator}/{f.denominator}"
    if k=="conditional_prob":
        f=Fraction(p[1],p[0]+p[1]-1); return f"{f.numerator}/{f.denominator}"
    keys={
        "complexity":"O(n²)","false_green":"Measure production-like load/resource behavior",
        "fresh_source":"Current official release/documentation","scope":"Only the benchmark-specific result is supported",
        "control":"Improvement alone does not identify the intervention as the cause","preregister":"Pre-register the primary analysis/decision rule",
        "secret":"Environment/secret store outside tracked files","least_privilege":"Read access only to the required scope",
        "critical_path":"Measure the load-bearing condition","reversible":"The cheap reversible probe",
    }
    return keys[k]


def build(seed: int | None=None, setup_text: str="") -> dict[str,Any]:
    seed = seed if seed is not None else random.SystemRandom().randrange(1,2**31)
    rng=random.Random(seed)
    selected=list(CORE)
    inferred=infer_domains(setup_text)
    for d in inferred:
        if d not in selected: selected.append(d)
    objective=[]
    for d in CORE:
        for i in range(2):
            item=GEN[d](rng,i); item.update({"id":f"{d}-{i+1}","domain":d,"confidence_prompt":"Confidence 0-100?"}); objective.append(item)
    rng.shuffle(objective)
    return {
        "schema":SCHEMA,"seed":seed,"setup_text":setup_text,"selected_domains":selected,
        "limits":["Experimental onboarding; not an IQ, clinical, diagnostic, or employment test.","Initial classifications are provisional hypotheses.","Self-report does not prove ability.","Open design/creativity/communication tasks need rubric review."],
        "context_questions":[{"id":k,"prompt":v} for k,v in CONTEXT],
        "style_scale":{"min":1,"max":5},"style_items":[{"id":k,"prompt":v} for k,v in STYLE],
        "self_estimate_domains":selected,
        "objective_items":objective,
        "open_probes":OPEN,
        "response_schema":{
            "context":{k:None for k,_ in CONTEXT},"style":{k:None for k,_ in STYLE},"self_estimates":{d:None for d in selected},
            "objective":{x["id"]:{"choice":None,"confidence":None,"assistance":"none"} for x in objective},
            "open":{x["id"]:{"response":None,"assistance":"none"} for x in OPEN},
        },
    }


def normalize_choice(item:dict,value:Any)->str|None:
    if value is None:return None
    if isinstance(value,int) and 0<=value<len(item["options"]):return item["options"][value]
    s=str(value).strip()
    if len(s)==1 and s.upper() in "ABCD":
        i=ord(s.upper())-65
        if i<len(item["options"]):return item["options"][i]
    return s or None


def score(session:dict,responses:dict)->dict[str,Any]:
    by:dict[str,list[dict]]={d:[] for d in CORE}
    for item in session["objective_items"]:
        raw=responses.get("objective",{}).get(item["id"],{})
        choice=normalize_choice(item,raw.get("choice"))
        if choice is None:continue
        good=choice==answer(item)
        by[item["domain"]].append({"correct":good,"confidence":raw.get("confidence"),"assistance":raw.get("assistance","none")})
    result={}
    for d,rows in by.items():
        independent=[r for r in rows if r["assistance"] in (None,"none","independent")]
        c=sum(r["correct"] for r in independent); n=len(independent)
        if n<2: cls="INSUFFICIENT_EVIDENCE"
        elif c==n: cls="PROMISING_STRENGTH"
        elif c==0: cls="POSSIBLE_GAP"
        else: cls="UNCERTAIN"
        result[d]={"answered":len(rows),"independent_n":n,"independent_correct":c,"classification":cls,"note":"Requires fresh follow-up before a stable label."}
    return {"schema":SCHEMA,"seed":session["seed"],"domain_evidence":result,"style":responses.get("style",{}),"self_estimates":responses.get("self_estimates",{}),"context":responses.get("context",{}),"open_status":{x["id"]:"NEEDS_RUBRIC_REVIEW" for x in session["open_probes"]}}


def apply_to_profile(name:str,report:dict)->None:
    profile=load_profile(name)
    for d in report.get("self_estimates",{}): ensure_domain(profile,d,declared=True)
    for d,row in report.get("domain_evidence",{}).items():
        n=int(row.get("independent_n",0)); c=int(row.get("independent_correct",0))
        if n>=2:
            for i in range(n): observe(profile,d,"correct" if i<c else "incorrect","none",source="assessment",representation=f"screen-{i+1}")
    for key,value in report.get("style",{}).items():
        if value is not None: profile.setdefault("preferences",{})[key]=value
    ctx=report.get("context",{})
    goal=ctx.get("goal")
    if goal: profile["goals"]=list(dict.fromkeys([*profile.get("goals",[]),str(goal)]))
    for domain in infer_domains(" ".join(str(v) for v in ctx.values() if v)):
        ensure_domain(profile,domain,declared=True)
    save_profile(profile)


def write(path:str,obj:Any)->None:
    Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("start"); s.add_argument("--seed",type=int); s.add_argument("--setup-text",default=""); s.add_argument("--out",default="foil_assessment.json"); s.add_argument("--responses",default="foil_responses.json")
    sc=sub.add_parser("score"); sc.add_argument("session"); sc.add_argument("responses"); sc.add_argument("--out",default="foil_assessment_report.json"); sc.add_argument("--profile")
    args=p.parse_args(argv)
    if args.cmd=="start":
        session=build(args.seed,args.setup_text); write(args.out,session); write(args.responses,session["response_schema"]); print(f"created {args.out} and {args.responses}; seed={session['seed']}"); return 0
    session=json.loads(Path(args.session).read_text(encoding="utf-8")); responses=json.loads(Path(args.responses).read_text(encoding="utf-8")); report=score(session,responses); write(args.out,report)
    if args.profile: apply_to_profile(args.profile,report)
    print(f"created {args.out}" + (f" and updated profile {args.profile}" if args.profile else "")); return 0


if __name__=="__main__": raise SystemExit(main())
