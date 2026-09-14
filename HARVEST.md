# HARVEST

What GATECRASHER took from the rest of the portfolio, and where it deliberately diverges.
BUILD_SPEC section 3 requires this file so the provenance of the code is as traceable as
the provenance of the data.

## Lifted

| From | What | Where it lives here | Changed? |
|---|---|---|---|
| `CODSWALLOP/pipeline/cif2plip.py` | The whole PLIP runner, above all `renumber_contiguous`, the `pdb_tidy` CONECT serial-gap workaround | `pipeline/gcrash/vendor/cif2plip.py` | No. Byte-identical, called as a library from `struct.py` |
| `CODSWALLOP/codswallop/contacts.py` | The pattern of calling those helpers in order (tidy, renumber, CONECT), and the PATH fix needed when Python is invoked by absolute path | `struct.plip_interactions` | Reimplemented against our cache layout |
| `GOBSMACKED/app/services/interactions.py` | PLIP invoked as a subprocess, never imported (PLIP is GPL-2.0), and the XML parse shape: pick the binding site with the most interactions, read `dist` / `dist_h-a` / `centdist` per group | `struct._parse_plip` | Extended: our records keep chain, resnum and angle, and normalise to our own interaction vocabulary |
| `GOBSMACKED/app/services/annotate.py` | The KLIFS fetch layer and the lesson that kinase name search is fuzzy, so the UniProt accession decides which hit is right | `struct.klifs_pocket` | Diverged, see below |
| `GOBSMACKED/app/static/js/viewer.js` | Mol\* setup and camera control: empty `extensions`, representation before colour, loci built from `atomicHierarchy`, `handleResize` from a `ResizeObserver` | Stage 2 | Pending |
| `GOBSMACKED/app/static/js/sequence_track.js` | SVG residue track with feature bands and slanted labels: the closer ancestor of the KLIFS ruler than ALPHABETTI's DOM ruler | Stage 2 | Pending |
| `GOBSMACKED/app/templates/about.html`, `software.yaml`, `scripts/check_refs.py` | About-tab pipeline schematic, the software and reference table, and checking DOIs against Crossref rather than publisher sites | Stage 4 | Pending |
| `AlphaFraud/alphafraud/report.py` | Plotly layout conventions and the quadrant-scatter idiom | Stage 2 | Pending |
| `AlphaFraud/deploy/` | nginx template with placeholders, static served `immutable` with `?v=mtime`, certbot retried three times, the HTTP/2 patch certbot omits on nginx 1.24 | Stage 4 | Pending |
| `ALPHABETTI/static/js/ui.js` | Residue-indexed track alignment, and `highlight()` scrolling only when the residue is out of view | Stage 2 | Pending |
| `BoltzMaker/BoltzMaker.py` | Input validation approach (per-block field whitelists, errors carrying line numbers) and core-aligned depiction via `GenerateDepictionMatching2DStructure` with a `Compute2DCoords` fallback | `chem.depict`, `validate.py` | Adapted |
| `FlexAppeal/flexappeal/runtime/` | OpenMM setup, minimisation, the restraint ramp, RMSF on CA atoms, and trajectory decimation | Stage 4 | Pending |
| `chatMCD/space/app.py` | The retrieval contract: a measured similarity floor and a "do not guess" answer | Stage 4 | Pending |
| `marcs-vibe-coding` skill | Brand tokens, README house standard, mobile-responsive conventions | Stage 4 | Pending |

## Divergences, and why

1. **The pipeline package is `gcrash`, not `gc`.** BUILD_SPEC section 4 names the package `gc`,
   but `gc` is a Python built-in module and built-in modules always win an import, so
   `from gc import cli` can never resolve to a package on the path. The **command is still
   `gc`**, exactly as the spec requires: only the importable name changed.

2. **`cif_to_plip.py` is really called `cif2plip.py`.** The spec's filename does not exist on
   this machine; the script's own docstring uses the spec's spelling. Four identical copies
   exist and the newest, in CODSWALLOP, is the one vendored here.

