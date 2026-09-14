# GATECRASHER: 9E5D, KRAS G12D
#
# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.
#   pymol 9e5d_gatecrasher.pml
#
# The residue colouring is this campaign's own motif assignment, the same one the
# web app uses, so the two views match.

reinitialize
set assembly, 1
fetch 9E5D, async=0
hide everything
bg_color white
set ray_opaque_background, 0
set cartoon_transparency, 0.15
set ray_shadows, 0
set antialias, 2

select protein_chain, 9E5D and polymer and chain A
show cartoon, protein_chain
color grey80, protein_chain

select ligand, 9E5D and resn A1BEI
show sticks, ligand
color yellow, ligand and elem C
util.cnc ligand

# Everything within 5 A of the ligand, which is the pocket the paper discusses.
select pocket, byres (protein_chain within 5 of ligand)
show sticks, pocket and sidechain
set stick_radius, 0.12, pocket

select motif_P_loop, protein_chain and resi 10+11+13+14+15+16+17
color 0x9BB8D3, motif_P_loop
show sticks, motif_P_loop and sidechain
select motif_back_pocket, protein_chain and resi 95+96+99
color 0xFFB4A2, motif_back_pocket
show sticks, motif_back_pocket and sidechain
select motif_mutation_site, protein_chain and resi 12
color 0xFF6FA5, motif_mutation_site
show sticks, motif_mutation_site and sidechain
select motif_switch_I, protein_chain and resi 30+31+32+33+34+35+36+37+38+39+40
color 0x7FDBCA, motif_switch_I
show sticks, motif_switch_I and sidechain
select motif_switch_II, protein_chain and resi 60+61+62+63+64+65+66+67+68+69+70+71+72+73+74+75+76
color 0xC792EA, motif_switch_II
show sticks, motif_switch_II and sidechain

orient ligand
zoom ligand, 6
deselect

# Uncomment for a figure-quality render (slow):
# set ray_trace_mode, 1
# ray 2000, 1500
# png 9e5d.png, dpi=300
