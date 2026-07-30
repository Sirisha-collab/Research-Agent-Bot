"""FAISS index + chunk metadata, persisted to disk.

One flat inner-product index for the whole library. Flat is exact and fast well
past 100k chunks, which is more than a personal paper collection ever hits, and
it avoids the training step IVF/HNSW would need.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from backend.config import CANDIDATE_K, INDEX_DIR, MIN_SCORE
from backend.core import embeddings

log = logging.getLogger(__name__)

INDEX_PATH = INDEX_DIR / "faiss.index"
META_PATH = INDEX_DIR / "chunks.json"
DOCS_PATH = INDEX_DIR / "documents.json"

_lock = threading.RLock()


class VectorStore:
    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.chunks: list[dict[str, Any]] = []
        self.documents: dict[str, dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------- persistence
    def _load(self) -> None:
        if META_PATH.exists():
            self.chunks = json.loads(META_PATH.read_text(encoding="utf-8"))
        if DOCS_PATH.exists():
            self.documents = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
        if INDEX_PATH.exists():
            try:
                self.index = faiss.read_index(str(INDEX_PATH))
                log.info("Loaded FAISS index: %d vectors", self.index.ntotal)
            except Exception as exc:
                log.warning("Could not read index (%s); starting empty", exc)
                self.index = None
        if self.index is not None and self.index.ntotal != len(self.chunks):
            log.warning("Index/metadata mismatch - rebuilding on next ingest")

    def _save(self) -> None:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_PATH))
        META_PATH.write_text(json.dumps(self.chunks, ensure_ascii=False), encoding="utf-8")
        DOCS_PATH.write_text(json.dumps(self.documents, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # ------------------------------------------------------------------ write
    def add_document(self, doc_meta: dict[str, Any], chunks: list[dict[str, Any]]) -> int:
        with _lock:
            doc_id = doc_meta["doc_id"]
            if doc_id in self.documents:
                self.delete_document(doc_id)

            vectors = embeddings.encode([c["embed_text"] for c in chunks])
            if self.index is None:
                self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)
            self.chunks.extend(chunks)
            doc_meta["n_chunks"] = len(chunks)
            self.documents[doc_id] = doc_meta
            self._save()
            return len(chunks)

    def delete_document(self, doc_id: str) -> None:
        """Flat indexes can't remove rows cheaply, so rebuild without that doc."""
        with _lock:
            keep = [c for c in self.chunks if c["doc_id"] != doc_id]
            self.documents.pop(doc_id, None)
            self.chunks = keep
            if not keep:
                self.index = None
                for p in (INDEX_PATH, META_PATH, DOCS_PATH):
                    if p.exists() and p != DOCS_PATH:
                        p.unlink()
                self._save()
                return
            vectors = embeddings.encode([c["embed_text"] for c in keep])
            self.index = faiss.IndexFlatIP(vectors.shape[1])
            self.index.add(vectors)
            self._save()

    def reset(self) -> None:
        with _lock:
            self.index = None
            self.chunks = []
            self.documents = {}
            for p in (INDEX_PATH, META_PATH, DOCS_PATH):
                if p.exists():
                    p.unlink()

    # ------------------------------------------------------------------- read
    @property
    def size(self) -> int:
        return 0 if self.index is None else int(self.index.ntotal)

    def search(self, query: str, k: int = CANDIDATE_K,
               doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
        if self.index is None or not self.chunks:
            return []
        qv = embeddings.encode([query], is_query=True)
        # over-fetch, then filter by document, so a per-paper search still fills k
        fetch = min(len(self.chunks), max(k * 6, k) if doc_ids else k * 2)
        scores, idxs = self.index.search(qv, fetch)

        hits: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            if doc_ids and chunk["doc_id"] not in doc_ids:
                continue
            if float(score) < MIN_SCORE:
                continue
            hit = dict(chunk)
            hit["score"] = round(float(score), 4)
            hits.append(hit)
            if len(hits) >= k:
                break
        return hits

    def multi_search(self, queries: list[str], k: int = CANDIDATE_K,
                     doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """Union of several query rewrites, deduped, best score wins."""
        pool: dict[str, dict[str, Any]] = {}
        for q in queries:
            for hit in self.search(q, k=k, doc_ids=doc_ids):
                prev = pool.get(hit["id"])
                if prev is None or hit["score"] > prev["score"]:
                    pool[hit["id"]] = hit
        ranked = sorted(pool.values(), key=lambda h: h["score"], reverse=True)
        return ranked[:k]

    def chunks_of(self, doc_id: str) -> list[dict[str, Any]]:
        return [c for c in self.chunks if c["doc_id"] == doc_id]

    def list_documents(self) -> list[dict[str, Any]]:
        return sorted(self.documents.values(), key=lambda d: d.get("ingested_at", ""), reverse=True)


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
