"""Headless CLI - useful for building the library from a folder of papers.

    python scripts/cli.py ingest papers/            # a folder or a single pdf
    python scripts/cli.py ask "what datasets are used across these papers?"
    python scripts/cli.py list
"""
from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import UPLOAD_DIR  # noqa: E402
from backend.core import pipeline  # noqa: E402
from backend.core.vectorstore import get_store  # noqa: E402


def cmd_ingest(args: argparse.Namespace) -> None:
    target = Path(args.path)
    pdfs = sorted(target.glob("**/*.pdf")) if target.is_dir() else [target]
    if not pdfs:
        print("No PDFs found.")
        return
    for pdf in pdfs:
        doc_id = uuid.uuid4().hex[:12]
        dest = UPLOAD_DIR / f"{doc_id}_{pdf.name.replace(' ', '_')}"
        shutil.copy(pdf, dest)
        print(f"→ {pdf.name}")
        result = pipeline.ingest_pdf(dest, doc_id, run_understanding=not args.no_understand)
        print(f"  {result['title'][:80]}")
        print(f"  {result['n_chunks']} chunks, {result['n_tables']} tables, "
              f"{result['n_figures']} figures, {result['elapsed_s']}s")


def cmd_ask(args: argparse.Namespace) -> None:
    result = pipeline.ask(args.question, args.doc_ids or None)
    print("\n" + result["answer"] + "\n")
    for s in result["sources"]:
        print(f"  [{s['label']}] {s['doc_title'][:50]} · {s['section']} · p.{s['page']} "
              f"· sim {s['score']}")


def cmd_list(_: argparse.Namespace) -> None:
    docs = get_store().list_documents()
    if not docs:
        print("Library is empty.")
        return
    for d in docs:
        print(f"{d['doc_id']}  {d['title'][:70]:<72} {d['page_count']}p  {d['n_chunks']} chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-Assistant-Bot CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="index a PDF or a folder of PDFs")
    p_ing.add_argument("path")
    p_ing.add_argument("--no-understand", action="store_true",
                       help="index only, skip LLM summarisation")
    p_ing.set_defaults(func=cmd_ingest)

    p_ask = sub.add_parser("ask", help="ask the indexed library a question")
    p_ask.add_argument("question")
    p_ask.add_argument("--doc-ids", nargs="*", dest="doc_ids")
    p_ask.set_defaults(func=cmd_ask)

    p_list = sub.add_parser("list", help="show indexed documents")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
