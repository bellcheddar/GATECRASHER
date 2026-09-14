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
        # A structure-scoped override wins over an unscoped one.
        override = (overrides.get(f"{entry['pdb_id'].upper()}|{chain_id}:{resnum}")
                    or overrides.get(f"{chain_id}:{resnum}", {}))
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
    """Optional hand-curated motif table: required for KRAS, which has no KLIFS mapping.

    An optional pdb_id column scopes a row to one structure. That matters whenever a bundle
    holds two DIFFERENT proteins: JAK1's His885 and JAK2's Asn859 are unrelated residues, and
    without scoping each would be stamped onto the other structure at the same number.
    """
    path = paths.raw_dir(slug) / "motifs.tsv"
    if not path.exists():
        return {}
    out = {}
    with path.open() as fh:
        for row in csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t"):
            pdb_id = (row.get("pdb_id") or "").strip().upper()
            key = f"{row['chain'].strip()}:{int(row['resnum'])}"
            if pdb_id:
                key = f"{pdb_id}|{key}"
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


def plip_interactions(pdb_id: str, ligand_code: str, chain: str = "") -> dict:
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
    # chain_map is ORIGINAL -> the single letter PLIP will see, assigned in order of
    # appearance. The caller names the chain the rest of the bundle describes, and the
    # contacts have to come from that same copy.
    return _parse_plip(work / "report.xml", pdb_id, ligand_code, resname_map,
                       (chain_map or {}).get(chain, chain))


PLIP_TYPES = {
    "hydrogen_bonds": "hbond",
    "hydrophobic_interactions": "hydrophobic",
    "pi_stacks": "pi_stack",
    "salt_bridges": "salt_bridge",
    "water_bridges": "water_bridge",
    "halogen_bonds": "halogen",
    "pi_cation_interactions": "pi_cation",
}


def _parse_plip(xml_path: Path, pdb_id: str, ligand_code: str, resname_map: dict,
                prefer_chain: str = "") -> dict:
    import xml.etree.ElementTree as ET

    # The vendored remapper shortens any residue name longer than three characters, so a
    # modern five-character ligand code such as A1BEJ reaches PLIP as A1B. resname_map is
    # keyed ORIGINAL -> SHORTENED; reading it the other way round silently matches nothing
    # and returns an empty contact list for a structure full of contacts.
    code = ligand_code.upper()
    mapping = {k.upper(): v.upper() for k, v in (resname_map or {}).items()}
    wanted = {code, mapping.get(code, code)}
    wanted |= {k for k, v in mapping.items() if v == code}

    root = ET.parse(xml_path).getroot()
    seen_hetids: list[str] = []
    # (chain matches the one we asked for, number of contacts, rows, hetid, chain)
    best: tuple[int, int, list[dict], str, str] = (0, 0, [], "", "")
    for site in root.iter("bindingsite"):
        hetid = (site.findtext("identifiers/hetid") or "").upper()
        seen_hetids.append(hetid)
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
        # PLIP names a binding site's chain in identifiers/chain. identifiers/reschain does
        # not exist, which is why every interactions file used to record ligand_chain as an
        # empty string. The contact rows carry their residues' chains, so if the identifier
        # is ever missing the chain most of them share stands in for it.
        site_chain = (site.findtext("identifiers/chain") or "").strip()
        if not site_chain and rows:
            chains = [row["chain"] for row in rows if row["chain"]]
            site_chain = max(set(chains), key=chains.count) if chains else ""
        # The asymmetric unit usually holds more than one copy, and picking whichever copy
        # happened to have the most contacts is how 10PI came to describe chain B while
        # residues.csv, the ruler and every caption described chain A: contacts that named
        # residues the rest of the bundle did not contain.
        rank = (1 if prefer_chain and site_chain == prefer_chain else 0, len(rows))
        if rows and rank > (best[0], best[1]):
            best = (rank[0], len(rows), rows, hetid, site_chain)

    if not best[2] and seen_hetids:
        # Loud, not silent: PLIP ran and found binding sites, but none of them was the ligand
        # asked for. That is a naming problem, and it must never look like "no contacts".
        raise SystemExit(
            f"{pdb_id}: PLIP found binding sites for {sorted(set(seen_hetids))} but none "
            f"matched ligand {ligand_code} (tried {sorted(wanted)}). "
            f"Residue name mapping was {resname_map}."
        )
    if prefer_chain and best[2] and best[4] != prefer_chain:
        raise SystemExit(
            f"{pdb_id}: the only binding site PLIP found for {ligand_code} is in chain "
            f"{best[4]!r}, but this bundle describes chain {prefer_chain!r}. Contacts from "
            f"another copy would name residues that are not in residues.csv.")
    return {
        "pdb_id": pdb_id,
        "ligand_code": ligand_code,
        "ligand_chain": best[4],
        "interactions": best[2],
    }


