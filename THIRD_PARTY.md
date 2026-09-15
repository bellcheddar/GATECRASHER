# Third-party software

GATECRASHER itself is MIT licensed (see `LICENSE`). This file lists everything it uses,
what it uses it for, and under what licence.

**Nothing copyleft is linked into this project.** PLIP is GPL-2.0 and Open Babel, which it
loads, is GPL-2.0: PLIP is invoked as a subprocess and never imported, so neither is
linked into our code, and neither is redistributed. PyMOL is likewise run as a subprocess.
The molecular dynamics stack sits behind the same boundary: OpenMM is LGPL-3.0-or-later
and MDTraj is LGPL-2.1-or-later, and both are imported only inside `pipeline/md/`, which
runs under a different interpreter launched as a subprocess. No module of `gcrash` imports
either, nothing they produce carries their code, and no trajectory tool reaches the browser.
PDF handling uses pypdfium2 rather than PyMuPDF, because PyMuPDF is AGPL-3.0 and this
pipeline imports its PDF library.

**Precompute** tools run on the Mac and never ship. **Browser** libraries are vendored in
`web/js/vendor/` and served from this app's own origin, each with its upstream licence
text beside it, as their licences require.

This file is generated from `web/data/software.json` by `gc third-party`. Edit that file,
not this one.


## Precompute

| Tool | Version | Role | Licence | Reference |
|---|---|---|---|---|
| [RDKit](https://www.rdkit.org/) | 2026.3.6 | Descriptors, maximum common substructure, core-aligned depictions, fragment assembly with molzip | BSD-3-Clause |  |
| [OPSIN](https://github.com/dan2097/opsin) | 1.2.0 | Parsing the papers' own IUPAC names into structures, to verify every hand-built SMILES by connectivity rather than by formula | MIT | [10.1186/1758-2946-3-41](https://doi.org/10.1186/1758-2946-3-41) |
| [PLIP](https://github.com/pharmai/plip) | 3.0.1 | Protein-ligand interaction profiling: every distance drawn in the app comes from here | GPL-2.0, invoked as a subprocess and never imported | [10.1093/nar/gkab294](https://doi.org/10.1093/nar/gkab294) |
| [gemmi](https://gemmi.readthedocs.io/) | 0.7.5 | mmCIF parsing and structure handling | MPL-2.0 | [10.21105/joss.04200](https://doi.org/10.21105/joss.04200) |
| [biotite](https://www.biotite-python.org/) | 1.7.1 | Sequence and structure handling | BSD-3-Clause | [10.1186/s12859-018-2367-z](https://doi.org/10.1186/s12859-018-2367-z) |
| [DSSP](https://github.com/PDB-REDO/dssp) | 4 | Secondary structure assignment, collapsed to helix, strand and loop | BSD-2-Clause | [10.1002/bip.360221211](https://doi.org/10.1002/bip.360221211) |
| [PDB-Tools](http://www.bonvinlab.org/pdb-tools/) | 2.7.0 | Tidying coordinates before interaction profiling | Apache-2.0 | [10.12688/f1000research.17456.1](https://doi.org/10.12688/f1000research.17456.1) |
| [Open Babel](https://openbabel.org/) | 3.2.1 | Chemical perception inside PLIP | GPL-2.0, reached only inside the PLIP subprocess | [10.1186/1758-2946-3-33](https://doi.org/10.1186/1758-2946-3-33) |
| [PyMOL](https://github.com/schrodinger/pymol-open-source) | 3.1.0 | The downloadable script, session and still image for each structure | Open-Source PyMOL licence (BSD-style), invoked as a subprocess |  |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | 5.13.0 | Text and page images out of the paper PDFs, on the Mac only; nothing it produces enters the repository | BSD-3-Clause / Apache-2.0 |  |
| [OpenMM](https://openmm.org/) | 8.5.2 | The molecular dynamics engine for the short per-structure runs | LGPL-3.0-or-later, run under a separate interpreter as a subprocess and never imported | [10.1371/journal.pcbi.1005659](https://doi.org/10.1371/journal.pcbi.1005659) |
| [OpenFF Toolkit](https://github.com/openforcefield/openff-toolkit) | 0.18.0 | Ligand parameters from the Open Force Field small-molecule force field, with AM1-BCC charges | MIT | [10.1021/acs.jctc.1c00571](https://doi.org/10.1021/acs.jctc.1c00571) |
| [PDBFixer](https://github.com/openmm/pdbfixer) | 1.12.0 | Missing atoms and loops rebuilt, and protonation set, before solvation | MIT |  |
| [MDTraj](https://mdtraj.org/) | 1.11.1 | Trajectory analysis: per-residue RMSF, ligand RMSD against the crystal pose, and contact occupancy per frame | LGPL-2.1-or-later, run under a separate interpreter as a subprocess and never imported | [10.1016/j.bpj.2015.08.015](https://doi.org/10.1016/j.bpj.2015.08.015) |

## Browser

| Library | Version | Role | Licence | Notice in `web/js/vendor/` | Reference |
|---|---|---|---|---|---|
| [Archivo Narrow](https://fonts.google.com/specimen/Archivo+Narrow) | v35 | The interface face: labels, tables and the title block | SIL Open Font Licence 1.1 | `fonts/OFL-archivonarrow.txt` |  |
| [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) | v20 | Every measured value, residue label, chip and provenance rail | SIL Open Font Licence 1.1 | `fonts/OFL-ibmplexmono.txt` |  |
| [Newsreader](https://fonts.google.com/specimen/Newsreader) | v26 | The narrative prose, where the register changes typographically as well as verbally | SIL Open Font Licence 1.1 | `fonts/OFL-newsreader.txt` |  |
| [Mol*](https://molstar.org/) | 5.11.0 | The structure viewer, including the camera-locked twin view | MIT | `js/vendor/molstar.LICENSE.txt` | [10.1093/nar/gkab314](https://doi.org/10.1093/nar/gkab314) |
| [Plotly.js](https://plotly.com/javascript/) | 2.35.2 | Every figure, on one shared template; the basic partial bundle, fetched on first use | MIT | `js/vendor/plotly.LICENSE.txt`, and `plotly-basic.min.js.LICENSE.txt` for the libraries it bundles |  |
| [RDKit.js](https://github.com/rdkit/rdkit-js) | 2025.3.4 | Depiction and changed-atom highlighting in the page | BSD-3-Clause | `js/vendor/RDKit_minimal.LICENSE.txt` (RDKit.js and RDKit) |  |

## Data sources

| Source | Used for | Reference |
|---|---|---|
| [RCSB PDB](https://www.rcsb.org/) | Every coordinate file in this app is fetched from RCSB at view time. None is redistributed here. | [10.1093/nar/28.1.235](https://doi.org/10.1093/nar/28.1.235) |
| [KLIFS](https://klifs.net/) | Kinase pocket numbering: the 1 to 85 positions and their region labels, per structure | [10.1093/nar/gkaa895](https://doi.org/10.1093/nar/gkaa895) |
| [PubChem](https://pubchem.ncbi.nlm.nih.gov/) | Structures for the approved comparator drugs, checked against each paper's published formula | [10.1093/nar/gkac956](https://doi.org/10.1093/nar/gkac956) |
