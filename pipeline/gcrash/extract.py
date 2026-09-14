"""Get text and page images out of a publisher PDF, into cache/ only.

This deliberately does not write raw/. The SAR tables in all four papers are images with no
text layer, so their numbers cannot be parsed: they are read off a rendered page by eye and
typed into raw/<slug>/*.tsv by hand, which is also what makes the transcription reviewable.
Publisher PDFs and anything derived verbatim from them stay out of the repository.

PDF handling is pypdfium2 (BSD-3-Clause / Apache-2.0), not PyMuPDF. PyMuPDF is AGPL-3.0,
and because this module imports it, keeping it would have made the whole project AGPL. See
THIRD_PARTY.md.
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
    import pypdfium2 as pdfium

    slug = paths.check_slug(slug)
    source = Path(pdf).expanduser()
    if not source.is_file():
        raise SystemExit(f"no PDF at {source}")

    doc = pdfium.PdfDocument(source)
    try:
        page_count = len(doc)
        chunks = []
        for i in range(page_count):
            textpage = doc[i].get_textpage()
            chunks.append(f"\n=== PAGE {i + 1} ===\n" + textpage.get_text_bounded())
            textpage.close()
        text_path = paths.cache_dir("text") / f"{slug}.txt"
        text_path.write_text("\n".join(chunks))

        image_dir = paths.cache_dir("pages")
        images = []
        for number in parse_pages(pages, page_count):
            out = image_dir / f"{slug}_p{number}.png"
            # PDF user space is 72 points per inch, so the scale for a given dpi is dpi / 72.
            doc[number - 1].render(scale=dpi / 72).to_pil().save(out)
            images.append(str(out))
    finally:
        doc.close()

    return {"text": str(text_path), "images": images, "page_count": page_count}
