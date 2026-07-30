"""Table extraction with Camelot.

Camelot has two modes and they fail in opposite situations, so we run lattice
first (ruled tables), then stream (whitespace-aligned tables) on the pages
lattice found nothing on. Everything is wrapped: a missing Ghostscript install
degrades the app to "no tables" instead of crashing it.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from backend.config import CAMELOT_MAX_PAGES, ENABLE_CAMELOT

log = logging.getLogger(__name__)

TABLE_CAPTION = re.compile(r"^table\s*\.?\s*(\d+|[IVX]+)\s*[.:\-–]?\s*(.*)", re.I)


@dataclass
class ExtractedTable:
    id: str
    page: int
    flavour: str
    accuracy: float
    n_rows: int
    n_cols: int
    markdown: str
    csv: str
    caption: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _df_to_markdown(df) -> str:
    rows = df.fillna("").astype(str).values.tolist()
    if not rows:
        return ""
    rows = [[re.sub(r"\s+", " ", c).strip() for c in row] for row in rows]
    header, body = rows[0], rows[1:]
    if not any(header):
        header = [f"col{i+1}" for i in range(len(rows[0]))]
        body = rows
    width = len(header)
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join(["---"] * width) + " |"]
    for row in body:
        row = (row + [""] * width)[:width]
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def _harvest(tables, flavour: str, doc_id: str, start: int,
             captions: dict[int, list[str]]) -> list[ExtractedTable]:
    out: list[ExtractedTable] = []
    for i, t in enumerate(tables):
        df = t.df
        if df.shape[0] < 2 or df.shape[1] < 2:
            continue
        cells = df.astype(str).values.ravel()
        if sum(1 for c in cells if c.strip()) < 4:
            continue
        page = int(getattr(t, "page", 0) or 0)
        caps = captions.get(page, [])
        out.append(
            ExtractedTable(
                id=f"{doc_id}_t{start + i}",
                page=page,
                flavour=flavour,
                accuracy=round(float(getattr(t, "accuracy", 0.0) or 0.0), 2),
                n_rows=int(df.shape[0]),
                n_cols=int(df.shape[1]),
                markdown=_df_to_markdown(df),
                csv=df.to_csv(index=False, header=False),
                caption=caps.pop(0) if caps else "",
            )
        )
    return out


def find_table_captions(full_text: str) -> dict[int, list[str]]:
    """Best-effort caption pool (page unknown -> keyed 0, matched loosely)."""
    caps: dict[int, list[str]] = {}
    for line in full_text.splitlines():
        line = line.strip()
        if TABLE_CAPTION.match(line):
            caps.setdefault(0, []).append(line[:300])
    return caps


def extract_tables(pdf_path: str | Path, doc_id: str, page_count: int,
                   captions: dict[int, list[str]] | None = None) -> list[ExtractedTable]:
    if not ENABLE_CAMELOT:
        return []
    try:
        import camelot  # noqa: WPS433 (optional heavy dep)
    except Exception as exc:  # pragma: no cover
        log.warning("Camelot unavailable (%s) - skipping table extraction", exc)
        return []

    captions = dict(captions or {})
    pages = f"1-{min(page_count, CAMELOT_MAX_PAGES)}"
    results: list[ExtractedTable] = []

    try:
        lattice = camelot.read_pdf(
            str(pdf_path), pages=pages, flavor="lattice", suppress_stdout=True
        )
        results += _harvest(lattice, "lattice", doc_id, 0, captions)
    except Exception as exc:
        log.warning("Camelot lattice failed: %s", exc)

    covered = {t.page for t in results}
    remaining = [p for p in range(1, min(page_count, CAMELOT_MAX_PAGES) + 1) if p not in covered]
    if remaining:
        try:
            stream = camelot.read_pdf(
                str(pdf_path),
                pages=",".join(str(p) for p in remaining),
                flavor="stream",
                edge_tol=200,
                suppress_stdout=True,
            )
            results += _harvest(stream, "stream", doc_id, len(results), captions)
        except Exception as exc:
            log.warning("Camelot stream failed: %s", exc)

    # keep the trustworthy ones, biggest first
    results = [t for t in results if t.accuracy == 0 or t.accuracy >= 60]
    results.sort(key=lambda t: (t.page, -t.n_rows))
    return results