3. **KLIFS is asked for the pocket mapping, not aligned against.** GOBSMACKED places the
   85-character pocket string onto the sequence region by region. The
   `interactions_match_residues` endpoint returns the mapping directly, per structure:
   pocket index, crystallographic residue number and region label. That removes the
   guesswork an alignment introduces where a crystal has gaps, and it supplies the region
   labels (`GK`, `hinge`, `g.l`, `DFG`) that our motif vocabulary is derived from. The
   fuzzy-name lesson is still honoured: the UniProt accession picks the kinase.

4. **Mol\* will be vendored, not loaded from cdnjs.** BUILD_SPEC section 2 says a pinned UMD
   build from cdnjs, but cdnjs does not carry Mol\*. GOBSMACKED serves `molstar.js` 5.11.0
   from its own origin, which also satisfies the spec's own Stage 4 rule that no runtime
   request may go anywhere but our origin and the pinned CDNs. Plotly and RDKit.js are
   treated the same way. Each vendored file records its version and source in
   `web/js/vendor/README.md`.

5. **PLIP and OpenBabel are an optional dependency group.** They are awkward on Apple
   silicon: BoltzMaker's pixi notes that solvers try to build OpenBabel from source.
   `openbabel-wheel` plus `pdb-tools` in the `interactions` extra works on Python 3.12 here.
   `pdb_tidy` must be on PATH, which is why `struct.py` prepends the interpreter's own
   `bin/` before shelling out.

6. **`change_type` gains `polar_addition`.** The spec's vocabulary has no term for adding a
   polar group to lower lipophilicity, which is the CDK2 campaign's most repeated property
   move. Recorded in `pipeline/raw/cdk2/ISSUES.md` item 8 for review.

7. **The raw layer keeps one file per published table.** The spec asks for hand-QC'd TSVs;
   this splits them as `table1.tsv`, `table2.tsv`, `table3.tsv`, `figure2.tsv` plus a
   `tables.json` that maps columns to assay ids. Provenance then comes from the file a number
   lives in rather than from a column someone has to remember to fill, and melting to
   long-format `measurements.csv` needs no per-paper code.

8. **No mlx embedding model exists to lift.** The spec's retrieval stack cites `mlx-lm`
   embeddings, but chatPDB embeds with `BAAI/bge-base-en-v1.5` through
   sentence-transformers, and chatMCD with `all-MiniLM-L6-v2` and a measured similarity
   floor of 0.55. Stage 4 will follow chatMCD, and the floor will be measured here rather
   than inherited.

9. **`marcs-vibe-icon` and `marcs-page-icon` do not exist on this machine.** BUILD_SPEC
   section 10 Stage 4 calls for both. Per-project `make_icon.py` scripts exist in ALPHABETTI,
   PfamIE, HAWKER and PUNT; Stage 4 will follow one of those instead.

## Known traps carried forward

- **The CONECT serial gap.** `pdb_tidy` gives the inter-chain TER its own serial and then
  starts the next chain one number too high. OpenBabel maps CONECT records by position, so
  every ligand bond after the gap is dropped: the ligand comes back with wrong bonds and PLIP
  invents interactions, with no error anywhere. Order is tidy, then renumber, then CONECT.
- **Mol\* representation before colour**, or the colour is discarded.
- **Loci indices are positions inside `unit.elements`**, not atom ids. Getting it wrong
  highlights the wrong atoms silently.
- **Mol\* `extensions: []`**, or creating the viewer makes a network request.
- **A blank `access_log off;`** on an mdeller-landing beacon leaves the hit count at zero.
- **Apple OpenCL is single precision only**; asking for `mixed` silently falls back to CPU,
  seven times slower. Relevant to Stage 4's OpenMM run.
- **OpenMM on OpenCL leaks about 3 kB per step** on an M1 Max and only a restart from
  checkpoint in a fresh process reclaims it.
