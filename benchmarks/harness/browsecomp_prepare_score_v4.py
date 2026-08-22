import browsecomp_prepare_score as b

# Exclusions are frozen without consulting hidden gold:
# - three BASE items where public benchmark/answer traces surfaced during browsing;
# - one FOIL item that is an official published BrowseComp example whose gold surfaced;
# - four deterministic high-index opposite-condition balancing drops.
DROP={
    "bc-02-842f7932","bc-12-d8f30932","bc-18-d5cf07ab",
    "bc-05-1f3b974a",
    "bc-15-c746c21f","bc-17-c9b9a839","bc-19-a304e964",
    "bc-16-d067f146",
}
_original=b.prepare

def prepare():
    qs,gold=_original(); qs=[q for q in qs if q['id'] not in DROP]; gold={k:v for k,v in gold.items() if k not in DROP}
    import json
    (b.OUT/'browsecomp_questions.json').write_text(json.dumps({'schema':'foil-browsecomp-questions/v4','selection_seed':b.SEED,'source':b.URL,'excluded_ids':sorted(DROP),'conditions':{'BASE':'straightforward browsing with the same web access','FOIL_MM':'FOIL evidence routing + counterevidence + exact-answer audit with the same web access'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
    return qs,gold
b.prepare=prepare
if __name__=='__main__': b.main()
