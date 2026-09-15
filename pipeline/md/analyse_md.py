#!/usr/bin/env python
"""Turn one finished MD run into a track, a verdict and a trajectory the page can play.

Runs under the same interpreter as run_md.py (MDTraj lives there), invoked by
gcrash/dynamics.py. Nothing in gcrash imports MDTraj.

    analyse_md.py --work DIR --spec raw/<slug>/dynamics.json --pdb-id 8UV0 \
                  --interactions build/<slug>/interactions/8UV0.json --out build/<slug>/dynamics

What comes out:

  <PDB>.json      RMSF per residue, ligand RMSD, one entry per claim, and a verdict
  <PDB>_md.pdb    topology for the viewer: the pocket and the ligand, one copy
  <PDB>_md.xtc    the decimated trajectory, 200 frames, compressed

The verdict is the whole point. BUILD_SPEC Stage 4: if a trajectory does not support what
the paper claims, it does not ship. A claim is a sentence from the bundle's own caption
turned into a measurement: the fraction of frames in which a contact is made. `expect:
absent` is a real answer, and a claim of absence is tested the same way.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def log(message: str) -> None:
    print(f"    {message}", flush=True)


def read_spec(path: Path, pdb_id: str) -> dict:
    spec = json.loads(path.read_text())
    for entry in spec.get("structures", []):
        if entry["pdb_id"].upper() == pdb_id.upper():
            return {**{k: v for k, v in spec.items() if k != "structures"}, **entry}
    raise SystemExit(f"{path}: no dynamics entry for {pdb_id}")


def resolve_claim_atoms(claim: dict, traj, ligand_name: str, interactions: dict,
                        crystal_xyz) -> tuple[list[int], list[int]]:
    """The atoms a claim is measured between, as indices into the trajectory's topology.

    Protein side: the named atoms of the named residue. Ligand side: either the atoms
    matching a SMARTS, or the atom nearest the coordinates PLIP recorded for its contact
    with that residue, so what is measured is what PLIP measured.
    """
    import numpy as np

    chain, resnum = claim["residue"].split(":")
    wanted = set(claim.get("protein_atoms") or [])
    protein = [a.index for a in traj.topology.atoms
               if a.residue.resSeq == int(resnum) and a.residue.name != ligand_name
               and (not wanted or a.name in wanted)]

    ligand_atoms = [a for a in traj.topology.atoms if a.residue.name == ligand_name]
    heavy = [a for a in ligand_atoms if a.element.symbol != "H"]

    if claim.get("ligand_from_plip"):
        spec = claim["ligand_from_plip"]
        targets = [row for row in interactions.get("interactions", [])
                   if row.get("resnum") == spec.get("resnum")
                   and (not spec.get("types") or row.get("type") in spec["types"])
                   and row.get("ligand_coords")]
        if not targets:
            raise SystemExit(f"{claim['id']}: no PLIP contact with residue {spec.get('resnum')} "
                             f"to take ligand atoms from")
        chosen = []
        for row in targets:
            point = np.array(row["ligand_coords"], dtype=float) / 10.0   # PLIP is in angstrom
            distances = [np.linalg.norm(crystal_xyz[a.index] - point) for a in heavy]
            chosen.append(heavy[int(np.argmin(distances))].index)
        ligand = sorted(set(chosen))
    else:
        from rdkit import Chem
        pattern = Chem.MolFromSmarts(claim["ligand_smarts"])
        # Matched against the SDF WRITTEN AT PREPARATION, not against a molecule rebuilt from
        # the SMILES string. Those two have different atom orders (measured on CDK2: the SDF
        # runs C,C,C,C,N where the SMILES runs C,C,C,O,C), and the topology inherits the
        # SDF's. Matching the SMILES would hand back indices for a different atom and report
        # a confident occupancy for the wrong contact.
        reference = Chem.SDMolSupplier(str(claim["_ligand_sdf"]), removeHs=True)[0]
        if pattern is None or reference is None:
            raise SystemExit(f"{claim['id']}: SMARTS or prepared ligand does not parse")
        matches = reference.GetSubstructMatches(pattern)
        if not matches:
            raise SystemExit(f"{claim['id']}: {claim['ligand_smarts']} matches nothing in the "
                             f"prepared ligand")
        wanted_ligand = sorted({index for match in matches for index in match})
        if max(wanted_ligand) >= len(heavy):
            raise SystemExit(f"{claim['id']}: matched atom {max(wanted_ligand)} but the "
                             f"topology has {len(heavy)} heavy ligand atoms")
        ligand = [heavy[i].index for i in wanted_ligand]

    if not protein or not ligand:
        raise SystemExit(f"{claim['id']}: resolved {len(protein)} protein and {len(ligand)} "
                         f"ligand atoms; a claim cannot be measured between nothing")
    return protein, ligand


def main() -> int:
    import mdtraj as md
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--pdb-id", required=True)
    parser.add_argument("--interactions", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames", type=int, default=200)
    args = parser.parse_args()

    work, out = Path(args.work), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = read_spec(Path(args.spec), args.pdb_id)
    progress = json.loads((work / "progress.json").read_text())
    prepared = json.loads((work / "prepared.json").read_text())
    interactions = json.loads(Path(args.interactions).read_text()) if Path(args.interactions).exists() else {}
    ligand_name = next((d["residue_name"] for d in prepared["molecules"].values()
                        if d["role"] == "ligand"), "LIG")
    ligand_sdf = next((work / d["sdf"] for d in prepared["molecules"].values()
                       if d["role"] == "ligand"), None)

    traj = md.load(str(work / "traj.dcd"), top=str(work / "topology.pdb"))
    crystal = md.load(str(work / "topology.pdb"))
    log(f"{traj.n_frames} frames, {traj.n_atoms} atoms, "
        f"{progress['done_ps']:.0f} ps at {progress['frame_interval_ps']:.0f} ps per frame")

    # Everything is measured against the prepared complex, which is the crystal pose: the
    # protein is superposed frame by frame so a drifting box cannot read as a moving ligand.
    protein_ca = traj.topology.select("name CA")
    traj.superpose(crystal, atom_indices=protein_ca)

    # RMSF per residue, on CA, in angstrom.
    rmsf_nm = md.rmsf(traj, traj, 0, atom_indices=protein_ca)
    rmsf_rows = []
    for atom_index, value in zip(protein_ca, rmsf_nm):
        residue = traj.topology.atom(int(atom_index)).residue
        rmsf_rows.append({"chain": spec["chain"], "resnum": int(residue.resSeq),
                          "resname": residue.name, "rmsf_a": round(float(value) * 10, 2)})

    # Ligand RMSD against the crystal pose, heavy atoms only.
    ligand_heavy = traj.topology.select(f"resname {ligand_name} and not element H")
    rmsd_a = md.rmsd(traj, crystal, 0, atom_indices=ligand_heavy) * 10
    log(f"ligand RMSD: median {float(np.median(rmsd_a)):.2f} A, "
        f"90th percentile {float(np.percentile(rmsd_a, 90)):.2f} A")

    # Claims: the fraction of frames in which the contact is made.
    thresholds = spec.get("thresholds", {})
    present_min = float(thresholds.get("present_min_occupancy", 0.5))
    absent_max = float(thresholds.get("absent_max_occupancy", 0.2))
    rmsd_max = float(thresholds.get("ligand_rmsd_median_max_a", 2.0))

    claim_rows = []
    for claim in spec.get("claims", []):
        claim = {**claim, "_ligand_sdf": ligand_sdf}
        protein_atoms, ligand_atoms = resolve_claim_atoms(
            claim, traj, ligand_name, interactions, crystal.xyz[0])
        pairs = np.array([(p, l) for p in protein_atoms for l in ligand_atoms])
        distances = md.compute_distances(traj, pairs) * 10        # angstrom
        closest = distances.min(axis=1)
        occupancy = float((closest <= claim["cutoff_a"]).mean())
        passed = (occupancy >= present_min if claim["expect"] == "present"
                  else occupancy <= absent_max)
        claim_rows.append({
            "id": claim["id"], "label": claim["label"], "residue": claim["residue"],
            "expect": claim["expect"], "cutoff_a": claim["cutoff_a"],
            "occupancy": round(occupancy, 3),
            "median_distance_a": round(float(np.median(closest)), 2),
            "pass": bool(passed), "source": claim["source"],
        })
        log(f"{claim['id']}: {occupancy:.0%} of frames within {claim['cutoff_a']} A "
            f"(expected {claim['expect']}) -> {'pass' if passed else 'FAIL'}")

    median_rmsd = float(np.median(rmsd_a))
    drifted = median_rmsd > rmsd_max
    supported = all(row["pass"] for row in claim_rows) and not drifted
    verdict = "supports" if supported else "does_not_support"

    # The trajectory the page plays: the pocket and the ligand, decimated. Water is 90 per
    # cent of the atoms and none of the argument, and the whole protein is more than the
    # 2 MB budget allows.
    pocket = traj.topology.select(
        f"(protein and not element H) or resname {ligand_name}")
    # Evenly spaced indices, not a fixed step. `n // target` floor-divides to 1 whenever the
    # source has fewer than twice the target, so a 250 frame run against a 200 frame target
    # gave stride 1 and shipped all 250: the decimation was a no-op in exactly the regime it
    # exists for. CDK2 came out at 2261 kB gzipped against a 2048 kB budget, and XTC is
    # already compressed, so the only way under is to ship less.
    keep = np.unique(np.linspace(0, traj.n_frames - 1,
                                 min(traj.n_frames, args.frames)).round().astype(int))
    shipped = traj.atom_slice(pocket)[keep]
    topology_path = out / f"{args.pdb_id}_md.pdb"
    trajectory_path = out / f"{args.pdb_id}_md.xtc"
    if supported:
        shipped[0].save_pdb(str(topology_path))
        shipped.save_xtc(str(trajectory_path))
        log(f"wrote {shipped.n_frames} frames of {shipped.n_atoms} atoms "
            f"({trajectory_path.stat().st_size / 1024:.0f} kB)")
    else:
        for path in (topology_path, trajectory_path):
            path.unlink(missing_ok=True)
        log("verdict: the trajectory does not support the claims, so it is not written")

    report = {
        "pdb_id": args.pdb_id,
        "verdict": verdict,
        "production_ps": progress["done_ps"],
        "frames_analysed": int(traj.n_frames),
        "frame_interval_ps": progress["frame_interval_ps"],
        "method": {
            "forcefield": "amber14-all, TIP3P water",
            "ligand_forcefield": progress.get("ligand_forcefield", "openff-2.1.0"),
            "charges": "AM1-BCC",
            "temperature_k": progress.get("temperature_k", 300.0),
            "timestep_fs": progress["timestep_fs"],
            "hydrogen_mass_amu": progress.get("hydrogen_mass_amu"),
            "padding_nm": progress.get("padding_nm"),
            "ionic_strength_m": progress.get("ionic_strength_m"),
            "equilibration_ps": progress.get("equilibration_ps"),
            "platform": progress.get("platform"),
            "gaps_modelled": prepared["fixer"]["gaps_modelled"],
            "gaps_left_open": prepared["fixer"]["gaps_left_open"],
            "nonstandard_replaced": prepared["fixer"]["nonstandard_replaced"],
        },
        "ligand": {
            "resname": ligand_name,
            "rmsd_median_a": round(median_rmsd, 2),
            "rmsd_p90_a": round(float(np.percentile(rmsd_a, 90)), 2),
            "rmsd_max_a": round(rmsd_max, 2),
            "within_budget": not drifted,
            # The same frames the trajectory ships, so the series lines up with what plays.
            "series_a": [round(float(v), 2) for v in rmsd_a[keep]],
        },
        "rmsf": rmsf_rows,
        "claims": claim_rows,
        "not_assessed": spec.get("not_assessed", []),
        "trajectory": ({"topology": topology_path.name, "xtc": trajectory_path.name,
                        "frames": int(shipped.n_frames), "atoms": int(shipped.n_atoms),
                        "bytes": trajectory_path.stat().st_size} if supported else None),
    }
    (out / f"{args.pdb_id}.json").write_text(json.dumps(report, indent=1))
    log(f"verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
