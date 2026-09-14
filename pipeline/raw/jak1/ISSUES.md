# JAK1 bundle: data issues and decisions

Zhuo et al., *J. Med. Chem.* 2026, drug annotation. DOI 10.1021/acs.jmedchem.5c03753.

## BUILD_SPEC 9.5 item 1: the PDB codes. Resolved against RCSB.

1. **The codes are `10PI` and `10PJ`, with the digit one and the digit zero.**
   The paper prints them as `1OPI` and `1OPJ` in one place, which would be the letter O, and
   both of those are real, unrelated entries: `1OPI` is a solution structure of a U2AF65 RNA
   recognition motif, and `1OPJ` is the auto-inhibited form of c-Abl. Neither has anything to
   do with JAK. Searching RCSB for povorcitinib and for INCB054707 returns `10PI` and `10PJ`,
   both titled "JAK1 kinase (JH1 domain) in complex with povorcitinib" and the JAK2
   equivalent, at 1.54 and 1.59 A, and both containing ligand `A1C68`, which is povorcitinib.
   The bundle uses the verified codes and never the letter-O forms.

## BUILD_SPEC 9.5 item 4: murine or rat? The methods say rat.

2. **The abstract and the conclusions say "murine arthritis models"; the model described in
   the methods is an adjuvant-induced arthritis model in RATS.** The text is explicit:
   "the adjuvant-induced arthritis (AIA) model in rats", and the histopathology work is "an
   AIA rat model". Rats are not mice. The bundle and every caption in the app say rat, per
   BUILD_SPEC 9.5 item 4, and the paper's own wording is recorded here rather than repeated.

## The selectivity explanation is a hypothesis, and is labelled as one

3. **The authors call their own structural explanation speculative, twice.** The P-loop
   argument, JAK1's His885 pointing at solvent against JAK2's Asn859 bending into the pocket
   and hydrogen bonding Glu1015, plus JAK2's Phe860 closing the space, is offered as
   "hypothesised" and "these observations are speculative and under further investigation".
   The app marks every statement of it as the authors' hypothesis. This is exactly what the
   provenance rail is for: the data is a measurement, the explanation is a proposal, and the
   difference is visible.

4. **The paper numbers the JAK1 hinge with JAK2's residue numbers.** The text names the hinge
   Glu930 and Leu932 while describing both isoforms. That is right for JAK2: in 10PJ, 930 is
   GLU and 932 is LEU. It is wrong for JAK1: in 10PI, 930 is ARG, and the hinge is 957 GLU,
   958 PHE, 959 LEU against JAK2's 930 GLU, 931 TYR, 932 LEU. PLIP finds the ligand hydrogen
   bonding LEU959 of 10PI, which is the contact the paper calls Leu932. The offset is +27 at
   the hinge and +26 at the P-loop (JAK1 His885 is JAK2 Asn859, JAK1 Phe886 is JAK2 Phe860),
   so no single offset converts one numbering into the other.

   This app uses each entry's own deposited numbering and says so wherever the paper's
   numbers differ. Both readings are kept: the caption names Glu957 and Leu959 and records
   that the paper calls them Glu930 and Leu932.

   Corrected on 2026-09-14. Until then `motifs.tsv` annotated 10PI residues 930 and 932 as
   the JAK1 hinge, which marked an arginine as a hinge residue, and gave the JAK1 DFG
   aspartate as Asp1042. The DFG is 1021 ASP, 1022 PHE, 1023 GLY; 1042 is an unrelated
   aspartate. `motifs.tsv` scopes every row to its structure with a `pdb_id` column, because
   without that scoping JAK1's His885 would be stamped onto whatever JAK2 has at 885 (it is
   a glutamine).

## The contact list is shorter than the caption, and the caption is right

