"""Write THIRD_PARTY.md from web/data/software.json.

The About sheet renders the same file, so the page and the repository's licence record
cannot drift apart. Edit software.json, then run `gc third-party`; never edit the output.
"""
from __future__ import annotations

import json

from . import paths

ROOT = paths.WEB_DATA.parents[1]

HEADER = """# Third-party software

GATECRASHER itself is MIT licensed (see `LICENSE`). This file lists everything it uses,
what it uses it for, and under what licence.

**Nothing copyleft is linked into this project.** PLIP is GPL-2.0 and Open Babel, which it
loads, is GPL-2.0: PLIP is invoked as a subprocess and never imported, so neither is
linked into our code, and neither is redistributed. PyMOL is likewise run as a subprocess.
The molecular dynamics stack sits behind the same boundary: OpenMM is LGPL-3.0-or-later
and MDTraj is LGPL-2.1-or-later, and both are imported only inside `pipeline/md/`, which
runs under a different interpreter launched as a subprocess. No module of `gcrash` imports
either, nothing they produce carries their code, and no trajectory tool reaches the browser.
PDF handling uses pypdfium2 rather than PyMuPDF, because PyMuPDF is AGPL-3.0 and this
pipeline imports its PDF library.

**Precompute** tools run on the Mac and never ship. **Browser** libraries are vendored in
`web/js/vendor/` and served from this app's own origin, each with its upstream licence
text beside it, as their licences require.

This file is generated from `web/data/software.json` by `gc third-party`. Edit that file,
not this one.
"""

VENDORED = {
    "Mol*": "`molstar.LICENSE.txt`",
    "Plotly.js": "`plotly.LICENSE.txt`, and `plotly-basic.min.js.LICENSE.txt` for the libraries it bundles",
    "RDKit.js": "`RDKit_minimal.LICENSE.txt` (RDKit.js and RDKit)",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _ref(entry: dict) -> str:
    doi = entry.get("doi")
    return f"[{doi}](https://doi.org/{doi})" if doi else ""


def render() -> str:
    data = json.loads((paths.WEB_DATA / "software.json").read_text())
    out = [HEADER]
    for stage, title in (("precompute", "Precompute"), ("browser", "Browser")):
        rows = [s for s in data["software"] if s["stage"] == stage]
        out.append(f"\n## {title}\n")
        if stage == "browser":
            out.append("| Library | Version | Role | Licence | Notice in `web/js/vendor/` | Reference |")
            out.append("|---|---|---|---|---|---|")
        else:
            out.append("| Tool | Version | Role | Licence | Reference |")
            out.append("|---|---|---|---|---|")
        for s in rows:
            name = f"[{_cell(s['name'])}]({s['url']})"
            cells = [name, s.get("version", ""), _cell(s["role"]), _cell(s["licence"])]
            if stage == "browser":
                cells.append(VENDORED.get(s["name"], ""))
            cells.append(_ref(s))
            out.append("| " + " | ".join(cells) + " |")

    out.append("\n## Data sources\n")
    out.append("| Source | Used for | Reference |")
    out.append("|---|---|---|")
    for d in data["data_sources"]:
        out.append(f"| [{_cell(d['name'])}]({d['url']}) | {_cell(d['role'])} | {_ref(d)} |")
    return "\n".join(out) + "\n"


def build() -> dict:
    missing = [s["name"] for s in json.loads((paths.WEB_DATA / "software.json").read_text())["software"]
               if s["stage"] == "browser" and s["name"] not in VENDORED]
    if missing:
        raise SystemExit(f"browser libraries with no vendored licence notice recorded: {missing}")
    text = render()
    target = ROOT / "THIRD_PARTY.md"
    target.write_text(text)
    return {"path": str(target), "bytes": len(text.encode())}
