# GATECRASHER: 8E1X, FGFR2
#
# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.
#   pymol 8e1x_gatecrasher.pml
#
# The residue colouring is this campaign's own motif assignment, the same one the
# web app uses, so the two views match.

reinitialize
set assembly, 1
fetch 8E1X, async=0
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

select protein_chain, 8E1X and polymer and chain A
show cartoon, protein_chain
color grey80, protein_chain

select ligand, 8E1X and resn U9P
show sticks, ligand
color yellow, ligand and elem C
util.cnc ligand

# Everything within 5 A of the ligand, which is the pocket the paper discusses.
select pocket, byres (protein_chain within 5 of ligand)
show sticks, pocket and sidechain
set stick_radius, 0.12, pocket

select motif_DFG, protein_chain and resi 643+644+645+646
color 0xC792EA, motif_DFG
show sticks, motif_DFG and sidechain
select motif_back_pocket, protein_chain and resi 541+542+545+546+547+548+549+647+648
color 0xFFB4A2, motif_back_pocket
show sticks, motif_back_pocket and sidechain
select motif_catalytic_lys, protein_chain and resi 517
color 0x7FDBCA, motif_catalytic_lys
show sticks, motif_catalytic_lys and sidechain
select motif_front_pocket, protein_chain and resi 568+569+570+571
color 0x6FD3FF, motif_front_pocket
show sticks, motif_front_pocket and sidechain
select motif_gatekeeper, protein_chain and resi 564
color 0xFFD166, motif_gatekeeper
show sticks, motif_gatekeeper and sidechain
select motif_glycine_rich_loop, protein_chain and resi 488+489+490+491+492+493
color 0x9BB8D3, motif_glycine_rich_loop
show sticks, motif_glycine_rich_loop and sidechain
select motif_hinge, protein_chain and resi 565+566+567
color 0x6FD3FF, motif_hinge
show sticks, motif_hinge and sidechain

orient ligand
zoom ligand, 6
deselect

# Uncomment for a figure-quality render (slow):
# set ray_trace_mode, 1
# ray 2000, 1500
# png 8e1x.png, dpi=300
