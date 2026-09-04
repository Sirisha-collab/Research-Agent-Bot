# Research-Assistant-Bot

Upload a research paper, get a plain-English explanation of what it found, then ask the
paper questions and get answers with page-level citations.

```
PDF ──► PyMuPDF + rules ──► sections, figures ─┐
        Camelot ──────────► tables ────────────┤
                                               ├─► chunks ─► embeddings ─► FAISS
                                               │
                     LangGraph "understand" ───┴─► summary · explanation · findings
                     LangGraph "ask" ───────────► retrieve → grade → (retry) → answer
```

## 1. Prerequisites

| Thing | Why | Notes |
| --- | --- | --- |
| **Python 3.10 – 3.12** | everything | 3.13 not yet supported by some wheels. Check: `python --version` |
| **VS Code** + Python extension | editing / running | Extension id: `ms-python.python` |
| **Ghostscript** | Camelot's `lattice` mode (ruled tables) | Optional. Without it you still get `stream` tables |
| **Groq API key** | the LLM | Free: https://console.groq.com/keys |

---

## 2. Set up in VS Code (step by step)

**Step 1 — create a virtual environment**

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

**Step 2 — install dependencies**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Step 3 — add your API key**

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

**Step 4 — run it**

The simple way, one terminal:

```bash
python run.py
```

```bash
# terminal 1
uvicorn backend.main:app --reload --port 8000

# terminal 2  (activate .venv here too)
cd frontend
npm run dev
```

## 3. What each file does

```
research-assistant-bot/
├── run.py                       one-command launcher (API thread + Gradio)
├── requirements.txt
├── .env.example                 copy to .env and add your key
├── backend/
│   ├── config.py                every tunable setting, reads .env
│   ├── main.py                  FastAPI endpoints
│   ├── schemas.py               request/response models
│   ├── ingestion/
│   │   ├── pdf_extract.py       PyMuPDF text, font-size heading rules, section tree,
│   │   │                        header/footer removal, de-hyphenation, image export
│   │   └── tables.py            Camelot lattice → stream fallback, markdown conversion
│   └── core/
│       ├── chunking.py          section-aware chunking with overlap
│       ├── embeddings.py        sentence-transformers wrapper (normalised vectors)
│       ├── vectorstore.py       FAISS index + metadata, save/load/delete/multi-query
│       ├── llm.py               Groq client, retries, JSON mode
│       ├── prompts.py           every prompt in one file
│       ├── graph.py             the two LangGraph workflows
│       └── pipeline.py          ingest orchestration + artifact persistence
├── frontend/app.py              Gradio UI
├── scripts/cli.py               headless batch ingest / ask
└── data/                        uploads, faiss index, extracted artifacts, reports
```

