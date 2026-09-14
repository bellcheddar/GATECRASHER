# 🧬 GATECRASHER

> **Four drug discovery campaigns, opened up: the pocket, the structure-activity relationships, the chemical edits, and the structural basis of selectivity.**

[![live](https://img.shields.io/badge/live-gatecrasher.mdeller.com-00d084?logo=icloud&logoColor=white)](https://gatecrasher.mdeller.com)
![python](https://img.shields.io/badge/python-3.12.13-3776AB?logo=python&logoColor=white)
![rdkit](https://img.shields.io/badge/rdkit-2026.3.6-8B0000)
![gemmi](https://img.shields.io/badge/gemmi-0.7.5-2E8B57)
![biotite](https://img.shields.io/badge/biotite-1.7.1-4B8BBE)
![plip](https://img.shields.io/badge/plip-3.0.1-6A5ACD)
![opsin](https://img.shields.io/badge/opsin-1.2.0-C71585)
![molstar](https://img.shields.io/badge/mol*-5.11.0-1B6FA8)
![plotly](https://img.shields.io/badge/plotly-2.35.2-3F4F75?logo=plotly&logoColor=white)
![rdkit.js](https://img.shields.io/badge/rdkit.js-2025.3.4-8B0000)
![browser checks](https://img.shields.io/badge/browser%20checks-73%20passing-00d084)
![bundles](https://img.shields.io/badge/bundles-4%20validating-00d084)
![data](https://img.shields.io/badge/data-RCSB%20PDB%20·%20KLIFS%20·%20PubChem-fcb900)
![phase](https://img.shields.io/badge/phase-stage%204-ff6900)
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

## 🏗️ How it is built

Two halves, and the boundary between them is the point:

- **`pipeline/`** runs on the Mac and never ships. It fetches coordinates, runs DSSP, asks KLIFS for pocket numbering, runs PLIP for contacts, computes descriptors and core-aligned depictions with RDKit, and writes validated JSON and CSV.
- **`web/`** is what gets deployed: vanilla ES modules, no build step, no framework, no server. Mol\*, Plotly and RDKit.js are vendored and served from the app's own origin.

```
gc extract <slug> --pdf <file> --pages 1-10   # text and page images, for hand transcription
gc chem    <slug>                             # descriptors, scaffold, core-aligned depictions
gc struct  <slug>                             # mmCIF, DSSP, KLIFS, PLIP contacts
gc bundle  <slug>                             # melt the published tables into web/data/
gc validate [slug]                            # schema, provenance, chemistry, cross-references
gc all     <slug>                             # the four above, in order
```

```bash
bash tools/copy_check.sh                                  # the company is never named, no em dashes
python3 tools/browser_check.py --base http://127.0.0.1:8099   # 67 checks in a real browser
```

### The validation gate

`gc validate` fails the build, not a warning, when: a measurement has no `source_table`; an InChIKey does not match its SMILES; two compounds are the same molecule; an R-group fragment is not actually present in its parent; a residue cited by an edit or a story beat does not exist in the structure it is cited against; or an assay, compound or edit id is referenced but not defined.

## 🗂️ Repository layout

| Path | What it is |
|---|---|
| `pipeline/raw/<slug>/` | Hand-curated source of truth: one file per published table, plus `ISSUES.md` |
| `pipeline/schemas/` | JSON Schema for every published artefact |
| `pipeline/gcrash/` | The `gc` command. Named `gcrash` because `gc` is a Python built-in module name and built-ins always win an import |
| `web/data/papers/<slug>/` | The deployed bundles |
| `tools/` | The browser check and the copy gate |
| `deploy/` | nginx site and the rsync deployment |

## 📐 Reading the drawing

The app is laid out as a technical drawing, and the colours carry meaning rather than decoration:

| Colour | Means |
|---|---|
| Amber | A measured value or distance, always drawn from the PLIP measurement and never hand-placed |
| Cyan | The protein you want to hit, and annotation leader lines |
| Rose | The protein you must not hit |
| Green | An edit that improved something |
| Coral | A clash, a liability, or an edit that failed |

Dark is the default and light is a first-class citizen, not an afterthought. Both are contrast-checked in the browser test.

## 🔍 What the papers disagree with themselves about

Each bundle carries an `ISSUES.md` recording every place a paper contradicts itself, with both readings kept and neither averaged. Some of what is in there:

- **KRAS**: the graphical abstract gives compound 10 at 451 nM and compound 23 at 2.2 nM where the tables give 410 nM and 22 nM. Both are shown, labelled by source.
- **JAK1**: the PDB codes are printed two ways, and one spelling points at two real but unrelated entries (an RNA recognition motif and auto-inhibited c-Abl). Resolved against RCSB before anything was built.
- **JAK1**: the abstract says the arthritis model was murine; the methods describe rats. The app says rats.
- **FGFR**: the RCSB entry title for 8E1X names compound 29, while the paper names compound 30. The deposited ligand's formula settles it: it is compound 30.
- **CDK2**: Table 1 puts two isoform values in one cell, which reads like a value and a fold and is not.

## ⚖️ What this app does not reproduce

No publisher figure, graphical abstract or full text is reproduced here. Every molecule is drawn from SMILES with RDKit, every structure is rendered from coordinates fetched from the RCSB PDB, and the narrative is written fresh. Abstracts are quoted verbatim in a marked quotation block with their citation and DOI, which is ordinary scholarly quotation. The paper PDFs themselves are not in this repository and never will be.

Where a paper's only record of something is a figure we may not copy, the app says so plainly rather than inventing a substitute: the KRAS paper's model of its final compound is described and not shown, because no coordinates exist for it.

## ✅ To Do

- [x] **Harvest pass**: lift the PLIP runner, Mol\* setup, KLIFS layer, Plotly conventions and track rendering from the existing repositories, and record what came from where in `HARVEST.md`
- [x] **Data contract**: long-format measurements, per-paper assay dictionaries, JSON Schema for every artefact, and a provenance gate that fails the build
- [x] **CDK2 end to end**: 18 compounds, 251 measurements, 8UV0 with PLIP contacts and the KLIFS ruler
- [x] **Blueprint shell**: tokens, sheets with live title blocks, the drawing grammar, `AppState` with URL-hash serialisation
- [x] **Structure, SAR and Properties sheets**: Mol\*, the pocket ruler, motif chips, contact list with measure lines, R-group grid, selectivity matrix, activity cliffs, the three Plotly figures
- [x] **Story and Edit Log**: five beats per paper in two registers, the graphical abstract re-creation drawn from SMILES, change-type filtering
- [x] **All four papers**: FGFR, KRAS and JAK1 curated, including the non-KLIFS path and the twin-structure anti-target
- [x] **Verification**: OPSIN name-to-structure checking, `molzip` fragment assembly, 67 browser checks, the copy gate
- [x] **About sheet**: the pipeline in six stages, every tool with its version, licence and DOI, the data sources, and the statement of what is rendered rather than reproduced, all rendered from `data/software.json`
- [x] **Deploy**: nginx and certbot on the droplet, HTTP/2 patched in the form nginx 1.24 wants, asset URLs stamped with their modification times so an immutable cache cannot hide a deploy, and the entry in the mdeller.com launcher
- [x] **In-browser search**: BM25 over this project's own prose and data, indexed once on the Mac and scored in the page, with "not stated in this project" as a first-class answer. Embeddings were the plan, but a static site cannot embed the query without a server or a model shipped to the page
- [ ] **Short molecular dynamics**: an RMSF track on the ruler and a decimated trajectory per primary structure, and no trajectory ships that does not support what the paper claims
- [x] **PyMOL downloads**: a `.pml` script, a `.pse` session and a still image per structure, on the Structure sheet
- [ ] **Performance budget**: first meaningful paint under two seconds cold, under 1.5 MB initial transfer excluding Mol\*, lazy-loaded structures
- [x] **Licence**: MIT. The one dependency that would have forced AGPL-3.0, PyMuPDF, is replaced by pypdfium2; the GPL tools run as subprocesses only; the vendored libraries carry their notices. See `THIRD_PARTY.md`

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
| [gemmi](https://gemmi.readthedocs.io/) | mmCIF handling | MPL-2.0 |
| [biotite](https://www.biotite-python.org/) | Structure handling | BSD-3-Clause |
| [DSSP](https://github.com/PDB-REDO/dssp) | Secondary structure | BSD-2-Clause |
| [Open Babel](https://openbabel.org/) | Chemical perception inside PLIP | GPL-2.0, reached only inside the PLIP subprocess |
| [PyMOL](https://github.com/schrodinger/pymol-open-source) | The downloadable script, session and still per structure | Open-Source PyMOL licence, invoked as a subprocess |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Text and page images out of the PDFs, on the Mac only | BSD-3-Clause / Apache-2.0 |
| [Mol\*](https://molstar.org/) | The structure viewer | MIT |
| [Plotly.js](https://plotly.com/javascript/) | Every figure | MIT |
| [RDKit.js](https://github.com/rdkit/rdkit-js) | In-browser depiction and highlighting | BSD-3-Clause |
| [KLIFS](https://klifs.net/) | Kinase pocket numbering | Academic use |
| [RCSB PDB](https://www.rcsb.org/) | All coordinates | Public domain |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Reference drug structures | Public domain |

GATECRASHER is released under the [MIT licence](LICENSE). Versions, roles, references and the licence notices for the vendored libraries are in [`THIRD_PARTY.md`](THIRD_PARTY.md), which is generated from the same `data/software.json` the About sheet renders.

---

Built by [Marc C. Deller, D.Phil.](https://marcdeller.com) · [marc@marcdeller.com](mailto:marc@marcdeller.com)
