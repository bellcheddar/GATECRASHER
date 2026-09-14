# GATECRASHER: Build Spec for Claude Code

**Version** 1.0
**Author** Marc C. Deller
**Target repo** `/Users/dellboy/Documents/Vibe_Coding/GATECRASHER`
**GitHub** `github.com/bellcheddar/GATECRASHER`
**Deployment** `gatecrasher.mdeller.com` (static bundle behind nginx on the existing droplet)

---

## 0. What this is

GATECRASHER is an interactive dashboard that opens four medicinal chemistry discovery campaigns and lets a reader walk through how each drug was designed: the pocket, the structure-activity relationships, the specific chemical edits, and the protein structural basis for selectivity.

One shell, four papers. The panels, the layout and the interactions never change between papers: only the data bundle swaps. The spine of the app is **selectivity**, because all four campaigns are the same shape: a selectivity problem solved at a pocket, then carried over the line by property work.

Two audiences, served by one build:

- **Primary**: structural biologists and medicinal chemists who want the contacts, the KLIFS numbering, the R-group tables and the edit-by-edit rationale.
- **Secondary**: general visitors to marcdeller.com and recruiters, who need to understand what they are looking at inside thirty seconds without a chemistry degree.

The Story panel (Section 7.5) is what serves the second audience without diluting the first.

---

## 1. Ground rules

These are hard constraints. Violating any of them is a build failure.

1. **No company name anywhere.** Do not name the company, its research institute, its address, or any author affiliation, in code, copy, metadata, alt text, commit messages or the README. Published compound codes (INCB159020, INCB054707) and generic drug names (povorcitinib) are compound identifiers and are fine. Author names and DOIs in citations are fine.
2. **No compute on the droplet.** Everything is precomputed on the Mac (64 GB M1). The droplet serves static files only: no Python process, no queue, no WASM job that phones home. If a feature cannot be precomputed, it does not ship.
3. **No republication of copyrighted assets.** Do not embed the publishers' figures, graphical abstracts or full text. Every molecule depiction is rendered from SMILES with RDKit; every structure view is rendered from coordinates fetched from the RCSB PDB; every piece of prose is written fresh. Abstracts may be quoted verbatim in a clearly marked quote block with citation and DOI link, since that is standard scholarly quotation, but the surrounding narrative must be original. The "graphical abstract" panel is an **original interactive re-creation**, not a copy of the published image.
4. **Everything is a control.** No panel is read-only. Clicking a residue, a dot, a substituent, a table row, a motif chip or a story beat updates the rest of the app. Section 8 defines the cross-link matrix exhaustively.
5. **Dark by default, light available.** The Blueprint theme is dark-first with a persistent toggle (Section 6). The light theme is a first-class citizen, not an afterthought.
6. **British English. No em dashes.** Use colons or parentheses. Forbidden words in all copy: groundbreaking, revolutionary, paradigm-shifting, game-changing, cutting-edge, delve, leverage (as a verb).
7. **Provenance or it does not render.** Every number carries a source: a table number, a figure number, or a PDB entry. `gc validate` fails the build if any measurement lacks one.
8. **No build step.** Vanilla ES modules, pinned CDN libraries, no bundler, no framework, no node_modules in the deployed artefact. This matches the rest of the portfolio and keeps the droplet deployment a single rsync.

---

## 2. Stack

**Web app (static)**

| Concern | Choice | Notes |
|---|---|---|
| Structure viewer | Mol\* (molstar) | Pinned UMD build from cdnjs. Two synchronised instances for the anti-target comparison. |
| Molecule depiction | RDKit.js (WASM) | Core-aligned 2D depictions rendered client-side from SMILES, so depictions stay consistent with the R-group decomposition. |
| Plots | Plotly.js (`plotly.js-dist-min`) | All plots. Custom Blueprint layout template, shared across every figure. |
| Layout | CSS grid + custom properties | No CSS framework. |
| State | One `AppState` module with a pub/sub bus | Section 8. Serialised to the URL hash. |
| Search | Precomputed embedding index + in-browser cosine search | No runtime model. Section 5.7. |

**Precompute pipeline (Mac only)**

| Concern | Choice |
|---|---|
| Environment | `uv` project, Python 3.12, `pyproject.toml` |
| Cheminformatics | RDKit |
| Structures | `gemmi` (mmCIF), `biotite`, `pdb-tools` |
| Interactions | PLIP, driven by the existing `cif_to_plip.py` |
| Kinase annotation | KLIFS REST API |
| Secondary structure | DSSP (`mkdssp`) |
| Dynamics | OpenMM |
| Figures | PyMOL (headless) |
| Retrieval index | `mlx-lm` embeddings, local model, inference only. **No training, no fine-tuning.** |

---

