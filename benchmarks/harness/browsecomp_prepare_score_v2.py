import browsecomp_prepare_score as b

# During the pre-commit search pass, external benchmark-agent traces containing
# these BASE questions surfaced in search results. No gold answer was used, but
# we exclude them conservatively. To preserve 1:1 condition balance without
# inspecting gold, drop the two highest-index FOIL assignments deterministically.
DROP={"bc-02-842f7932","bc-12-d8f30932","bc-17-c9b9a839","bc-19-a304e964"}
_original_prepare=b.prepare

def prepare():
    qs,gold=_original_prepare()
    qs=[q for q in qs if q['id'] not in DROP]
    gold={k:v for k,v in gold.items() if k not in DROP}
    out=b.OUT/'browsecomp_questions.json'
    import json
    out.write_text(json.dumps({'schema':'foil-browsecomp-questions/v2','selection_seed':b.SEED,'source':b.URL,'excluded_ids':sorted(DROP),'conditions':{'BASE':'straightforward browsing with the same web access','FOIL_MM':'FOIL evidence routing + counterevidence + exact-answer audit with the same web access'},'questions':qs},indent=2,ensure_ascii=False)+'\n')
    return qs,gold
b.prepare=prepare

if __name__=='__main__': b.main()
