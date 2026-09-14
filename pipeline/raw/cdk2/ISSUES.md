# CDK2 bundle: data issues and decisions

Hummel et al., *J. Med. Chem.* 2024, 67, 3112-3126. DOI 10.1021/acs.jmedchem.3c02287.

Every item here was found while curating `raw/cdk2/` by hand. Nothing in this list is guessed:
where the paper disagrees with itself, both readings are recorded and neither is averaged.

## Resolved during curation

1. **BUILD_SPEC 9.5 item 6: two values in one cell. Confirmed and handled.**
   Table 1 has a single `CDK4/D1 CDK6/D3 (nM)` column holding two numbers, for example `3.2/10`
   for compound 4. It is **not** a value/fold pair: in Table 2 the same isoforms get separate
   columns and compound 4's neighbours read `5/17x`, which *is* value/fold. `table1.tsv` therefore
   splits the Table 1 column into `cdk4_d1_ic50` and `cdk6_d3_ic50`, and only `cdk1_b1_ic50`
   carries a fold in that table. Misreading this would silently invent a 10-fold CDK4 margin
   for compound 4 where the paper reports 3.2 nM and 10 nM absolute.

2. **Table 1 has no fold columns for CDK4 or CDK6, Table 2 has them for every isoform.**
   The published folds are carried across exactly as printed and are never recomputed, so a
   reader comparing the app with the paper sees the same numbers. Where a fold is absent it stays
   absent rather than being derived.

3. **SMILES provenance.** No structure was read off a table image. Compounds 2 to 18 were built
   from the IUPAC names in the Experimental Section, then checked against the molecular formula
   the paper reports for each `(M + H)+`: all 17 match. Compound 17 uses the RCSB chemical
   component `XKU` SMILES verbatim, so the depiction cannot drift from the crystal ligand.
   Compound 1 has no synthesis in the paper and was transcribed from the Figure 2 depiction
   by eye: it is the one identity in this bundle resting on a drawing, and it is flagged in
   `compounds.tsv` `notes`.

4. **Compound 1 is racemic** (published as `(+/-)-1`). The SMILES carries no stereocentre
   configuration, which is correct for a racemate, so any ligand efficiency or property
   calculation treats it as one species.

## Disagreements inside the paper, both readings kept

5. **Compound 9 gastric solubility: text says `>400 ug/mL`, Table 1 says `842 ug/mL`.**
   The table value is used for plotting because it is a measurement rather than a bound, and
   the text reading is recorded here. Same pattern, opposite direction, for compound 5, where
   the table itself prints `>400`: that one stays a bound with its qualifier preserved.

6. **Compound 17 gastric solubility is `>400 ug/mL` in both text and Table 2.** It is a bound,
   not a number, and must not be coerced to 400 in any plot or sort.

7. **Compound 6 whole blood potency: text says `about 5 uM`, Table 1 says `5111 nM`.**
   These agree; the table value is used. Noted only because the text rounds.

## What PLIP reproduces of the published structure description, and what it does not

The paper describes four things about compound 17 in 8UV0. PLIP, run through the vendored
`cif2plip` preparation, reproduces three of them outright:

| Paper's claim | PLIP result |
|---|---|
| The 2-aminopyrimidine makes the hinge binding interaction | Two hydrogen bonds to Leu83, 1.85 A and 2.35 A |
| Sulfonamide oxygens accept from the backbone N-H of Asp86 | Hydrogen bond to Asp86, 2.17 A, protein as donor |
| The tertiary hydroxyl interacts with Asp145 | Hydrogen bond to Asp145, 2.71 A |
| A water-mediated interaction with Lys89 **and** Gln85 | Partly: a water bridge to **Gln85** (2.98 A and 3.06 A legs), plus a **direct** hydrogen bond to Lys89 at 2.93 A |

12. **The Lys89 contact is direct in PLIP's reading, water-mediated in the paper's.**
    Checked against the coordinates independently: water A491 sits within hydrogen-bonding
    distance of both Gln85 NE2 and Lys89 NZ, so the structural claim is sound and the
    difference is one of assignment, not of fact. Both readings are shown in the app: the
    contact list reports what PLIP measured, and the caption states what the authors
    described. Neither is presented as the other.

13. **PLIP calls a salt bridge to Asp86 at 4.96 A.** Compound 17 carries no formal charge at
    that end of the molecule (the piperidine nitrogen is sulfonylated, so it is not basic),
    which makes this assignment doubtful. It is kept because the pipeline does not edit
    PLIP's output, but it is worth knowing before the contact is built into any narrative.

14. **The trifluoromethyl to Phe80 contact does not appear at all.** This is the single most
    important interaction in the campaign's story and PLIP classifies nothing for it: the
    contact is a fluorine pointing at an aromatic face, which falls outside PLIP's
    hydrophobic and pi-stacking criteria. The Structure sheet must therefore draw the Phe80
    relationship from the motif annotation and the paper's own description, not from the
    contact list, and must not imply a measured interaction where there is none.

## Open decisions for review

8. **`change_type` enum extension.** BUILD_SPEC 5.7 fixes the `change_type` vocabulary, but it
   has no term for *adding* a polar group to lower lipophilicity, which is what compounds 10, 11
   and the alcohol of 9 do. `polarity_reduction` means the opposite. Three edits
   (`cdk2-e08`, `cdk2-e09`, `cdk2-e10`) use **`polar_addition`**, an addition to the enum.
   The alternative is to overload `bioisostere`, which would hide the campaign's most repeated
   property move. Flagged for Marc.

9. **OVCAR3 pNPM T199 direction is inverted relative to every other potency column.**
   It is a cellular CDK1 counter-screen, so a *higher* IC50 is the better result.
   `assays.json` marks it `direction: higher_better`. Any generic "lower is better" colour scale
   over potency columns would paint this one exactly wrong.

10. **Table 3 doses differ row by row** (cassette against discrete, and three different oral
    doses). AUC values are not comparable across rows without the footnote, so each row carries
    its own `dose_note` and the Properties sheet must show it beside the PK ladder.

## Not applicable to this bundle

11. BUILD_SPEC 9.5 items 1 to 5 concern the JAK1, KRAS and FGFR bundles and are recorded in
    their own `ISSUES.md` files when those are curated in Stage 3.
