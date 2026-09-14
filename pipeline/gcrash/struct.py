"""Structures: mmCIF fetch, DSSP secondary structure, KLIFS pocket numbering, PLIP contacts.

KLIFS is asked for the pocket mapping rather than aligned against by hand: the
interactions_match_residues endpoint returns, per structure, the 1-85 pocket index, the
crystallographic residue number and the KLIFS region label. That removes the guesswork
that an alignment-based mapping introduces when a structure has gaps.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import gemmi
import requests

from . import paths

RCSB_CIF = "https://files.rcsb.org/download/{pdb_id}.cif"
KLIFS = "https://klifs.net/api"
UA = {"User-Agent": "GATECRASHER precompute (marc@marcdeller.com)"}

# KLIFS region prefix -> our motif vocabulary. The endpoint labels every pocket position
# with a region, so the gatekeeper and hinge come from KLIFS rather than from a hard-coded
# residue number that would be wrong for the next kinase.
KLIFS_REGION_MOTIF = {
    "g.l": "glycine_rich_loop",
    "GK": "gatekeeper",
    "hinge": "hinge",
    "linker": "front_pocket",
    "DFG": "DFG",
    "xDFG": "DFG",
    "a.l": "back_pocket",
    "b.l": "back_pocket",
}

DSSP_COLLAPSE = {"H": "H", "G": "H", "I": "H", "P": "H", "E": "E", "B": "E"}


# --------------------------------------------------------------------------- fetch

def fetch_cif(pdb_id: str) -> Path:
    pdb_id = pdb_id.upper()
    out = paths.cache_dir("struct") / f"{pdb_id}.cif"
    if out.exists() and out.stat().st_size > 1000:
        return out
    r = requests.get(RCSB_CIF.format(pdb_id=pdb_id), headers=UA, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


# ----------------------------------------------------------------------------- DSSP

def _mkdssp() -> str:
    for candidate in ("mkdssp", "/Applications/ccp4-9/bin/mkdssp", "/opt/homebrew/bin/mkdssp"):
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    raise SystemExit("mkdssp not found: install DSSP or adjust gcrash/struct.py")


def dssp_sse(cif: Path) -> dict[tuple[str, int], str]:
    """(chain, resnum) -> H | E | L, from the classic DSSP table."""
    out = paths.cache_dir("struct") / f"{cif.stem}.dssp"
    if not out.exists():
        subprocess.run([_mkdssp(), "--output-format", "dssp", str(cif), str(out)],
                       check=True, capture_output=True)
    sse: dict[tuple[str, int], str] = {}
    started = False
    for line in out.read_text(errors="replace").splitlines():
        if line.startswith("  #  RESIDUE"):
            started = True
            continue
        if not started or len(line) < 17:
            continue
        if line[13] == "!":               # chain break marker
            continue
        try:
            resnum = int(line[5:10])
        except ValueError:
            continue
        chain = line[11].strip()
        sse[(chain, resnum)] = DSSP_COLLAPSE.get(line[16], "L")
    return sse


# ---------------------------------------------------------------------------- KLIFS

def klifs_pocket(uniprot: str, gene: str, pdb_id: str, chain: str) -> dict[int, dict]:
    """resnum -> {klifs_index, region}. Empty dict when the target is not a kinase."""
    kinases = _klifs_get("kinase_ID", {"kinase_name": gene, "species": "HUMAN"})
    if not isinstance(kinases, list) or not kinases:
        return {}
    # name search is fuzzy and can return a paralogue, so prefer the UniProt match
    match = next((k for k in kinases if k.get("uniprot") == uniprot), kinases[0])
    structures = _klifs_get("structures_list", {"kinase_ID": match["kinase_ID"]})
    if not isinstance(structures, list):
        return {}
    entries = [s for s in structures
               if s.get("pdb", "").upper() == pdb_id.upper() and s.get("chain") == chain]
    if not entries:
        return {}
    entries.sort(key=lambda s: (s.get("alt") or "", -float(s.get("quality_score") or 0)))
    rows = _klifs_get("interactions_match_residues", {"structure_ID": entries[0]["structure_ID"]})
    if not isinstance(rows, list):
        return {}
    mapping: dict[int, dict] = {}
    for row in rows:
        pos = str(row.get("Xray_position", "")).strip()
        if not pos or pos == "-":          # a pocket position with no residue in this crystal
            continue
        try:
            resnum = int(pos)
        except ValueError:
            continue
        region = str(row.get("KLIFS_position", ""))
        mapping[resnum] = {
            "klifs_index": int(row["index"]),
            "region": region,
            "motif": _region_motif(region),
        }
    return mapping


def _region_motif(region: str) -> str:
    prefix = region.rsplit(".", 1)[0] if "." in region else region
    return KLIFS_REGION_MOTIF.get(prefix, KLIFS_REGION_MOTIF.get(region, "other"))


def _klifs_get(endpoint: str, params: dict):
    r = requests.get(f"{KLIFS}/{endpoint}", params=params, headers=UA, timeout=60)
    if r.status_code == 400:
        return None
    r.raise_for_status()
    return r.json()


# -------------------------------------------------------------------------- residues

def residues(slug: str, entry: dict, sse: dict, pocket: dict, overrides: dict) -> list[dict]:
    """One row per polymer residue of the named chain, annotated with sse, KLIFS and motif."""
    cif = fetch_cif(entry["pdb_id"])
    st = gemmi.read_structure(str(cif))
    st.setup_entities()
    chain_id = entry["chain"]
    chain = st[0][chain_id]
    if chain is None:
        raise SystemExit(f"{entry['pdb_id']}: no chain {chain_id}")
    rows = []
    for res in chain:
        info = gemmi.find_tabulated_residue(res.name)
        if not (info and info.is_amino_acid()):
            continue
        resnum = res.seqid.num
        klifs = pocket.get(resnum)
        override = overrides.get(f"{chain_id}:{resnum}", {})
        rows.append({
            "pdb_id": entry["pdb_id"],
            "chain": chain_id,
            "resnum": resnum,
            "resname": res.name,
            "sse": sse.get((chain_id, resnum), "L"),
            "klifs_index": klifs["klifs_index"] if klifs else "NA",
            "motif": override.get("motif") or (klifs["motif"] if klifs else "other"),
            "role_note": override.get("role_note") or (klifs["region"] if klifs else None),
        })
    return rows


def read_overrides(slug: str) -> dict:
    """Optional hand-curated motif table: required for KRAS, which has no KLIFS mapping."""
    path = paths.raw_dir(slug) / "motifs.tsv"
    if not path.exists():
        return {}
    out = {}
    with path.open() as fh:
        for row in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            key = f"{row['chain'].strip()}:{int(row['resnum'])}"
            out[key] = {"motif": row["motif"].strip(),
                        "role_note": (row.get("role_note") or "").strip() or None}
    return out


# ------------------------------------------------------------------------------ PLIP

def _vendor():
    """Load the vendored cif2plip helpers, which carry the CONECT serial-gap workaround."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cif2plip", Path(__file__).parent / "vendor" / "cif2plip.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def plip_interactions(pdb_id: str, ligand_code: str) -> dict:
    """Run PLIP on a tidied, renumbered PDB and normalise the XML to our schema.

    The order tidy -> renumber -> CONECT matters: pdb_tidy gives the inter-chain TER its own
    serial and then starts the next chain one number too high, and OpenBabel maps CONECT
    records by position, so without the renumber step every ligand bond after the gap is
    silently dropped and the interaction list comes back quietly wrong.
    """
    v = _vendor()
    cif = fetch_cif(pdb_id)
    work = Path(tempfile.mkdtemp(prefix=f"plip_{pdb_id}_"))
    st, chain_map, resname_map, ligand_resnames = v.remap_structure(str(cif))
    raw_pdb = work / "raw.pdb"
    v.write_pdb(st, str(raw_pdb))

    env = dict(os.environ)
    env["PATH"] = f"{Path(sys.executable).parent}:{env.get('PATH', '')}"
    tidied = work / "tidy.pdb"
    with tidied.open("w") as out:
        subprocess.run(["pdb_tidy", str(raw_pdb)], check=True, stdout=out, env=env)

    v.renumber_contiguous(str(tidied))
    v.add_ligand_conect(str(tidied), ligand_resnames)

    subprocess.run([sys.executable, "-m", "plip.plipcmd", "-f", str(tidied),
                    "-x", "-o", str(work), "--name", "report"],
                   check=True, capture_output=True, timeout=600, env=env)
    return _parse_plip(work / "report.xml", pdb_id, ligand_code, resname_map)


