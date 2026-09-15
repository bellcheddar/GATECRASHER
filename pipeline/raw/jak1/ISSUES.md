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

## Short molecular dynamics: the first run measured our mistakes, the second measures the paper

13. **The corrected 5 ns run supports all three claims, and the trajectory is published.** The
    first run supported one of three and was withheld. Both are recorded, because the gap
    between them is the whole point: neither failure was a finding about the paper, and it took
    measuring to prove that rather than assuming it.

    | Claim | Expected | First run | Corrected run | Crystal | Cutoff |
    |---|---|---|---|---|---|
    | `hinge-leu959` | present | 96%, 3.14 A | 100%, 3.05 A | 2.93 A | 3.5 A |
    | `hinge-glu957` | present | 0%, 5.67 A | 100%, 2.83 A | 2.81 A | 3.5 A |
    | `ploop-groove-cf3` | present | 0%, 8.27 A | 98%, 3.22 A | 3.05 A | 4.5 A |

    The glutamate row is the one that settles it. With the NH on the nitrogen that faces
    Glu957 the bond forms in every frame and lands at 2.83 A against 2.81 A in the deposited
    coordinates, agreement to 0.02 A. With the proton on the other nitrogen the bond cannot
    form at all, which is exactly what the first run reported. The leucine contact tightening
    from 96 to 100 per cent is a consequence rather than a coincidence: held against the hinge
    by a real pair of hydrogen bonds, the ligand keeps its partner contact better too.

    Ligand heavy-atom RMSD rose from 0.79 to 1.10 A median. That is noted rather than explained
    away. It sits between FGFR's 0.80 A and the 2.0 A threshold, the two distributions overlap
    heavily, and a different seed with a different tautomer moving 0.3 A is unremarkable at this
    scale. Measured over 5000 ps at 300 K, 250 frames, decimated to 200 for shipping.

    **Neither failure is a finding about the paper. Both are ours, and they are different
    kinds of fault**, which took measuring to separate. An earlier draft of this item blamed
    the force field for the first one. That was wrong, and the correction matters because it
    moves the defect from chemistry into the pipeline.

    **13a. The simulated ligand carried the wrong tautomer, and the pipeline chose it.** The
    deposited coordinates of chain A put ligand N6 2.81 A from the Glu957 carbonyl and N5 2.93
    A from the Leu959 amide: the ordinary pyrazole hinge pair, one NH donating and one lone
    pair accepting. The prepared ligand had its NH on N5, the nitrogen that must accept. The
    run was therefore physically unable to form the Glu957 bond, and reported 0% at a 5.67 A
    median. Leu959 still scored 96% only because that claim measures a heavy-atom N to N
    distance, which is blind to where the proton sits.

    Why it happened: `molecule_from_crystal` maps our verified SMILES onto the crystal atoms by
    substructure match, and for a 3,5-dimethyl-4-aryl pyrazole the two tautomers are the same
    molecule. Moving the `[nH]` across the ring gives an identical canonical SMILES, so the
    spec cannot express which nitrogen donates, and RDKit returns **two symmetry-equivalent
    matches**. The pick is deterministic, not random, which is the better failure: it is
    reproducibly wrong rather than intermittently wrong. Only this ligand is exposed, since the
    other three bundles have no aromatic NH at all.

    **The durable fix has landed.** `molecule_from_crystal` now asks for every equivalent
    mapping rather than the first one, and where more than one survives it lets the receptor
    decide: the mapping that seats this molecule's donors closest to receptor hydrogen-bond
    acceptors wins. For povorcitinib there are 24 equivalent mappings, most of them harmless
    permutations of the trifluoromethyl fluorines, and two that matter. The chosen one puts
    the NH 2.81 A from the Glu957 carbonyl oxygen and leaves the other ring nitrogen, carrying
    no hydrogen, 2.93 A from the Leu959 amide. Both reproduce the deposited distances exactly,
    and the proton is now derived rather than placed by hand.

    The first version of that tie-break was nearly useless and is worth recording. It counted
    every receptor nitrogen and oxygen as a partner, which includes backbone amide nitrogens:
    those already carry a hydrogen, so they donate and cannot accept. Scoring against them put
    the two tautomers 0.12 A apart, which is thinner than the coordinate error being used to
    judge them, so the correct answer won by luck rather than by evidence. Because
    `fix_receptor` has already added hydrogens at pH 7.4, donors can be recognised instead of
    assumed: an oxygen always accepts, a nitrogen accepts only when nothing is bonded to it.
    That drops the partner count from 247 to 155 and widens the margin to 0.80 A.

    The hand-placed proton in `pipeline/cache/md/10PI/A1C68.sdf` is therefore no longer
    load-bearing, and `gc dynamics jak1 --stage prepare` can be run again without quietly
    restoring the inverted tautomer.

    **13b. The CF3 claim named the wrong residue.** It tested His885 at 5.0 A and scored 0% at
    a 8.27 A median while the ligand held a 0.79 A RMSD, and a stationary ligand cannot drift
    past a cutoff. Measured in chain A, the CF3 is 3.05 A from the Phe886 side chain, 3.21 from
    Gly887, 3.39 from His918 and 3.83 from Leu910; His885 is 7.09 A away and PLIP sees it only
    as a water bridge. The groove the caption describes is real and the group sits in it. The
    caption names no residue, and His885 was a proxy chosen here: the measurement was right
    about the distance and wrong about what the distance meant. The claim now names Phe886's
    phenyl ring at 4.5 A.

    **Status: the corrected run finished 2026-09-15 10:26 and the bundle publishes it.** The
    verdict is `supports`, the trajectory ships, and all four bundles validate with no failures
    and no warnings. The `does_not_support` result is kept above rather than deleted, because
    the record of having been wrong is worth more than a tidy file: it is what distinguishes a
    pipeline that can be checked from one that merely agrees with its sources.

    The falsification machinery is sound in both directions and neither direction is decorative.
    It returned `does_not_support` here when the input was broken, and it did not soften that
    verdict to fit the paper. Separately, the KRAS bundle reproduced that paper's own assertion
    of no contact with Asp12 at 0% occupancy. A test that can only ever agree proves nothing;
    this one disagreed, loudly, and was right to, about our own ligand rather than their
    chemistry.