## 3. Harvest pass (do this first)

Before writing new code, read these repos and lift what already works. Report in `HARVEST.md` what was taken from where, so the provenance of the code is as traceable as the provenance of the data.

| Source repo | Take |
|---|---|
| `AlphaFraud` | The Plotly figure conventions and quadrant-scatter idiom, the static-asset layout and the nginx/certbot deployment pattern, the stats-page structure. |
| `GOBSMACKED` | The PLIP and PandaMap handling, the Mol\* setup and camera control, the KLIFS and annotation fetch layer, the About-tab pipeline schematic and software/reference table pattern. |
| `FlexAppeal` | The OpenMM system setup, minimisation and short-MD runner, and the trajectory post-processing. |
| `BoltzMaker` | The campaign-scale CLI ergonomics, the input-validation approach, the pixi/uv environment pattern. |
| `ALPHABETTI` | The sequence-track rendering and residue-indexed track alignment. This is the basis of the KLIFS ruler. |
| `CODSWALLOP` | The PDB mining queries and family-aware table handling. |
| `chatPDB` | The retrieval layer: chunking, embedding, cosine search, and the "cite or decline" answer contract. |
| `cif_to_plip.py` | Use as-is. **Carry the `pdb_tidy` CONECT serial-gap workaround forward**: it corrupts OpenBabel bond perception and silently produces wrong interaction assignments. |
| `marcs-vibe-coding` skill | Brand tokens, README house standard, mobile-responsive conventions. |

Do not re-implement anything on this list from scratch. Where a lifted module needs changing, change it in GATECRASHER and note the divergence in `HARVEST.md`.

---

## 4. Repository layout

```
GATECRASHER/
├── README.md                  # house standard, written in Stage 4
├── HARVEST.md                 # what came from which repo
├── BUILD_SPEC.md              # this file
├── pipeline/                  # Mac-only precompute, never deployed
│   ├── pyproject.toml
│   ├── gc/
│   │   ├── cli.py             # `gc <command>`
│   │   ├── extract.py         # PDF and SI tables -> raw TSV for QC
│   │   ├── chem.py            # RDKit: descriptors, MCS, R-groups, cliffs, depictions
│   │   ├── struct.py          # mmCIF fetch, PLIP, KLIFS, DSSP, motif table
│   │   ├── dynamics.py        # OpenMM minimise + short MD -> RMSF + frames
│   │   ├── figures.py         # PyMOL stills, .pml and .pse download bundles
│   │   ├── retrieval.py       # chunk, embed, index (inference only)
│   │   ├── validate.py        # schema + provenance gate
│   │   └── bundle.py          # write web/data/, gzip, coverage report
│   ├── raw/<slug>/            # hand-QC'd TSVs, the human-curated source of truth
│   └── schemas/*.json         # JSON Schema for every published artefact
└── web/                       # this directory is what gets deployed
    ├── index.html
    ├── css/{tokens,blueprint,sheets,panels,responsive}.css
    ├── js/
    │   ├── state.js           # AppState + event bus + URL hash
    │   ├── data.js            # bundle loader, indexes, pivots
    │   ├── panels/{structure,editlog,sar,properties,story,rail}.js
    │   ├── viewers/{molstar,rdkit,plotly}.js
    │   ├── draw.js            # Blueprint drawing primitives (measure lines, callouts)
    │   └── search.js          # in-browser retrieval
    └── data/
        ├── index.json         # list of papers + bundle versions
        └── papers/<slug>/…    # Section 5
```

`slug` is one of: `cdk2`, `fgfr`, `kras`, `jak1`.

---

## 5. Data contract

This is the most important section. Get it right in Stage 1 and everything else is assembly.

### 5.1 Design principle

Assay columns differ wildly between the four papers (CDK2 reports six isoform IC50 columns plus whole blood and SGF solubility; KRAS reports SPR, nucleotide exchange, pERK and human whole blood pERK; JAK1 reports enzyme, INA-6, whole-blood IL-6 and TPO). **Do not** try to force one wide table. Use:

- `compounds.csv` (one row per compound: identity and computed properties)
- `measurements.csv` (**long format**: one row per compound per assay)
- `assays.json` (the dictionary that gives each assay its label, units, direction and category)

This is what makes the shared shell possible.

### 5.2 `paper.json`