PLIP_TYPES = {
    "hydrogen_bonds": "hbond",
    "hydrophobic_interactions": "hydrophobic",
    "pi_stacks": "pi_stack",
    "salt_bridges": "salt_bridge",
    "water_bridges": "water_bridge",
    "halogen_bonds": "halogen",
    "pi_cation_interactions": "pi_cation",
}


def _parse_plip(xml_path: Path, pdb_id: str, ligand_code: str, resname_map: dict) -> dict:
    import xml.etree.ElementTree as ET

    # the vendored remapper shortens long residue names, so map back to the published code
    inverse = {v: k for k, v in (resname_map or {}).items()}
    wanted = {ligand_code.upper(), inverse.get(ligand_code.upper(), ligand_code).upper()}
    for short, full in (resname_map or {}).items():
        if full.upper() == ligand_code.upper():
            wanted.add(short.upper())

    root = ET.parse(xml_path).getroot()
    best: tuple[int, list[dict], str, str] = (0, [], "", "")
    for site in root.iter("bindingsite"):
        hetid = (site.findtext("identifiers/hetid") or "").upper()
        if wanted and hetid not in wanted:
            continue
        rows: list[dict] = []
        for group, kind in PLIP_TYPES.items():
            for node in site.iter(group[:-1] if group.endswith("s") else group):
                # Each interaction type names its distance differently, and a water bridge
                # names TWO: acceptor-to-water and donor-to-water. Reading only dist,
                # dist_h-a and centdist silently drops every water bridge, which in 8UV0
                # meant losing the Gln85 contact the paper builds its argument on.
                dist = (node.findtext("dist") or node.findtext("dist_h-a")
                        or node.findtext("centdist") or node.findtext("dist_a-w"))
                if dist is None:
                    continue
                try:
                    resnum = int(node.findtext("resnr") or "0")
                except ValueError:
                    continue
                row = {
                    "type": kind,
                    "residue": (node.findtext("restype") or "").strip(),
                    "chain": (node.findtext("reschain") or "").strip(),
                    "resnum": resnum,
                    "ligand_atom": node.findtext("ligcarbonidx") or node.findtext("acceptoridx")
                                   or node.findtext("donoridx"),
                    "protein_atom": node.findtext("protcarbonidx"),
                    "distance_a": round(float(dist), 2),
                    "angle_deg": _maybe_float(node.findtext("angle") or node.findtext("don_angle")
                                              or node.findtext("water_angle")),
                    "protein_is_donor": _maybe_bool(node.findtext("protisdon")),
                }
                # Coordinates are what the amber measure line is drawn between, so a contact
                # without them can be listed but never drawn. PLIP gives both endpoints.
                lig_xyz = _coords(node.find("ligcoo"))
                prot_xyz = _coords(node.find("protcoo"))
                if lig_xyz:
                    row["ligand_coords"] = lig_xyz
                if prot_xyz:
                    row["protein_coords"] = prot_xyz
                if kind == "water_bridge":
                    # The measure line for a water bridge is drawn in two legs, so both
                    # distances and the bridging water travel with the record.
                    row["distance_donor_water_a"] = _maybe_float(node.findtext("dist_d-w"))
                    row["water_idx"] = _maybe_int(node.findtext("water_idx"))
                rows.append(row)
        if len(rows) > best[0]:
            best = (len(rows), rows, hetid, (site.findtext("identifiers/reschain") or "").strip())
    return {
        "pdb_id": pdb_id,
        "ligand_code": ligand_code,
        "ligand_chain": best[3],
        "interactions": best[1],
    }


