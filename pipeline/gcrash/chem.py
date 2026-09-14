"""RDKit work: descriptors, the series scaffold, core-aligned depictions and activity cliffs.

Nothing here invents chemistry. The R-group assignment is hand-curated in compounds.tsv;
this module's job is to verify it, compute properties from it, and draw it consistently.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Crippen, Descriptors, rdFMCS, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from . import paths

RDLogger.DisableLog("rdApp.warning")

# Depictions are rendered once and shown on both themes, so carbon and bond black is
# rewritten to currentColor and the CSS decides. Heteroatom colours stay as drawn.
_BLACK = re.compile(r"(#000000|#000\b)", re.IGNORECASE)


@dataclass
class Compound:
    compound_id: str
    label: str
    series: str
    role: str
    smiles: str
    r_groups: dict
    source_table: str
    notes: str = ""
    mol: Chem.Mol | None = None
    props: dict = field(default_factory=dict)


def read_compounds(slug: str) -> list[Compound]:
    path = paths.raw_dir(slug) / "compounds.tsv"
    out: list[Compound] = []
    with path.open() as fh:
        for row in csv.DictReader(_strip_comments(fh), delimiter="\t"):
            mol = Chem.MolFromSmiles(row["smiles"])
            if mol is None:
                raise SystemExit(f"{path}: compound {row['compound_id']} has unparseable SMILES")
            out.append(
                Compound(
                    compound_id=row["compound_id"].strip(),
                    label=row["label"].strip(),
                    series=row["series"].strip(),
                    role=row["role"].strip(),
                    smiles=row["smiles"].strip(),
                    r_groups=json.loads(row.get("r_groups") or "{}"),
                    source_table=row["source_table"].strip(),
                    notes=(row.get("notes") or "").strip(),
                    mol=mol,
                )
            )
    if not out:
        raise SystemExit(f"{path}: no compounds")
    return out


def _strip_comments(fh):
    for line in fh:
        if not line.startswith("#"):
            yield line


def descriptors(mol: Chem.Mol) -> dict:
    return {
        "inchikey": Chem.MolToInchiKey(mol),
        "mw": round(Descriptors.MolWt(mol), 2),
        "clogp": round(Crippen.MolLogP(mol), 2),
        "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 1),
        "hbd": rdMolDescriptors.CalcNumHBD(mol),
        "hba": rdMolDescriptors.CalcNumHBA(mol),
        "rotb": rdMolDescriptors.CalcNumRotatableBonds(mol),
        "hac": mol.GetNumHeavyAtoms(),
        "fsp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
    }


def scaffold(compounds: list[Compound], timeout: int = 20) -> tuple[Chem.Mol | None, str]:
    """The maximum common substructure across the campaign, used as the depiction template.

    Ring matching is constrained so the MCS cannot cut a ring in half, which would make
    the aligned depictions flip between compounds for no chemical reason.
    """
    mols = [c.mol for c in compounds if c.mol is not None]
    if len(mols) < 2:
        return None, ""
    res = rdFMCS.FindMCS(
        mols,
        timeout=timeout,
        ringMatchesRingOnly=True,
        completeRingsOnly=True,
        matchValences=True,
    )
    if not res or res.canceled or not res.smartsString:
        return None, ""
    core = Chem.MolFromSmarts(res.smartsString)
    if core is not None:
        AllChem.Compute2DCoords(core)
    return core, res.smartsString


def check_r_groups(compounds: list[Compound]) -> list[str]:
    """Every curated R-group fragment must really be present in its parent molecule.

    This is the gate that catches a transcription slip in the R-group table: a substituent
    recorded against the wrong compound almost always fails to match.
    """
    problems: list[str] = []
    for c in compounds:
        for position, spec in (c.r_groups or {}).items():
            frag_smiles = spec.get("smiles") if isinstance(spec, dict) else None
            if not frag_smiles:
                problems.append(f"compound {c.compound_id}: {position} has no SMILES")
                continue
            frag = Chem.MolFromSmiles(frag_smiles, sanitize=False)
            if frag is None:
                problems.append(f"compound {c.compound_id}: {position} fragment does not parse")
                continue
            Chem.SanitizeMol(frag, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES, catchErrors=True)
            if not c.mol.HasSubstructMatch(frag, useChirality=False):
                problems.append(
                    f"compound {c.compound_id}: {position} fragment {frag_smiles!r} "
                    f"({spec.get('label')}) is not a substructure of the parent"
                )
    return problems


def depict(mol: Chem.Mol, core: Chem.Mol | None, out: Path, size=(320, 240),
           highlight: list[int] | None = None) -> None:
    """Write one core-aligned SVG. Falls back to free coordinates if alignment fails."""
    target = Chem.Mol(mol)
    AllChem.Compute2DCoords(target)
    if core is not None:
        try:
            rdMolDraw2D.PrepareAndDrawMolecule(rdMolDraw2D.MolDraw2DSVG(1, 1), target)  # sanity
        except Exception:
            pass
        try:
            AllChem.GenerateDepictionMatching2DStructure(target, core, acceptFailure=True)
        except Exception:
            AllChem.Compute2DCoords(target)

    drawer = rdMolDraw2D.MolDraw2DSVG(*size)
    opts = drawer.drawOptions()
    opts.clearBackground = False          # the sheet colour shows through
    opts.bondLineWidth = 2
    opts.padding = 0.08
    opts.additionalAtomLabelPadding = 0.04
    rdMolDraw2D.PrepareAndDrawMolecule(
        drawer, target,
        highlightAtoms=highlight or [],
    )
    drawer.FinishDrawing()
    svg = _BLACK.sub("currentColor", drawer.GetDrawingText())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)


def changed_atoms(from_mol: Chem.Mol, to_mol: Chem.Mol) -> tuple[list[int], list[int]]:
    """Atoms that differ between a matched pair, for the edit-log before and after highlight."""
    res = rdFMCS.FindMCS([from_mol, to_mol], timeout=10, ringMatchesRingOnly=True,
                         completeRingsOnly=True)
    if not res or not res.smartsString:
        return [], []
    common = Chem.MolFromSmarts(res.smartsString)
    if common is None:
        return [], []
    a = set(from_mol.GetSubstructMatch(common))
    b = set(to_mol.GetSubstructMatch(common))
    return (
        [i for i in range(from_mol.GetNumAtoms()) if i not in a],
        [i for i in range(to_mol.GetNumAtoms()) if i not in b],
    )


def cliffs(compounds: list[Compound], values: dict[str, float], min_fold: float = 3.0) -> list[dict]:
    """Matched pairs ranked by fold change per heavy atom changed.

    `values` holds the primary potency per compound, already unqualified: a bounded value
    such as '>10000' has no place in a fold ratio and is excluded by the caller.
    """
    by_id = {c.compound_id: c for c in compounds}
    out: list[dict] = []
    ids = [c.compound_id for c in compounds if c.compound_id in values]
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1:]:
            a, b = by_id[a_id], by_id[b_id]
            if a.series != b.series and not _shares_scaffold(a, b):
                continue
            va, vb = values[a_id], values[b_id]
            if va <= 0 or vb <= 0:
                continue
            fold = max(va, vb) / min(va, vb)
            if fold < min_fold:
                continue
            changed_a, changed_b = changed_atoms(a.mol, b.mol)
            n_changed = max(len(changed_a) + len(changed_b), 1)
            out.append({
                "from_compound": a_id if va > vb else b_id,   # from the weaker compound
                "to_compound": b_id if va > vb else a_id,
                "fold": round(fold, 1),
                "atoms_changed": n_changed,
                "fold_per_atom": round(fold / n_changed, 2),
            })
    out.sort(key=lambda r: r["fold_per_atom"], reverse=True)
    return out


def _shares_scaffold(a: Compound, b: Compound) -> bool:
    core, _ = scaffold([a, b], timeout=5)
    if core is None:
        return False
    return core.GetNumHeavyAtoms() >= 0.6 * min(a.mol.GetNumHeavyAtoms(), b.mol.GetNumHeavyAtoms())


def build(slug: str) -> dict:
    """gc chem: descriptors, scaffold, depictions. Writes build/<slug>/compounds.json."""
    slug = paths.check_slug(slug)
    compounds = read_compounds(slug)
    problems = check_r_groups(compounds)

    core, smarts = scaffold(compounds)
    dep_dir = paths.build_dir(slug) / "depictions"
    rows = []
    for c in compounds:
        c.props = descriptors(c.mol)
        rel = f"depictions/{c.compound_id}.svg"
        depict(c.mol, core, dep_dir / f"{c.compound_id}.svg")
        rows.append({
            "compound_id": c.compound_id,
            "label": c.label,
            "series": c.series,
            "role": c.role,
            "smiles": c.smiles,
            "r_groups": c.r_groups,
            "depiction": rel,
            "mol3d": None,
            "source_table": c.source_table,
            "notes": c.notes or None,
            **c.props,
        })

    keys = [r["inchikey"] for r in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        problems.append(f"duplicate InChIKeys, so two rows are the same molecule: {sorted(dupes)}")

    out = paths.build_dir(slug) / "compounds.json"
    out.write_text(json.dumps(rows, indent=1))
    (paths.build_dir(slug) / "scaffold.json").write_text(
        json.dumps({"mcs_smarts": smarts, "n_atoms": core.GetNumHeavyAtoms() if core else 0}, indent=1)
    )
    return {"compounds": len(rows), "scaffold_atoms": core.GetNumHeavyAtoms() if core else 0,
            "problems": problems, "depictions": len(rows)}