```jsonc
{
  "slug": "cdk2",
  "title": "…",                       // as published
  "authors_short": "Hummel et al.",
  "journal": "J. Med. Chem.",
  "year": 2024, "volume": 67, "pages": "3112-3126",
  "doi": "10.1021/acs.jmedchem.3c02287",
  "target": { "name": "CDK2", "partner": "cyclin E1", "family": "CMGC kinase", "uniprot": "P24941" },
  "anti_targets": [ { "name": "CDK1", "partner": "cyclin B1" }, … ],
  "one_line": "…",                    // plain register, <=140 chars
  "abstract": "…",                    // verbatim, rendered in a marked quote block
  "graphical_abstract": {             // ORIGINAL re-creation, see 7.6
    "panels": [ { "kind": "compound", "compound_id": "1", "caption": "HTS hit", "values": [ … ] }, … ]
  },
  "problem": { "disease": "…", "selectivity": "…", "property": "…" },
  "bundle_version": "1.0.0"
}
```

### 5.3 `compounds.csv`

`compound_id, label, series, role, smiles, inchikey, r_groups, mw, clogp, tpsa, hbd, hba, rotb, hac, fsp3, depiction, mol3d, source_table, notes`

- `role` ∈ `reference | hit | intermediate | milestone | lead | tool`
- `r_groups` is a JSON object keyed by the R-position label used in that paper's table (`R1`, `R2`, `X`, `Y`)
- `depiction` is the relative path to the core-aligned SVG; `mol3d` to a 3D SDF where one exists
- `compound_id` matches the published numbering exactly. Do not renumber.

### 5.4 `measurements.csv`

`compound_id, assay_id, value, qualifier, units, n, source_table, source_note`

- `qualifier` ∈ `= | < | > | ~ | NA`. Values like `<0.001` and `>10000` are common and must not be coerced to numbers.
- Every row must carry `source_table` (for example `T2` or `Fig4`). `gc validate` fails otherwise.

### 5.5 `assays.json`

```jsonc
{
  "cdk2_e1_ic50": {
    "label": "CDK2 / cyclin E1 IC50", "short": "CDK2", "units": "nM",
    "category": "potency", "direction": "lower_better", "log": true,
    "conditions": "1 mM ATP", "is_primary": true
  },
  "wb_pRb": { "label": "Whole blood pRb S780", "short": "WB", "units": "nM", "category": "cell", … },
  "sgf_solubility": { "…": "…", "direction": "higher_better" },
  "h_cl": { "label": "Human microsomal intrinsic clearance", "units": "L/h/kg", "category": "adme", "direction": "lower_better" }
}
```

`is_primary` marks the potency axis for that paper. `anti_target_of` links an assay to the target assay it is a counter-screen for: this is what drives the selectivity plot automatically.

### 5.6 Structures, motifs and interactions

`structures.json` (one entry per deposited or referenced structure):

```jsonc
{
  "pdb_id": "8UV0", "role": "primary",
  "contains": { "protein": "CDK2", "ligand_compound_id": "17", "ligand_code": "…" },
  "resolution_a": 1.55,
  "chain": "A",
  "klifs": true,
  "caption_specialist": "…", "caption_plain": "…",
  "source": "deposited"            // deposited | referenced | modelled
}
```

`residues.csv` per structure: `pdb_id, chain, resnum, resname, sse, klifs_index, motif, role_note`

- `sse` from DSSP, collapsed to `H | E | L`
- `klifs_index` is the 1-85 KLIFS pocket position, `NA` for non-kinases
- `motif` ∈ `hinge | gatekeeper | DFG | catalytic_lys | glycine_rich_loop | P_loop | solvent_front | front_pocket | back_pocket | switch_I | switch_II | mutation_site | other`

**KRAS is not a kinase, so KLIFS does not apply.** For `kras`, `klifs_index` is `NA` throughout and the motif column is populated from a hand-curated table (switch I, switch II, P-loop, Asp12 mutation site, Tyr96, Gly10). The KLIFS ruler component must degrade to a plain sequence ruler when `klifs: false`, with no missing-data holes in the UI.

`interactions/<pdb_id>.json`: normalised PLIP output. One record per interaction: `type` (hbond, hydrophobic, pi_stack, salt_bridge, water_bridge, halogen), `residue`, `ligand_atom`, `distance_a`, `angle_deg`. Distances feed the amber measure lines directly (Section 6.4).

### 5.7 Story, edits and retrieval

`edits.csv` is the SAR move graph and drives the Edit Log panel:

`edit_id, from_compound, to_compound, vector, change_type, headline, rationale_specialist, rationale_plain, consequences, structural_basis, evidence`

- `vector` names the position in the scaffold, using the paper's own label
- `change_type` ∈ `isostere | bioisostere | ring_change | scaffold_hop | rigidification | conformational_lock | halogenation | alkylation | deuteration | homologation | polarity_reduction | sp3_enrichment | stereochemistry | hinge_swap`
- `consequences` is a JSON array of `{assay_id, from, to, fold, direction}`
- `structural_basis` is a JSON array of residue ids that explain the change
- `evidence` is the table or figure reference

`story.json` is the Feature panel:

