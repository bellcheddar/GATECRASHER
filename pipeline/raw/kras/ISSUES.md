# KRAS bundle: data issues and decisions

Ye et al., *J. Med. Chem.* 2025, 68, 1924-1939. DOI 10.1021/acs.jmedchem.4c02662.

## BUILD_SPEC 9.5 item 2: the graphical abstract disagrees with the tables. Confirmed, twice.

1. **Compound 10, whole blood pERK: 451 nM in the graphical abstract, 410 nM in Table 1 and
   Figure 4.** Both are recorded. The bundle plots the table value, because that is where the
   assay is reported with its conditions, and the graphical abstract panel displays its own
   number with the table value beside it. Neither is averaged and neither is dropped.

2. **Compound 23, SPR: 2.2 nM in the graphical abstract, 22 nM in Table 3.** A factor of ten,
   which is exactly the kind of difference that looks like a typographical slip and cannot be
   resolved from the paper alone. Both readings are shown, labelled by source. The Story text
   quotes neither as a bare fact: it says the compound trades roughly a thousand-fold of
   binding potency for oral exposure, which is true on either reading.

3. **Selectivity over wild-type KRAS: the text says 50-fold in binding, Table 5 says 45-fold.**
   Same pattern, smaller stakes. Table 5 is used, the text value noted here.

## Structures

4. **Two deposited structures, both used.** 9E5F is compound 3 (ligand A1BEJ, 1.35 A) and
   9E5D is compound 5a, the methyl ester analogue of compound 5 (ligand A1BEI, 1.36 A). The
   paper states this pairing explicitly in the Figure 3 caption, and both deposited ligands
   match those compounds.

5. **The paper's Figure 7 model of compound 23 is NOT shown in this app.** BUILD_SPEC 9.3 asks
   for it to be labelled `source: modelled` and rendered visually distinct, but there are no
   coordinates for it: it exists only as a figure in the paper, and BUILD_SPEC ground rule 3
   forbids reproducing the publisher's figures. Rather than fabricate a model or copy an
   image, the app says plainly that the binding mode of the final compound was inferred from
   the structures of 3 and 5a, and shows those instead. This is a deliberate omission.

6. **KRAS is not a kinase, so there is no KLIFS mapping.** `klifs` is false for both
   structures, `klifs_index` is NA throughout, and every motif in `motifs.tsv` is assigned by
   hand from the standard KRAS regions (P-loop 10-17, switch I 30-40, switch II 60-76) plus
   the residues this paper actually discusses: Asp12, Tyr96 and Gly10. The ruler degrades to
   a plain sequence ruler, with no empty pocket affordances anywhere.

## PLIP against the published figure: same contacts, different convention

13. **The distances in the app are not the distances printed in Figure 3, and both are right.**
    Figure 3 labels heavy-atom distances: Tyr96 at 2.8 A, the bridging water at 2.9 and 3.0,
    Gly10 at 3.1. PLIP reports hydrogen bonds as the donor-hydrogen to acceptor distance, so
    the same Tyr96 contacts come back as 1.82 and 2.19 A. Neither is wrong and they are not
    comparable. The contact list shows what PLIP measured and says so; the captions quote the
    paper's figures and attribute them. Nothing in the app presents one number as the other.

14. **PLIP confirms the paper's structural argument independently.** In 9E5F it finds the
    Tyr96 hydrogen bonds and a water bridge to Gly10, exactly as described. In 9E5D it finds
    a direct hydrogen bond to Asp12 at 1.92 A, which is the backbone contact the 55-fold
    wild-type selectivity is attributed to. It also finds contacts the paper does not
    discuss, including Glu62, Glu63 and Arg102: those are shown as measured, without being
    given a significance the paper never claimed for them.

15. **The five-character ligand codes nearly hid all of this.** `A1BEJ` and `A1BEI` are
    shortened to three characters during PLIP preparation, and the first run reported zero
    interactions for both structures rather than failing. The pipeline now raises an error
    naming the binding sites it did find whenever the requested ligand is not among them,
    because a silent empty contact list on a 1.35 A structure is the most dangerous possible
    output: it looks like an answer.

## Chemistry

7. **Every compound in this paper is atropisomeric.** There is a stable atropisomeric axis
   around the bond joining the core to the Switch II aryl group, and unless stated otherwise
   the paper reports potency for the more potent atropisomer. Compounds 14, 18, 19 and 20 are
   published as mixtures of atropisomers and are flagged in the table files. The SMILES in
   this bundle do not encode atropisomerism: it is a conformational property that SMILES
   cannot express without an explicit stereo bond, so the depictions show the constitution
   and the atropisomer status travels as data.

8. **Compound 5a is not compound 5.** It is the methyl ester analogue, made to get a crystal.
   It is carried as its own compound with `role: tool`, so that nothing in the app implies
   the crystal structure is of the compound whose potency is quoted beside it.

9. **BUILD_SPEC 9.5 item 5: Scheme 5 is captioned "alkyne 40" while the text says "alkyne 38".**
   Confirmed, and out of scope: it concerns a synthetic intermediate that does not appear in
   this bundle. Noted for completeness.

## Blanks and bounds that are real

10. **"N/A" in Tables 1, 2 and 3 means not tested**, not zero and not missing. Those cells are
    left empty and the app draws them as deliberately empty.

11. **Caco-2 values of "<0.1" are a floor, not a measurement.** The paper says no compound in
    the early series had any measurable flux at all. The qualifier travels with the value and
    these points are drawn as bounds, never plotted as 0.1.

12. **Compound 18's non-human primate oral AUC is BQL, below the quantifiable limit.** It is
    recorded as an absent value with its bioavailability of 0 per cent, which is the reported
    result, rather than as a zero AUC that would plot as a real measurement.
