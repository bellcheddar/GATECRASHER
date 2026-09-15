# 🧬 GATECRASHER

> **Four drug discovery campaigns, opened up: the pocket, the structure-activity relationships, the chemical edits, and the structural basis of selectivity.**

[![live](https://img.shields.io/badge/live-gatecrasher.mdeller.com-00d084?logo=icloud&logoColor=white)](https://gatecrasher.mdeller.com)
![python](https://img.shields.io/badge/python-3.12.13-3776AB?logo=python&logoColor=white)
![rdkit](https://img.shields.io/badge/rdkit-2026.3.6-8B0000)
![gemmi](https://img.shields.io/badge/gemmi-0.7.5-2E8B57)
![biotite](https://img.shields.io/badge/biotite-1.7.1-4B8BBE)
![plip](https://img.shields.io/badge/plip-3.0.1-6A5ACD)
![opsin](https://img.shields.io/badge/opsin-1.2.0-C71585)
![openmm](https://img.shields.io/badge/openmm-8.5.2-D2691E)
![openff](https://img.shields.io/badge/openff--toolkit-0.18.0-2E8B57)
![mdtraj](https://img.shields.io/badge/mdtraj-1.11.1-4B8BBE)
![molstar](https://img.shields.io/badge/mol*-5.11.0-1B6FA8)
![plotly](https://img.shields.io/badge/plotly-2.35.2-3F4F75?logo=plotly&logoColor=white)
![rdkit.js](https://img.shields.io/badge/rdkit.js-2025.3.4-8B0000)
![browser checks](https://img.shields.io/badge/browser%20checks-120%20passing-00d084)
![bundles](https://img.shields.io/badge/bundles-4%20validating-00d084)
![data](https://img.shields.io/badge/data-RCSB%20PDB%20·%20KLIFS%20·%20PubChem-fcb900)
![licence](https://img.shields.io/badge/licence-MIT-blue)
![author](https://img.shields.io/badge/author-Marc%20C.%20Deller-1C244B)

| | |
|---|---|
| 🌐 **App** | [gatecrasher.mdeller.com](https://gatecrasher.mdeller.com) |
| ✉️ **Contact** | [marc@marcdeller.com](mailto:marc@marcdeller.com) |
| 📦 **Repository** | [github.com/bellcheddar/GATECRASHER](https://github.com/bellcheddar/GATECRASHER) |

![The Structure sheet: compound 17 in the CDK2 ATP site at 1.55 Å, with the PLIP contact list, the KLIFS pocket ruler and the edit log](docs/screenshots/structure-dark.png)

**Why it matters:** a published medicinal chemistry paper tells you what was made and what it did, but the reasoning that connects one compound to the next is spread across tables, figures and a supporting information file, and the structural basis for it sits in a database somewhere else. GATECRASHER puts them in one place and makes them click through to each other: select a residue in three dimensions and the compound table filters to the molecules whose edits cite it; select a compound and its ligand appears in the pocket, its point lights up on every plot, and the edit log scrolls to the changes that made it. Every number on screen carries the table or figure it came from, and the build fails if one does not. It is useful for anyone who wants to see how a drug was actually designed: structural biologists and medicinal chemists who want the contacts and the R-group tables, and everyone else who wants to understand in thirty seconds what the molecule does and why it was hard.

## 🔬 The four campaigns

Each is a selectivity problem solved at a pocket, then carried over the line by property work.

| Campaign | Target, and what had to be spared | Structures | The move it turns on |
|---|---|---|---|
| **CDK2** (Hummel *et al.* 2024) | CDK2/cyclin E1, sparing CDK1, 4, 6, 7, 9 | [8UV0](https://www.rcsb.org/structure/8UV0) | A screening hit that was really a JAK2 inhibitor: an sp3 aminopiperidine erased JAK2 and found CDK2 |
| **FGFR2/3** (Shvartsbart *et al.* 2022) | FGFR2 and FGFR3 including gatekeeper mutants, sparing FGFR1 | [8E1X](https://www.rcsb.org/structure/8E1X), [4K33](https://www.rcsb.org/structure/4K33) | A hydrogen bond designed on a docking model, then confirmed and partly contradicted by the crystal structure |
| **KRAS G12D** (Ye *et al.* 2025) | KRAS G12D, sparing wild-type KRAS | [9E5F](https://www.rcsb.org/structure/9E5F), [9E5D](https://www.rcsb.org/structure/9E5D) | A thousand-fold of binding potency given away on purpose, for oral exposure |
| **JAK1** (Zhuo *et al.* 2026) | JAK1, sparing JAK2 | [10PI](https://www.rcsb.org/structure/10PI), [10PJ](https://www.rcsb.org/structure/10PJ) | One ligand crystallised in both the target and the anti-target: the only true twin in the set |

Marc C. Deller is a co-author on all four papers, contributing the protein crystallography.

## 📊 What is in the bundles

| | |
|---|---|
| Compounds | 91, every one with a verified structure |
| Measurements | 859, each carrying the table or figure it was printed in |
| Structures | 7 deposited entries |
| Residues | 1,786 annotated with secondary structure and motif |
| Edits | 56 designed changes, with their consequences and structural basis |
| Story beats | 20, in a specialist and a plain register |

## 🧪 How a structure gets into this app

No compound structure in this repository was drawn by hand and trusted. Each one is verified, and the notes column of every `compounds.tsv` records **how strongly**:

| Strength | Meaning |
|---|---|
| `ligand-verified` | Matches the chemical component deposited in the PDB, atom for atom |
| `name-verified` | The paper's own IUPAC name, parsed with OPSIN, agrees atom for atom |
| `source-verified` | Fetched from PubChem and checked against the published formula |
| `anchor-derived` | Built with RDKit `molzip` from a verified core by one documented substitution |
| `figure-derived` | Read from a drawing, with no name and no coordinates to check it against. The weakest, and flagged as such wherever it appears |

**A molecular formula check is not enough, and this is not a theoretical concern.** While curating the FGFR bundle, a hand-built scaffold reproduced the paper's published formula exactly while having the wrong connectivity: in a SMILES prefix fragment the bond to the next atom comes from the fragment's *last* atom, so every cyclic ether had attached through a ring carbon with its oxygen left dangling. Same atoms, wrong molecule, identical formula. Only comparing against the structure parsed from the published name caught it. Fragments are now joined with `molzip` at labelled attachment points, and the scheme is proved by rebuilding each verified anchor exactly.

The same principle governs what gets drawn in the pocket: every distance in the app comes from a PLIP measurement on real coordinates, and nothing is hand-placed. A contact whose atoms cannot be located is listed but never drawn, because a measure line without a measurement is the one thing this drawing grammar forbids.

## 🧲 What the dynamics are for

The crystal structure is one pose at one temperature. The short molecular dynamics run asks a narrower and more useful question: **does the contact the paper leans on actually hold?**

Each primary structure gets a run under amber14-all with TIP3P water, the ligand parameterised by the Open Force Field small-molecule force field (openff-2.1.0) with AM1-BCC charges, in a 1 nm box at 0.15 M NaCl, 300 K, 2 fs steps with hydrogen mass repartitioning at 4 amu, a Monte Carlo barostat, 200 ps of restrained equilibration released in five steps, then 5 ns of production sampled every 20 ps.

Each run carries the paper's own claims, written as testable statements before the run starts, and each is scored against thresholds fixed in advance:

| Claim shape | Passes when |
|---|---|
| A contact the paper says is present | Held in at least **50%** of frames |
| A contact the paper says is absent | Present in at most **20%** of frames |
| The ligand stays where it was crystallised | Median heavy-atom RMSD to the crystal pose at most **2 Å** |

**A trajectory that fails its claims is not published.** The verdict is written either way, so the page can say what was run and what it showed, rather than offering a control that quietly does nothing.

### What the runs found

All four support their papers. Twelve claims, every one scored against a threshold fixed before the run:

| Campaign | Claim | Expected | Occupancy | Median |
|---|---|---|---|---|
| **CDK2** | 2-aminopyrimidine to the Leu83 hinge | present | 100% | 2.78 Å |
| | Sulfonamide oxygen from the Asp86 backbone amide | present | 92.8% | 3.07 Å |
| | C5 trifluoromethyl at the Phe80 gatekeeper | present | 100% | 3.19 Å |
| **FGFR** | Hinge contact to Ala567 | present | 99.6% | 3.02 Å |
| | **The designed hydrogen bond to Asn571** | present | **64.8%** | 3.17 Å |
| | Pyridine nitrogen at the Val564 gatekeeper | present | 86.0% | 3.92 Å |
| **KRAS** | Bicyclic amine to Tyr96 | present | 100% | 2.85 Å |
| | **No direct contact with Asp12** | **absent** | **0%** | 4.65 Å |
| | Amine to the Glu62 carboxylate | present | 99.2% | 2.81 Å |
| **JAK1** | Pyrazole nitrogen from the Leu959 amide | present | 100% | 3.05 Å |
| | Pyrazole NH to the Glu957 carbonyl | present | 100% | 2.83 Å |
| | Trifluoromethyl in the P-loop groove at Phe886 | present | 98.0% | 3.22 Å |

Two rows repay reading. **FGFR's Asn571 bond is the one the chemists designed**, and it is real but intermittent: present in 64.8% of frames, which a single crystal structure cannot tell you and which no amount of staring at a 3.17 Å distance would reveal. **KRAS's Asp12 row runs the other way**: the paper asserts the ligand does *not* reach Asp12, contrary to the original design hypothesis, and the run reproduces that absence at 0% occupancy. A test that can only ever agree proves nothing; this one is scored in both directions.

JAK1's Glu957 contact lands at 2.83 Å against 2.81 Å measured in the deposited coordinates, agreement to 0.02 Å.

### What the runs could not test

Each run names its limits before it starts, and those reach the page beside the claims rather than stopping at the report. They are drawn as neither a pass nor a failure, because a limit is the absence of a verdict rather than one:

- **CDK2 and KRAS** each declare a water-mediated contact they cannot follow. The trajectory carries the crystal waters, but a bridge handed on between exchanging waters is invisible to a solute-only analysis.
- **FGFR** declares its activation loop, whose two phosphotyrosines are reverted to tyrosine for want of parameters, so its conformation is not the deposited one.
- **JAK1** declares the selectivity explanation itself, which the authors call a hypothesis under investigation, and which would need the JAK2 twin simulated alongside to say anything about at all.

Where a run passes, the page gains a per-residue RMSF band on the pocket ruler and a decimated trajectory of the pocket and ligand that plays in the viewer.

## 📈 Where potency actually comes from

Activity cliffs are ranked by fold change per heavy atom changed, so a large gain bought with a large edit does not outrank a small edit that bought the same thing:

| Campaign | Steepest pair | Fold | Atoms changed | Per atom |
|---|---|---|---|---|
| JAK1 | 20 to 18 | 1256 | 12 | 104.7 |
| FGFR | 13 to 25 | 858 | 12 | 71.5 |
| KRAS | 13 to 11 | 103 | **2** | 51.5 |
| CDK2 | 4 to 7 | 3.6 | **1** | 3.6 |

The KRAS and CDK2 rows are the interesting shape: a hundredfold from two atoms, and CDK2's flattest table in the set, where potency was never the hard part and selectivity and exposure were.

## ⚖️ What this app does not reproduce

No publisher figure, graphical abstract or full text is reproduced here. Every molecule is drawn from SMILES with RDKit, every structure is rendered from coordinates fetched from the RCSB PDB, and the narrative is written fresh. Abstracts are quoted verbatim in a marked quotation block with their citation and DOI, which is ordinary scholarly quotation. The paper PDFs themselves are not in this repository and never will be.

Where a paper's only record of something is a figure we may not copy, the app says so plainly rather than inventing a substitute: the KRAS paper's model of its final compound is described and not shown, because no coordinates exist for it.

## 🏗️ Running the pipeline

`pipeline/` runs on the Mac and never ships; `web/` is what gets deployed, as vanilla ES modules with no build step and no server. Curated source tables live in `pipeline/raw/<slug>/`, published bundles in `web/data/papers/<slug>/`.

```
gc extract  <slug> --pdf <file> --pages 1-10   # text and page images, for hand transcription
gc chem     <slug>                             # descriptors, scaffold, core-aligned depictions
gc struct   <slug>                             # mmCIF, DSSP, KLIFS, PLIP contacts
gc dynamics <slug> --stage all                 # OpenMM run, RMSF track, claim verdicts
gc bundle   <slug>                             # melt the published tables into web/data/
gc validate [slug]                             # schema, provenance, chemistry, cross-references
gc all      <slug>                             # the pipeline, in order
```

### The validation gate

`gc validate` fails the build, not a warning, when: a measurement has no `source_table`; an InChIKey does not match its SMILES; two compounds are the same molecule; an R-group fragment is not actually present in its parent; a residue cited by an edit, a story beat or a contact does not exist in the structure it is cited against; or an assay, compound or edit id is referenced but not defined.

## ✅ To Do

Roadmap, roughly in dependency order.

- [x] **Data contract.** Long-format measurements, per-paper assay dictionaries, JSON Schema for every artefact, and a provenance gate that fails the build rather than warning
- [x] **CDK2 end to end.** 18 compounds, 251 measurements, 8UV0 with PLIP contacts and the KLIFS pocket ruler, as the shape every later bundle had to fit
- [x] **All four campaigns.** FGFR, KRAS and JAK1 curated, including the non-kinase path for KRAS where there is no KLIFS numbering, and the twin-structure anti-target for JAK1
- [x] **Chemical verification.** OPSIN name-to-structure checking and `molzip` fragment assembly on verified cores, after a formula check passed a molecule with the wrong connectivity
- [x] **Structural annotation.** DSSP secondary structure, KLIFS pocket numbering, PLIP contacts per structure, and a gate that every cited residue exists in the coordinates it is cited against, which caught a hinge labelled on an arginine
- [x] **Selectivity analysis.** The anti-target twin view with the two structures superposed before drawing, the selectivity matrix, and activity cliffs ranked from the primary potency only
- [x] **In-browser search.** BM25 over this project's own prose and data, indexed once on the Mac and scored in the page, with "not stated in this project" as a first-class answer
- [x] **Take the view away.** A PyMOL script, session and still image per structure, so the pocket leaves the browser
- [x] **Gates in CI.** The schema, provenance, chemistry and cross-reference checks run on every push, along with the copy gate, so a bundle that contradicts itself cannot reach the branch. Proved by breaking one on purpose: a blanked `source_table` fails the build rather than warning, which is the behaviour the gate exists for
- [x] **Every cross-link asserted.** Each row of the interaction matrix is now tested for the state change it causes rather than for the element being drawn: a plot point, an R-group cell, a substituent, a cliff pair and an edit card all have to move the selection, not merely exist. Writing them found the last unimplemented row, so a substituent now filters the table to the compounds carrying it
- [x] **Where the page phones.** The app contacts its own origin and the RCSB, for coordinates it never redistributes, and nothing else. The three faces are served from here rather than a font CDN, so the rule holds strictly rather than by interpretation, and a test pins the page to exactly that list: a new third party has to be added deliberately rather than arriving unnoticed
- [x] **Reachable without a mouse, legible in both themes.** Every control that answers Enter or Space is now tested on the key as well as the click, and the contrast of the prose, the grid ground and the provenance rail is measured in the dark theme as well as the light one. Dark is what most readers see and was the half going unmeasured
- [x] **What the run could not test, published with what it did.** Each simulation names its own limits before it starts, and those now reach the page beside the claims rather than stopping at the report: the water-mediated bridges a solute-only trajectory cannot follow, an activation loop modelled without its phosphotyrosines, a selectivity argument that would need the anti-target simulated alongside. Drawn as neither a pass nor a failure, because a limit is the absence of a verdict rather than one
- [x] **Short molecular dynamics.** Four 5 ns runs, one per primary structure, each carrying the paper's own claims as testable statements written before it started. All four support theirs. JAK1 took two attempts: the first returned `does_not_support` and withheld its trajectory, correctly, because the prepared ligand carried the wrong pyrazole tautomer and the hinge bond to Glu957 had no proton to donate. The verdict was about our ligand, not the paper. `molecule_from_crystal` now resolves symmetric substructure matches by receptor geometry, which puts the NH 2.81 Å from the Glu957 carbonyl and leaves the other ring nitrogen 2.93 Å from the Leu959 amide, both reproducing the deposited distances exactly
- [x] **Cliff tables that say the same thing twice.** Matched-pair detection ran a common substructure search on a five second budget, and a timeout was recorded as "these molecules share nothing", which is indistinguishable from a real negative. The published tables were therefore a function of machine load: JAK1 was missing the first, second and fourth entries of its own table, so the panel headlined 45.5 fold per atom when the true top was 104.7, and KRAS was missing five. A cancelled search is now treated as the lower bound it actually is, the full budget is spent only on pairs close enough to deserve it, and anything still unresolved is recorded rather than dropped. Two consecutive rebuilds produce byte identical tables for all four campaigns. One 88.9-fold KRAS pair is withheld rather than published with a truncated core that would mis-sort the table, and is listed as a loss rather than absorbed into the total
- [ ] **Per-residue dynamics on the anti-target.** Povorcitinib is the only ligand in this set crystallised in both its target and its anti-target, and the authors' explanation for its JAK1 over JAK2 selectivity is explicitly labelled speculative in their own paper. The twin view compares the two crystal poses; simulating 10PJ alongside 10PI would compare their flexibility, which is the first measurement that could bear on that hypothesis. JAK1's run already names this as the thing it could not test

## 📚 Citations

| Campaign | Citation |
|---|---|
| CDK2 | Hummel J. R., Xiao K.-J., Yang J. C., Epling L. B., Mukai K., Ye Q., Xu M., Qian D., Huo L., Weber M., Roman V., Lo Y., Drake K., Stump K., Covington M., Kapilashrami K., Zhang G., Ye M., Diamond S., Yeleswaram S., Macarron R., **Deller M. C.**, Wee S., Kim S., Wang X., Wu L., Yao W. *J. Med. Chem.* **2024**, 67, 3112-3126. [10.1021/acs.jmedchem.3c02287](https://doi.org/10.1021/acs.jmedchem.3c02287) |
| FGFR2/3 | Shvartsbart A., Roach J. J., Witten M. R., Koblish H., Harris J. J., Covington M., Hess R., Lin L., Frascella M., Truong L., Leffet L., Conlen P., Beshad E., Klabe R., Katiyar K., Kaldon L., Young-Sciame R., He X., Petusky S., Chen K.-J., Horsey A., Lei H.-T., Epling L. B., **Deller M. C.**, Vechorkin O., Yao W. *J. Med. Chem.* **2022**, 65, 15433-15442. [10.1021/acs.jmedchem.2c01366](https://doi.org/10.1021/acs.jmedchem.2c01366) |
| KRAS G12D | Ye Q., Shvartsbart A., Li Z., Gan P., Policarpo R. L., Qi C., Roach J. J., Zhu W., McCammant M. S., Hu B., Li G., Yin H., Carlsen P., Hoang G., Zhao L., Susick R., Zhang F., Lai C.-T., Allali Hassani A., Epling L. B., Gallion A., Kurzeja-Lipinski K., Gallagher K., Roman V., Farren M. R., Kong W., **Deller M. C.**, Zhang G., Covington M., Diamond S., Kim S., Yao W., Sokolsky A., Wang X. *J. Med. Chem.* **2025**, 68, 1924-1939. [10.1021/acs.jmedchem.4c02662](https://doi.org/10.1021/acs.jmedchem.4c02662) |
| JAK1 | Zhuo J., Li Y.-L., Qian D.-Q., Burns D. M., Mei S., Rafalski M., Xu M., Cao G., Pan Y., Jia Z., Jalluri R., Epling L. B., Fenalti G., **Deller M. C.**, Procak J., Covington M., He X., Collins R., Stubbs M., Burke K., Oliver J., Margulis A., Boer J., Wynn R., Scherle P., Diamond S., Newton R., Zhang Y., Metcalf B., Yao W. *J. Med. Chem.* **2026**. [10.1021/acs.jmedchem.5c03753](https://doi.org/10.1021/acs.jmedchem.5c03753) |

## 🛠️ Software this stands on

| Tool | Used for | Licence |
|---|---|---|
| [RDKit](https://www.rdkit.org/) | Descriptors, MCS, core-aligned depictions, fragment assembly | BSD-3-Clause |
| [OPSIN](https://github.com/dan2097/opsin) | Turning the papers' IUPAC names into structures, for verification | MIT |
| [PLIP](https://github.com/pharmai/plip) | Protein-ligand interaction profiling | GPL-2.0, invoked as a subprocess and never imported |
| [gemmi](https://gemmi.readthedocs.io/) | mmCIF handling and structure superposition | MPL-2.0 |
| [biotite](https://www.biotite-python.org/) | Structure handling | BSD-3-Clause |
| [DSSP](https://github.com/PDB-REDO/dssp) | Secondary structure | BSD-2-Clause |
| [Open Babel](https://openbabel.org/) | Chemical perception inside PLIP | GPL-2.0, reached only inside the PLIP subprocess |
| [OpenMM](https://openmm.org/) | The molecular dynamics engine | LGPL-3.0-or-later, run as a subprocess under a separate interpreter |
| [OpenFF Toolkit](https://github.com/openforcefield/openff-toolkit) | Ligand parameters with AM1-BCC charges | MIT |
| [PDBFixer](https://github.com/openmm/pdbfixer) | Missing atoms and protonation before solvation | MIT |
| [MDTraj](https://mdtraj.org/) | RMSF, ligand RMSD and contact occupancy from the trajectories | LGPL-2.1-or-later, run as a subprocess under a separate interpreter |
| [PyMOL](https://github.com/schrodinger/pymol-open-source) | The downloadable script, session and still per structure | Open-Source PyMOL licence, invoked as a subprocess |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Text and page images out of the PDFs, on the Mac only | BSD-3-Clause / Apache-2.0 |
| [Mol\*](https://molstar.org/) | The structure viewer | MIT |
| [Plotly.js](https://plotly.com/javascript/) | Every figure | MIT |
| [RDKit.js](https://github.com/rdkit/rdkit-js) | In-browser depiction and highlighting | BSD-3-Clause |
| [Archivo Narrow](https://fonts.google.com/specimen/Archivo+Narrow) | The interface face | SIL Open Font Licence 1.1 |
| [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) | Every measured value and residue label | SIL Open Font Licence 1.1 |
| [Newsreader](https://fonts.google.com/specimen/Newsreader) | The narrative prose | SIL Open Font Licence 1.1 |
| [KLIFS](https://klifs.net/) | Kinase pocket numbering | Academic use |
| [RCSB PDB](https://www.rcsb.org/) | All coordinates | Public domain |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Reference drug structures | Public domain |

GATECRASHER is released under the [MIT licence](LICENSE). Nothing copyleft is linked in: the GPL and LGPL tools above are each invoked as a subprocess and never imported, and none of them reaches the browser. Versions, roles, references and the licence notices for the vendored libraries are in [`THIRD_PARTY.md`](THIRD_PARTY.md), which is generated from the same `web/data/software.json` the About sheet renders.

---

Built by [Marc C. Deller, D.Phil.](https://marcdeller.com) · [marc@marcdeller.com](mailto:marc@marcdeller.com)

---

## 👤 Author

**Marc C. Deller, D.Phil.**  
Structural biologist & drug discovery scientist  

<table>
<tr>
<td>🌐</td><td><a href="https://marcdeller.com" target="_blank" rel="noopener noreferrer">marcdeller.com</a></td>
<td>✉️</td><td><a href="mailto:marc@marcdeller.com">marc@marcdeller.com</a></td>
<td>🐙</td><td><a href="https://github.com/bellcheddar/GATECRASHER" target="_blank" rel="noopener noreferrer">github.com/bellcheddar/GATECRASHER</a></td>
</tr>
</table>
