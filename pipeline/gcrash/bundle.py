"""Assemble web/data/papers/<slug>/ from the curated raw files and the gc chem / gc struct output.

The wide published tables are melted into long-format measurements here, driven entirely by
raw/<slug>/tables.json, so a paper with a different assay panel needs new data, not new code.
"""
from __future__ import annotations

import csv
import gzip
import json
import shutil
from pathlib import Path

from . import chem, paths

QUALIFIERS = ("<=", ">=", "<", ">", "~", "=")


def parse_value(raw: str) -> tuple[float | None, str] | None:
    """'<0.001' -> (0.001, '<'). Returns None for an empty cell, which becomes no row at all.

    A bound is never coerced to a number: the qualifier travels with the value all the way
    to the table cell, so '>10000' can never be sorted or plotted as if it were 10000.
    """
    text = (raw or "").strip()
    if text == "" or text.lower() in ("na", "n/a", "nd", "-"):
        return None
    qualifier = "="
    for q in QUALIFIERS:
        if text.startswith(q):
            qualifier = "<" if q == "<=" else (">" if q == ">=" else q)
            text = text[len(q):].strip()
            break
    text = text.replace(",", "")
    try:
        return float(text), qualifier
    except ValueError:
        return None


def _rows(path: Path):
    with path.open() as fh:
        yield from csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")


def measurements(slug: str, assays: dict) -> tuple[list[dict], list[str]]:
    spec = json.loads((paths.raw_dir(slug) / "tables.json").read_text())
    out: list[dict] = []
    problems: list[str] = []
    for table in spec["tables"]:
        path = paths.raw_dir(slug) / table["file"]
        source = table["source_table"]
        note_col = table.get("note_column")
        species_col = table.get("species_column")
        for row in _rows(path):
            compound_id = row["compound_id"].strip()
            if species_col:
                species = (row.get(species_col) or "").strip()
                columns = (table.get("columns_by_species") or {}).get(species)
                if columns is None:
                    problems.append(f"{table['file']}: no column map for species {species!r}")
                    continue
            else:
                columns = table["columns"]
            for column, assay_id in columns.items():
                parsed = parse_value(row.get(column, ""))
                if parsed is None:
                    continue
                if assay_id not in assays:
                    problems.append(f"{table['file']}: column {column} maps to unknown assay {assay_id}")
                    continue
                value, qualifier = parsed
                out.append({
                    "compound_id": compound_id,
                    "assay_id": assay_id,
                    "value": value,
                    "qualifier": qualifier,
                    "units": assays[assay_id]["units"],
                    "n": None,
                    "source_table": source,
                    "source_note": (row.get(note_col) or "").strip() or None if note_col else None,
                })
    return out, problems


def primary_values(assays: dict, rows: list[dict]) -> dict[str, float]:
    """Unqualified primary potency per compound, for the activity cliff ranking."""
    primary = next((a for a, spec in assays.items() if spec.get("is_primary")), None)
    if primary is None:
        return {}
    return {r["compound_id"]: r["value"] for r in rows
            if r["assay_id"] == primary and r["qualifier"] == "=" and r["value"]}


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else
                                 json.dumps(row[k]) if isinstance(row[k], (dict, list)) else row[k])
                             for k in fields})


def edits(slug: str) -> list[dict]:
    rows = []
    for row in _rows(paths.raw_dir(slug) / "edits.tsv"):
        rows.append({
            **row,
            "consequences": json.loads(row["consequences"] or "[]"),
            "structural_basis": json.loads(row["structural_basis"] or "[]"),
        })
    return rows


def build(slug: str) -> dict:
    slug = paths.check_slug(slug)
    raw, build_d, out = paths.raw_dir(slug), paths.build_dir(slug), paths.bundle_dir(slug)

    assays = json.loads((raw / "assays.json").read_text())
    compounds = json.loads((build_d / "compounds.json").read_text())
    rows, problems = measurements(slug, assays)

    # compounds.csv
    fields = ["compound_id", "label", "series", "role", "smiles", "inchikey", "r_groups",
              "mw", "clogp", "tpsa", "hbd", "hba", "rotb", "hac", "fsp3",
              "depiction", "mol3d", "source_table", "notes"]
    _write_csv(out / "compounds.csv", compounds, fields)
    _write_csv(out / "measurements.csv", rows,
               ["compound_id", "assay_id", "value", "qualifier", "units", "n",
                "source_table", "source_note"])

    # straight copies of the curated artefacts
    for name in ("paper.json", "assays.json", "structures.json"):
        shutil.copy2(raw / name, out / name)
    (out / "edits.json").write_text(json.dumps(edits(slug), indent=1))
    story = raw / "story.json"
    if story.exists():
        shutil.copy2(story, out / "story.json")

    # structure products
    if (build_d / "residues.csv").exists():
        shutil.copy2(build_d / "residues.csv", out / "residues.csv")
    if (build_d / "interactions").is_dir():
        target = out / "interactions"
        target.mkdir(exist_ok=True)
        for src in (build_d / "interactions").glob("*.json"):
            shutil.copy2(src, target / src.name)

    # depictions
    dep_out = out / "depictions"
    dep_out.mkdir(exist_ok=True)
    for src in (build_d / "depictions").glob("*.svg"):
        shutil.copy2(src, dep_out / src.name)

    # PyMOL deliverables, where gc figures has produced them. A .pse is several megabytes,
    # so it is published as a download rather than anything the page loads.
    if (build_d / "figures").is_dir():
        fig_out = out / "figures"
        fig_out.mkdir(exist_ok=True)
        manifest: dict[str, dict] = {}
        for src in sorted((build_d / "figures").iterdir()):
            if not src.is_file():
                continue
            shutil.copy2(src, fig_out / src.name)
            # Files are named <pdbid>_gatecrasher.pml / .pse and <pdbid>.png, so the entry
            # they belong to is the leading token. A manifest means the page can offer only
            # the downloads that exist, rather than linking at a URL and hoping.
            pdb_id = src.stem.split("_")[0].upper()
            entry = manifest.setdefault(pdb_id, {})
            entry[src.suffix.lstrip(".")] = f"figures/{src.name}"
            entry[f"{src.suffix.lstrip('.')}_bytes"] = src.stat().st_size
        (out / "figures.json").write_text(json.dumps(manifest, indent=1))

    # activity cliffs, from the primary potency only
    cliff_rows = chem.cliffs(chem.read_compounds(slug), primary_values(assays, rows))
    (out / "cliffs.json").write_text(json.dumps(cliff_rows[:40], indent=1))

    write_index()
    return {
        "compounds": len(compounds),
        "measurements": len(rows),
        "assays": len(assays),
        "cliffs": len(cliff_rows),
        "problems": problems,
        "bytes": sum(f.stat().st_size for f in out.rglob("*") if f.is_file()),
    }


def write_index() -> None:
    """web/data/index.json: which papers exist and at which bundle version."""
    entries = []
    for slug in paths.SLUGS:
        paper_file = paths.PAPERS / slug / "paper.json"
        if not paper_file.exists():
            continue
        paper = json.loads(paper_file.read_text())
        entries.append({
            "slug": slug,
            "title": paper["title"],
            "authors_short": paper["authors_short"],
            "year": paper["year"],
            "target": paper["target"]["name"],
            "one_line": paper["one_line"],
            "bundle_version": paper["bundle_version"],
        })
    paths.WEB_DATA.mkdir(parents=True, exist_ok=True)
    (paths.WEB_DATA / "index.json").write_text(json.dumps({"papers": entries}, indent=1))
