"""Sentence-transformers embedder, loaded once and reused."""
from __future__ import annotations

import logging
import threading
from functools import lru_cache

import numpy as np

from backend.config import EMBED_BATCH, EMBED_MODEL, EMBED_QUERY_PREFIX

log = logging.getLogger(__name__)
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    log.info("Loading embedding model %s (first run downloads ~130MB)", EMBED_MODEL)
    return SentenceTransformer(EMBED_MODEL)


def dimension() -> int:
    return int(_model().get_sentence_embedding_dimension())


def encode(texts: list[str], is_query: bool = False) -> np.ndarray:
    """Return L2-normalised float32 vectors, so inner product == cosine."""
    if not texts:
        return np.zeros((0, dimension()), dtype="float32")
    if is_query and EMBED_QUERY_PREFIX:
        texts = [EMBED_QUERY_PREFIX + t for t in texts]
    with _lock:
        vecs = _model().encode(
            texts,
            batch_size=EMBED_BATCH,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 200,
        )
    return np.asarray(vecs, dtype="float32")
