from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.core import pipeline
from backend.core.llm import LLMError
from backend.core.citations import library_to_bibtex
from backend.core.report import build_markdown, safe_filename
from backend.core.vectorstore import get_store
from backend.schemas import (
    AskRequest,
    AskResponse,
    DocumentSummary,
    HealthResponse,
    IngestResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("research-assistant")

app = FastAPI(
    title="Research-Assistant-Bot API",
    description="Upload papers, index them, ask questions, get plain-English explanations.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    store = get_store()
    return HealthResponse(
        status="ok",
        llm_provider=config.LLM_PROVIDER,
        llm_model=config.LLM_MODEL,
        api_key_configured=not config.missing_api_key(),
        embedding_model=config.EMBED_MODEL,
        indexed_documents=len(store.documents),
        indexed_chunks=store.size,
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...), understand: bool = True) -> IngestResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a .pdf file.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "That file is empty.")
    if config.missing_api_key() and understand:
        raise HTTPException(
            400,
            f"No API key set for provider '{config.LLM_PROVIDER}'. "
            "Add it to .env and restart the server.",
        )

    digest = pipeline.file_hash(data)
    existing = pipeline.find_by_hash(digest)
    if existing is not None:
        return IngestResponse(
            **{k: v for k, v in existing.items() if k in IngestResponse.model_fields}
        )

    doc_id, path = pipeline.save_pdf(data, file.filename)
    log.info("Ingesting %s as %s", file.filename, doc_id)
    try:
        result = pipeline.ingest_pdf(path, doc_id, run_understanding=understand, digest=digest)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    except Exception as exc:
        log.exception("Ingest failed")
        raise HTTPException(500, f"Could not process that PDF: {exc}") from exc
    return IngestResponse(**{k: v for k, v in result.items() if k in IngestResponse.model_fields})


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    store = get_store()
    if store.size == 0:
        raise HTTPException(400, "Nothing indexed yet. Upload a PDF first.")
    try:
        return AskResponse(**pipeline.ask(req.question, req.doc_ids or None))
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/documents", response_model=list[DocumentSummary])
def documents() -> list[DocumentSummary]:
    return [
        DocumentSummary(**{k: v for k, v in d.items() if k in DocumentSummary.model_fields})
        for d in get_store().list_documents()
    ]


@app.get("/documents/{doc_id}")
def document(doc_id: str) -> dict:
    doc = pipeline.load_artifact(doc_id, "document.json")
    if doc is None:
        raise HTTPException(404, "Unknown document id.")
    return doc


@app.get("/documents/{doc_id}/tables")
def tables(doc_id: str) -> list[dict]:
    return pipeline.load_artifact(doc_id, "tables.json", default=[])


@app.get("/documents/{doc_id}/figures/{figure_id}")
def figure(doc_id: str, figure_id: str) -> FileResponse:
    path = pipeline.artifact_path(doc_id, f"images/{figure_id}.png")
    if not Path(path).exists():
        raise HTTPException(404, "Unknown figure.")
    return FileResponse(path, media_type="image/png")


@app.get("/documents/{doc_id}/report")
def report(doc_id: str, format: str = Query("md", pattern="^(md|json)$")) -> Response:
    doc = pipeline.load_artifact(doc_id, "document.json")
    if doc is None:
        raise HTTPException(404, "Unknown document id.")
    title = doc.get("title", "paper")
    if format == "json":
        body = json.dumps(doc, ensure_ascii=False, indent=2)
        media, name = "application/json", safe_filename(title, doc_id, "json")
    else:
        body = build_markdown(doc)
        media, name = "text/markdown; charset=utf-8", safe_filename(title, doc_id, "md")
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/library/bibtex")
def library_bibtex(doc_ids: str = Query("")) -> Response:
    store = get_store()
    wanted = [d.strip() for d in doc_ids.split(",") if d.strip()]
    docs = []
    for summary in store.list_documents():
        if wanted and summary["doc_id"] not in wanted:
            continue
        full = pipeline.load_artifact(summary["doc_id"], "document.json") or summary
        docs.append(full)
    if not docs:
        raise HTTPException(404, "No indexed documents to export.")
    return Response(
        content=library_to_bibtex(docs),
        media_type="application/x-bibtex; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="library.bib"'},
    )


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict:
    get_store().delete_document(doc_id)
    pipeline.clear_answer_cache()
    return {"deleted": doc_id}


@app.post("/reset")
def reset() -> dict:
    get_store().reset()
    pipeline.clear_answer_cache()
    return {"status": "index cleared"}


_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")


def run() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host=config.API_HOST, port=config.API_PORT, reload=False)


if __name__ == "__main__":
    run()