```jsonc
{ "beats": [ {
  "id": "cdk2-2", "kicker": "The swap that changed target",
  "title": "…",
  "body_specialist": "…",              // 60-110 words
  "body_plain": "…",                   // 50-90 words, no jargon
  "focus": { "structure": "8UV0", "residues": ["A:80","A:83"], "compound": "2",
             "edit": "cdk2-e01", "plot": "selectivity", "camera": "hinge" },
  "evidence": "T1"
} ] }
```

Retrieval: `chunks.jsonl` (section-tagged text, tables as flattened rows, captions) plus `embeddings.f32` and `chunk_index.json`. Embeddings are computed once on the Mac with a local model via `mlx-lm`. The browser loads the index, embeds nothing, and answers by **returning the best-matching chunks with their source labels**. It never generates text at runtime. If no chunk clears the similarity floor, the UI says "not stated in this paper", which is a first-class answer and should be styled as one, not as an error.

The plain-register captions and `body_plain` fields may be drafted with the local model during precompute, but every one is reviewed by hand before it enters `raw/`. No generated text ships unread.

---

## 6. Visual system: Blueprint

The app looks like a technical drawing of a drug discovery campaign. Structure-based design is design, so it is drawn as design.

### 6.1 Tokens

Define every token in bare `:root` (dark is the default here, so the bare block is dark), redefine under `@media (prefers-color-scheme: light)` guarded as `:root:not([data-theme="dark"])`, and again under `:root[data-theme="light"]` so the toggle wins in both directions. Never define a colour only inside a media or `[data-theme]` block.

**Dark (default)**

```
--bg           #0B2542   /* blueprint navy */
--surface      #0F2E50   /* prose and table grounds, sits above the grid */
--surface-2    #143458
--grid         rgba(127,179,213,.11)
--ink          #DCEAF6
--ink-dim      #8FB4CF
--line         rgba(127,179,213,.35)
--line-strong  rgba(127,179,213,.55)
--target       #6FD3FF   /* the protein you want to hit */
--anti         #FF6FA5   /* the protein you must not hit */
--measure      #FFD166   /* every measured value and distance */
--gain         #5FD39B   /* an edit that improved something */
--loss         #FF5C5C   /* a clash, a liability, a failed edit */
```

**Light**

```
--bg #F4F7FC  --surface #FFFFFF  --surface-2 #EBF1FA
--grid rgba(28,36,75,.07)  --ink #1C244B  --ink-dim #5C6785
--line rgba(28,36,75,.18)  --line-strong rgba(28,36,75,.32)
--target #1B6FA8  --anti #C2185B  --measure #B26B00  --gain #10756A  --loss #C33A2E
```

Theme choice persists in `localStorage` inside `try/catch`, defaults to dark when nothing is stored, and the toggle is in the top-right of the title bar.

### 6.2 Type

| Role | Face | Notes |
|---|---|---|
| UI, labels, callouts | Archivo Narrow | Long residue and subpocket names fit in tight callouts |
| All numerals, residues, PDB codes, assay values | IBM Plex Mono | `font-variant-numeric: tabular-nums` everywhere |
| Story panel prose only | Newsreader | The register change is typographic as well as verbal |

Load in one Google Fonts request with a real fallback stack on each.

### 6.3 Sheets

Every panel is a **sheet**. A sheet has a 1px border in `--line`, a 3px inset dashed inner rule, and a **title block** in the bottom-right corner in mono at 10px: sheet number, paper slug, and the current compound or structure id. The title block updates live with app state, which makes the cross-linking visible rather than merely functional.

Sheet numbering is content, not decoration: 01 Story, 02 Structure, 03 Edit log, 04 SAR, 05 Properties.

The grid background lives on the app ground only. Prose and tables always sit on `--surface` so text never fights the grid.

### 6.4 Drawing grammar

This grammar is consistent across all four papers and every panel. Implement it once in `draw.js`.

| Element | Rule |
|---|---|
| Measured distance | Amber (`--measure`) line with end ticks, value in mono with `Å`, always rendered from the PLIP `distance_a` value, never hand-placed |
| Annotation | Cyan (`--target`) leader line, 3-2 dash, label in Archivo Narrow, pointing at a named motif or subpocket |
| Anti-target overlay | Rose (`--anti`), same geometry, so the eye reads the pair without a legend |
| Clash or liability | Coral (`--loss`), solid, with a short hatch |
| Improvement | Green (`--gain`), reserved for edit consequences only |
| Isostere swap | Before and after depictions side by side with a mono arrow, the changed atoms highlighted, deltas in mono beneath |

Motion: measure lines draw themselves over 240 ms on selection; isostere swaps morph rather than cut; everything else is instant. All of it respects `prefers-reduced-motion`.

---

## 7. Panels

### 7.1 Shell

