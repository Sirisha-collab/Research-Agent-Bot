"""Start the API and the UI with one command:  python run.py

Runs uvicorn in a background thread, waits for /health, then launches Gradio.
Prefer two terminals (see README) while developing - you get cleaner logs and
auto-reload on the API.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests  # noqa: E402
import uvicorn  # noqa: E402

from backend import config  # noqa: E402


def _serve_api() -> None:
    uvicorn.run(
        "backend.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
        reload=False,
    )


def _wait_for_api(seconds: int = 90) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if requests.get(f"{config.API_URL}/health", timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main() -> None:
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    if config.missing_api_key():
        print(f"!  No API key for provider '{config.LLM_PROVIDER}'. "
              "Copy .env.example to .env and add your key, or the app will only index.\n")

    threading.Thread(target=_serve_api, daemon=True).start()
    print(f"→ API starting on {config.API_URL} (docs at {config.API_URL}/docs)")
    if not _wait_for_api():
        print("!  API did not come up in time. Check the traceback above.")
        sys.exit(1)
    print("→ API ready. Loading the embedding model, then the UI…")

    from frontend.app import build_ui

    build_ui().launch(
        server_port=config.GRADIO_PORT,
        share=config.GRADIO_SHARE,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
