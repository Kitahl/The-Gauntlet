import browsecomp_prepare_score as b

# Conservative post-selection exclusions, all frozen without consulting the
# harness's hidden gold. Reasons are recorded publicly in docs/BENCHMARKS.md.
DROP={
    # BASE: public benchmark/agent traces surfaced during browsing.
    "bc-02-842f7932","bc-12-d8f30932","bc-18-d5cf07ab",
    # FOIL: official example / indexed benchmark answer surfaced during browsing.
    "bc-05-1f3b974a","bc-07-8eb2d427",
    # Deterministic opposite-condition balancing drops (highest indices).
    "bc-14-6a55785e","bc-15-c746c21f","bc-16-d067f146","bc-17-c9b9a839","bc-19-a304e964",
}
_original=b.prepare

def prepare():
    qs,gold=_original(); qs=[q for q in qs if q['id'] not in DROP]; gold={k:v for k,v in gold.items() if k not in DROP}
    import json
    (b.OUT/'browsecomp_questions.json').write_text(json.dumps({'schema':'foil-browsecomp-questions/v5','selection_seed':b.SEED,'source':b.URL,'excluded_ids':sorted(DROP),'conditions':{'BASE':'straightforward browsing with the same web access','FOIL_MM':'FOIL evidence routing + counterevidence + exact-answer audit with the same web access'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
    return qs,gold
b.prepare=prepare
if __name__=='__main__': b.main()
