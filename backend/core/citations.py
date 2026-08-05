from __future__ import annotations

import re
from typing import Any

STOPWORDS = {
    "a", "an", "the", "on", "of", "for", "and", "in", "with", "to", "from",
    "using", "via", "towards", "toward", "based", "by", "at",
}

LATEX_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _escape(text: str) -> str:
    text = (text or "").replace("\\", r"\textbackslash{}")
    for char, repl in LATEX_ESCAPES.items():
        text = text.replace(char, repl)
    return re.sub(r"\s+", " ", text).strip()


def _year(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata") or {}
    created = str(meta.get("created", ""))
    match = re.search(r"(19|20)\d{2}", created)
    if match:
        return match.group(0)
    arxiv = str(meta.get("arxiv", ""))
    if re.match(r"^\d{4}\.", arxiv):
        prefix = arxiv[:2]
        return f"20{prefix}" if prefix.isdigit() else ""
    match = re.search(r"(19|20)\d{2}", str(doc.get("title", "")))
    return match.group(0) if match else ""


def _authors_field(raw: str) -> str:
    if not raw:
        return ""
    cleaned = re.sub(r"\s*\d+\s*", " ", raw)
    cleaned = re.sub(r"[*†‡§¶]", "", cleaned)
    parts = re.split(r",| and | & ", cleaned)
    names = [re.sub(r"\s+", " ", p).strip() for p in parts]
    names = [n for n in names if 1 < len(n) < 60 and " " in n]
    return " and ".join(names[:12])


def _first_author_surname(raw: str) -> str:
    field = _authors_field(raw)
    if not field:
        return "anon"
    first = field.split(" and ")[0]
    surname = first.split()[-1]
    return re.sub(r"[^A-Za-z]", "", surname).lower() or "anon"


def _title_word(title: str) -> str:
    for word in re.findall(r"[A-Za-z]{3,}", title or ""):
        if word.lower() not in STOPWORDS:
            return word.lower()
    return "paper"


def make_key(doc: dict[str, Any], taken: set[str]) -> str:
    base = f"{_first_author_surname(doc.get('authors',''))}{_year(doc) or 'nd'}{_title_word(doc.get('title',''))}"
    key = re.sub(r"[^a-z0-9]", "", base) or "ref"
    candidate = key
    suffix = ord("a")
    while candidate in taken:
        candidate = f"{key}{chr(suffix)}"
        suffix += 1
    taken.add(candidate)
    return candidate


def to_bibtex(doc: dict[str, Any], taken: set[str]) -> str:
    meta = doc.get("metadata") or {}
    doi = str(meta.get("doi", "")).strip()
    arxiv = str(meta.get("arxiv", "")).strip()
    entry_type = "article" if (doi or arxiv) else "misc"

    fields: list[tuple[str, str]] = [("title", _escape(doc.get("title", "Untitled")))]
    authors = _authors_field(doc.get("authors", ""))
    if authors:
        fields.append(("author", _escape(authors)))
    year = _year(doc)
    if year:
        fields.append(("year", year))
    if arxiv:
        fields.append(("eprint", arxiv))
        fields.append(("archivePrefix", "arXiv"))
        fields.append(("journal", f"arXiv preprint arXiv:{arxiv}"))
    if doi:
        fields.append(("doi", doi))
        fields.append(("url", f"https://doi.org/{doi}"))
    fields.append(("note", _escape(f"Indexed from {doc.get('filename','local PDF')}")))

    key = make_key(doc, taken)
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n{body}\n}}"


def library_to_bibtex(docs: list[dict[str, Any]]) -> str:
    taken: set[str] = set()
    entries = [to_bibtex(doc, taken) for doc in docs]
    header = (
        f"% Research-Assistant-Bot library export\n"
        f"% {len(entries)} entries\n"
        f"% Fields are parsed heuristically from each PDF; verify before submitting.\n\n"
    )
    return header + "\n\n".join(entries) + "\n"
