# Array Visual and Marketing System

## 1. North star

**Museum study room × scientific instrument bench × modern evidence console.**

The historical layer supplies cultural depth and a visual language of observation, classification, geometry, construction, and calibration. The modern layer supplies explicit state, source, uncertainty, and authority boundaries.

Recommended composition ratio, recorded as a design decision rather than an empirical claim:

- `65%` classical / archival / natural-history / instrument language;
- `25%` contemporary technical and evidence interface;
- `10%` annotation, inspection, and boundary marks.

## 2. Palette

| Token | Value | Use |
|---|---|---|
| `paper` | `#F2EBDD` | primary background |
| `paper_deep` | `#E2D5BF` | secondary archival plane |
| `ink` | `#171714` | primary text and structural line |
| `slate` | `#3D4546` | technical text and secondary information |
| `bronze` | `#77634C` | quiet archival rule and calibration line |
| `oxide` | `#8B3F2F` | issue, inspection, boundary, amendment, decisive emphasis |
| `verdigris` | `#476B63` | observation, taxonomy, supported/pass state |
| `white` | `#FCFAF4` | clean evidence surface |

`oxide` must not be used as a decorative brand color with no meaning.

## 3. Typography

| Layer | Preferred | Repository-safe fallback | Use |
|---|---|---|---|
| Editorial | Source Serif 4 | Georgia, Times New Roman, serif | product name, major statements, section headings |
| Technical | IBM Plex Sans | system UI, Segoe UI, sans-serif | body, navigation, explanations |
| Receipt | IBM Plex Mono | ui-monospace, SFMono-Regular, Menlo, monospace | statuses, hashes, paths, commands, labels |

No font files are committed by this brand change. The static site uses system-safe fallbacks and makes no network request for fonts.

## 4. Image grammar

| Instrument | Visual family | Motif |
|---|---|---|
| Diamond | geometry / navigation | armillary rings, axes, obligation routes |
| Sapphire | geometry | compass construction, Euclidean figures, proof points |
| Emerald | botany / taxonomy | specimen stem, leaves, taxon labels, source scale |
| Ruby | morphology / engineering | transformations, mechanism delta, falsifier sequence |
| Garnet | engineering | exploded gear train, source/build/entry/verify alignment |
| Topaz | metrology | calibrated dial, baseline points, decision hand |
| Onyx | inspection | gauge, boundary marks, integrity ledger |
| Citrine | navigation | triangulation and value-of-computation bearing |
| Amethyst | comparative specimen board | independent seats, reveal, off-diagonal critique |
| Opal | optics | paired lenses, ray trace, gap between perspectives |
| Quartz | instrument cabinet | provider/tool/session mechanisms behind a hard authority boundary |
| Obsidian | fracture / stress plate | attack axes, break triples, participation marks |

## 5. Evidence boundary

Historical styling stops at factual claim tables. Evidence surfaces use:

- white or near-white background;
- sans and mono typography;
- explicit sample size or test count where available;
- explicit status vocabulary;
- direct repository source path;
- visible unresolved state;
- no antiqued certificate, seal, wax stamp, patent plate, or faux accession identifier.

## 6. Approved labels

`PLATE` · `SPECIMEN` · `METHOD` · `INSTRUMENT` · `RECEIPT` · `STATUS` · `SOURCE` · `BOUNDARY`

Numbering such as `PLATE 01` is a layout index only. It must not resemble a scientific receipt or catalog identifier unless it is tied to a real project record.

## 7. Prohibited cues

- jeweled superhero glove or derivative franchise imagery;
- Roman eagle, military imperial emblem, laurel authority seal, or fake academic crest;
- fake founding date or “centuries of knowledge” claim;
- fake museum, university, government, or standards-body endorsement;
- fake patent, accession, manuscript, specimen, or receipt ID;
- generated art described as historical or archival;
- historical image used without item-level rights and source evidence;
- benchmark result placed on a visual without its sample, boundary, and source;
- “ancient wisdom meets AI” language;
- antique styling used to make an unsupported result appear established.

## 8. Motion and interaction

- use slow line construction, instrument rotation, or specimen annotation only;
- evidence-state changes are immediate rather than theatrical;
- no dust, magic particles, neon circuitry, glowing brain, or “awakening” effect;
- respect `prefers-reduced-motion` and preserve all information without animation;
- keep all navigation and controls at least 24×24 CSS pixels; the implemented site targets 44-pixel controls.

## 9. Accessibility

- informative illustrations require descriptive alt text;
- decorative marks use empty alt text;
- status is always text plus color, never color alone;
- content order remains useful with CSS, animation, or images disabled;
- source and boundary labels remain readable on small screens;
- canvas art is decorative and marked `aria-hidden`;
- local-only CSS and JavaScript avoid third-party tracking and availability dependencies.

## 10. Implemented assets

| Asset | Type | Source | Boundary |
|---|---|---|---|
| `docs/visuals/apparatus-frontispiece.svg` | original SVG | project-authored for this branch | Brand image only; not evidence; no external artwork embedded or traced |
| `docs/visuals/elenchion-mark.svg` | original SVG | project-authored for this branch | Brand mark only; no legal trademark claim |
| `docs/system-field.js` | original Canvas2D visualization | architecture and skill contracts | Conceptual system visualization, not a live execution trace |
