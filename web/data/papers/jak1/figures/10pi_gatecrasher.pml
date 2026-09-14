# GATECRASHER: 10PI, JAK1
#
# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.
#   pymol 10pi_gatecrasher.pml
#
# The residue colouring is this campaign's own motif assignment, the same one the
# web app uses, so the two views match.

reinitialize
set assembly, 1
fetch 10PI, async=0
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

select protein_chain, 10PI and polymer and chain A
show cartoon, protein_chain
color grey80, protein_chain

select ligand, 10PI and resn A1C68
show sticks, ligand
color yellow, ligand and elem C
util.cnc ligand

# Everything within 5 A of the ligand, which is the pocket the paper discusses.
select pocket, byres (protein_chain within 5 of ligand)
show sticks, pocket and sidechain
set stick_radius, 0.12, pocket

select motif_DFG, protein_chain and resi 1021
color 0xC792EA, motif_DFG
show sticks, motif_DFG and sidechain
select motif_P_loop, protein_chain and resi 885+886
color 0x9BB8D3, motif_P_loop
show sticks, motif_P_loop and sidechain
select motif_hinge, protein_chain and resi 957+958+959
color 0x6FD3FF, motif_hinge
show sticks, motif_hinge and sidechain

orient ligand
zoom ligand, 6
deselect

# Uncomment for a figure-quality render (slow):
# set ray_trace_mode, 1
# ray 2000, 1500
# png 10pi.png, dpi=300
