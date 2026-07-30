"""Text, structure and image extraction with PyMuPDF + rule-based heuristics.

The goal is not perfect parsing, it is *useful* parsing: clean body text, a
section tree that matches how papers are actually written, figure captions kept
next to their images, and references chopped off so they never pollute the
index.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from backend.config import ENABLE_IMAGES, MIN_IMAGE_PIXELS

# --------------------------------------------------------------------- rules
CANONICAL_SECTIONS = [
    ("abstract", r"^abstract\b"),
    ("introduction", r"^(1\.?\s*)?introduction\b"),
    ("background", r"^(\d+\.?\s*)?(background|related\s+work|prior\s+work|literature\s+review)\b"),
    ("method", r"^(\d+\.?\s*)?(method(s|ology)?|approach|model|architecture|materials\s+and\s+methods|experimental\s+setup)\b"),
    ("data", r"^(\d+\.?\s*)?(data(set)?s?|corpus)\b"),
    ("results", r"^(\d+\.?\s*)?(results?|findings|experiments?|evaluation)\b"),
    ("discussion", r"^(\d+\.?\s*)?(discussion|analysis|ablation)\b"),
    ("limitations", r"^(\d+\.?\s*)?(limitations?|threats\s+to\s+validity)\b"),
    ("conclusion", r"^(\d+\.?\s*)?(conclusions?|concluding\s+remarks|summary\s+and\s+conclusion)\b"),
    ("references", r"^(references|bibliography)\s*$"),
    ("appendix", r"^(appendix|supplementary)\b"),
    ("acknowledgment", r"^acknowledge?ments?\b"),
]

NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z][^.]{2,80}$")
CAPTION_RE = re.compile(r"^(fig(?:ure)?|table|algorithm)\s*\.?\s*(\d+|[IVX]+)\s*[.:\-–]?\s*(.*)", re.I)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:\w]+\b")
ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})", re.I)
EMAIL_RE = re.compile(r"[\w.\-+]+@[\w\-]+\.[\w.\-]+")


# --------------------------------------------------------------------- types
@dataclass
class Section:
    id: str
    title: str
    canonical: str          # abstract / method / results / other ...
    page_start: int
    page_end: int
    text: str = ""

    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class Figure:
    id: str
    page: int
    path: str
    caption: str = ""
    width: int = 0
    height: int = 0


@dataclass
class ParsedPDF:
    doc_id: str
    filename: str
    title: str
    authors: str
    page_count: int
    metadata: dict[str, Any]
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    full_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ------------------------------------------------------------------- helpers
def _clean(text: str) -> str:
    text = text.replace("\ufb00", "ff").replace("\ufb01", "fi").replace("\ufb02", "fl")
    text = text.replace("\u00ad", "")
    # de-hyphenate across line breaks: "represen-\ntation" -> "representation"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # single newlines inside a paragraph become spaces, blank lines stay
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _canonical_of(title: str) -> str:
    t = title.strip().lower()
    t = re.sub(r"^[ivx]+\.\s*", "", t)
    for name, pattern in CANONICAL_SECTIONS:
        if re.match(pattern, t):
            return name
    return "other"


def _line_records(doc: fitz.Document) -> list[dict[str, Any]]:
    """Flatten the PDF into line records carrying font stats and position."""
    lines: list[dict[str, Any]] = []
    for pno, page in enumerate(doc, start=1):
        blocks = page.get_text("dict").get("blocks", [])
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                sizes = [round(s["size"], 1) for s in spans]
                bold = any("bold" in s.get("font", "").lower() or s.get("flags", 0) & 2 ** 4 for s in spans)
                lines.append(
                    {
                        "page": pno,
                        "text": text,
                        "size": max(sizes),
                        "bold": bold,
                        "y": round(line["bbox"][1], 1),
                        "x": round(line["bbox"][0], 1),
                        "upper_ratio": sum(c.isupper() for c in text) / max(len(text), 1),
                    }
                )
    return lines


def _body_size(lines: list[dict[str, Any]]) -> float:
    sizes = [ln["size"] for ln in lines]
    if not sizes:
        return 10.0
    try:
        return statistics.mode(sizes)
    except statistics.StatisticsError:
        return statistics.median(sizes)


def _is_heading(line: dict[str, Any], body: float) -> bool:
    text = line["text"].strip()
    if len(text) < 3 or len(text) > 110:
        return False
    if text.endswith((".", ",", ";")) and not NUMBERED_HEADING.match(text):
        return False
    if CAPTION_RE.match(text):
        return False
    if EMAIL_RE.search(text) or DOI_RE.search(text):
        return False
    if _canonical_of(text) != "other":
        return True
    bigger = line["size"] >= body * 1.12
    boldish = line["bold"] and line["size"] >= body * 1.0
    shouty = line["upper_ratio"] > 0.7 and len(text.split()) <= 8
    if NUMBERED_HEADING.match(text) and (bigger or boldish):
        return True
    return (bigger or shouty) and len(text.split()) <= 12


def _repeated_lines(lines: list[dict[str, Any]], page_count: int) -> set[str]:
    """Headers/footers: same short string on many pages."""
    from collections import Counter

    counts = Counter(
        ln["text"].strip()
        for ln in lines
        if len(ln["text"].strip()) < 90 and len(ln["text"].split()) <= 14
    )
    threshold = max(3, int(page_count * 0.4))
    return {t for t, c in counts.items() if c >= threshold}


def _guess_title(doc: fitz.Document, lines: list[dict[str, Any]], meta_title: str) -> str:
    if meta_title and 8 < len(meta_title) < 220 and "untitled" not in meta_title.lower():
        return meta_title.strip()
    first_page = [ln for ln in lines if ln["page"] == 1 and ln["y"] < 380]
    if not first_page:
        return "Untitled document"
    top = max(ln["size"] for ln in first_page)
    parts = [ln["text"] for ln in first_page if ln["size"] >= top - 0.6][:4]
    title = " ".join(parts).strip()
    return title[:220] or "Untitled document"


def _guess_authors(lines: list[dict[str, Any]], title: str) -> str:
    cands = [
        ln["text"]
        for ln in lines
        if ln["page"] == 1 and ln["y"] < 520 and ln["text"] not in title
    ]
    for text in cands:
        if EMAIL_RE.search(text):
            continue
        commas = text.count(",")
        words = text.split()
        if 2 <= len(words) <= 40 and (commas >= 1 or " and " in text.lower()):
            if not re.search(r"(abstract|university|institute|department)", text, re.I):
                return text.strip()[:300]
    return ""


# -------------------------------------------------------------------- images
def _extract_images(doc: fitz.Document, out_dir: Path, doc_id: str,
                    captions_by_page: dict[int, list[str]]) -> list[Figure]:
    if not ENABLE_IMAGES:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    figures: list[Figure] = []
    seen: set[int] = set()
    for pno, page in enumerate(doc, start=1):
        for idx, info in enumerate(page.get_images(full=True)):
            xref = info[0]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.width * pix.height < MIN_IMAGE_PIXELS:
                    continue
                if pix.n - pix.alpha >= 4:  # CMYK -> RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                fid = f"{doc_id}_p{pno}_i{idx}"
                path = out_dir / f"{fid}.png"
                pix.save(path)
                caps = captions_by_page.get(pno, [])
                figures.append(
                    Figure(
                        id=fid,
                        page=pno,
                        path=str(path),
                        caption=caps.pop(0) if caps else "",
                        width=pix.width,
                        height=pix.height,
                    )
                )
            except Exception:
                continue
            finally:
                pix = None
    return figures


# --------------------------------------------------------------------- main
def parse_pdf(pdf_path: str | Path, doc_id: str, image_dir: Path) -> ParsedPDF:
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)

    lines = _line_records(doc)
    body = _body_size(lines)
    junk = _repeated_lines(lines, doc.page_count)

    captions_by_page: dict[int, list[str]] = {}
    for ln in lines:
        m = CAPTION_RE.match(ln["text"])
        if m and m.group(1).lower().startswith("fig"):
            captions_by_page.setdefault(ln["page"], []).append(ln["text"].strip())

    meta = doc.metadata or {}
    title = _guess_title(doc, lines, meta.get("title", "") or "")
    authors = _guess_authors(lines, title)

    # --- walk lines, cutting a new section every time a heading appears
    sections: list[Section] = []
    current = Section(id="s0", title="Front matter", canonical="frontmatter",
                      page_start=1, page_end=1)
    buffer: list[str] = []
    stop_indexing = False

    for ln in lines:
        text = ln["text"].strip()
        if text in junk or re.fullmatch(r"[\d\s\-–—|]+", text):
            continue
        if _is_heading(ln, body):
            canon = _canonical_of(text)
            current.text = _clean("\n".join(buffer))
            if current.text or current.canonical != "frontmatter":
                sections.append(current)
            buffer = []
            current = Section(
                id=f"s{len(sections)}",
                title=re.sub(r"\s+", " ", text)[:120],
                canonical=canon,
                page_start=ln["page"],
                page_end=ln["page"],
            )
            # everything after References is noise for retrieval
            stop_indexing = canon in {"references", "acknowledgment"}
            continue
        if stop_indexing:
            continue
        buffer.append(text)
        current.page_end = ln["page"]

    current.text = _clean("\n".join(buffer))
    sections.append(current)
    sections = [s for s in sections if s.word_count() >= 12 or s.canonical == "abstract"]

    figures = _extract_images(doc, image_dir, doc_id, dict(captions_by_page))
    full_text = "\n\n".join(f"## {s.title}\n{s.text}" for s in sections)

    ids = {"doi": "", "arxiv": ""}
    head = full_text[:4000]
    if (m := DOI_RE.search(head)):
        ids["doi"] = m.group(0)
    if (m := ARXIV_RE.search(head)):
        ids["arxiv"] = m.group(1)

    parsed = ParsedPDF(
        doc_id=doc_id,
        filename=pdf_path.name,
        title=title,
        authors=authors,
        page_count=doc.page_count,
        metadata={
            "pdf_title": meta.get("title", ""),
            "pdf_author": meta.get("author", ""),
            "created": meta.get("creationDate", ""),
            **ids,
        },
        sections=sections,
        figures=figures,
        full_text=full_text,
    )
    doc.close()
    return parsed


def section_by_kind(parsed: ParsedPDF, kind: str) -> Section | None:
    for s in parsed.sections:
        if s.canonical == kind:
            return s
    return None