Persistent title bar: wordmark, paper switcher (four items, keyboard `1`-`4`), tab strip, theme toggle, and the provenance rail. The switcher swaps the data bundle and nothing else: layout, scroll position semantics and selected tab persist across a paper change wherever the new paper has an equivalent selection.

Tabs: **Story · Structure · SAR · Properties**. The Edit Log lives inside Structure on desktop and as its own tab below 900px.

### 7.2 Structure sheet (Mol\*)

- Primary Mol\* instance loads the deposited mmCIF, ligand highlighted, pocket residues by motif colour.
- **Anti-target is optional and off by default.** A toggle opens a second synchronised instance (locked cameras, shared representation). This was an explicit requirement: the comparison is available on demand, not imposed.
- KLIFS ruler beneath the viewer: the 85-position pocket track with motif bands, built on the ALPHABETTI track renderer. Degrades to a plain sequence ruler for KRAS.
- Contact list from PLIP, grouped by interaction type, each row hovering to draw its measure line in the 3D scene.
- Motif chips (hinge, gatekeeper, DFG, P-loop, switch II, catalytic lysine, solvent front) select their residues.
- Representation presets: cartoon + ligand, surface, pocket-only, and B-factor colouring.
- **PyMOL download**: a `.pml` script and a `.pse` session per structure, precomputed by `gc figures`, plus the PyMOL-rendered still as a fallback image. The button is in the sheet title block.

### 7.3 Edit log sheet

The SBDD narrative made mechanical. One card per row of `edits.csv`:

before depiction → arrow → after depiction, with the changed atoms highlighted, the `change_type` as a tag, the property deltas in mono coloured by `--gain` or `--loss`, the rationale in the current register, and residue chips from `structural_basis` that drive the structure sheet on click.

Filter by `change_type`. The isostere filter is the default view, since that is the technique the app most wants to teach.

### 7.4 SAR sheet

- **R-group decomposition grid**: positions across, substituents down, primary potency as colour. Axis labels are RDKit-rendered substituent SVGs, not SMILES strings. Empty cells are drawn as deliberately empty, not blank.
- **Compound table**: `measurements.csv` pivoted on demand, column set driven by `assays.json`, sortable, filterable, with qualifiers preserved as text.
- **Isoform selectivity matrix**: target and every anti-target, fold values, coloured on a log scale.
- **Activity cliffs**: matched pairs ranked by fold change per heavy atom, each linking to its edit-log card.

### 7.5 Story sheet (the Feature)

The second audience lives here. A scroll-driven column of beats from `story.json`, set in Newsreader, with the structure and plot panels pinned beside it and following each beat's `focus` block: camera moves, residues highlight, the compound changes, the plot re-points.

A **register toggle** (Specialist / Plain) switches every `body_*` and every caption in the app at once. It is one control, not a per-panel setting, and its state persists.

Five beats per paper, no more. The last beat always ends on the lead compound and its in vivo result, then hands off to the Structure tab with an explicit control.

### 7.6 Graphical abstract re-creation

An original interactive strip at the top of the Story tab: hit → key intermediate → lead, each a live RDKit depiction with its headline values beneath, arrows carrying the one-sentence reason for the jump. Clicking any panel selects that compound everywhere. This is built from `paper.json.graphical_abstract` and is drawn by us, from SMILES: it is not the publisher's image.

### 7.7 Properties sheet

Plotly only, on one shared Blueprint template.

- Potency versus property scatter, property axis selectable from `assays.json` where `category: adme`
- LipE or ligand efficiency across the campaign, with the lead tracked
- PK species ladder (rat, dog, cynomolgus, NHP) where reported
- Parallel coordinates behind a toggle, never the default view

### 7.8 Provenance rail

Always visible. Shows the current paper, compound, structure and source table, with links out to the DOI and the RCSB entry. This is what makes the app defensible to a specialist and is non-negotiable.

---

## 8. Cross-linking

One `AppState` object, one event bus, no component reaching into another. State keys:

`paper, tab, register, compound, antiTargetOn, structure, residues[], motif, edit, assayX, assayY, beat, theme`

State serialises to the URL hash (`#cdk2/structure?cmpd=17&res=A:80,A:83&edit=cdk2-e04`) so any view is linkable. This matters for the blog and for sending a recruiter straight to the good bit.

**Cross-link matrix. Implement every row.**