def _ca_deviations(fixed_chain, moving_chain, transform) -> tuple[list[float], int, int]:
    """Per-residue CA deviations after superposition, and the numbering offset used.

    Residues are paired through an offset DISCOVERED from the data: the one that makes the
    most residue names agree. Pairing on the raw residue number would compare unrelated
    residues and report nonsense with no error anywhere, because two isoforms are numbered
    differently. Measured here: +9 for FGFR3 4K33 against FGFR2 8E1X (250 names agree), 0 for
    the two KRAS entries (169), and +27 for JAK2 10PJ against JAK1 10PI (108), which is the
    same +27 that separates Glu957 from Glu930 at the hinge.

    gemmi's own alignment would serve, but align_string_sequences wants a sequence of single
    characters rather than the string one_letter_code returns, and AlignmentResult has no
    cigar() to walk, so this stays arithmetic and is checked against a known answer.
    """
    import math

    def residues(chain):
        return [r for r in chain if r.het_flag != "H" and not r.is_water()]

    fixed_residues, moving_residues = residues(fixed_chain), residues(moving_chain)
    fixed_names = {r.seqid.num: r.name for r in fixed_residues}
    moving_names = {r.seqid.num: r.name for r in moving_residues}
    offset, agreeing = 0, -1
    for candidate in range(-60, 61):
        score = sum(1 for num, name in fixed_names.items()
                    if moving_names.get(num - candidate) == name)
        if score > agreeing:
            offset, agreeing = candidate, score

    moving_ca = {r.seqid.num: r.find_atom("CA", "*") for r in moving_residues}
    deviations: list[float] = []
    for residue in fixed_residues:
        atom = residue.find_atom("CA", "*")
        partner = moving_ca.get(residue.seqid.num - offset)
        if atom is None or partner is None:
            continue
        moved = transform.apply(partner.pos)
        deviations.append(math.dist((atom.pos.x, atom.pos.y, atom.pos.z),
                                    (moved.x, moved.y, moved.z)))
    return deviations, offset, agreeing


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
            data = plip_interactions(entry["pdb_id"], ligand_code, entry["chain"])
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

    # Superpositions onto the paper's primary structure. The Structure sheet's twin view
    # locks the two cameras together (BUILD_SPEC 7.2), and a shared camera is meaningless
    # while each entry sits in its own crystal frame: 10PI and 10PJ are 89 A apart, so the
    # second viewer was pointed at empty space and drew nothing at all. The transform is
    # computed here, once, and travels with the bundle.
    primary = next((e for e in entries if e.get("role") == "primary"), None)
    superpositions = {}
    if primary and len(entries) > 1:
        fixed = gemmi.read_structure(str(fetch_cif(primary["pdb_id"])))
        fixed.setup_entities()
        for entry in entries:
            if entry["pdb_id"] == primary["pdb_id"]:
                continue
            moving = gemmi.read_structure(str(fetch_cif(entry["pdb_id"])))
            moving.setup_entities()
            result = gemmi.calculate_superposition(
                fixed[0][primary["chain"]].get_polymer(),
                moving[0][entry["chain"]].get_polymer(),
                gemmi.PolymerType.PeptideL, gemmi.SupSelect.CaP)
            rows = [[result.transform.mat.row_copy(i)[j] for j in range(3)] for i in range(3)]
            vec = result.transform.vec
            # An RMSD is one number over the whole chain, and a handful of loose loops drag
            # it a long way: FGFR3 4K33 onto FGFR2 8E1X is 3.82 A whole-chain while the
            # MEDIAN CA deviation is 1.01 A, because 26 residues in five short stretches
            # carry the error. Both numbers travel, so a good fit cannot read as a bad one.
            deviations, offset, agreeing = _ca_deviations(
                fixed[0][primary["chain"]], moving[0][entry["chain"]], result.transform)
            median = (round(sorted(deviations)[len(deviations) // 2], 2) if deviations else None)
            superpositions[entry["pdb_id"]] = {
                "onto": primary["pdb_id"],
                "chain": entry["chain"],
                "onto_chain": primary["chain"],
                "rmsd_a": round(result.rmsd, 2),
                "median_ca_deviation_a": median,
                "numbering_offset": offset,
                "residue_names_agreeing": agreeing,
                "pairs": int(result.count),
                # Row-major 4x4, so the viewer can apply it without a matrix library.
                "matrix": [round(v, 6) for row, t in zip(rows, (vec.x, vec.y, vec.z))
                           for v in (*row, t)] + [0.0, 0.0, 0.0, 1.0],
            }
            report["structures"] = [
                {**s, "superposed_onto": primary["pdb_id"],
                 "superposition_rmsd_a": superpositions[entry["pdb_id"]]["rmsd_a"]}
                if s["pdb_id"] == entry["pdb_id"] else s for s in report["structures"]]
    (out_dir / "superpositions.json").write_text(json.dumps(superpositions, indent=1))

    with (out_dir / "residues.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["pdb_id", "chain", "resnum", "resname",
                                                "sse", "klifs_index", "motif", "role_note"])
        writer.writeheader()
        writer.writerows(all_rows)
    report["residues"] = len(all_rows)
    return report