def _maybe_float(value):
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _coords(node):
    """PLIP writes an endpoint as <ligcoo><x/><y/><z/></ligcoo>."""
    if node is None:
        return None
    try:
        return [round(float(node.findtext(axis)), 3) for axis in ("x", "y", "z")]
    except (TypeError, ValueError):
        return None


def _maybe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _maybe_bool(value):
    if value is None:
        return None
    return str(value).strip().lower() in ("true", "1", "yes")


# ----------------------------------------------------------------------------- build

def build(slug: str) -> dict:
    """gc struct: residues.csv and interactions/<pdb_id>.json into build/<slug>/."""
    slug = paths.check_slug(slug)
    paper = json.loads((paths.raw_dir(slug) / "paper.json").read_text())
    entries = json.loads((paths.raw_dir(slug) / "structures.json").read_text())
    overrides = read_overrides(slug)
    out_dir = paths.build_dir(slug)
    (out_dir / "interactions").mkdir(exist_ok=True)

    all_rows: list[dict] = []
    report = {"structures": [], "residues": 0, "interactions": 0, "problems": []}
    for entry in entries:
        cif = fetch_cif(entry["pdb_id"])
        sse = dssp_sse(cif)
        pocket = {}
        if entry.get("klifs"):
            pocket = klifs_pocket(paper["target"].get("uniprot", ""),
                                  entry["contains"]["protein"],
                                  entry["pdb_id"], entry["chain"])
            if not pocket:
                report["problems"].append(
                    f"{entry['pdb_id']}: klifs is true but KLIFS returned no pocket mapping")
        rows = residues(slug, entry, sse, pocket, overrides)
        all_rows.extend(rows)

        n_inter = 0
        ligand_code = (entry.get("contains") or {}).get("ligand_code")
        if ligand_code:
            data = plip_interactions(entry["pdb_id"], ligand_code)
            (out_dir / "interactions" / f"{entry['pdb_id']}.json").write_text(
                json.dumps(data, indent=1))
            n_inter = len(data["interactions"])
            if n_inter == 0:
                report["problems"].append(
                    f"{entry['pdb_id']}: PLIP found no interactions for ligand {ligand_code}")
        report["structures"].append({
            "pdb_id": entry["pdb_id"], "residues": len(rows),
            "klifs_mapped": sum(1 for r in rows if r["klifs_index"] != "NA"),
            "interactions": n_inter,
        })
        report["interactions"] += n_inter

    with (out_dir / "residues.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["pdb_id", "chain", "resnum", "resname",
                                                "sse", "klifs_index", "motif", "role_note"])
        writer.writeheader()
        writer.writerows(all_rows)
    report["residues"] = len(all_rows)
    return report
