"""Section-aware chunking.

Chunks never cross a section boundary, and each one carries its section title in
the embedded text, so a query like "what dataset did they use" lands on the Data
section even when the sentence itself never says "dataset".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable

from backend.config import CHUNK_OVERLAP_WORDS, CHUNK_WORDS
from backend.ingestion.pdf_extract import ParsedPDF

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


@dataclass
class Chunk:
    id: str
    doc_id: str
    doc_title: str
    section_title: str
    section_kind: str
    page_start: int
    page_end: int
    text: str
    kind: str = "text"  # text | table | caption

    def embed_text(self) -> str:
        return f"{self.doc_title} | {self.section_title}\n{self.text}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pack(sentences: Iterable[str], size: int, overlap: int) -> list[str]:
    out, buf, count = [], [], 0
    for sent in sentences:
        words = len(sent.split())
        if count + words > size and buf:
            out.append(" ".join(buf))
            keep, kept = [], 0
            for prev in reversed(buf):
                kept += len(prev.split())
                keep.insert(0, prev)
                if kept >= overlap:
                    break
            buf, count = keep, kept
        buf.append(sent)
        count += words
    if buf:
        out.append(" ".join(buf))
    return [c.strip() for c in out if len(c.split()) >= 20 or len(out) == 1]


def chunk_document(parsed: ParsedPDF, tables: list[dict[str, Any]] | None = None) -> list[Chunk]:
    chunks: list[Chunk] = []
    n = 0
    for section in parsed.sections:
        if section.canonical in {"references", "acknowledgment"}:
            continue
        text = section.text.strip()
        if not text:
            continue
        sentences = SENT_SPLIT.split(text)
        for piece in _pack(sentences, CHUNK_WORDS, CHUNK_OVERLAP_WORDS):
            chunks.append(
                Chunk(
                    id=f"{parsed.doc_id}_c{n}",
                    doc_id=parsed.doc_id,
                    doc_title=parsed.title,
                    section_title=section.title,
                    section_kind=section.canonical,
                    page_start=section.page_start,
                    page_end=section.page_end,
                    text=piece,
                )
            )
            n += 1

    for fig in parsed.figures:
        if fig.caption and len(fig.caption.split()) >= 5:
            chunks.append(
                Chunk(
                    id=f"{parsed.doc_id}_c{n}",
                    doc_id=parsed.doc_id,
                    doc_title=parsed.title,
                    section_title=f"Figure (page {fig.page})",
                    section_kind="figure",
                    page_start=fig.page,
                    page_end=fig.page,
                    text=fig.caption,
                    kind="caption",
                )
            )
            n += 1

    for tbl in tables or []:
        body = (tbl.get("caption", "") + "\n" + tbl.get("markdown", "")).strip()
        if len(body.split()) < 8:
            continue
        chunks.append(
            Chunk(
                id=f"{parsed.doc_id}_c{n}",
                doc_id=parsed.doc_id,
                doc_title=parsed.title,
                section_title=f"Table (page {tbl.get('page', 0)})",
                section_kind="table",
                page_start=int(tbl.get("page", 0)),
                page_end=int(tbl.get("page", 0)),
                text=body[:4000],
                kind="table",
            )
        )
        n += 1

    return chunks
