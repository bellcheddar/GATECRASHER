"""PyMOL deliverables: a script, a session and a still image per structure.

BUILD_SPEC 7.2 and Stage 4. The point of these is that a structural biologist can take the
view away and keep working in their own tools rather than being trapped in a web page.

The `.pml` is written to be portable: it fetches the entry from RCSB rather than depending
on a local file, so it runs on anyone's machine. The `.pse` and the `.png` are built here,
headless, from the mmCIF already in the cache.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import paths, struct

# The motif colours are the app's own, so a session opened in PyMOL looks like the page it
# came from. Kept in sync with web/css/blueprint.css by hand: there are eight of them.
MOTIF_COLOURS = {
    "gatekeeper": "0xFFD166",
    "hinge": "0x6FD3FF",
    "DFG": "0xC792EA",
    "catalytic_lys": "0x7FDBCA",
    "glycine_rich_loop": "0x9BB8D3",
    "P_loop": "0x9BB8D3",
    "switch_I": "0x7FDBCA",
    "switch_II": "0xC792EA",
    "solvent_front": "0x8FB4CF",
    "front_pocket": "0x6FD3FF",
    "back_pocket": "0xFFB4A2",
    "mutation_site": "0xFF6FA5",
}


def _pymol() -> str | None:
    return shutil.which("pymol") or shutil.which("/opt/homebrew/bin/pymol")


def script_for(entry: dict, residues: list[dict], ligand_code: str | None) -> str:
    """A standalone .pml a reader can run anywhere, with our motif colouring."""
    pdb_id = entry["pdb_id"]
    chain = entry["chain"]
    lines = [
        f"# GATECRASHER: {pdb_id}, {entry['contains']['protein']}",
        "#",
        "# Runs anywhere: it fetches the entry from RCSB rather than needing a local file.",
        "#   pymol " + f"{pdb_id.lower()}_gatecrasher.pml",
        "#",
        "# The residue colouring is this campaign's own motif assignment, the same one the",
        "# web app uses, so the two views match.",
        "",
        "reinitialize",
        "set assembly, 1",
        f"fetch {pdb_id}, async=0",
        "hide everything",
        "bg_color white",
        "set ray_opaque_background, 0",
        "set cartoon_transparency, 0.15",
        "set ray_shadows, 0",
        "set antialias, 2",
        "",
        "# One copy only. A deposited entry holds whatever the crystal packed into its",
        "# asymmetric unit, which here is often two copies of the same kinase: a dimer of",
        "# crystallisation rather than of biology. The second copy is removed outright, not",
        "# just hidden, so a ligand selection cannot pick up its twin and `within` cannot",
        f"# measure to it. A real hetero partner would be a different chain and kept.",
        f"remove not (chain {chain})",
        "",
        f"select protein_chain, {pdb_id} and polymer and chain {chain}",
        "show cartoon, protein_chain",
        "color grey80, protein_chain",
        "",
    ]

    if ligand_code:
        lines += [
            f"select ligand, {pdb_id} and resn {ligand_code}",
            "show sticks, ligand",
            "color yellow, ligand and elem C",
            "util.cnc ligand",
            "",
            "# Everything within 5 A of the ligand, which is the pocket the paper discusses.",
            "select pocket, byres (protein_chain within 5 of ligand)",
            "show sticks, pocket and sidechain",
            "set stick_radius, 0.12, pocket",
            "",
        ]

    by_motif: dict[str, list[int]] = {}
    for row in residues:
        if row["pdb_id"] != pdb_id or row["motif"] == "other":
            continue
        by_motif.setdefault(row["motif"], []).append(row["resnum"])

    for motif, numbers in sorted(by_motif.items()):
        colour = MOTIF_COLOURS.get(motif, "0x8FB4CF")
        selection = "+".join(str(n) for n in sorted(numbers))
        name = f"motif_{motif}"
        lines += [
            f"select {name}, protein_chain and resi {selection}",
            f"color {colour}, {name}",
            f"show sticks, {name} and sidechain",
        ]
    lines.append("")

    if ligand_code:
        lines += ["orient ligand", "zoom ligand, 6"]
    else:
        lines += ["orient protein_chain"]

    lines += [
        "deselect",
        "",
        "# Uncomment for a figure-quality render (slow):",
        "# set ray_trace_mode, 1",
        # One command per line. PyMOL splits a line on ';' before it treats '#' as a comment,
        # so "# ray 2000, 1500; png x.png" ran the png half: every build left a stray still
        # in the working directory, and so would every visitor's copy of this script.
        "# ray 2000, 1500",
        f"# png {pdb_id.lower()}.png, dpi=300",
        "",
    ]
    return "\n".join(lines)


def build(slug: str) -> dict:
    """gc figures: .pml, .pse and a still per structure, into build/<slug>/figures/."""
    slug = paths.check_slug(slug)
    entries = json.loads((paths.raw_dir(slug) / "structures.json").read_text())
    residues_csv = paths.build_dir(slug) / "residues.csv"
    if not residues_csv.exists():
        raise SystemExit(f"{slug}: run gc struct first, residues.csv is missing")

    import csv
    with residues_csv.open() as fh:
        residues = [{**row, "resnum": int(row["resnum"])} for row in csv.DictReader(fh)]

    out_dir = paths.build_dir(slug) / "figures"
    out_dir.mkdir(exist_ok=True)
    report = {"scripts": 0, "sessions": 0, "stills": 0, "problems": []}
    pymol = _pymol()

    for entry in entries:
        pdb_id = entry["pdb_id"]
        ligand = (entry.get("contains") or {}).get("ligand_code")
        pml = out_dir / f"{pdb_id.lower()}_gatecrasher.pml"
        pml.write_text(script_for(entry, residues, ligand))
        report["scripts"] += 1

        if not pymol:
            report["problems"].append("pymol not found: no session or still written")
            continue

        # Build the session from the cached mmCIF rather than fetching again, and save both
        # the .pse and a still. PyMOL is run headless with -cq so it never opens a window.
        cif = struct.fetch_cif(pdb_id)
        pse = out_dir / f"{pdb_id.lower()}_gatecrasher.pse"
        png = out_dir / f"{pdb_id.lower()}.png"
        local = script_for(entry, residues, ligand).replace(
            f"fetch {pdb_id}, async=0", f'load {cif}, {pdb_id}')
        with tempfile.NamedTemporaryFile("w", suffix=".pml", delete=False) as fh:
            fh.write(local)
            fh.write(f"\nsave {pse}\n")
            # The still is a FALLBACK for readers without WebGL, not the deliverable: the
            # .pse is what a structural biologist actually wants. At 1400x1050 and 150 dpi
            # these came out at 0.5 to 0.9 MB each and pushed the FGFR bundle to 4 MB,
            # over the 3 MB per-paper budget, for an image nobody looks at when the viewer
            # works. 1000x750 at 96 dpi is ample for a fallback.
            fh.write(f"png {png}, width=1000, height=750, dpi=96, ray=0\n")
            script_path = fh.name
        try:
            subprocess.run([pymol, "-cq", script_path], check=True,
                           capture_output=True, timeout=300)
            if pse.exists():
                report["sessions"] += 1
            if png.exists():
                report["stills"] += 1
        except subprocess.CalledProcessError as err:
            report["problems"].append(
                f"{pdb_id}: pymol failed: {err.stderr.decode()[:200]}")
        except subprocess.TimeoutExpired:
            report["problems"].append(f"{pdb_id}: pymol timed out")
        finally:
            Path(script_path).unlink(missing_ok=True)

    return report
