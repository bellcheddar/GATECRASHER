"""Where everything lives. One place, so no module guesses a path."""
from __future__ import annotations

from pathlib import Path

PIPELINE = Path(__file__).resolve().parent.parent
REPO = PIPELINE.parent

RAW = PIPELINE / "raw"
SCHEMAS = PIPELINE / "schemas"
CACHE = PIPELINE / "cache"           # never committed: PDFs, mmCIF, DSSP, PLIP scratch
BUILD = PIPELINE / "build"           # never committed: intermediates between gc steps

WEB = REPO / "web"
WEB_DATA = WEB / "data"
PAPERS = WEB_DATA / "papers"

SLUGS = ("cdk2", "fgfr", "kras", "jak1")


def raw_dir(slug: str) -> Path:
    return RAW / slug


def build_dir(slug: str) -> Path:
    p = BUILD / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def bundle_dir(slug: str) -> Path:
    p = PAPERS / slug
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(*parts: str) -> Path:
    p = CACHE.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def check_slug(slug: str) -> str:
    if slug not in SLUGS:
        raise SystemExit(f"unknown paper slug {slug!r}: expected one of {', '.join(SLUGS)}")
    if not raw_dir(slug).is_dir():
        raise SystemExit(f"no curated data at {raw_dir(slug)}")
    return slug