4b. **PLIP does not report the pyrazole NH donation to the hinge glutamate.** The captions
   describe two hinge hydrogen bonds, and the deposited coordinates carry both: in 10PI the
   Glu957 backbone carbonyl is 2.81 A from ligand nitrogen N6, and Leu959's backbone amide
   is 2.93 A from N5. In 10PJ the same pair is 2.91 A to Glu930 and 2.96 A from Leu932. PLIP
   lists only the leucine half in either structure.

   The likely reason is the tautomer: a deposited structure carries no hydrogens, and the
   3,5-dimethylpyrazole's NH can be placed on either ring nitrogen. PLIP appears to put it on
   the nitrogen that accepts from the leucine, which leaves the donation to the glutamate
   with no hydrogen to donate. The distances are measured here rather than asserted, and the
   contact list ships exactly as PLIP produced it: the app never hand-adds a contact.

## KLIFS has not indexed these structures yet

5. **JAK1 and JAK2 are kinases, but `klifs` is false for both structures in this bundle.**
   KLIFS knows both kinases and has 85-position pocket definitions for them, but 10PI and
   10PJ are too recently deposited to appear in its structure list, so there is no pocket
   mapping to fetch for these particular entries. Setting `klifs: true` would claim a pocket
   index the bundle does not have and leave the ruler with 85 empty affordances.

   The flag therefore says false, the ruler runs off the sequence exactly as it does for
   KRAS, and the motifs come from the hand-curated table. Nothing about the app implies a
   pocket numbering that is not there. When KLIFS indexes these entries the flag can be
   turned back on and `gc struct` will pick the mapping up with no other change.

   This is also why `residues with motif` is 11 here against 61 for FGFR: every motif in
   this bundle is hand-assigned from the paper's own text, rather than inherited from a
   pocket definition covering 85 positions.

## Scope

5. **Table 3 is deliberately not in this bundle.** It lists two earlier in-house compounds,
   an approved c-Met inhibitor and a clinical 11-beta-HSD1 inhibitor, as precedent for the
   intramolecular hydrogen bonding tactic. They are not compounds of this campaign and they
   act on entirely different targets, so including them would put two unrelated drugs in the
   SAR table. The precedent itself is told in the Story.

6. **Compounds 10 to 13 do not appear in the paper's main tables.** The numbering jumps from
   9 to 14 in Table 4 because 11 and 13 are the Table 3 precedent compounds. There is no gap
   in this bundle's data: those numbers simply belong to other molecules.

## Transcription and blanks

7. **Table 1 is laid out with compounds as columns and assays as rows**, the opposite of
   every other table in this set, and was transcribed accordingly. Compound 4 has no whole
   blood, selectivity or clearance data published: those cells are empty, not zero.

8. **Compounds 14 and 17 have incomplete cynomolgus data**, and compound 14 has none at all.
   Empty cells stay empty.

9. **Doses differ between rows and between tables.** Compound 9 appears in Tables 1, 2 and 4
   with consistent values, and its PK rows carry different doses in different tables, so each
   row keeps its own dose note and no AUC is compared across rows without it.

10. **The IL-2 T cell value is published as a range**, 10 to 30 nM across pSTAT3, pSTAT5 and
    proliferation. It is stored as its midpoint with the range recorded in the row's note,
    because a range cannot be plotted and must not be silently narrowed to one end.

## Chemistry

11. **Povorcitinib is verified twice.** Its structure matches the deposited chemical component
    `A1C68` found in both 10PI and 10PJ, and PubChem's povorcitinib, including the
    (2S) stereocentre of the trifluoropropan-2-yl amide. The Table 4, 5 and 6 series is built
    from that verified core by molzip, changing only the hinge binder, the two aryl fluorines
    and the amide substituent.

12. **The Table 1 scaffolds (compounds 4 to 8) are figure-derived.** They appear only as a
    composite drawing with three shared cores and six capping groups, with no IUPAC names in
    the main text and no coordinates. They are flagged as such in `compounds.tsv`, and they
    are the least certain identities in this bundle.
