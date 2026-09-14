# GATECRASHER: 4K33, FGFR3
#
# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.
#   pymol 4k33_gatecrasher.pml
#
# The residue colouring is this campaign's own motif assignment, the same one the
# web app uses, so the two views match.

reinitialize
set assembly, 1
fetch 4K33, async=0
hide everything
bg_color white
set ray_opaque_background, 0
set cartoon_transparency, 0.15
set ray_shadows, 0
set antialias, 2

# One copy only. A deposited entry holds whatever the crystal packed into its
# asymmetric unit, which here is often two copies of the same kinase: a dimer of
# crystallisation rather than of biology. The second copy is removed outright, not
# just hidden, so a ligand selection cannot pick up its twin and `within` cannot
# measure to it. A real hetero partner would be a different chain and kept.
remove not (chain A)

select protein_chain, 4K33 and polymer and chain A
show cartoon, protein_chain
color grey80, protein_chain

select ligand, 4K33 and resn ACP
show sticks, ligand
color yellow, ligand and elem C
util.cnc ligand

# Everything within 5 A of the ligand, which is the pocket the paper discusses.
select pocket, byres (protein_chain within 5 of ligand)
show sticks, pocket and sidechain
set stick_radius, 0.12, pocket

select motif_DFG, protein_chain and resi 634+635+636+637
color 0xC792EA, motif_DFG
show sticks, motif_DFG and sidechain
select motif_back_pocket, protein_chain and resi 532+533+536+537+538+539+540+638+639
color 0xFFB4A2, motif_back_pocket
show sticks, motif_back_pocket and sidechain
select motif_catalytic_lys, protein_chain and resi 517
color 0x7FDBCA, motif_catalytic_lys
show sticks, motif_catalytic_lys and sidechain
select motif_front_pocket, protein_chain and resi 559+560+561+562+571
color 0x6FD3FF, motif_front_pocket
show sticks, motif_front_pocket and sidechain
select motif_gatekeeper, protein_chain and resi 555+564
color 0xFFD166, motif_gatekeeper
show sticks, motif_gatekeeper and sidechain
select motif_glycine_rich_loop, protein_chain and resi 479+480+481+482+483+484
color 0x9BB8D3, motif_glycine_rich_loop
show sticks, motif_glycine_rich_loop and sidechain
select motif_hinge, protein_chain and resi 556+557+558+565+566+567
color 0x6FD3FF, motif_hinge
show sticks, motif_hinge and sidechain

orient ligand
zoom ligand, 6
deselect

# Uncomment for a figure-quality render (slow):
# set ray_trace_mode, 1
# ray 2000, 1500
# png 4k33.png, dpi=300
