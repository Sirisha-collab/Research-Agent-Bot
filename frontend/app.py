"""Gradio UI for Research-Assistant-Bot.

Talks to the FastAPI backend over HTTP, so you can run the two separately or
together (python run.py). Visual direction: a reading desk - serif for the parts
you read, mono for the parts you scan (pages, scores, section names).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import gradio as gr
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import API_URL, GRADIO_PORT, GRADIO_SHARE  # noqa: E402

TIMEOUT = 900
REPORT_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

CSS = """
.gradio-container {max-width: 1180px !important;}
#masthead {border-bottom: 2px solid var(--body-text-color); padding-bottom: .6rem; margin-bottom: .4rem;}
#masthead h1 {font-size: 1.65rem; letter-spacing: -.02em; margin: 0 0 .15rem 0;}
#masthead p {font-family: var(--font-mono); font-size: .78rem; text-transform: uppercase;
             letter-spacing: .14em; opacity: .65; margin: 0;}
.reading p, .reading li {font-size: 1.02rem; line-height: 1.66;}
.reading h3 {font-family: var(--font-mono); font-size: .82rem; text-transform: uppercase;
             letter-spacing: .12em; opacity: .7; margin-top: 1.3rem;}
.slip {border-left: 3px solid var(--color-accent); padding: .1rem 0 .1rem .8rem; margin: .7rem 0;}
.slip .meta {font-family: var(--font-mono); font-size: .74rem; opacity: .7;}
.statusbar {font-family: var(--font-mono); font-size: .8rem;}
footer {display: none !important;}
"""

THEME = gr.themes.Soft(
    primary_hue=gr.themes.colors.indigo,
    secondary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("Source Serif 4"), "Georgia", "serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "ui-monospace", "monospace"],
)


# ------------------------------------------------------------------ transport
def _get(path: str, **kw):
    return requests.get(f"{API_URL}{path}", timeout=TIMEOUT, **kw)


def _post(path: str, **kw):
    return requests.post(f"{API_URL}{path}", timeout=TIMEOUT, **kw)


def _error_text(resp: requests.Response) -> str:
    try:
        return resp.json().get("detail", resp.text)
    except Exception:
        return resp.text[:400]


def backend_status() -> str:
    try:
        r = _get("/health")
        h = r.json()
    except Exception:
        return (f"Backend unreachable at {API_URL}. Start it with "
                "`uvicorn backend.main:app --port 8000` in another terminal.")
    key = "key loaded" if h["api_key_configured"] else "NO API KEY - add it to .env"
    return (f"{h['llm_provider']} / {h['llm_model']} · {key} · "
            f"{h['indexed_documents']} docs · {h['indexed_chunks']} chunks indexed")


# -------------------------------------------------------------------- render
def _findings_md(findings: dict) -> str:
    if not findings:
        return "_No findings extracted._"
    out: list[str] = []
    items = findings.get("findings") or []
    if items:
        out.append("### Findings")
        for i, f in enumerate(items, 1):
            out.append(f"**{i}. {f.get('finding','')}**")
            ev = (f.get("evidence") or "").strip()
            sec = (f.get("section") or "").strip()
            if ev or sec:
                out.append(f"<div class='slip'><div class='meta'>{sec}</div>{ev}</div>")
    metrics = findings.get("metrics") or []
    if metrics:
        out.append("### Reported numbers")
        out.append("| Metric | Value | Where |")
        out.append("| --- | --- | --- |")
        for m in metrics:
            out.append(f"| {m.get('name','')} | {m.get('value','')} | {m.get('context','')} |")
    for key, label in (("contributions", "Contributions"),
                       ("methods", "Methods, data and models used"),
                       ("limitations", "Limitations the authors admit"),
                       ("future_work", "What they suggest next")):
        vals = findings.get(key) or []
        if vals:
            out.append(f"### {label}")
            out += [f"- {v}" for v in vals]
    return "\n\n".join(out)


def _tables_md(tables: list[dict]) -> str:
    if not tables:
        return ("_No tables detected._ Camelot needs Ghostscript for ruled tables - "
                "see the README if you expected tables here.")
    parts = []
    for t in tables:
        head = f"**Table on page {t.get('page')}** · {t.get('n_rows')}×{t.get('n_cols')}"
        if t.get("accuracy"):
            head += f" · {t['flavour']} · accuracy {t['accuracy']}"
        parts.append(head)
        if t.get("caption"):
            parts.append(f"_{t['caption']}_")
        parts.append(t.get("markdown", ""))
    return "\n\n".join(parts)


def _sections_md(doc: dict) -> str:
    rows = ["| Section | Kind | Page | Words |", "| --- | --- | --- | --- |"]
    for s in doc.get("sections", []):
        rows.append(f"| {s['title']} | `{s['canonical']}` | {s['page_start']} | {s['words']} |")
    return "\n".join(rows)


def _write_report(doc: dict) -> list[str]:
    doc_id = doc["doc_id"]
    stem = "".join(ch for ch in doc.get("title", "paper")[:60] if ch.isalnum() or ch in " -_").strip()
    stem = (stem or "paper").replace(" ", "_")
    md = REPORT_DIR / f"{stem}_{doc_id}.md"
    body = [
        f"# {doc.get('title','Untitled')}",
        f"*{doc.get('authors','')}*" if doc.get("authors") else "",
        f"`{doc.get('filename','')}` · {doc.get('page_count',0)} pages · "
        f"{doc.get('n_chunks',0)} indexed chunks",
        "\n## Plain-English explanation\n", doc.get("explanation", ""),
        "\n## Summary\n", doc.get("summary", ""),
        "\n## Key findings\n", _findings_md(doc.get("findings", {})),
        "\n## Tables\n", _tables_md(doc.get("tables", [])),
    ]
    md.write_text("\n".join(p for p in body if p), encoding="utf-8")
    js = REPORT_DIR / f"{stem}_{doc_id}.json"
    js.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return [str(md), str(js)]


# -------------------------------------------------------------------- actions
def process_pdf(file_obj, run_understanding, progress=gr.Progress()):
    empty = (gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
             gr.update(), gr.update(), gr.update(), gr.update())
    if file_obj is None:
        return ("Choose a PDF first.", *empty[:8], None)

    progress(0.1, desc="Uploading")
    path = Path(file_obj.name if hasattr(file_obj, "name") else file_obj)
    try:
        with path.open("rb") as fh:
            resp = _post(
                "/ingest",
                files={"file": (path.name, fh, "application/pdf")},
                params={"understand": str(bool(run_understanding)).lower()},
            )
    except requests.exceptions.ConnectionError:
        return (f"Backend unreachable at {API_URL}. Is the API running?",
                *empty[:8], None)
    if resp.status_code != 200:
        return (f"Failed: {_error_text(resp)}", *empty[:8], None)

    progress(0.9, desc="Rendering")
    doc = resp.json()
    files = _write_report(doc)
    figures = []
    for f in doc.get("figures", []):
        local = f.get("path", "")
        src = local if local and Path(local).exists() else \
            f"{API_URL}/documents/{doc['doc_id']}/figures/{f['id']}"
        figures.append((src, f.get("caption") or f"page {f['page']}"))
    header = (
        f"### {doc.get('title','Untitled')}\n"
        + (f"*{doc['authors']}*\n\n" if doc.get("authors") else "\n")
        + f"`{doc.get('page_count',0)} pages · {doc.get('n_chunks',0)} chunks · "
          f"{len(doc.get('tables',[]))} tables · {len(doc.get('figures',[]))} figures · "
          f"{doc.get('elapsed_s',0)}s`"
    )
    followups = doc.get("followups") or []
    status = f"Done in {doc.get('elapsed_s', 0)}s. Ask it anything in the Ask tab."
    if doc.get("warnings"):
        status += f" ({len(doc['warnings'])} section(s) fell back to raw text)"

    return (
        status,
        header,
        doc.get("explanation") or "_No explanation produced._",
        doc.get("summary") or "_No summary produced._",
        _findings_md(doc.get("findings", {})),
        _tables_md(doc.get("tables", [])),
        figures,
        _sections_md(doc),
        gr.update(choices=followups, value=None, visible=bool(followups)),
        files,
    )


def refresh_library():
    try:
        docs = _get("/documents").json()
    except Exception:
        return gr.update(choices=[], value=[]), "Backend unreachable."
    choices = [(f"{d['title'][:70]} ({d['page_count']}p)", d["doc_id"]) for d in docs]
    return gr.update(choices=choices), f"{len(docs)} document(s) in the library."


def ask_question(question, history, doc_ids):
    history = history or []
    if not question or not question.strip():
        return history, "", ""
    history = history + [{"role": "user", "content": question}]
    try:
        resp = _post("/ask", json={"question": question, "doc_ids": doc_ids or []})
    except requests.exceptions.ConnectionError:
        history.append({"role": "assistant", "content": f"Backend unreachable at {API_URL}."})
        return history, "", ""
    if resp.status_code != 200:
        history.append({"role": "assistant", "content": _error_text(resp)})
        return history, "", ""

    data = resp.json()
    history.append({"role": "assistant", "content": data["answer"]})
    slips = [f"_Retrieval rounds: {data.get('retrieval_rounds', 1)}_"]
    for s in data.get("sources", []):
        slips.append(
            f"<div class='slip'><div class='meta'>[{s['label']}] {s['doc_title'][:60]} · "
            f"{s['section']} · p.{s['page']} · sim {s['score']}</div>{s['snippet']}…</div>"
        )
    return history, "", "\n".join(slips)


def clear_library():
    try:
        _post("/reset")
    except Exception:
        return "Backend unreachable."
    return "Index cleared."


# ----------------------------------------------------------------------- ui
def build_ui() -> gr.Blocks:
    with gr.Blocks(theme=THEME, css=CSS, title="Research-Assistant-Bot") as demo:
        gr.HTML(
            "<div id='masthead'><h1>Research-Assistant-Bot</h1>"
            "<p>read the paper · ask the paper</p></div>"
        )
        status = gr.Markdown(backend_status(), elem_classes="statusbar")

        with gr.Row():
            with gr.Column(scale=1):
                pdf = gr.File(label="Research paper (PDF)", file_types=[".pdf"], type="filepath")
                understand = gr.Checkbox(
                    value=True,
                    label="Explain and summarise after indexing",
                    info="Uncheck to index only - faster, no LLM calls.",
                )
                go = gr.Button("Read this paper", variant="primary")
                run_status = gr.Markdown("", elem_classes="statusbar")
                downloads = gr.Files(label="Download report")

                gr.Markdown("#### Library")
                library = gr.CheckboxGroup(
                    choices=[], label="Search across", info="Leave empty to search everything."
                )
                with gr.Row():
                    refresh = gr.Button("Refresh", size="sm")
                    clear = gr.Button("Clear index", size="sm", variant="stop")

            with gr.Column(scale=2):
                header = gr.Markdown("Upload a paper to begin.")
                with gr.Tabs():
                    with gr.Tab("Explanation"):
                        explanation = gr.Markdown("", elem_classes="reading")
                    with gr.Tab("Summary"):
                        summary = gr.Markdown("", elem_classes="reading")
                    with gr.Tab("Findings"):
                        findings = gr.Markdown("", elem_classes="reading")
                    with gr.Tab("Tables"):
                        tables = gr.Markdown("")
                    with gr.Tab("Figures"):
                        figures = gr.Gallery(columns=3, height=420, show_label=False)
                    with gr.Tab("Structure"):
                        sections = gr.Markdown("")
                    with gr.Tab("Ask"):
                        chat = gr.Chatbot(height=380, show_label=False)
                        suggested = gr.Radio(
                            choices=[], label="Suggested questions", visible=False
                        )
                        question = gr.Textbox(
                            placeholder="What dataset did they evaluate on?",
                            label="Your question", lines=2,
                        )
                        with gr.Row():
                            send = gr.Button("Ask", variant="primary")
                            reset_chat = gr.Button("New conversation")
                        cited = gr.Markdown("", label="Sources")

        outputs = [run_status, header, explanation, summary, findings, tables,
                   figures, sections, suggested, downloads]
        go.click(process_pdf, [pdf, understand], outputs).then(
            refresh_library, None, [library, status]
        )
        refresh.click(refresh_library, None, [library, status])
        clear.click(clear_library, None, run_status).then(refresh_library, None, [library, status])

        send.click(ask_question, [question, chat, library], [chat, question, cited])
        question.submit(ask_question, [question, chat, library], [chat, question, cited])
        suggested.select(lambda q: q, suggested, question)
        reset_chat.click(lambda: ([], "", ""), None, [chat, question, cited])

        demo.load(refresh_library, None, [library, status])
    return demo


if __name__ == "__main__":
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    build_ui().launch(server_port=GRADIO_PORT, share=GRADIO_SHARE)
