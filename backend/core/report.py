from __future__ import annotations

import re
from typing import Any


def _findings_md(findings: dict[str, Any]) -> str:
    if not findings:
        return "_No findings extracted._"
    out: list[str] = []
    items = findings.get("findings") or []
    if items:
        out.append("### Findings")
        for i, f in enumerate(items, 1):
            out.append(f"**{i}. {f.get('finding','')}**")
            evidence = (f.get("evidence") or "").strip()
            section = (f.get("section") or "").strip()
            if evidence:
                out.append(f"> {evidence}" + (f"  \n> — {section}" if section else ""))
    metrics = findings.get("metrics") or []
    if metrics:
        out.append("### Reported numbers")
        out.append("| Metric | Value | Where |")
        out.append("| --- | --- | --- |")
        for m in metrics:
            out.append(f"| {m.get('name','')} | {m.get('value','')} | {m.get('context','')} |")
    for key, label in (
        ("contributions", "Contributions"),
        ("methods", "Methods, data and models used"),
        ("limitations", "Limitations"),
        ("future_work", "Future work"),
    ):
        vals = findings.get(key) or []
        if vals:
            out.append(f"### {label}")
            out += [f"- {v}" for v in vals]
    return "\n\n".join(out)


def _tables_md(tables: list[dict[str, Any]]) -> str:
    if not tables:
        return "_No tables detected._"
    parts: list[str] = []
    for t in tables:
        head = f"**Table on page {t.get('page')}** · {t.get('n_rows')}×{t.get('n_cols')}"
        if t.get("accuracy"):
            head += f" · {t.get('flavour')} · accuracy {t.get('accuracy')}"
        parts.append(head)
        if t.get("caption"):
            parts.append(f"_{t['caption']}_")
        parts.append(t.get("markdown", ""))
    return "\n\n".join(parts)


def _structure_md(doc: dict[str, Any]) -> str:
    rows = ["| Section | Kind | Page | Words |", "| --- | --- | --- | --- |"]
    for s in doc.get("sections", []):
        rows.append(
            f"| {s.get('title','')} | `{s.get('canonical','')}` | "
            f"{s.get('page_start','')} | {s.get('words','')} |"
        )
    return "\n".join(rows)


def build_markdown(doc: dict[str, Any]) -> str:
    blocks = [
        f"# {doc.get('title','Untitled')}",
        f"*{doc.get('authors','')}*" if doc.get("authors") else "",
        f"`{doc.get('filename','')}` · {doc.get('page_count',0)} pages · "
        f"{doc.get('n_chunks',0)} indexed chunks · ingested {doc.get('ingested_at','')}",
        "## Summary",
        doc.get("summary", "") or "_None._",
        "## Plain-English explanation",
        doc.get("explanation", "") or "_None._",
        "## Key findings",
        _findings_md(doc.get("findings", {})),
        "## Tables",
        _tables_md(doc.get("tables", [])),
        "## Structure",
        _structure_md(doc),
    ]
    return "\n\n".join(b for b in blocks if b)


def safe_filename(title: str, doc_id: str, ext: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9 _-]", "", title or "paper")[:60].strip().replace(" ", "_")
    return f"{stem or 'paper'}_{doc_id}.{ext}"
