#!/usr/bin/env python
"""Prepare, equilibrate and run a short MD of one deposited complex.

This script is NOT part of the gcrash package and is never imported by it. It runs under a
different interpreter: OpenMM, OpenFF, openmmforcefields and PDBFixer live in FlexAppeal's
pixi environment (see HARVEST.md), and `gc dynamics` invokes this file with that
interpreter, the way the PLIP stage shells out rather than imports.

    run_md.py prepare     --spec raw/<slug>/dynamics.json --pdb-id 8UV0 --cif <file> --out DIR
    run_md.py equilibrate --out DIR
    run_md.py produce     --out DIR --chunk-ps 250

Three stages, each resumable, because each fails in its own way and the third takes hours:

  prepare      mmCIF -> receptor + ligand + cofactors, short gaps modelled, hydrogens added
  equilibrate  solvate, parameterise, minimise, heat, release the restraints
  produce      ONE chunk of production, appended to the trajectory, then exit

One chunk per process is deliberate. OpenMM on Apple's OpenCL leaks about 3 kB per step,
which a long run turns into gigabytes, and only a fresh process gives it back. The driver
calls this until progress.json says the run is finished.

Lifted from GOBSMACKED/bundle_template/gobsmacked_run/md.py (system generation, the
restraint ramp, the solute-only DCD) and FlexAppeal's runtime (platform choice at a
precision Apple's OpenCL will accept). Divergences are recorded in HARVEST.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Shared with the analysis stage, which reads them back out of progress.json.
TEMPERATURE_K = 300.0
PRESSURE_BAR = 1.0
FRICTION_PER_PS = 1.0
PADDING_NM = 1.0
IONIC_STRENGTH_M = 0.15
HYDROGEN_MASS_AMU = 4.0
RESTRAINT_K = 1000.0            # kJ/mol/nm^2 on solute heavy atoms, released in steps
RESTRAINT_STEPS = 5
LIGAND_RESIDUE_NAME = "LIG"


def log(message: str) -> None:
    print(f"    {message}", flush=True)


def read_spec(path: Path, pdb_id: str) -> dict:
    spec = json.loads(path.read_text())
    for entry in spec.get("structures", []):
        if entry["pdb_id"].upper() == pdb_id.upper():
            return {**{k: v for k, v in spec.items() if k != "structures"}, **entry}
    raise SystemExit(f"{path}: no dynamics entry for {pdb_id}")


# --------------------------------------------------------------------------- prepare


def split_structure(cif: Path, chain: str, ligand_code: str, cofactor_codes: list[str],
                    ion_codes: list[str], keep_waters: bool, out: Path) -> dict:
    """Receptor (plus ions and waters) to PDB, and the coordinates of each small molecule.

    gemmi rather than PDBFixer for the splitting: a deposited entry carries alternate
    locations, several chains sharing one name (8E1X and 10PI put the protein, the ligand
    and the waters in three separate chains all called A), and hetero groups that are
    crystallisation additives rather than chemistry (EDO, DMS). PDBFixer's chain handling
    cannot express that.
    """
    import gemmi

    st = gemmi.read_structure(str(cif))
    st.setup_entities()
    st.remove_alternative_conformations()
    st.remove_hydrogens()
    model = st[0]

    receptor = gemmi.Structure()
    receptor.spacegroup_hm = st.spacegroup_hm
    receptor.cell = st.cell
    receptor.add_model(gemmi.Model("1"))
    protein_chain = gemmi.Chain(chain)
    hetero_chain = gemmi.Chain("B")          # ions and crystal waters, kept out of the polymer
    small: dict[str, list] = {}
    wanted_small = {ligand_code.upper(): "ligand",
                    **{c.upper(): "cofactor" for c in cofactor_codes}}
    ions = {c.upper() for c in ion_codes}

    for ch in model:
        if ch.name != chain:
            continue
        for res in ch:
            code = res.name.upper()
            if res.is_water():
                if keep_waters:
                    hetero_chain.add_residue(res)
            elif res.het_flag != "H":
                protein_chain.add_residue(res)
            elif code in wanted_small:
                small.setdefault(code, []).append(res)
            elif code in ions:
                hetero_chain.add_residue(res)

    if not len(protein_chain):
        raise SystemExit(f"{cif.name}: no polymer residues in chain {chain}")
    absent = [code for code in wanted_small if code not in small]
    if absent:
        raise SystemExit(f"{cif.name}: chain {chain} contains no {', '.join(absent)}")

    receptor[0].add_chain(protein_chain)
    if len(hetero_chain):
        receptor[0].add_chain(hetero_chain)
    # The DEPOSITED sequence has to travel with the coordinates. A fresh gemmi.Structure has
    # no entities, so setup_entities() rebuilds them from the atoms alone, the written PDB
    # carries no SEQRES, and PDBFixer has nothing to compare against: it reports zero missing
    # residues for a chain with three gaps, model_gaps_max silently does nothing, and the
    # protein is simulated with 7.2, 8.5 and 14.9 A holes in it.
    receptor.entities = st.entities
    receptor.setup_entities()
    receptor.write_pdb(str(out / "receptor_raw.pdb"))
    seqres = sum(1 for line in (out / "receptor_raw.pdb").read_text().splitlines()
                 if line.startswith("SEQRES"))
    if not seqres:
        raise SystemExit(f"{cif.name}: no SEQRES written, so gaps cannot be found")

    coords = {}
    for code, residues in small.items():
        coords[code] = {
            "role": wanted_small[code],
            "copies_in_chain": len(residues),
            "atoms": [{"name": a.name, "element": a.element.name,
                       "xyz": [a.pos.x, a.pos.y, a.pos.z]}
                      for a in residues[0] if a.element.name != "H"],
        }
    (out / "small_molecules.json").write_text(json.dumps(coords, indent=1))
    waters = sum(1 for res in hetero_chain if res.is_water())
    return {"polymer_residues": len(protein_chain), "crystal_waters": waters,
            "ions": [res.name for res in hetero_chain if not res.is_water()],
            "small_molecules": {k: len(v["atoms"]) for k, v in coords.items()}}


def fix_receptor(out: Path, model_gaps_max: int) -> dict:
    """Model short internal gaps, add missing heavy atoms, add hydrogens at pH 7.4.

    Terminal gaps are never modelled: an unresolved tail is disordered, and inventing one
    gives the protein a flapping arm that dominates the RMSF of everything near it. Internal
    gaps longer than model_gaps_max are left open and reported, because a modelled
    ten-residue loop is a prediction, and this app does not show predictions as measurements.
    """
    from openmm import app
    from pdbfixer import PDBFixer

    fixer = PDBFixer(filename=str(out / "receptor_raw.pdb"))
    fixer.findMissingResidues()
    chains = list(fixer.topology.chains())
    modelled, left_open = [], []
    keep = {}
    for (chain_index, residue_index), names in fixer.missingResidues.items():
        chain = chains[chain_index]
        where = "terminal" if residue_index in (0, len(list(chain.residues()))) else "internal"
        record = {"chain": chain.id, "after_residue_index": residue_index,
                  "length": len(names), "where": where}
        if where == "internal" and len(names) <= model_gaps_max:
            keep[(chain_index, residue_index)] = names
            modelled.append(record)
        else:
            left_open.append(record)
    fixer.missingResidues = keep

    fixer.findNonstandardResidues()
    replaced = [[f"{residue.name}{residue.id}", str(standard)]
                for residue, standard in fixer.nonstandardResidues]
    fixer.replaceNonstandardResidues()
    fixer.findMissingAtoms()
    added = sum(len(atoms) for atoms in fixer.missingAtoms.values())
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(7.4)
    with (out / "receptor.pdb").open("w") as handle:
        app.PDBFile.writeFile(fixer.topology, fixer.positions, handle, keepIds=True)
    return {"gaps_modelled": modelled, "gaps_left_open": left_open,
            "nonstandard_replaced": replaced, "missing_heavy_atoms_added": added}


def molecule_from_crystal(smiles: str, atoms: list[dict], residue_name: str):
    """Our verified SMILES, wearing the crystal ligand's coordinates.

    Not bond perception from the coordinates: a deposited file has no bond orders, and
    guessing them is exactly how a formula-correct, connectivity-wrong molecule ends up
    simulated. The SMILES is the one in compounds.tsv, already verified against the
    deposited chemical component or through OPSIN, and it carries the protonation the run is
    meant to test. The crystal supplies coordinates only, matched onto that graph.
    """
    from openff.toolkit import Molecule
    from rdkit import Chem
    from rdkit.Geometry import Point3D

    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise SystemExit(f"{residue_name}: RDKit cannot parse the SMILES")
    # A deuterium in the SMILES (FGFR compound 30 carries a d3-methyl amide) is the point of
    # the compound but not of its force field: OpenFF has no deuterium, and the mass changes
    # no pose. Simulated as hydrogen, and reported as such.
    deuteriums = 0
    for atom in template.GetAtoms():
        if atom.GetIsotope():
            atom.SetIsotope(0)
            deuteriums += 1
    heavy = Chem.RemoveHs(template)

    # PDB is a FIXED-COLUMN format and RDKit reads it as one: the atom name occupies columns
    # 13 to 16, and a name shorter than four characters starts at column 14, not 13. Writing
    # it one column to the left parses as zero atoms, with no error and no warning, and the
    # only symptom is a substructure match against an empty molecule.
    lines = []
    for index, atom in enumerate(atoms, start=1):
        name = atom["name"][:4]
        padded = name if len(name) == 4 else f" {name:<3s}"
        lines.append(
            f"HETATM{index:5d} {padded} {residue_name[:3]:>3s} A   1    "
            f"{atom['xyz'][0]:8.3f}{atom['xyz'][1]:8.3f}{atom['xyz'][2]:8.3f}"
            f"  1.00  0.00          {atom['element'][:2]:>2s}")
    crystal = Chem.MolFromPDBBlock("\n".join(lines) + "\nEND\n", sanitize=False,
                                   removeHs=True, proximityBonding=True)
    if crystal is None:
        raise SystemExit(f"{residue_name}: cannot read the deposited coordinates")
    crystal.UpdatePropertyCache(strict=False)
    Chem.FastFindRings(crystal)

    # The query is the SKELETON of our molecule: elements and connectivity, with bond orders,
    # aromaticity and formal charges stripped out. The crystal has none of those to match
    # against, and leaving them on fails a molecule whose every element count is identical:
    # GDP (C10 N5 O11 P2 on both sides) matched nothing because the query carried -3 on its
    # phosphate oxygens and aromatic flags on its guanine. The real charges are restored
    # below, because GDP genuinely is -3 at pH 7.4 and the force field needs to know.
    skeleton = Chem.RWMol(heavy)
    for atom in skeleton.GetAtoms():
        atom.SetFormalCharge(0)
        atom.SetIsAromatic(False)
        atom.SetNoImplicit(True)
        atom.SetNumExplicitHs(0)
    for bond in skeleton.GetBonds():
        bond.SetBondType(Chem.BondType.SINGLE)
        bond.SetIsAromatic(False)
    skeleton = skeleton.GetMol()
    skeleton.UpdatePropertyCache(strict=False)
    Chem.FastFindRings(skeleton)

    params = Chem.AdjustQueryParameters()
    params.makeBondsGeneric = True      # the crystal carries no bond orders to match against
    params.aromatizeIfPossible = False
    match = crystal.GetSubstructMatch(Chem.AdjustQueryProperties(skeleton, params))
    if not match:
        raise SystemExit(
            f"{residue_name}: the SMILES ({heavy.GetNumAtoms()} heavy atoms) does not match "
            f"the deposited ligand ({crystal.GetNumAtoms()} heavy atoms)")

    mol = Chem.RWMol(heavy)
    conformer = Chem.Conformer(mol.GetNumAtoms())
    crystal_positions = crystal.GetConformer()
    for template_index, crystal_index in enumerate(match):
        point = crystal_positions.GetAtomPosition(crystal_index)
        conformer.SetAtomPosition(template_index, Point3D(point.x, point.y, point.z))
    mol.RemoveAllConformers()
    mol.AddConformer(conformer, assignId=True)
    Chem.SanitizeMol(mol)
    # Stereochemistry from the coordinates, not from the SMILES: where the two disagree the
    # crystal is the measurement. KRAS compound 3's deposited component carries no
    # stereocentres at all, and the paper's compound is a single enantiomer.
    Chem.AssignStereochemistryFrom3D(mol)
    with_hydrogens = Chem.AddHs(mol, addCoords=True)

    offmol = Molecule.from_rdkit(with_hydrogens, allow_undefined_stereo=True)
    offmol.name = residue_name
    offmol.generate_unique_atom_names()
    return offmol, {"heavy_atoms": int(heavy.GetNumAtoms()),
                    "deuteriums_simulated_as_hydrogen": deuteriums,
                    "formal_charge": int(Chem.GetFormalCharge(with_hydrogens)),
                    "smiles": Chem.MolToSmiles(mol)}


def prepare(args) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = read_spec(Path(args.spec), args.pdb_id)
    report = {"pdb_id": args.pdb_id.upper(), "spec": spec, "prepared_at": time.strftime("%Y-%m-%d %H:%M")}

    log(f"splitting {Path(args.cif).name}: chain {spec['chain']}, ligand {spec['ligand_code']}")
    report["split"] = split_structure(
        Path(args.cif), spec["chain"], spec["ligand_code"],
        [c["code"] for c in spec.get("cofactors", [])], spec.get("ions", []),
        bool(spec.get("keep_crystal_waters", True)), out)
    log(f"receptor: {report['split']['polymer_residues']} residues, "
        f"{report['split']['crystal_waters']} crystal waters, ions {report['split']['ions']}")

    log("modelling short internal gaps, adding heavy atoms and hydrogens at pH 7.4")
    report["fixer"] = fix_receptor(out, int(spec.get("model_gaps_max", 6)))
    for gap in report["fixer"]["gaps_modelled"]:
        log(f"modelled a {gap['length']}-residue internal gap in chain {gap['chain']}")
    for gap in report["fixer"]["gaps_left_open"]:
        log(f"left a {gap['length']}-residue {gap['where']} gap open")
    for old, new in report["fixer"]["nonstandard_replaced"]:
        log(f"replaced nonstandard residue {old} with {new}")

    smiles_by_code = {spec["ligand_code"].upper(): spec["ligand_smiles_md"]}
    for cofactor in spec.get("cofactors", []):
        smiles_by_code[cofactor["code"].upper()] = cofactor["smiles"]

    details = {}
    for code, entry in json.loads((out / "small_molecules.json").read_text()).items():
        name = LIGAND_RESIDUE_NAME if entry["role"] == "ligand" else code[:3].upper()
        offmol, detail = molecule_from_crystal(smiles_by_code[code], entry["atoms"], name)
        offmol.to_file(str(out / f"{code}.sdf"), file_format="sdf")
        details[code] = {**detail, "role": entry["role"], "residue_name": name,
                         "sdf": f"{code}.sdf"}
        log(f"{code}: {detail['heavy_atoms']} heavy atoms, formal charge "
            f"{detail['formal_charge']}, as {name}")
    report["molecules"] = details
    (out / "prepared.json").write_text(json.dumps(report, indent=1))
    log(f"prepared in {out}")


# ----------------------------------------------------------------------- equilibrate


def build_system(out: Path, spec: dict):
    """Solvated system and topology, exactly as equilibration and production both need it."""
    import openmm
    from openff.toolkit import Molecule
    from openmm import app, unit
    from openmmforcefields.generators import SystemGenerator

    prepared = json.loads((out / "prepared.json").read_text())
    molecules, by_code = [], {}
    for code, detail in prepared["molecules"].items():
        offmol = Molecule.from_file(str(out / detail["sdf"]), file_format="sdf",
                                    allow_undefined_stereo=True)
        molecules.append(offmol)
        by_code[code] = (offmol, detail)

    generator = SystemGenerator(
        forcefields=["amber14-all.xml", "amber14/tip3p.xml"],
        small_molecule_forcefield=spec.get("ligand_forcefield", "openff-2.1.0"),
        molecules=molecules,
        forcefield_kwargs={"constraints": app.HBonds, "rigidWater": True,
                           "removeCMMotion": True,
                           "hydrogenMass": HYDROGEN_MASS_AMU * unit.amu},
        cache=str(out / "parameters.json"),
    )

    receptor = app.PDBFile(str(out / "receptor.pdb"))
    modeller = app.Modeller(receptor.topology, receptor.positions)
    for code, (offmol, detail) in by_code.items():
        topology = offmol.to_topology().to_openmm()
        # OpenFF names every small molecule's residue UNK, and MDTraj counts UNK as protein:
        # "not protein" then selects nothing, and the ligand series comes back empty with no
        # error anywhere. Named here, once; the analysis selects on these names.
        for residue in topology.residues():
            residue.name = detail["residue_name"]
        modeller.add(topology, offmol.conformers[0].to_openmm())
    solute_atoms = modeller.topology.getNumAtoms()

    log(f"solvating {solute_atoms} solute atoms: {PADDING_NM * 10:.0f} A padding, "
        f"{IONIC_STRENGTH_M} M NaCl")
    modeller.addSolvent(generator.forcefield, model="tip3p",
                        padding=PADDING_NM * unit.nanometer,
                        ionicStrength=IONIC_STRENGTH_M * unit.molar, neutralize=True)
    log(f"parameterising {modeller.topology.getNumAtoms()} atoms "
        f"({spec.get('ligand_forcefield', 'openff-2.1.0')}, AM1-BCC charges)")
    system = generator.create_system(modeller.topology, molecules=molecules)
    system.addForce(openmm.MonteCarloBarostat(PRESSURE_BAR * unit.bar,
                                              TEMPERATURE_K * unit.kelvin))
    names = {code: detail["residue_name"] for code, (_, detail) in by_code.items()}
    return modeller, system, solute_atoms, names


def add_restraints(system, topology, positions, solute_atoms: int):
    """Positional restraints on solute heavy atoms, released through a global parameter.

    periodicdistance, not a plain distance: an atom crossing a periodic boundary would
    otherwise be hauled back across the whole box.
    """
    import openmm
    from openmm import unit

    restraint = openmm.CustomExternalForce(
        "k_restraint*periodicdistance(x, y, z, x0, y0, z0)^2")
    restraint.addGlobalParameter("k_restraint",
                                 RESTRAINT_K * unit.kilojoules_per_mole / unit.nanometer ** 2)
    for name in ("x0", "y0", "z0"):
        restraint.addPerParticleParameter(name)
    atoms = list(topology.atoms())
    for index in range(min(solute_atoms, len(atoms))):
        if atoms[index].element is None or atoms[index].element.symbol == "H":
            continue
        restraint.addParticle(index, positions[index].value_in_unit(unit.nanometer))
    system.addForce(restraint)
    return restraint


def choose_platform(wanted: str):
    """The fastest platform available, at a precision it will actually accept.

    Apple's OpenCL is single precision only. Asking it for `mixed` fails with "No compatible
    OpenCL platform is available", an error that names the platform rather than the property,
    reads as "you have no GPU", and drops the run onto the CPU at a tenth of the speed with
    nothing in the output to say so.
    """
    import openmm

    available = [openmm.Platform.getPlatform(i).getName()
                 for i in range(openmm.Platform.getNumPlatforms())]
    for name in ([wanted] if wanted != "auto" else ["CUDA", "OpenCL", "CPU"]):
        if name not in available:
            continue
        properties = {"CUDA": {"Precision": "mixed"}, "OpenCL": {"Precision": "single"}}.get(name, {})
        return openmm.Platform.getPlatformByName(name), properties
    raise SystemExit(f"no usable OpenMM platform among {available}")


def equilibrate(args) -> None:
    import openmm
    from openmm import app, unit

    out = Path(args.out)
    prepared = json.loads((out / "prepared.json").read_text())
    spec = prepared["spec"]
    started = time.time()

    modeller, system, solute_atoms, ligand_names = build_system(out, spec)
    restraint = add_restraints(system, modeller.topology, modeller.positions, solute_atoms)
    timestep = float(spec.get("timestep_fs", 2.0))
    integrator = openmm.LangevinMiddleIntegrator(TEMPERATURE_K * unit.kelvin,
                                                 FRICTION_PER_PS / unit.picosecond,
                                                 timestep * unit.femtoseconds)
    integrator.setRandomNumberSeed(int(spec.get("seed", 20260914)))
    platform, properties = choose_platform(spec.get("platform", "auto"))
    simulation = app.Simulation(modeller.topology, system, integrator, platform, properties)
    simulation.context.setPositions(modeller.positions)

    log(f"minimising on {simulation.context.getPlatform().getName()}")
    simulation.minimizeEnergy(maxIterations=int(spec.get("minimise_steps", 5000)))

    equil_ps = float(spec.get("equilibration_ps", 200))
    equil_steps = int(equil_ps * 1000 / timestep)
    simulation.context.setVelocitiesToTemperature(TEMPERATURE_K * unit.kelvin)
    per_step = max(1, equil_steps // RESTRAINT_STEPS)
    for index in range(RESTRAINT_STEPS):
        k = RESTRAINT_K * (1.0 - index / RESTRAINT_STEPS)
        simulation.context.setParameter("k_restraint", k)
        simulation.step(per_step)
        log(f"equilibrating: restraint {k:.0f} kJ/mol/nm^2, "
            f"{(index + 1) * per_step * timestep / 1000:.0f} of {equil_ps:.0f} ps")
    simulation.context.setParameter("k_restraint", 0.0)

    # The serialised system keeps whatever DEFAULT the global parameter was given, not the
    # value the context happens to hold. Left at 1000, every production chunk would reload a
    # fully restrained protein and report a beautifully rigid trajectory.
    restraint.setGlobalParameterDefaultValue(0, 0.0)

    state = simulation.context.getState(getPositions=True)
    positions = state.getPositions(asNumpy=True)
    # Topology for the analysis: the solute only, in the same atom order as the frames.
    solute = app.Modeller(modeller.topology, state.getPositions())
    solute.delete([atom for index, atom in enumerate(solute.topology.atoms())
                   if index >= solute_atoms])
    with (out / "topology.pdb").open("w") as handle:
        app.PDBFile.writeFile(solute.topology, positions[:solute_atoms], handle, keepIds=True)
    # And the whole solvated box, so production rebuilds nothing: re-running build_system per
    # chunk would re-fit AM1-BCC charges every time.
    with (out / "solvated.cif").open("w") as handle:
        app.PDBxFile.writeFile(modeller.topology, positions, handle, keepIds=True)

    (out / "system.xml").write_text(openmm.XmlSerializer.serialize(system))
    simulation.saveCheckpoint(str(out / "state.chk"))
    (out / "progress.json").write_text(json.dumps({
        "pdb_id": prepared["pdb_id"], "solute_atoms": solute_atoms,
        "total_atoms": modeller.topology.getNumAtoms(), "ligand_names": ligand_names,
        "timestep_fs": timestep, "frame_interval_ps": float(spec.get("frame_interval_ps", 20)),
        "production_ps": float(spec.get("production_ps", 5000)), "done_ps": 0.0, "chunks": [],
        "platform": simulation.context.getPlatform().getName(),
        "equilibration_ps": equil_ps, "equilibrated_in_s": round(time.time() - started, 1),
        "temperature_k": TEMPERATURE_K, "padding_nm": PADDING_NM,
        "ionic_strength_m": IONIC_STRENGTH_M, "hydrogen_mass_amu": HYDROGEN_MASS_AMU,
        "ligand_forcefield": spec.get("ligand_forcefield", "openff-2.1.0"),
    }, indent=1))
    log(f"equilibrated in {time.time() - started:.0f} s")


# --------------------------------------------------------------------------- produce


def produce(args) -> None:
    import openmm
    from openmm import app, unit

    out = Path(args.out)
    progress = json.loads((out / "progress.json").read_text())
    remaining = progress["production_ps"] - progress["done_ps"]
    if remaining <= 0:
        log("production is already complete")
        return

    chunk_ps = min(float(args.chunk_ps), remaining)
    timestep = progress["timestep_fs"]
    steps = int(chunk_ps * 1000 / timestep)
    interval_steps = max(1, int(progress["frame_interval_ps"] * 1000 / timestep))

    solvated = app.PDBxFile(str(out / "solvated.cif"))
    system = openmm.XmlSerializer.deserialize((out / "system.xml").read_text())
    integrator = openmm.LangevinMiddleIntegrator(TEMPERATURE_K * unit.kelvin,
                                                 FRICTION_PER_PS / unit.picosecond,
                                                 timestep * unit.femtoseconds)
    platform, properties = choose_platform(progress.get("platform", "auto"))
    simulation = app.Simulation(solvated.topology, system, integrator, platform, properties)
    simulation.loadCheckpoint(str(out / "state.chk"))

    append = (out / "traj.dcd").exists()
    simulation.reporters.append(app.DCDReporter(
        str(out / "traj.dcd"), interval_steps, append=append,
        # enforcePeriodicBox=False: the subset written here IS the molecule being measured,
        # and wrapping it into the box splits it whenever it drifts across a face. That is
        # invisible in any single frame and shows up later as a residue that appears to
        # fluctuate by a box length.
        enforcePeriodicBox=False, atomSubset=list(range(progress["solute_atoms"]))))
    simulation.reporters.append(app.StateDataReporter(
        str(out / "md.csv"), interval_steps, step=True, time=True, potentialEnergy=True,
        temperature=True, density=True, speed=True, append=append))

    started = time.time()
    simulation.step(steps)
    elapsed = max(1e-6, time.time() - started)
    simulation.saveCheckpoint(str(out / "state.chk"))

    progress["done_ps"] = round(progress["done_ps"] + chunk_ps, 3)
    progress["chunks"].append({"ps": chunk_ps, "seconds": round(elapsed, 1),
                               "ns_per_day": round(chunk_ps / 1000 / elapsed * 86400, 1)})
    (out / "progress.json").write_text(json.dumps(progress, indent=1))
    log(f"{progress['done_ps']:.0f} of {progress['production_ps']:.0f} ps done, "
        f"{progress['chunks'][-1]['ns_per_day']:.0f} ns/day")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="stage", required=True)

    stage = sub.add_parser("prepare")
    stage.add_argument("--spec", required=True)
    stage.add_argument("--pdb-id", required=True)
    stage.add_argument("--cif", required=True)
    stage.add_argument("--out", required=True)
    stage.set_defaults(func=prepare)

    stage = sub.add_parser("equilibrate")
    stage.add_argument("--out", required=True)
    stage.set_defaults(func=equilibrate)

    stage = sub.add_parser("produce")
    stage.add_argument("--out", required=True)
    stage.add_argument("--chunk-ps", type=float, default=250.0)
    stage.set_defaults(func=produce)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
