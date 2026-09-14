"""`gc <command>`: the precompute pipeline. Mac only, never deployed.

The package is called gcrash rather than gc because gc is a Python built-in module name
and built-in modules always win an import, so a package called gc can never be imported.
The command stays `gc`, as BUILD_SPEC section 4 specifies.
"""
from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from . import paths

app = typer.Typer(add_completion=False, help="GATECRASHER precompute pipeline.")
console = Console()


@app.command()
def extract(slug: str = typer.Argument(..., help="cdk2 | fgfr | kras | jak1"),
            pdf: str = typer.Option(..., help="Path to the publisher PDF."),
            pages: str = typer.Option("", help="Pages to render as images, e.g. 3-5.")):
    """Pull text and page images out of a PDF, for hand transcription into raw/<slug>/.

    This writes to cache/, never to raw/: the published tables are images, so the numbers
    are read by eye and typed into the raw TSVs by hand. Nothing here writes data.
    """
    from . import extract as extract_mod
    result = extract_mod.run(slug, pdf, pages)
    console.print(f"text: [bold]{result['text']}[/bold]")
    for image in result["images"]:
        console.print(f"page image: {image}")


@app.command()
def chem(slug: str):
    """Descriptors, the series scaffold and core-aligned depictions."""
    from . import chem as chem_mod
    result = chem_mod.build(paths.check_slug(slug))
    console.print(f"compounds [bold]{result['compounds']}[/bold], "
                  f"scaffold {result['scaffold_atoms']} atoms, "
                  f"depictions {result['depictions']}")
    _problems(result["problems"])


@app.command()
def struct(slug: str):
    """mmCIF fetch, DSSP, KLIFS pocket mapping and PLIP contacts."""
    from . import struct as struct_mod
    result = struct_mod.build(paths.check_slug(slug))
    for entry in result["structures"]:
        console.print(f"{entry['pdb_id']}: {entry['residues']} residues, "
                      f"{entry['klifs_mapped']} KLIFS-mapped, "
                      f"{entry['interactions']} interactions")
    _problems(result["problems"])


@app.command()
def retrieval(slug: str = typer.Argument("", help="Omit to index every bundled paper.")):
    """Build the in-page search index over this project's own prose and data."""
    from . import retrieval as retrieval_mod
    result = retrieval_mod.build(paths.check_slug(slug) if slug else None)
    console.print(f"units {result['units']}, terms {result['terms']}, "
                  f"{result['bytes'] / 1024:.0f} kB")
    for one, count in result["by_slug"].items():
        console.print(f"  {one}: {count} units")


@app.command()
def dynamics(slug: str = typer.Argument(..., help="cdk2 | fgfr | kras | jak1"),
             pdb: str = typer.Option("", help="One structure, rather than every one in the spec."),
             stage: str = typer.Option("all", help="prepare | equilibrate | produce | analyse | all"),
             chunk_ps: float = typer.Option(250.0, help="Production per process, in picoseconds.")):
    """OpenMM minimisation and a short MD per structure: an RMSF track and a trajectory.

    The work runs under a different interpreter (OpenMM, OpenFF and PDBFixer live in
    FlexAppeal's pixi environment), invoked as a subprocess the way PLIP is. Production runs
    one chunk per process on purpose: OpenMM on Apple's OpenCL leaks about 3 kB per step and
    only a fresh process gives it back.
    """
    from . import dynamics as dynamics_mod
    result = dynamics_mod.build(paths.check_slug(slug), pdb_id=pdb or None,
                                stage=stage, chunk_ps=chunk_ps)
    for line in result["lines"]:
        console.print(line)
    _problems(result["problems"])


@app.command()
def figures(slug: str):
    """PyMOL script, session and still per structure, for taking the view away."""
    from . import figures as figures_mod
    result = figures_mod.build(paths.check_slug(slug))
    console.print(f"scripts {result['scripts']}, sessions {result['sessions']}, "
                  f"stills {result['stills']}")
    _problems(result["problems"])


@app.command()
def bundle(slug: str):
    """Write web/data/papers/<slug>/ from the curated files and the build products."""
    from . import bundle as bundle_mod
    result = bundle_mod.build(paths.check_slug(slug))
    console.print(f"compounds {result['compounds']}, measurements {result['measurements']}, "
                  f"assays {result['assays']}, cliffs {result['cliffs']}, "
                  f"{result['bytes'] / 1024:.0f} kB")
    # A published file the build no longer makes is deleted, and said out loud. A withdrawn
    # trajectory vanishing without a line in the log is how you end up unsure, weeks later,
    # whether it was ever published at all.
    if result["withdrawn"]:
        console.print(f"withdrawn {len(result['withdrawn'])}: "
                      + ", ".join(result["withdrawn"]))
    _problems(result["problems"])


@app.command()
def validate(slug: str = typer.Argument("", help="Omit to validate every bundled paper.")):
    """Schema, provenance, chemistry and cross-reference gates. Non-zero exit on any failure."""
    from . import validate as validate_mod
    slugs = [slug] if slug else [s for s in paths.SLUGS if (paths.PAPERS / s).is_dir()]
    if not slugs:
        raise typer.Exit(code=1)
    failed = False
    for one in slugs:
        report = validate_mod.run(one)
        table = Table(title=f"{one}: coverage", show_header=False, title_justify="left")
        for key, value in report.counts.items():
            table.add_row(key.replace("_", " "), str(value))
        console.print(table)
        for warning in report.warnings:
            console.print(f"[yellow]warn[/yellow] {warning}")
        for failure in report.failures:
            console.print(f"[red]FAIL[/red] {failure}")
        verdict = "[green]passes[/green]" if report.ok else "[red]FAILS[/red]"
        console.print(f"{one} {verdict} with {len(report.failures)} failures, "
                      f"{len(report.warnings)} warnings\n")
        failed = failed or not report.ok
    if failed:
        raise typer.Exit(code=1)


@app.command(name="all")
def run_all(slug: str):
    """chem, struct, bundle, validate, in that order."""
    slug = paths.check_slug(slug)
    chem(slug)
    struct(slug)
    bundle(slug)
    validate(slug)


@app.command(name="third-party")
def third_party():
    """Rewrite THIRD_PARTY.md from web/data/software.json."""
    from . import thirdparty
    result = thirdparty.build()
    console.print(f"{result['path']}: {result['bytes'] / 1024:.1f} kB")


@app.command()
def index():
    """Rewrite web/data/index.json from whatever bundles exist."""
    from . import bundle as bundle_mod
    bundle_mod.write_index()
    console.print(json.dumps(json.loads((paths.WEB_DATA / "index.json").read_text()), indent=1))


def _problems(problems: list[str]) -> None:
    for problem in problems:
        console.print(f"[yellow]problem[/yellow] {problem}")


if __name__ == "__main__":
    app()