| Click this | These update |
|---|---|
| Residue in 3D | `residues`; KLIFS ruler scrolls and highlights; contact list filters; SAR table filters to compounds whose edits cite that residue; edit-log filters likewise |
| Residue on the KLIFS ruler | `residues`; camera focuses that residue; contact list filters |
| Motif chip | `motif` and its residue set; camera preset for that motif |
| Contact row | Measure line draws in 3D; both partner residues select |
| Compound row in SAR table | `compound`; ligand swaps in 3D where a structure exists, otherwise the depiction panel updates with an explicit "no structure for this compound" state; all plots highlight that point; edit-log scrolls to the edits entering and leaving it |
| Point on any plot | `compound`, as above |
| Cliff pair line | Both compounds select; edit-log opens the edit linking them |
| Cell in the R-group grid | `compound` for that cell; the substituent highlights in the depiction |
| Substituent in a depiction | SAR table filters to compounds sharing it |
| Edit-log card | `edit`; both compounds enter a comparison state; cited residues highlight; consequence assays become `assayX`/`assayY` |
| Story beat scrolling into view | `beat` and everything in its `focus` block |
| Anti-target toggle | Second viewer opens, cameras lock, anti-target assay columns surface in the SAR table, rose overlays appear |
| Paper switcher | `paper`; equivalent selections carry over where they exist, otherwise fall back to that paper's lead compound and primary structure |
| Register toggle | Every caption and body text in the app |

Guard against loops: the bus dispatches once per user action, and panels must not emit while handling an event.

---

## 9. Content plan

Five story beats per paper. Written by Marc, drafted by the pipeline, always reviewed. The technical anchors below are already extracted and verified against the papers.

### 9.1 CDK2 (Hummel et al., *J. Med. Chem.* 2024, 67, 3112-3126)

Target CDK2/cyclin E1. Anti-targets CDK1/B1, CDK4/D1, CDK6/D3, CDK7/H, CDK9/T1. Structure **8UV0**, compound 17, 1.55 Å.

Beats: (1) an HTS hit that was really a JAK2 inhibitor (compound 1: CDK2 607 nM, JAK2 <1 nM); (2) the sp3 swap to 1-(methylsulfonyl)piperidin-4-ylamine that killed JAK2 (>10,000 nM) and found CDK2 (16 nM); (3) the gatekeeper Phe80 and the C5 chlorine-to-trifluoromethyl change that took CDK1 selectivity from 64-fold to 130-fold; (4) the tug of war between solubility and isoform selectivity across Table 2, ending in the cyclopropyl sulfonyl of 17; (5) compound 17 at 0.29 nM with 220-fold over CDK1, and reduced Rb phosphorylation in the CCNE1-amplified model.

Structural anchors: Phe80 gatekeeper, Glu81 / Phe82 / Leu83 hinge, Asp86 backbone NH to the sulfonamide, Lys89 and Gln85 water-mediated contact, glycine-rich loop Ile10-Val18, catalytic triad Lys33 / Glu51 / Asp145 with Asp145 hydrogen bonding the tertiary hydroxyl.

### 9.2 FGFR2/3 (Shvartsbart et al., *J. Med. Chem.* 2022, 65, 15433-15442)

Target FGFR2 and FGFR3 including gatekeeper mutants FGFR3 V555L and V555M. Anti-target FGFR1 (the hyperphosphataemia hypothesis). Structures **8E1X** (compound 30 bound to FGFR2, deposited) and **4K33** (apo FGFR3, referenced, used for the docking that designed the tetrahydrofuranyl ether).

Beats: (1) why first-generation pan-FGFR inhibitors lose the gatekeeper mutants and raise serum phosphate; (2) the hit and the methoxy, then the discovery that sp3 rings are tolerated at that ether; (3) the designed hydrogen bond to the asparagine, and the oxetane and (S)-tetrahydrofuran that delivered 0.9 nM at 30-fold; (4) the crystal structure disagreeing with the docking model: the pyridyl ring is flipped, which is exactly what explains the V555L and V555M potency losses; (5) the scaffold hop and the N-CD3 amide that cleared CYP3A4, giving compound 29 at 82% oral bioavailability in rat, with pERK down and serum phosphate flat.

Structural anchors: Ala558 hinge, Lys508 catalytic lysine, Val555 gatekeeper (FGFR3 numbering); Ala567, Lys517, Val564, Asn571 (FGFR2 numbering in 8E1X). Flag the dual numbering explicitly in the UI: this is exactly the kind of thing that confuses readers and the app should handle it, not hide it.

This paper carries the clearest **deuteration** and **scaffold hop** edits in the set, and the cleanest **structure-based design** beat (designed hydrogen bond, then confirmed and partly contradicted by the structure).

### 9.3 KRAS G12D (Ye et al., *J. Med. Chem.* 2025, 68, 1924-1939)

Target KRAS G12D, switch II pocket. Anti-target wild-type KRAS (and the HRAS/NRAS counter-screens). Structures **9E5F** (compound 3) and **9E5D** (compound 5a). Note Figure 7 of the paper is a **model** of compound 23, not a crystal structure: it must be labelled `source: modelled` and rendered visually distinct.

