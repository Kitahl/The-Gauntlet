# Research Website & Research-Software Benchmark

Date: 2026-08-22

Scope: public-facing research institutes, research indexes, open-science catalogs, and mature research-software repositories that provide useful design and information-architecture comparisons for The Gauntlet.

This is a **benchmark set, not an objective world ranking**. The purpose is to identify recurring mechanisms that make serious research easy to inspect, navigate, reproduce, and cite.

## Executive summary

The strongest research sites do not merely look polished. They expose the research objects themselves. Across the benchmark set, the recurring pattern is:

1. a clear research mission or question near the top;
2. a visible index of research outputs — papers, projects, tools, data, reports, or releases;
3. explicit metadata such as date, team/lab, venue, status, or artifact type;
4. direct paths from a claim to the underlying paper, code, data, method, or reproducibility material;
5. search/filter or strong categorical navigation once output volume becomes large;
6. clear separation between research findings, software/tooling, explanatory material, and organizational news;
7. for research software, immediate install/test/docs/contribution/citation/license routes;
8. visible openness boundaries — what is public, what is a pilot, what is peer reviewed, and what remains unresolved.

The main gap found in The Gauntlet after Showcase R14 is therefore **not visual quality**. R14 already established a strong editorial presentation. The remaining gap is research-object discoverability: a first-time reviewer should be able to see the current research question, output classes, evidence chain, reproduction path, and next unresolved study without reconstructing them from several repository files.

---

## Benchmark set

### 1. Arc Institute

Public surfaces reviewed:
- https://arcinstitute.org/
- https://arcinstitute.org/research

**What it looks like**

Arc uses large editorial imagery and substantial white space, but the visual system is subordinate to real scientific outputs. Featured research entries carry a date, journal or preprint venue, lab attribution, title, summary, and a direct path into the work. The home page also states the institutional model and research mission before presenting featured results.

**Mechanism worth transferring**

- Put the research mission/question before the catalog.
- Treat each research output as an object with type, status, source, and context.
- Make the lab/method/output relationship visible rather than forcing the visitor to infer it.

**Do not copy**

- Biological imagery or laboratory branding has no analogue in The Gauntlet and would be decorative.

---

### 2. Google DeepMind Research

Public surfaces reviewed:
- https://deepmind.google/research/
- https://deepmind.google/research/projects/
- https://deepmind.google/research/publications/

**What it looks like**

DeepMind separates three distinct layers: high-level research identity, visual project/breakthrough pages, and a dense chronological publications index. The project layer is image-led and explanatory; the publications layer becomes intentionally utilitarian once scale demands it.

**Mechanism worth transferring**

- Separate showcase/explanation from the canonical index.
- Use visually rich mechanism pages for understanding and dense indexes for retrieval.
- Give recent work and stable archival work different presentation roles.

**Do not copy**

- Large product-style imagery or motion that does not carry evidence would add weight without research value.

---

### 3. Anthropic Research

Public surfaces reviewed:
- https://www.anthropic.com/research
- https://www.anthropic.com/research/team/interpretability

**What it looks like**

Anthropic presents research through named programs/teams and then provides a searchable publication stream containing date, category, title, and article-level detail. Individual research articles prominently expose the paper where available. The result is a useful bridge from understandable narrative to formal research output.

**Mechanism worth transferring**

- Show the research taxonomy explicitly.
- Keep output metadata compact and consistent.
- Link explanatory pages to the strongest underlying artifact rather than making the article itself the terminal source.

**Do not copy**

- A team taxonomy should not be invented for a single-project repository. The transferable unit is evidence/method taxonomy, not organizational hierarchy.

---

### 4. OpenAI Research

Public surfaces reviewed:
- https://openai.com/research/
- https://openai.com/research/index/

**What it looks like**

The landing page states a broad research direction and focus areas; the research index is a chronological ledger that distinguishes publication, conclusion, milestone, release, and other output classes. The strength is not visual complexity but explicit **content typing**.

**Mechanism worth transferring**

- Give every public research object an explicit class.
- Separate a research conclusion or pilot from a release or engineering milestone.
- Preserve date and status in the index.

**Do not copy**

- The Gauntlet should not label internal reports as publications or conclusions when the evidence level does not support that term.

---

### 5. Our World in Data

Public surface reviewed:
- https://ourworldindata.org/

**What it looks like**

Our World in Data makes the *research material itself* the visual identity: charts, data explorers, topic pages, and article summaries. The homepage quantifies the corpus — charts, topics, explorers, articles — and states that the work is open access/openly licensed. Data objects link to sources and explanatory context.

**Mechanism worth transferring**

