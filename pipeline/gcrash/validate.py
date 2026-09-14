"""The gate. Schema conformance, provenance, chemistry and cross-reference integrity.

BUILD_SPEC ground rule 7: provenance or it does not render. A measurement without a
source_table fails the build, and so does a residue cited by an edit that does not exist
in the structure it is cited against.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from rdkit import Chem, RDLogger

from . import paths

RDLogger.DisableLog("rdApp.*")


class Report:
    def __init__(self, slug: str):
        self.slug = slug
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.counts: dict[str, int] = {}

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.failures


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((paths.SCHEMAS / f"{name}.schema.json").read_text()))


def _read_csv(path: Path) -> list[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def _typed_compounds(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        for key in ("mw", "clogp", "tpsa", "fsp3"):
            item[key] = float(row[key])
        for key in ("hbd", "hba", "rotb", "hac"):
            item[key] = int(row[key])
        item["r_groups"] = json.loads(row["r_groups"] or "{}")
        item["mol3d"] = row["mol3d"] or None
        item["notes"] = row["notes"] or None
        out.append(item)
    return out


def _typed_measurements(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["value"] = float(row["value"]) if row["value"] not in ("", None) else None
        item["n"] = int(row["n"]) if row["n"] else None
        item["source_note"] = row["source_note"] or None
        out.append(item)
    return out


def _typed_residues(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        item["resnum"] = int(row["resnum"])
        item["klifs_index"] = row["klifs_index"] if row["klifs_index"] == "NA" else int(row["klifs_index"])
        item["role_note"] = row["role_note"] or None
        out.append(item)
    return out


def run(slug: str) -> Report:
    slug = paths.check_slug(slug)
    bundle = paths.PAPERS / slug
    report = Report(slug)
    if not bundle.is_dir():
        report.fail(f"no bundle at {bundle}: run gc bundle {slug} first")
        return report

    # ---------------------------------------------------------------- schema gate
    paper = json.loads((bundle / "paper.json").read_text())
    assays = json.loads((bundle / "assays.json").read_text())
    structures = json.loads((bundle / "structures.json").read_text())
    compounds = _typed_compounds(_read_csv(bundle / "compounds.csv"))
    measurements = _typed_measurements(_read_csv(bundle / "measurements.csv"))
    edits = json.loads((bundle / "edits.json").read_text())
    residues = _typed_residues(_read_csv(bundle / "residues.csv")) if (bundle / "residues.csv").exists() else []

    for name, payload in (("paper", paper), ("assays", assays), ("structures", structures),
                          ("compounds", compounds), ("measurements", measurements),
                          ("edits", edits), ("residues", residues)):
        if name == "residues" and not residues:
            report.warn("no residues.csv: gc struct has not run for this paper")
            continue
        for error in sorted(_schema(name).iter_errors(payload), key=lambda e: list(e.path)):
            location = "/".join(str(p) for p in error.path)
            report.fail(f"{name}.schema: {location or '(root)'}: {error.message}")

    for path in sorted((bundle / "interactions").glob("*.json")) if (bundle / "interactions").is_dir() else []:
        payload = json.loads(path.read_text())
        for error in _schema("interactions").iter_errors(payload):
            report.fail(f"interactions/{path.name}: {error.message}")

    # ------------------------------------------------------------ provenance gate
    for row in measurements:
        if not (row.get("source_table") or "").strip():
            report.fail(f"measurement {row['compound_id']}/{row['assay_id']} has no source_table")
    for row in compounds:
        if not (row.get("source_table") or "").strip():
            report.fail(f"compound {row['compound_id']} has no source_table")

    # ------------------------------------------------------------- chemistry gate
    seen: dict[str, str] = {}
    for row in compounds:
        mol = Chem.MolFromSmiles(row["smiles"])
        if mol is None:
            report.fail(f"compound {row['compound_id']}: SMILES does not parse")
            continue
        key = Chem.MolToInchiKey(mol)
        if key != row["inchikey"]:
            report.fail(f"compound {row['compound_id']}: InChIKey does not match its SMILES")
        if key in seen:
            report.fail(f"compound {row['compound_id']} is the same molecule as {seen[key]}")
        seen[key] = row["compound_id"]
        for position, spec in (row["r_groups"] or {}).items():
            frag = Chem.MolFromSmiles(spec["smiles"], sanitize=False)
            if frag is None or not mol.HasSubstructMatch(frag):
                report.fail(f"compound {row['compound_id']}: R-group {position} "
                            f"({spec.get('label')}) is not present in the parent structure")

    # ------------------------------------------------------------ reference gates
    compound_ids = {row["compound_id"] for row in compounds}
    primary = [a for a, spec in assays.items() if spec.get("is_primary")]
    if len(primary) != 1:
        report.fail(f"expected exactly one is_primary assay, found {len(primary)}")

    for row in measurements:
        if row["compound_id"] not in compound_ids:
            report.fail(f"measurement cites unknown compound {row['compound_id']}")
        if row["assay_id"] not in assays:
            report.fail(f"measurement cites unknown assay {row['assay_id']}")
    for assay_id, spec in assays.items():
        for link in ("anti_target_of", "of_assay"):
            if spec.get(link) and spec[link] not in assays:
                report.fail(f"assay {assay_id}: {link} points at unknown assay {spec[link]}")

    measured = {row["assay_id"] for row in measurements}
    for assay_id in assays:
        if assay_id not in measured:
            report.warn(f"assay {assay_id} is declared but never measured")
    for compound_id in compound_ids:
        if not any(row["compound_id"] == compound_id for row in measurements):
            report.warn(f"compound {compound_id} has no measurements")

    # structure gate: every cited residue must exist in the structure it is cited against
    residue_keys = {f"{row['chain']}:{row['resnum']}" for row in residues}
    for edit in edits:
        for ref in (edit.get("structural_basis") or []):
            if residues and ref not in residue_keys:
                report.fail(f"edit {edit['edit_id']} cites residue {ref}, "
                            f"which is not in residues.csv")
        for consequence in edit.get("consequences") or []:
            if consequence["assay_id"] not in assays:
                report.fail(f"edit {edit['edit_id']} cites unknown assay {consequence['assay_id']}")
        for key in ("from_compound", "to_compound"):
            if edit[key] not in compound_ids:
                report.fail(f"edit {edit['edit_id']} cites unknown compound {edit[key]}")

    story_path = bundle / "story.json"
    if story_path.exists():
        story = json.loads(story_path.read_text())
        for beat in story.get("beats", []):
            focus = beat.get("focus") or {}
            for ref in focus.get("residues") or []:
                if residues and ref not in residue_keys:
                    report.fail(f"beat {beat['id']} focuses residue {ref}, not in residues.csv")
            if focus.get("compound") and focus["compound"] not in compound_ids:
                report.fail(f"beat {beat['id']} focuses unknown compound {focus['compound']}")
            if focus.get("edit") and focus["edit"] not in {e["edit_id"] for e in edits}:
                report.fail(f"beat {beat['id']} focuses unknown edit {focus['edit']}")
    else:
        report.warn("no story.json: the Story sheet has nothing to render yet")

    # every compound with a structure should have a ligand code that matches
    for entry in structures:
        ligand_compound = (entry.get("contains") or {}).get("ligand_compound_id")
        if ligand_compound and ligand_compound not in compound_ids:
            report.fail(f"structure {entry['pdb_id']} names ligand compound "
                        f"{ligand_compound}, which is not in compounds.csv")

    report.counts = {
        "compounds": len(compounds),
        "measurements": len(measurements),
        "assays": len(assays),
        "structures": len(structures),
        "residues": len(residues),
        "residues_with_motif": sum(1 for r in residues if r["motif"] != "other"),
        "klifs_mapped": sum(1 for r in residues if r["klifs_index"] != "NA"),
        "edits": len(edits),
        "cliffs": len(json.loads((bundle / "cliffs.json").read_text())) if (bundle / "cliffs.json").exists() else 0,
    }
    return report
