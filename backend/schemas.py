from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    doc_ids: list[str] = Field(default_factory=list)


class Source(BaseModel):
    label: str
    doc_id: str
    doc_title: str
    section: str
    page: int
    score: float
    snippet: str
    full_text: str = ""
    kind: str = "text"


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[Source] = []
    queries_used: list[str] = []
    retrieval_rounds: int = 1
    llm_calls: int = 0
    cached: bool = False


class DocumentSummary(BaseModel):
    doc_id: str
    title: str
    authors: str = ""
    filename: str
    page_count: int = 0
    n_chunks: int = 0
    n_tables: int = 0
    n_figures: int = 0
    ingested_at: str = ""


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    authors: str = ""
    page_count: int = 0
    n_chunks: int = 0
    summary: str = ""
    explanation: str = ""
    findings: dict[str, Any] = {}
    followups: list[str] = []
    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    warnings: list[str] = []
    llm_calls: int = 0
    elapsed_s: float = 0.0


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_model: str
    api_key_configured: bool
    embedding_model: str
    indexed_documents: int
    indexed_chunks: int
