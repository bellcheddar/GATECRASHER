"""Get text and page images out of a publisher PDF, into cache/ only.

This deliberately does not write raw/. The SAR tables in all four papers are images with no
text layer, so their numbers cannot be parsed: they are read off a rendered page by eye and
typed into raw/<slug>/*.tsv by hand, which is also what makes the transcription reviewable.
Publisher PDFs and anything derived verbatim from them stay out of the repository.
"""
from __future__ import annotations

from pathlib import Path

from . import paths


def parse_pages(spec: str, page_count: int) -> list[int]:
    """'3-5,8' -> [3, 4, 5, 8], one-based, clamped to the document."""
    if not spec.strip():
        return []
    wanted: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = part.split("-", 1)
            wanted.extend(range(int(first), int(last) + 1))
        else:
            wanted.append(int(part))
    return [p for p in sorted(set(wanted)) if 1 <= p <= page_count]


def run(slug: str, pdf: str, pages: str = "", dpi: int = 200) -> dict:
    import pymupdf

    slug = paths.check_slug(slug)
    source = Path(pdf).expanduser()
    if not source.is_file():
        raise SystemExit(f"no PDF at {source}")

    doc = pymupdf.open(source)
    text_dir = paths.cache_dir("text")
    text_path = text_dir / f"{slug}.txt"
    text_path.write_text(
        "\n".join(f"\n=== PAGE {i + 1} ===\n" + page.get_text() for i, page in enumerate(doc))
    )

    image_dir = paths.cache_dir("pages")
    images = []
    for number in parse_pages(pages, doc.page_count):
        out = image_dir / f"{slug}_p{number}.png"
        doc[number - 1].get_pixmap(dpi=dpi).save(out)
        images.append(str(out))

    return {"text": str(text_path), "images": images, "page_count": doc.page_count}
