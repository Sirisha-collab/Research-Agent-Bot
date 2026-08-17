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

| Layer | Choice |
| --- | --- |
| Extraction | PyMuPDF (text, layout, images) + rule-based section detection, Camelot (tables) |
| API | FastAPI |
| Orchestration | LangGraph (two graphs: understand, ask) |
| Vectors | FAISS `IndexFlatIP` (exact cosine), persisted to disk |
| Embeddings | `BAAI/bge-small-en-v1.5`, local, CPU, free |
| LLM | Groq (free tier) or DeepSeek, OpenAI-compatible |
| UI | Gradio |

---

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
│       ├── llm.py               Groq/DeepSeek client, retries, JSON mode
│       ├── prompts.py           every prompt in one file
│       ├── graph.py             the two LangGraph workflows
│       └── pipeline.py          ingest orchestration + artifact persistence
├── frontend/app.py              Gradio UI
├── scripts/cli.py               headless batch ingest / ask
└── data/                        uploads, faiss index, extracted artifacts, reports
```

## 4. How the two LangGraph workflows work

**Understand** (runs once per upload)

`pick_sections → summarise_sections → write_summary → write_explanation → extract_findings → suggest_followups`

Sections are ranked so abstract/method/results always get summarised even in a long paper,
then each is summarised with the fast model (map), and the notes are reduced into a summary,
a four-part plain-English explanation, and a structured findings object.

**Ask** (runs per question, and it can loop)

`plan → retrieve → grade →  answer`
&nbsp;&nbsp;&nbsp;&nbsp;`↑___________________|` (when the grader says the excerpts don't cover it)

`plan` rewrites your question into three retrieval queries with different vocabulary.
`retrieve` unions the FAISS hits and dedupes. `grade` asks the fast model whether those
excerpts actually answer the question; if not, it feeds back *what's missing* as an extra
query and searches wider, up to `MAX_RETRIEVAL_LOOPS`. `answer` writes the response with
`[S1]`-style citations that map to the source slips under the chat.

## 5. Building a library from a folder

```bash
python scripts/cli.py ingest ~/papers --no-understand   # fast, index only
python scripts/cli.py ask "which papers use contrastive learning, and how?"
python scripts/cli.py list
```

## 6. Tuning notes

- **Chunk size** — `CHUNK_WORDS=220` suits dense papers. Raise to 350 for surveys, drop to
  150 if answers pull in too much unrelated text.
- **Scanned PDFs** — PyMuPDF returns nothing for image-only scans. Run OCR first
  (`ocrmypdf in.pdf out.pdf`) and ingest the output.
- **Better retrieval** — swap `EMBED_MODEL` to `BAAI/bge-base-en-v1.5` for a real accuracy
  bump at roughly 3× the embedding time.
- **Scale** — flat FAISS is exact and stays fast to ~100k chunks (a few hundred papers).
  Past that, switch `IndexFlatIP` to `IndexHNSWFlat` in `vectorstore.py`.
