import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:

    # Gemini Models
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_EMBED_MODEL = "models/gemini-embedding-001"
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    DEFAULT_SUMMARY_ENGINE = os.getenv("DEFAULT_SUMMARY_ENGINE", "deepseek")

    # ------------------------------------------------------------------
    # NEW - Summary styles exposed to the UI
    # ------------------------------------------------------------------
    SUMMARY_STYLES = {
        "bullet_points": "Bullet Points",
        "executive_summary": "Executive Summary",
        "key_takeaways": "Key Takeaways",
        "technical_analysis": "Technical Analysis",
        "action_items": "Action Items",
    }
    DEFAULT_SUMMARY_STYLE = "bullet_points"

    # Safety cap on how much document text is sent per summarization call,
    # to stay comfortably within free-tier token/context limits.
    SUMMARY_MAX_INPUT_CHARS = int(os.getenv("SUMMARY_MAX_INPUT_CHARS", "20000"))
    
    # FAISS Configuration
    FAISS_INDEX_DIMENSION = 768  # Embedding dimension for Gemini
    FAISS_INDEX_PATH = "faiss_index"
    DOCUMENTS_CACHE_PATH = "documents_cache.pkl"
    
    # Retrieval Configuration
    RETRIEVAL_TOP_K = 5
    MIN_SIMILARITY_SCORE = 0.3
    
    # Summary Configuration
    MIN_SUMMARY_LENGTH = 200
    MAX_SUMMARY_LENGTH = 500
    SUMMARY_TEMPERATURE = 0.3
    
    # Research Questions Configuration
    NUM_QUESTIONS = 5
    QUESTION_TEMPERATURE = 0.7
    
    # Server Configuration
    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 8000
    UPLOAD_FOLDER = "uploads"
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    # Retry Configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    @classmethod
    def validate(cls) -> tuple[bool, Optional[str]]:

        if not cls.GEMINI_API_KEY:
            return False, "GEMINI_API_KEY not set. Please set it in .env file"
        if not cls.DEEPSEEK_API_KEY:
            return False, "DEEPSEEK_API_KEY not set. Please set it in .env file"
        return True, None
    
    @classmethod
    def to_dict(cls) -> dict:
        return {
            "model": cls.GEMINI_MODEL,
            "embed_model": cls.GEMINI_EMBED_MODEL,
            "retrieval_top_k": cls.RETRIEVAL_TOP_K,
            "summary_length": f"{cls.MIN_SUMMARY_LENGTH}-{cls.MAX_SUMMARY_LENGTH}",
        }


# Export configuration
config = Config()
