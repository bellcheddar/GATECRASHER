"""`gc dynamics`: drive the OpenMM stages and collect what they produce.

The simulation itself runs under a DIFFERENT interpreter. OpenMM, OpenFF, openmmforcefields
and PDBFixer live in FlexAppeal's pixi environment (HARVEST.md), and this module invokes
pipeline/md/run_md.py there as a subprocess, the way the PLIP stage shells out rather than
imports. Nothing in gcrash imports OpenMM.

Production runs ONE chunk per process, in a loop here. OpenMM on Apple's OpenCL leaks about
3 kB per step, which a 5 ns run turns into gigabytes, and only a fresh process gives it back.

Work lives in cache/md/<PDB_ID>/ and is resumable: each stage checks what the last one left
behind, so an interrupted run continues rather than starting again.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import paths, struct

# FlexAppeal's environment, overridable for a machine that keeps it somewhere else.
DEFAULT_MD_PYTHON = Path.home() / "Documents/Vibe_Coding/FlexAppeal/.pixi/envs/default/bin/python"
RUNNER = paths.PIPELINE / "md" / "run_md.py"
ANALYSER = paths.PIPELINE / "md" / "analyse_md.py"


def md_python() -> Path:
    """The interpreter that has OpenMM. Named, checked, and never guessed at silently."""
    chosen = Path(os.environ.get("GATECRASHER_MD_PYTHON", DEFAULT_MD_PYTHON))
    if not chosen.is_file():
        raise SystemExit(
            f"no MD interpreter at {chosen}. Set GATECRASHER_MD_PYTHON to a python that has "
            f"openmm, openmmforcefields, openff-toolkit and pdbfixer (HARVEST.md explains "
            f"why this stage borrows FlexAppeal's environment rather than installing its own).")
    return chosen


def _run(args: list[str], lines: list[str]) -> None:
    """Invoke the runner with AmberTools on PATH, streaming what it says into the report.

    AMBERHOME and PATH matter: without the environment's bin on PATH the OpenFF toolkit does
    not register AmberTools, silently falls back to a graph-network charge model, and the
    ligand is parameterised by something other than AM1-BCC with nothing in the output to
    say so.
    """
    python = md_python()
    env = dict(os.environ)
    env["PATH"] = f"{python.parent}:{env.get('PATH', '')}"
    env["AMBERHOME"] = str(python.parent.parent)
    result = subprocess.run([str(python), str(RUNNER), *args], env=env,
                            capture_output=True, text=True)
    for line in (result.stdout or "").splitlines():
        if line.strip() and "warning" not in line.lower():
            lines.append(line.rstrip())
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").strip().splitlines()[-6:])
        raise SystemExit(f"{' '.join(args[:2])} failed:\n{tail}")


def build(slug: str, pdb_id: str | None = None, stage: str = "all",
          chunk_ps: float = 250.0) -> dict:
    spec_path = paths.raw_dir(slug) / "dynamics.json"
    if not spec_path.is_file():
        raise SystemExit(f"{slug}: no dynamics.json. Nothing says what to simulate, so nothing runs.")
    spec = json.loads(spec_path.read_text())

    entries = spec.get("structures", [])
    if pdb_id:
        entries = [e for e in entries if e["pdb_id"].upper() == pdb_id.upper()]
        if not entries:
            raise SystemExit(f"{slug}: dynamics.json has no entry for {pdb_id}")

    lines: list[str] = []
    problems: list[str] = []
    out_dir = paths.build_dir(slug) / "dynamics"
    out_dir.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        pdb = entry["pdb_id"].upper()
        work = paths.cache_dir("md", pdb)
        cif = struct.fetch_cif(pdb)
        lines.append(f"[bold]{pdb}[/bold] in {work}")

        if stage in ("prepare", "all") and not (work / "prepared.json").exists():
            _run(["prepare", "--spec", str(spec_path), "--pdb-id", pdb,
                  "--cif", str(cif), "--out", str(work)], lines)
        if stage in ("equilibrate", "all") and not (work / "progress.json").exists():
            _run(["equilibrate", "--out", str(work)], lines)

        if stage in ("produce", "all"):
            while True:
                progress = json.loads((work / "progress.json").read_text())
                if progress["done_ps"] >= progress["production_ps"]:
                    break
                # One chunk, one process: see the note at the top of this file.
                _run(["produce", "--out", str(work), "--chunk-ps", str(chunk_ps)], lines)

        if stage in ("analyse", "all"):
            if not (work / "traj.dcd").exists():
                problems.append(f"{pdb}: no trajectory to analyse yet")
                continue
            python = md_python()
            env = dict(os.environ)
            env["PATH"] = f"{python.parent}:{env.get('PATH', '')}"
            result = subprocess.run(
                [str(python), str(ANALYSER), "--work", str(work), "--spec", str(spec_path),
                 "--pdb-id", pdb, "--interactions",
                 str(paths.build_dir(slug) / "interactions" / f"{pdb}.json"),
                 "--out", str(out_dir)],
                env=env, capture_output=True, text=True)
            for line in (result.stdout or "").splitlines():
                if line.strip():
                    lines.append(line.rstrip())
            if result.returncode != 0:
                tail = "\n".join((result.stderr or "").strip().splitlines()[-6:])
                raise SystemExit(f"{pdb}: analysis failed:\n{tail}")

            report = json.loads((out_dir / f"{pdb}.json").read_text())
            if report["verdict"] != "supports":
                # BUILD_SPEC Stage 4: a trajectory that does not support what the paper claims
                # does not ship, and ISSUES.md says why. Loud here, so it cannot pass unseen.
                problems.append(
                    f"{pdb}: {report['verdict']}. "
                    + "; ".join(f"{c['id']} {c['occupancy']:.0%} ({c['expect']})"
                                for c in report["claims"] if not c["pass"])
                    + f". The trajectory is not published: record it in raw/{slug}/ISSUES.md")

    return {"lines": lines, "problems": problems}
