# Showcase Revision 14 — Mastermind design audit

## Reference set

Karimoku Research; Neko Health; Bisou Gallery; Living House; The Beautiful Truth; Slate + Ash; Whanganui UNESCO City of Design; Mennour; Angela Ricciardi; Standard Projects.

## Loop 1 — Remove the SaaS shell

**Observed defect:** The R13 public site is rigorous, but its dark background, rounded cards, repeated bordered panels, and metric tiles read as premium developer SaaS rather than a designed research publication.

**Mechanism:** Replace container density with editorial hierarchy: oversized title scale, long whitespace intervals, rule-based sections, typographic indexes, asymmetrical columns, and a mostly light paper-like canvas.

**Negative control:** Do not add more decorative cards, glow, blur, generic gradients, or remote visual assets.

## Loop 2 — Make the research artifacts the visual identity

**Observed defect:** R13 added correct mechanism diagrams, but they still sit inside a conventional UI frame and compete with supporting cards.

**Mechanism:** Treat the system map, FOIL loop, benchmark receipt, commands, and evidence ledger as publication plates. Redraw the three SVGs in a restrained editorial language and integrate them at large scale with numbered captions and source references.

**Negative control:** No invented product screenshots, fake dashboards, stock photography, or AI-generated illustration.

## Loop 3 — Convert navigation into an archive

**Observed defect:** The module and trust surfaces are complete but visually read as feature catalogs.

**Mechanism:** Present modules, evidence states, and trust/reproducibility artifacts as indexes/colophons with stable numbering and direct source links. Preserve all factual and version boundaries.

**Release gate:** R14 must preserve the existing mechanical, accessibility, payload, provenance, browser, and overclaim checks. The exact final PR head must pass Research software validation and CodeQL before merge.

## Admission assessment

- **A causal adequacy:** PASS for the stated presentation defect; mechanisms directly target card density, hierarchy, pacing, and artifact visibility.
- **B identifier independence:** PASS; changes do not depend on copying site-specific names, imagery, or CSS.
- **C representation transformation:** PASS; the same repository evidence is represented as editorial publication/index structures rather than SaaS components.
- **D negative control:** PASS by explicit exclusion of decorative AI/startup tropes.
- **E cross-domain transfer:** PASS; recurring mechanisms appear across galleries, architecture, editorial, cultural, health, and studio reference sites.
- **F existing-mechanism compression:** PASS; CSS/SVG/HTML only, no new framework or JavaScript.
- **G ablation:** PASS at the representation level. The redesigned page remains intelligible with the diagrams absent because captions, evidence ledgers, direct source links, and document indexes remain; the diagrams add explanatory compression rather than carrying unsupported claims.
- **H regression:** PASS on validated design head `a9f0429656d0db34ac77339032e93b5e6202171c`: 55/55 showcase checks, 37/37 runtime/layout tests, Research Orchestrator + Process Assurance validation, and CodeQL. The final receipt-containing PR head must repeat the normal Research software validation and CodeQL gates before promotion.

## First-failure correction

The first R14 CI candidate passed 54/55 showcase checks and failed only mobile horizontal overflow. The defect was corrected by reducing the oversized single-word mobile hero composition. The validator was not weakened and overflow was not hidden with clipping. The corrected design head passed 55/55 checks with no horizontal overflow on either desktop or mobile.
