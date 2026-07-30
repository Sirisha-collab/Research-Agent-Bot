"""Central configuration. Everything tunable lives here or in .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------- paths
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
INDEX_DIR = DATA_DIR / "index"
EXTRACT_DIR = DATA_DIR / "extracted"
for _d in (UPLOAD_DIR, INDEX_DIR, EXTRACT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- llm
# provider: "groq" (free tier) or "deepseek". Both speak the OpenAI wire format.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

_PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "fast_model": "llama-3.1-8b-instant",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "fast_model": "deepseek-chat",
    },
}

_p = _PROVIDERS[LLM_PROVIDER]
LLM_BASE_URL = os.getenv("LLM_BASE_URL", _p["base_url"])
LLM_API_KEY = os.getenv(_p["key_env"], "")
LLM_MODEL = os.getenv("LLM_MODEL", _p["default_model"])
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", _p["fast_model"])
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1400"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "90"))

# ---------------------------------------------------------------- embeddings
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "32"))
# bge models want this prefix on the *query* side only.
EMBED_QUERY_PREFIX = os.getenv(
    "EMBED_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
)

# ---------------------------------------------------------------- retrieval
CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "45"))
TOP_K = int(os.getenv("TOP_K", "6"))
CANDIDATE_K = int(os.getenv("CANDIDATE_K", "18"))
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.25"))
MAX_RETRIEVAL_LOOPS = int(os.getenv("MAX_RETRIEVAL_LOOPS", "2"))

# ---------------------------------------------------------------- extraction
ENABLE_CAMELOT = os.getenv("ENABLE_CAMELOT", "true").lower() == "true"
ENABLE_IMAGES = os.getenv("ENABLE_IMAGES", "true").lower() == "true"
MIN_IMAGE_PIXELS = int(os.getenv("MIN_IMAGE_PIXELS", "12000"))  # skip logos/rules
CAMELOT_MAX_PAGES = int(os.getenv("CAMELOT_MAX_PAGES", "30"))

# ---------------------------------------------------------------- server
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_URL = os.getenv("API_URL", f"http://{API_HOST}:{API_PORT}")
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "false").lower() == "true"


def missing_api_key() -> bool:
    return not LLM_API_KEY.strip()
