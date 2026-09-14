# GATECRASHER: 8UV0, CDK2
#
# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.
#   pymol 8uv0_gatecrasher.pml
#
# The residue colouring is this campaign's own motif assignment, the same one the
# web app uses, so the two views match.

reinitialize
set assembly, 1
fetch 8UV0, async=0
hide everything
bg_color white
set ray_opaque_background, 0
set cartoon_transparency, 0.15
set ray_shadows, 0
set antialias, 2

select protein_chain, 8UV0 and polymer and chain A
show cartoon, protein_chain
color grey80, protein_chain

select ligand, 8UV0 and resn XKU
show sticks, ligand
color yellow, ligand and elem C
util.cnc ligand

# Everything within 5 A of the ligand, which is the pocket the paper discusses.
select pocket, byres (protein_chain within 5 of ligand)
show sticks, pocket and sidechain
set stick_radius, 0.12, pocket

select motif_DFG, protein_chain and resi 144+145+146+147
color 0xC792EA, motif_DFG
show sticks, motif_DFG and sidechain
select motif_back_pocket, protein_chain and resi 58+59+61+62+63+64+65+148+149
color 0xFFB4A2, motif_back_pocket
show sticks, motif_back_pocket and sidechain
select motif_catalytic_lys, protein_chain and resi 33+51
color 0x7FDBCA, motif_catalytic_lys
show sticks, motif_catalytic_lys and sidechain
select motif_front_pocket, protein_chain and resi 84+85+89
color 0x6FD3FF, motif_front_pocket
show sticks, motif_front_pocket and sidechain
select motif_gatekeeper, protein_chain and resi 80
color 0xFFD166, motif_gatekeeper
show sticks, motif_gatekeeper and sidechain
select motif_glycine_rich_loop, protein_chain and resi 10+11+12+13+14+15+16+17+18
color 0x9BB8D3, motif_glycine_rich_loop
show sticks, motif_glycine_rich_loop and sidechain
select motif_hinge, protein_chain and resi 81+82+83+86
color 0x6FD3FF, motif_hinge
show sticks, motif_hinge and sidechain

orient ligand
zoom ligand, 6
deselect

# Uncomment for a figure-quality render (slow):
# set ray_trace_mode, 1
# ray 2000, 1500
# png 8uv0.png, dpi=300