- Let native research artifacts carry the visual identity.
- Surface corpus/status counts only when they correspond to inspectable objects.
- Pair every visual with source/context rather than using charts as decoration.

**Do not copy**

- The Gauntlet does not have a large empirical dataset catalog, so a data-explorer aesthetic would misrepresent the project.

---

### 6. Ai2 (Allen Institute for AI)

Public surfaces reviewed:
- https://allenai.org/
- https://allenai.org/papers

**What it looks like**

Ai2's paper index is built for retrieval: search, award status, year, tags, author list, venue, and abstract preview. The organizational site can be visually expansive, but the paper catalog prioritizes structured metadata and filtering.

**Mechanism worth transferring**

- Use an explicit research-output index with stable fields.
- Once the catalog grows, add filters/search rather than more cards.
- Make author/venue/status metadata visible where applicable.

**Do not copy**

- The Gauntlet currently has too few canonical outputs to justify a JavaScript filter interface. A static indexed dossier is more honest and lighter.

---

### 7. Broad Institute

Public surfaces reviewed:
- https://www.broadinstitute.org/
- https://www.broadinstitute.org/resources-services-and-tools

**What it looks like**

Broad treats software, datasets, portals, technology platforms, publications, and research areas as separate but connected public objects. The tools page is particularly relevant: resources are named, briefly described, and linked directly. It also preserves an archival distinction when a list is no longer maintained.

**Mechanism worth transferring**

- Separate research outputs from software/tool outputs while connecting them.
- Give public tools a short purpose statement and canonical source.
- Mark archival/stale surfaces rather than silently leaving them looking current.

**Do not copy**

- Enterprise-scale category counts would add noise to a ten-module project.

---

### 8. Janelia Research Campus

Public surfaces reviewed:
- https://www.janelia.org/open-science/overview
- https://www.janelia.org/open-science/tools-and-innovations

**What it looks like**

Janelia's open-science surface explicitly treats software, data, instrumentation, reagents, organisms, protocols, and publications as shareable research outputs. It names third-party repositories and open-source licenses and explains why these materials are released.

**Mechanism worth transferring**

- Make the openness model explicit.
- Show where each artifact lives: repository, benchmark receipt, validation file, citation record.
- Treat software and reproducibility materials as legitimate research outputs, without pretending they are peer-reviewed results.

**Do not copy**

- The Gauntlet should not imply institutional open-science infrastructure it does not possess.

---

### 9. scikit-learn GitHub repository

Public surface reviewed:
- https://github.com/scikit-learn/scikit-learn

**What it looks like**

The repository is utilitarian and mature: project definition, installation, dependencies, source, testing, contribution path, documentation/support channels, license, and explicit scientific citation. A researcher can rapidly move from “what is this?” to “how do I install/test/cite it?”

**Mechanism worth transferring**

- Give evaluators an immediate technical path: source → reproduce → cite → contribute/report.
- Make testing instructions part of the research-software identity, not buried developer trivia.
- Keep citation and license adjacent to real use.

**Do not copy**

- Badges and community metrics should not be added unless they convey a property relevant to evaluation.

---

### 10. PyTorch GitHub repository

Public surfaces reviewed:
- https://github.com/pytorch/pytorch
- https://github.com/pytorch/pytorch/blob/main/CONTRIBUTING.md

**What it looks like**

PyTorch's repository separates user-facing getting-started material, tutorials/examples/API references, releases, contribution processes, governance/community, and extensive developer documentation. The contribution path is unusually explicit about responsibility, testing, and review.

**Mechanism worth transferring**

- Keep user/evaluator and contributor paths distinct.
- State what changes require discussion/review and what constitutes acceptable evidence.
- Expose release/change processes as part of trust.

**Do not copy**

- PyTorch-scale governance or onboarding machinery would be ceremony without benefit at The Gauntlet's current size.

---

## Cross-site mechanism matrix

| Mechanism | Seen strongly in | Transfer to The Gauntlet |
|---|---|---|
| Mission / research question near top | Arc, DeepMind, Anthropic, OpenAI, OWID | **Yes — high priority** |
| Canonical output index | DeepMind, Anthropic, OpenAI, Ai2 | **Yes — high priority** |
| Explicit output classes | OpenAI, Janelia, Broad | **Yes — high priority** |
| Tool/data/software catalog | Broad, Janelia, OWID | **Yes, adapted to modules + receipts** |
| Search/filter | DeepMind, Anthropic, Ai2, Janelia | Later; current corpus too small |
| Native artifacts as visuals | Arc, DeepMind, OWID | Already present in R14; retain |
| Direct paper/source links | Arc, Anthropic, DeepMind | **Yes — use strongest underlying artifact** |
| Install/test/reproduce path | scikit-learn, PyTorch | Already present; make more prominent |
| Citation/license visibility | scikit-learn, Janelia | Already present; make evaluator path clearer |
| Current/archival distinction | Broad, research indexes | **Yes — expose open vs established state** |
| Research program / roadmap visibility | Research institutes | **Yes — adapt from ROADMAP.md** |

