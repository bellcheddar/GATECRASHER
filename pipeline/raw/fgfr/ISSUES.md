# FGFR bundle: data issues and decisions

Shvartsbart et al., *J. Med. Chem.* 2022, 65, 15433-15442. DOI 10.1021/acs.jmedchem.2c01366.

## Resolved, with evidence

1. **BUILD_SPEC 9.5 item 3: FASSIF against FaSSIF. Confirmed.**
   Table 5 prints `FASSIF`, Table 7 prints `FaSSIF`. One assay, two spellings. The assay id is
   normalised to `fassif_solubility` and each source string stays in the table file it came from.

2. **Which compound is in 8E1X, and it is not compound 29.**
   The RCSB entry title reads "FGFR2 kinase domain in complex with a Pyrazolo[1,5-a]pyrimidine
   analog (Compound 29)", while the paper's Figure 3 caption and text both say compound **30**,
   "an analogous compound". The coordinates settle it: the deposited ligand `U9P` is
   *N*-methyl-5-{5-{[(3S)-oxolan-3-yl]amino}-6-[1-(propan-2-yl)-1H-pyrazol-3-yl]pyrazolo[1,5-a]pyrimidin-3-yl}pyridine-3-carboxamide,
   which computes to **C23H26N8O2**. Compound 30's published HRMS is (M+H) C23H24D3N8O2, whose
   non-deuterated equivalent is exactly C23H26N8O2. Compound 29, by contrast, is
   C23H23D3N7O3: seven nitrogens and three oxygens, because its tetrahydrofuran is an **ether**,
   not an **amine**. The ligand therefore is compound 30 and the entry title is loose.
   The bundle records the ligand as compound 30 and the app states this on the structure caption.

3. **Compound 30 differs from the lead in three ways at once**, which is why the paper calls it
   analogous rather than identical: the pyrazole is attached at the 3-position rather than the
   4-position, the tetrahydrofuran is joined through nitrogen rather than oxygen, and the amide
   is N-CD3. Anyone reading the crystal structure as though it were the lead compound would be
   reading three edits too far along the campaign.

4. **Deuterium is not in the deposited model.** Compound 30 is an N-CD3 amide, and `U9P` is
   defined with ordinary hydrogens. X-ray structures at this resolution do not model hydrogen
   positions at all, so this is expected and is not a discrepancy: the depiction shown in the
   app is drawn from the paper's structure, with the deuterium, and the structure viewer shows
   the deposited coordinates.

5. **How each structure in this bundle is verified, and how strongly.**
   The paper names only four final compounds in its Experimental Section (25, 27, 29, 30), so
   the other twenty-three are built by substitution on a shared core. That makes the core the
   thing that has to be right, and both cores are verified independently:

   | Core | Used by | Verified against |
   |---|---|---|
   | imidazo[1,2-b]pyridazine | 4-25 | OPSIN's parse of compound 25's published name, atom for atom |
   | pyrazolo[1,5-a]pyrimidine | 26-30 | OPSIN's parse of compound 27's name, **and** the deposited ligand U9P for compound 30 |

   Compounds 25, 27, 29 and 30 additionally match their published HRMS formulas, deuterium
   included. The remaining compounds rest on a verified core plus a substituent read from the
   table image, and are marked in `compounds.tsv` as core-verified rather than name-verified.

   **A formula check on its own would not have been enough.** The first version of this core
   reproduced compound 25's published molecular formula exactly while having the wrong
   connectivity: in a SMILES prefix fragment the bond to the next atom comes from the
   fragment's last atom, so every cyclic ether had attached through a ring carbon with its
   oxygen left dangling. Same atoms, wrong molecule, identical formula. Only the
   name-to-structure comparison caught it.

6. **Compound 26 has no formula in the main text.** Its HRMS is in the Supporting Information,
   which is not part of this curation, so 26 is core-verified only.

## Dual residue numbering: handled, not hidden

6. **This paper carries two numbering schemes and moves between them without warning.**
   The docking model and all the design discussion are in **FGFR3** numbering; the crystal
   structure is **FGFR2**, because FGFR2 crystallised more readily and compound 30 was confirmed
   equipotent in both. The equivalences are:

   | Role | FGFR3 | FGFR2 (in 8E1X) |
   |---|---|---|
   | Hinge | Ala558 | Ala567 |
   | Catalytic lysine | Lys508 | Lys517 |
   | Gatekeeper | Val555 | Val564 |
   | Lower hinge asparagine, the designed hydrogen bond | Asn562 | Asn571 |

   `residues.csv` is in the deposited FGFR2 numbering, because that is what the coordinates say.
   The FGFR3 equivalent is carried in `role_note` for each of these residues so both appear in
   the app, which is what BUILD_SPEC 9.2 asks for: handle it, do not hide it.

## Blanks that are real

7. **Table 4 has genuinely empty cells**, not missing transcription: compound 20 has no R3
   value because its amide ring is a pyridine rather than a substituted benzene, and the V555L
   and V555M columns are empty for compounds 20, 5, 21 and 23. Those stay empty, and the
   R-group grid draws them as deliberately empty.

8. **Compound 5 appears in three tables** (1, 2 as compound 6's benzamide counterpart, and 4)
   with consistent values, so it is a single row in `compounds.csv` with measurements from each
   table carrying their own `source_table`.

## Worth knowing when reading the story

9. **The docking model was wrong about the pose and right about the hydrogen bond.**
   Figure 2's model of compound 9 in FGFR3 (built on apo 4K33) predicted the amide reaching the
   gatekeeper. The crystal structure shows the pyridyl ring flipped, with the pyridine nitrogen
   pointing at the gatekeeper instead, which is what explains the V555L and V555M potency losses
   that the lead does show. The designed contact to the asparagine is confirmed. Both the
   prediction and the correction are part of the story and the app shows them as such.

10. **4K33 is not an apo wild-type structure.** The paper describes it as "apo FGFR3" for the
    docking, but the entry is the FGFR3 kinase domain carrying the **K650E** gain-of-function
    mutation, with AMP-PCP and magnesium bound. It is recorded as `source: referenced` with this
    noted, and it is not rendered as though it were the campaign's own structure.

11. **The authors say plainly that modelling failed to explain the FGFR1 selectivity**, twice:
    once for the amide, once for compound 19 against compound 5, since FGFR1 has the same
    asparagine (Asn571). They offer a subtle P-loop or backbone conformational difference as a
    possibility. The app must carry that as the authors' hypothesis, not as an explanation.
