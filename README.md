# Research-Assistant-Bot

Upload a research paper, get a plain-English explanation of what it found, then ask the
paper questions and get answers with page-level citations. Papers stay in a local library,
so you can search across everything you've ever uploaded.

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

Installing Ghostscript:

- **Windows** — download the installer from https://ghostscript.com/releases/gsdnld.html, then reopen your terminal.
- **macOS** — `brew install ghostscript`
- **Linux** — `sudo apt install ghostscript python3-tk`

---

## 2. Set up in VS Code (step by step)

**Step 1 — open the project**

Unzip `research-assistant-bot.zip`, then in VS Code: `File → Open Folder…` → select the
`research-assistant-bot` folder.

**Step 2 — open a terminal inside VS Code**

`` Ctrl+` `` (backtick), or `Terminal → New Terminal`. The prompt should already be in the
project folder.

**Step 3 — create a virtual environment**

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

If PowerShell blocks activation, run once:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

**Step 4 — point VS Code at the environment**

`Ctrl+Shift+P` → *Python: Select Interpreter* → pick the one with `.venv` in the path.

**Step 5 — install dependencies**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This pulls PyTorch as a dependency of sentence-transformers, so it's a ~2GB download the
first time. Grab a coffee.

**Step 6 — add your API key**

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Open `.env` and paste your key:

```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

For DeepSeek instead: set `LLM_PROVIDER=deepseek` and fill `DEEPSEEK_API_KEY`.

**Step 7 — run it**

The simple way, one terminal:

```bash
python run.py
```

It starts the API on `http://127.0.0.1:8000`, waits for it, then opens the UI at
`http://127.0.0.1:7860`.

The developer way, two terminals (better logs, API auto-reloads on save):

```bash
# terminal 1
uvicorn backend.main:app --reload --port 8000

# terminal 2  (activate .venv here too)
python frontend/app.py
```

**Step 8 — use it**

1. Drop a PDF into the upload box.
2. Click **Read this paper**. First run also downloads the embedding model (~130MB).
3. Read the **Explanation** tab, then the **Findings** tab.
4. Go to **Ask** and ask something specific: *"what baseline did they compare against?"*
5. Download the generated report from the **Download report** box.

Expected timing on a normal laptop, 12-page paper: 10–25s for extraction and indexing,
30–70s more if summarisation is on (that part is LLM-bound).

---

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

## 5. API

Interactive docs while the server runs: http://127.0.0.1:8000/docs

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | provider, model, key status, index size |
| `POST` | `/ingest` | multipart PDF upload → full analysis |
| `POST` | `/ask` | `{"question": "...", "doc_ids": []}` |
| `GET` | `/documents` | library listing |
| `GET` | `/documents/{id}` | everything known about one paper |
| `GET` | `/documents/{id}/tables` | extracted tables |
| `DELETE` | `/documents/{id}` | remove one paper and reindex |
| `POST` | `/reset` | wipe the index |

## 6. Building a library from a folder

```bash
python scripts/cli.py ingest ~/papers --no-understand   # fast, index only
python scripts/cli.py ask "which papers use contrastive learning, and how?"
python scripts/cli.py list
```

Leave the library checkboxes empty in the UI to search across everything, or tick two
papers to compare them in one answer.

## 7. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `No API key found for provider 'groq'` | `.env` missing or key blank. Restart after editing |
| `Backend unreachable at http://127.0.0.1:8000` | API isn't running, or port 8000 is taken. Change `API_PORT` in `.env` |
| No tables detected | Install Ghostscript, or the PDF's tables are images — try `ENABLE_CAMELOT=true` and check the API log |
| `ModuleNotFoundError: backend` | Run commands from the project root, with `.venv` activated |
| Camelot import error on `cv2` | `pip install opencv-python-headless` |
| Rate limit / 429 from Groq | Free tier throttles. The client retries with backoff; for long papers set `LLM_FAST_MODEL=llama-3.1-8b-instant` |
| Answers say "the paper does not cover this" too often | Lower `MIN_SCORE` to `0.15`, raise `TOP_K` to `10` |
| Summary misses a section | Heading detection failed on an unusual layout. Check the **Structure** tab to see what was parsed |
| Torch install fails on Windows | Install it first: `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| Port 7860 in use | `GRADIO_PORT=7861` in `.env` |

## 8. Tuning notes

- **Chunk size** — `CHUNK_WORDS=220` suits dense papers. Raise to 350 for surveys, drop to
  150 if answers pull in too much unrelated text.
- **Scanned PDFs** — PyMuPDF returns nothing for image-only scans. Run OCR first
  (`ocrmypdf in.pdf out.pdf`) and ingest the output.
- **Better retrieval** — swap `EMBED_MODEL` to `BAAI/bge-base-en-v1.5` for a real accuracy
  bump at roughly 3× the embedding time.
- **Scale** — flat FAISS is exact and stays fast to ~100k chunks (a few hundred papers).
  Past that, switch `IndexFlatIP` to `IndexHNSWFlat` in `vectorstore.py`.