## FOIL diagnosis for The Gauntlet after R14

FOIL classification: **research-state discoverability and representation gap**, not a visual-style defect.

### F1 — Research question is too indirect

The canonical question exists in `RESEARCH.md`, but the homepage asks the visitor to infer it from architecture and evidence sections.

**Fix:** expose the current research question directly in a bounded Research Dossier.

### F2 — Research objects are present but not indexed as research outputs

The repository has a research statement, architecture, FOIL research basis, benchmark receipts, validation artifacts, reproducibility protocol, roadmap, and citation metadata. They are spread across different homepage chapters and repository paths.

**Fix:** add a canonical output index that names the artifact type, evidence class/status, purpose, and strongest source.

### F3 — The evidence chain is reconstructable but not immediate

A reviewer can discover question → mechanism → mechanical evidence → exploratory pilot → prospective study, but must traverse several sections.

**Fix:** add one compact evidence-state table showing that chain explicitly.

### F4 — Next research work is underexposed

`ROADMAP.md` is strong, but the homepage does not show that R2–R4 remain the central behavioral-evidence program and that stable release/DOI work is still open.

**Fix:** expose the next evidence program without converting planned studies into accomplishments.

### F5 — Technical evaluator path competes with narrative navigation

The site links a 5-minute evaluator path, reproducibility, citation, and repository, but not as one explicit evaluator route.

**Fix:** group Source / Reproduce / Cite / Research statement / Roadmap in the Research Dossier.

---

## Mastermind transfer decision

### Gate A — Causal adequacy

PASS. The proposed changes directly address discoverability and evidence-state reconstruction rather than aesthetics.

### Gate B — Identifier independence

PASS. The mechanisms do not depend on copying any benchmark site's names, branding, CSS, or imagery.

### Gate C — Representation transformation

PASS. Existing Gauntlet artifacts are reorganized into a research dossier/index without changing their scientific status.

### Gate D — Negative control

PASS. No new hero imagery, gradients, glass UI, research-themed stock photography, invented publications, or fake institutional metrics.

### Gate E — Cross-domain transfer

PASS. The same mechanism appears across AI labs, biomedical institutes, data journalism/research, and research-software repositories.

### Gate F — Existing-mechanism compression

PASS. HTML/CSS/index structures are sufficient. No client-side framework or search library is justified at current scale.

### Gate G — Ablation

PASS. If the new Research Dossier is removed, all underlying source artifacts still exist and the site remains usable; the dossier improves retrieval/compression rather than creating evidence.

### Gate H — Regression

Pending exact-head CI for the website update. Existing accessibility, browser, provenance, payload, overclaim, and visual-render gates remain authoritative.

---

## R15 website requirements admitted from the benchmark

1. Add a **Research Dossier** immediately after the hero.
2. State the exact current research question and explicitly keep the full behavioral answer open.
3. Add a compact **Research Output Index** using real repository artifacts; do not call them papers/publications unless they are.
4. Add a **Research State / Evidence Chain** showing implemented, recorded, exploratory, and prospective layers.
5. Expose the **next evidence program** from `ROADMAP.md` without implying completion.
6. Group evaluator actions: source, reproduce, cite, research statement, roadmap, benchmark report.
7. Keep R14's editorial visual system and mechanism-native SVG plates; this benchmark does not justify another style rewrite.
8. No search/filter UI until the output corpus is large enough to make it load-bearing.
9. No DOI badge until a DOI exists.
10. No claims of peer review, independent reproduction, behavioral efficacy, or formal external certification that are not already established.

## Source list

Accessed 2026-08-22.

- Arc Institute — https://arcinstitute.org/ and https://arcinstitute.org/research
- Google DeepMind — https://deepmind.google/research/ ; /projects/ ; /publications/
- Anthropic Research — https://www.anthropic.com/research and /research/team/interpretability
- OpenAI Research — https://openai.com/research/ and https://openai.com/research/index/
- Our World in Data — https://ourworldindata.org/
- Ai2 — https://allenai.org/ and https://allenai.org/papers
- Broad Institute — https://www.broadinstitute.org/ and /resources-services-and-tools
- Janelia Research Campus — https://www.janelia.org/open-science/overview and /open-science/tools-and-innovations
- scikit-learn — https://github.com/scikit-learn/scikit-learn
- PyTorch — https://github.com/pytorch/pytorch
