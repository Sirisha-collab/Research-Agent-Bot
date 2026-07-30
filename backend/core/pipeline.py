"""End-to-end ingestion: PDF in, indexed + understood document out."""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import EXTRACT_DIR, UPLOAD_DIR
from backend.core.chunking import chunk_document
from backend.core.graph import qa_graph, understand_graph
from backend.core.vectorstore import get_store
from backend.ingestion.pdf_extract import parse_pdf
from backend.ingestion.tables import extract_tables, find_table_captions

log = logging.getLogger(__name__)


def _doc_dir(doc_id: str) -> Path:
    d = EXTRACT_DIR / doc_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def artifact_path(doc_id: str, name: str) -> Path:
    return _doc_dir(doc_id) / name


def load_artifact(doc_id: str, name: str, default: Any = None) -> Any:
    p = artifact_path(doc_id, name)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_pdf(file_bytes: bytes, filename: str) -> tuple[str, Path]:
    doc_id = uuid.uuid4().hex[:12]
    safe = Path(filename).name.replace(" ", "_")
    dest = UPLOAD_DIR / f"{doc_id}_{safe}"
    dest.write_bytes(file_bytes)
    return doc_id, dest


def ingest_pdf(pdf_path: str | Path, doc_id: str, run_understanding: bool = True) -> dict[str, Any]:
    started = time.time()
    pdf_path = Path(pdf_path)
    out_dir = _doc_dir(doc_id)

    # 1. extract -------------------------------------------------------------
    parsed = parse_pdf(pdf_path, doc_id, out_dir / "images")
    log.info("Parsed %s: %d sections, %d figures", parsed.filename,
             len(parsed.sections), len(parsed.figures))

    # 2. tables --------------------------------------------------------------
    tables = [
        t.to_dict()
        for t in extract_tables(pdf_path, doc_id, parsed.page_count,
                                find_table_captions(parsed.full_text))
    ]
    log.info("Extracted %d tables", len(tables))

    # 3. chunk + index -------------------------------------------------------
    chunks = chunk_document(parsed, tables)
    payload = []
    for c in chunks:
        d = c.to_dict()
        d["embed_text"] = c.embed_text()
        payload.append(d)

    doc_meta = {
        "doc_id": doc_id,
        "filename": parsed.filename,
        "title": parsed.title,
        "authors": parsed.authors,
        "page_count": parsed.page_count,
        "metadata": parsed.metadata,
        "n_sections": len(parsed.sections),
        "n_tables": len(tables),
        "n_figures": len(parsed.figures),
        "pdf_path": str(pdf_path),
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    n_chunks = get_store().add_document(doc_meta, payload)

    # 4. persist raw artifacts ----------------------------------------------
    (out_dir / "parsed.json").write_text(
        json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "tables.json").write_text(
        json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result: dict[str, Any] = {
        **doc_meta,
        "n_chunks": n_chunks,
        "tables": tables,
        "figures": [f.__dict__ for f in parsed.figures],
        "sections": [{"title": s.title, "canonical": s.canonical,
                      "page_start": s.page_start, "words": s.word_count()}
                     for s in parsed.sections],
    }

    # 5. understand ----------------------------------------------------------
    if run_understanding:
        understanding = run_understand(parsed.to_dict(), doc_id)
        result.update(understanding)

    result["elapsed_s"] = round(time.time() - started, 1)
    (out_dir / "document.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result


def run_understand(parsed_dict: dict[str, Any], doc_id: str) -> dict[str, Any]:
    state = understand_graph().invoke(
        {
            "doc_id": doc_id,
            "title": parsed_dict["title"],
            "sections": parsed_dict["sections"],
            "errors": [],
        }
    )
    out = {
        "summary": state.get("summary", ""),
        "explanation": state.get("explanation", ""),
        "findings": state.get("findings", {}),
        "followups": state.get("followups", []),
        "section_notes": state.get("section_notes", []),
        "warnings": state.get("errors", []),
    }
    (_doc_dir(doc_id) / "understanding.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def ask(question: str, doc_ids: list[str] | None = None) -> dict[str, Any]:
    state = qa_graph().invoke(
        {"question": question, "doc_ids": doc_ids or [], "loops": 0}
    )
    return {
        "question": question,
        "answer": state.get("answer", ""),
        "sources": state.get("sources", []),
        "queries_used": state.get("queries", []),
        "retrieval_rounds": state.get("loops", 1),
    }


def compare(question: str, doc_ids: list[str]) -> dict[str, Any]:
    """Cross-document exploration: same question, whole library, one answer."""
    return ask(question, doc_ids=doc_ids)