Beats: (1) why aspartate is not cysteine, and why the covalent route was set aside; (2) the rigid azabicyclo[2.1.1]hexane that holds the protonated amine in a conformation that is otherwise hard to reach, hydrogen bonding Tyr96 with a water-mediated contact to Gly10; (3) the vector to Asp12: the carbonyl engages the **backbone** NH, not the side chain, and that is where the roughly 55-fold wild-type selectivity comes from; (4) rigidity and polarity as the property lever, including the conformational lock chosen after a 1 µs MD run identified the amide as the flexible handle; (5) trading three-fold potency for permeability to get 42% oral bioavailability in NHP.

Structural anchors: Asp12 (mutation site), Tyr96, Gly10, switch II pocket. **No KLIFS.** Motifs come from the curated table.

### 9.4 JAK1 (Zhuo et al., *J. Med. Chem.* 2026, drug annotation)

Target JAK1 JH1. Anti-target JAK2 JH1 (and JAK3, TYK2). Paired co-structures of povorcitinib in both JAK1 and JAK2: the only paper in the set with a true twin structure, so it is the showcase for the anti-target toggle.

Beats: (1) why sparing JAK2 matters (haematopoiesis, anaemia, cytopenias); (2) scaffold 9 and the isopropyl amide that first bought JAK1 selectivity; (3) the intramolecular hydrogen bond: the ortho-fluorine that lifted Caco-2 five-fold and cynomolgus exposure dramatically, proven by removing it again in compound 19 and watching the numbers collapse; (4) the hinge binder shrinking from pyrrolo[2,3-d]pyrimidine to 3,5-dimethylpyrazole, costing enzyme potency but taking dog oral bioavailability from 1% to 100%; (5) the P-loop groove: JAK1's P-loop sits higher than JAK2's, opening a small lipophilic pocket for the amide alkyl group, and the CF3 would clash in JAK2.

Structural anchors: Glu930 and Leu932 hinge (both isoforms), JAK1 His885 and JAK2 Asn859 in the P-loop, JAK2 Phe860, JAK2 Glu1015, JAK1 Asp1042. The authors describe the selectivity explanation as speculative, and **the app must say so too**: this is a good opportunity for the provenance rail to show its worth.

### 9.5 Known data issues (resolve during Stage 1, record in `raw/<slug>/ISSUES.md`)

1. **JAK1 PDB codes are ambiguous in the PDF.** The paper prints `1OPI` / `1OPJ` in one place, `10PI` / `10PJ` in another. Both `1OPI` and `1OPJ` are existing unrelated entries. Resolve against RCSB before Stage 3 and record the verified codes. Do not guess in the data bundle.
2. **KRAS TOC versus tables.** The graphical abstract gives compound 10 at 451 nM whole blood and compound 23 SPR 2.2 nM; the tables give 410 nM and 22 nM. Record both, cite both, do not average.
3. **FGFR** writes `FASSIF` in Table 5 and `FaSSIF` in Table 7. Normalise the assay id, keep the source strings.
4. **JAK1** abstract and conclusions say "murine" arthritis, but the model described in the methods is a rat adjuvant-induced arthritis model. Use the methods.
5. **KRAS** Scheme 5 is captioned "alkyne 40" while the text says "alkyne 38". Out of scope for the app, but note it.
6. **CDK2 Table 1** puts two values in one CDK4/CDK6 cell (for example `3.2/10`). The extractor must split these into two measurements.

---

## 10. Build stages

Four stages. Each ends with something that runs. Do not start the next stage until the acceptance criteria pass.

### Stage 1: Harvest and data spine

**Do**

- Scaffold the repo, write `HARVEST.md`, lift the modules in Section 3.
- Write `pipeline/schemas/*.json` for every artefact in Section 5.
- Build `gc extract`, `gc chem`, `gc struct`, `gc validate`, `gc bundle`.
- Curate **CDK2 only**, end to end, into `raw/cdk2/` by hand from the paper and SI, then through the pipeline.
- `gc struct` must fetch 8UV0, run PLIP through `cif_to_plip.py` with the CONECT workaround, pull KLIFS for CDK2, run DSSP, and emit `residues.csv` and `interactions/8UV0.json`.
- `gc chem` must produce core-aligned depictions, descriptors, the MCS scaffold, the R-group decomposition matching Tables 1 and 2, and the matched-pair cliff list.
- Resolve every item in Section 9.5 that touches CDK2.

**Acceptance**

- `gc validate cdk2` passes with zero provenance gaps.
- `web/data/papers/cdk2/` exists and every file validates against its schema.
- A coverage report prints: compounds, measurements, assays, structures, residues with motifs, edits, and flags anything unlinked.

**Do not yet**: write any panel code.

### Stage 2: Shell and core panels

