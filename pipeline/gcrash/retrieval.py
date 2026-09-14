"""Build the in-page search index. BUILD_SPEC 5.7 and Stage 4.

Two decisions here diverge from a literal reading of the spec. Both are deliberate and
both are forced.

**1. Only this project's own text is indexed.** The spec describes chunking the papers
themselves. An index shipped to the browser is published: anyone can read it straight out
of the JSON, so chunking the publishers' prose would breach ground rule 3 however it is
framed. The corpus is what this project wrote (story beats in both registers, edit
rationales, structure captions, the issues notes) plus the measured data rendered as
sentences: about 12,700 words over roughly 200 units. Searching for a contact or a
compound returns our sentence about it, with a link into the app.

**2. The search is lexical, not embedding cosine.** The spec asks for a precomputed
embedding index searched by cosine in the browser, and in the same breath says the browser
embeds nothing and runs no model. Those cannot both hold: a cosine search has to embed the
QUERY, and with no server (ground rule 2) and no runtime model there is nowhere to do it.
chatMCD can do this because it has a server process. This app does not.

So the index is BM25 over our own text, computed in the page. For a corpus this small that
is not a compromise: ~200 documents is instant, the index is a few hundred kilobytes of
JSON, there is no model to load, and the matching is explainable, which matters when the
honest answer is often "not stated in this paper". Term statistics are precomputed here so
the page only scores.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

from . import paths

# Short function words carry no signal and inflate every score.
STOP = set("""a an and are as at be been but by for from had has have in into is it its of
on or that the their then there these they this to was were which will with without would
its it's we our us you your he she them can could may might must should than when where
who whom whose how why what if not no nor only own same so too very just also each both
more most other some such over under again further once here all any""".split())

TOKEN = re.compile(r"[a-z0-9][a-z0-9\-']*")


def tokenise(text: str) -> list[str]:
    """Lowercase word tokens, minus stop words.

    Chemistry makes this slightly unusual: residue names (Asp86), PDB codes (8UV0) and
    compound numbers all matter and are exactly the sort of token a naive tokeniser
    mangles, so digits are kept inside tokens and hyphens are preserved.
    """
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


def _rows(path: Path):
    with path.open() as fh:
        yield from csv.DictReader((l for l in fh if not l.startswith("#")), delimiter="\t")


def units_for(slug: str) -> list[dict]:
    """Every searchable unit for one paper, each carrying what the app needs to act on a hit."""
    raw = paths.raw_dir(slug)
    out: list[dict] = []

    def add(kind, title, text, focus=None, source=None):
        text = " ".join(str(text).split())
        if len(text) < 40:
            return
        out.append({
            "id": f"{slug}-{kind}-{len(out):03d}",
            "slug": slug, "kind": kind, "title": title, "text": text,
            "focus": focus or {}, "source": source,
        })

    paper = json.loads((raw / "paper.json").read_text())
    add("paper", paper["title"], paper["one_line"], {"tab": "story"}, paper["doi"])
    for key, label in (("disease", "The disease"), ("selectivity", "The selectivity problem"),
                       ("property", "The property problem")):
        add("problem", label, paper["problem"][key], {"tab": "story"}, paper["doi"])

    story = raw / "story.json"
    if story.exists():
        for beat in json.loads(story.read_text())["beats"]:
            focus = {"tab": "story", "beat": beat["id"], **(beat.get("focus") or {})}
            add("beat", beat["title"], beat["body_specialist"], focus, beat["evidence"])
            add("beat_plain", beat["title"], beat["body_plain"], focus, beat["evidence"])

    edits = raw / "edits.tsv"
    if edits.exists():
        for row in _rows(edits):
            focus = {"tab": "structure", "edit": row["edit_id"],
                     "compound": row["to_compound"],
                     "residues": json.loads(row["structural_basis"] or "[]")}
            add("edit", row["headline"], row["rationale_specialist"], focus, row["evidence"])
            add("edit_plain", row["headline"], row["rationale_plain"], focus, row["evidence"])

    for entry in json.loads((raw / "structures.json").read_text()):
        focus = {"tab": "structure", "structure": entry["pdb_id"]}
        add("structure", f"{entry['pdb_id']}, {entry['contains']['protein']}",
            entry["caption_specialist"], focus, entry.get("evidence"))
        add("structure_plain", f"{entry['pdb_id']}, {entry['contains']['protein']}",
            entry["caption_plain"], focus, entry.get("evidence"))

    issues = raw / "ISSUES.md"
    if issues.exists():
        text = issues.read_text()
        for match in re.finditer(r"^\d+\.\s+\*\*(.+?)\*\*(.*?)(?=^\d+\.\s+\*\*|\Z)",
                                 text, re.S | re.M):
            add("issue", match.group(1).strip().rstrip("."),
                match.group(1) + " " + match.group(2), {"tab": "about"}, "ISSUES")

    # The data itself as sentences, so a measured number is findable in words.
    compounds = {r["compound_id"]: r for r in _rows(raw / "compounds.tsv")}
    assays = json.loads((raw / "assays.json").read_text())
    measurements = paths.bundle_dir(slug) / "measurements.csv"
    if measurements.exists():
        by_compound: dict[str, list[str]] = {}
        with measurements.open() as fh:
            for row in csv.DictReader(fh):
                spec = assays.get(row["assay_id"])
                if not spec or not row["value"]:
                    continue
                q = "" if row["qualifier"] == "=" else row["qualifier"]
                by_compound.setdefault(row["compound_id"], []).append(
                    f"{spec['label']} {q}{row['value']} {spec['units']}")
        for compound_id, facts in by_compound.items():
            info = compounds.get(compound_id)
            if not info:
                continue
            add("compound", f"Compound {info['label']}",
                f"Compound {info['label']}, {info['series']} series, {info['role']}: "
                + "; ".join(facts[:14]) + ". " + (info.get("notes") or ""),
                {"tab": "sar", "compound": compound_id}, info.get("source_table"))
    return out


def build(slug: str | None = None) -> dict:
    """gc retrieval: one index across every bundled paper, written to web/data/search.json."""
    slugs = [slug] if slug else [s for s in paths.SLUGS if (paths.PAPERS / s).is_dir()]
    units: list[dict] = []
    for one in slugs:
        units.extend(units_for(paths.check_slug(one)))

    # BM25 statistics, computed once here so the page only has to score.
    docs = []
    df = Counter()
    for unit in units:
        tokens = tokenise(f"{unit['title']} {unit['text']}")
        counts = Counter(tokens)
        docs.append({"tf": dict(counts), "len": len(tokens)})
        df.update(counts.keys())

    n = len(units) or 1
    avg_len = sum(d["len"] for d in docs) / n
    idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    payload = {
        "note": ("Only this project's own prose and its measured data are indexed. No text "
                 "from the publishers' papers is chunked, stored or shipped."),
        "scoring": "bm25",
        "k1": 1.5,
        "b": 0.75,
        "count": n,
        "avg_len": round(avg_len, 2),
        "idf": {term: round(value, 4) for term, value in sorted(idf.items())},
        "units": [
            {**{k: unit[k] for k in ("id", "slug", "kind", "title", "text", "focus", "source")},
             "tf": docs[i]["tf"], "len": docs[i]["len"]}
            for i, unit in enumerate(units)
        ],
    }

    out = paths.WEB_DATA / "search.json"
    out.write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "units": n,
        "terms": len(idf),
        "bytes": out.stat().st_size,
        "by_slug": {s: sum(1 for u in units if u["slug"] == s) for s in slugs},
    }