**Do**

- Tokens, Blueprint CSS, sheets, title blocks, theme toggle, `draw.js` grammar.
- `state.js` with the full key set, the event bus and URL hash serialisation.
- Structure sheet with Mol\*, KLIFS ruler, motif chips, contact list with live measure lines. Anti-target toggle wired but allowed to be a stub until Stage 3 if the second structure is not yet curated.
- SAR sheet: R-group grid, pivoted compound table, selectivity matrix, cliffs.
- Properties sheet: the three default Plotly figures on the shared template.
- Every row of the Section 8 matrix that involves these panels.

**Acceptance**

- CDK2 is fully explorable. Clicking Phe80 filters the SAR table; clicking compound 17 loads its ligand and highlights its point on every plot; a copied URL restores the exact view in a fresh tab.
- Both themes pass contrast at 4.5:1 for body text and 3:1 for UI, checked on the grid background as well as on `--surface`.
- Keyboard: tab order is sane, focus is always visible, `1`-`4` switch papers.

### Stage 3: Story, edit log and all four papers

**Do**

- Story sheet: scroll-driven beats, Newsreader, register toggle wired to every caption in the app.
- Graphical abstract re-creation strip.
- Edit log sheet with `change_type` filtering, isostere as the default filter.
- Curate FGFR, KRAS and JAK1 through the pipeline. KRAS exercises the non-KLIFS path; JAK1 exercises the true twin-structure anti-target path; FGFR exercises dual residue numbering.
- Write the twenty story beats, both registers.
- Paper switcher carrying selections across bundles.

**Acceptance**

- All four papers load, and switching between them never changes the furniture.
- KRAS renders with no empty KLIFS affordances anywhere.
- JAK1 opens both structures with locked cameras and the rose anti-target overlay.
- Every beat's `focus` block drives at least three panels.
- Reading the Story tab for any paper, with no chemistry background, explains what the drug does and why it was hard.

### Stage 4: Depth, polish and deploy

**Do**

- `gc dynamics`: OpenMM minimisation plus a short MD run per primary structure on the Mac, emitting an RMSF track for the ruler and a decimated trajectory (target 200 frames, under 2 MB gzipped) playable in Mol\*. If a trajectory does not support what the paper claims, **do not ship that trajectory**: say so in `ISSUES.md`.
- `gc figures`: PyMOL stills, `.pml` and `.pse` download bundles per structure.
- Retrieval: chunking, local embedding, in-browser cosine search, the "not stated in this paper" state.
- About sheet: pipeline schematic, software and reference table with GitHub links and DOIs, and a plain statement that all views are rendered from public coordinates and original depictions.
- Mobile: sheets stack, the twin view becomes a swipe, the KLIFS ruler scrolls horizontally in its own container.
- Performance budget: first meaningful paint under 2 s on a cold cache, total initial transfer under 1.5 MB excluding Mol\*, each paper bundle under 3 MB gzipped, lazy-load structures and trajectories.
- README to house standard, app icon via `marcs-vibe-icon`, page icon for the site nav via `marcs-page-icon`, deploy to `gatecrasher.mdeller.com` with nginx and certbot, rsync deployment script.

**Acceptance**

- Lighthouse: performance ≥ 90, accessibility ≥ 95 on desktop and mobile.
- Every structure offers a working PyMOL download.
- No network request at runtime except to the app's own origin and the pinned CDNs.
- A cold reader lands on the site, understands what it is within thirty seconds, and can reach a contact at atomic resolution within three clicks.

---

## 11. Testing and QA

- **Schema gate**: `gc validate` in CI (GitHub Actions) on every push. A missing `source_table` fails the build.
- **Chemistry gate**: every SMILES parses; every InChIKey is unique; every R-group decomposition reassembles to the parent SMILES; any failure is listed, not silently dropped.
- **Structure gate**: every residue cited in `edits.csv` or `story.json` exists in `residues.csv` for the referenced structure. This catches the numbering mistakes that Section 9.2 makes likely.
- **Cross-link smoke test**: a Playwright script that walks the Section 8 matrix and asserts the expected state change for each row.
- **Both themes** screenshot-compared per panel.
- **Copy check**: a script that greps for the company name, em dashes, and the forbidden-word list, and fails the build on a hit.

---

## 12. Out of scope for this build

Record these in the README roadmap and do not build them now: analogue sketching and rescoring, live docking, free energy calculations, ESMFold-predicted apo models, mutant side-chain rebuilding, cross-paper querying, and any runtime language model. Each of these needs compute, and this build has none.

---

## 13. Attribution

The four papers are published, peer-reviewed work with Marc C. Deller as a co-author, contributing the protein crystallography. The site describes his role plainly, credits all authors by name in each citation, links every DOI, and names no employer.
