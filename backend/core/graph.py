from __future__ import annotations

import logging
import re
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.config import (
    GRADE_STRONG_SCORE,
    GRADE_TOP_SCORE,
    LLM_CONTEXT_GRADING,
    LLM_QUERY_PLANNING,
    MAP_REDUCE_THRESHOLD,
    MAX_RETRIEVAL_LOOPS,
    SYNTHESIS_MAX_TOKENS,
    TOP_K,
)
from backend.core import prompts
from backend.core.llm import LLMError, chat, chat_json
from backend.core.vectorstore import get_store

log = logging.getLogger(__name__)

MAX_SECTION_CHARS = 6000
MAX_NOTES_CHARS = 40000
PRIORITY_SECTIONS = ["abstract", "introduction", "method", "data", "results",
                     "discussion", "limitations", "conclusion"]

EMPTY_FINDINGS = {
    "findings": [],
    "contributions": [],
    "limitations": [],
    "future_work": [],
    "methods": [],
    "metrics": [],
}


class UnderstandState(TypedDict, total=False):
    doc_id: str
    title: str
    sections: list[dict[str, Any]]
    total_words: int
    section_notes: list[dict[str, str]]
    notes_blob: str
    summary: str
    explanation: str
    findings: dict[str, Any]
    followups: list[str]
    llm_calls: int
    errors: list[str]


def _pick_sections(state: UnderstandState) -> UnderstandState:
    sections = [s for s in state["sections"] if s.get("text")]
    order = {k: i for i, k in enumerate(PRIORITY_SECTIONS)}

    def rank(s: dict[str, Any]) -> tuple[int, int]:
        return (order.get(s.get("canonical", "other"), 50), -len(s["text"]))

    ranked = sorted(sections, key=rank)[:12]
    ranked.sort(key=lambda s: s.get("page_start", 0))
    total = sum(len(s["text"].split()) for s in ranked)
    return {"sections": ranked, "total_words": total, "llm_calls": 0,
            "errors": state.get("errors", [])}


def _route_strategy(state: UnderstandState) -> Literal["summarise_sections", "synthesise"]:
    if state.get("total_words", 0) > MAP_REDUCE_THRESHOLD:
        log.info("Long paper (%d words): using map-reduce", state["total_words"])
        return "summarise_sections"
    log.info("Short paper (%d words): single synthesis call", state.get("total_words", 0))
    return "synthesise"


def _use_sections_directly(state: UnderstandState) -> str:
    parts = [f"[{s['title']}]\n{s['text']}" for s in state["sections"]]
    return "\n\n".join(parts)[:MAX_NOTES_CHARS]


def _summarise_sections(state: UnderstandState) -> UnderstandState:
    notes: list[dict[str, str]] = []
    errors = list(state.get("errors", []))
    calls = state.get("llm_calls", 0)
    for section in state["sections"]:
        text = section["text"][:MAX_SECTION_CHARS]
        if len(text.split()) < 40:
            notes.append({"section": section["title"], "note": text})
            continue
        try:
            note = chat(
                prompts.SECTION_SUMMARY.format(
                    title=state["title"], section=section["title"], text=text
                ),
                prompts.SYSTEM_SUMMARISER,
                fast=True,
                max_tokens=350,
            )
            calls += 1
        except LLMError as exc:
            errors.append(f"section '{section['title']}': {exc}")
            note = text[:900]
        notes.append({"section": section["title"], "note": note})
    blob = "\n\n".join(f"[{n['section']}]\n{n['note']}" for n in notes)
    return {"section_notes": notes, "notes_blob": blob[:14000],
            "llm_calls": calls, "errors": errors}


def _synthesise(state: UnderstandState) -> UnderstandState:
    notes = state.get("notes_blob") or _use_sections_directly(state)
    data = chat_json(
        prompts.SYNTHESIS.format(
            rules=prompts.PLAIN_ENGLISH_RULES, title=state["title"], notes=notes
        ),
        prompts.SYSTEM_SUMMARISER,
        max_tokens=SYNTHESIS_MAX_TOKENS,
        fallback=None,
    )
    calls = state.get("llm_calls", 0) + 1
    errors = list(state.get("errors", []))

    if not isinstance(data, dict):
        errors.append("synthesis returned unparseable JSON")
        return {"summary": "", "explanation": "", "findings": dict(EMPTY_FINDINGS),
                "followups": [], "notes_blob": notes, "llm_calls": calls, "errors": errors}

    findings = data.get("findings")
    if not isinstance(findings, dict):
        findings = dict(EMPTY_FINDINGS)
    else:
        findings = {**EMPTY_FINDINGS, **findings}

    followups = data.get("followups")
    followups = [q for q in followups if isinstance(q, str)][:4] if isinstance(followups, list) else []

    return {
        "summary": str(data.get("summary", "")).strip(),
        "explanation": str(data.get("explanation", "")).strip(),
        "findings": findings,
        "followups": followups,
        "notes_blob": notes,
        "llm_calls": calls,
        "errors": errors,
    }


def build_understand_graph():
    g = StateGraph(UnderstandState)
    g.add_node("pick_sections", _pick_sections)
    g.add_node("summarise_sections", _summarise_sections)
    g.add_node("synthesise", _synthesise)

    g.add_edge(START, "pick_sections")
    g.add_conditional_edges(
        "pick_sections",
        _route_strategy,
        {"summarise_sections": "summarise_sections", "synthesise": "synthesise"},
    )
    g.add_edge("summarise_sections", "synthesise")
    g.add_edge("synthesise", END)
    return g.compile()


def _keep_last(_old: Any, new: Any) -> Any:
    return new


class QAState(TypedDict, total=False):
    question: str
    doc_ids: list[str]
    queries: list[str]
    hits: list[dict[str, Any]]
    context: str
    sufficient: bool
    missing: str
    loops: Annotated[int, _keep_last]
    llm_calls: int
    answer: str
    sources: list[dict[str, Any]]


def _cheap_variants(question: str) -> list[str]:
    stripped = re.sub(r"^(what|how|why|which|when|where|who|do|does|did|is|are)\s+",
                      "", question.strip(), flags=re.I)
    keywords = " ".join(
        w for w in re.findall(r"[A-Za-z0-9-]{3,}", question)
        if w.lower() not in {"the", "and", "for", "with", "this", "that", "paper",
                             "they", "what", "how", "why", "does", "did", "was"}
    )
    return [v for v in (stripped, keywords) if v and v.lower() != question.lower()]


def _plan(state: QAState) -> QAState:
    question = state["question"]
    calls = state.get("llm_calls", 0)
    queries = [question] + _cheap_variants(question)

    if LLM_QUERY_PLANNING:
        data = chat_json(
            prompts.QUERY_PLAN.format(question=question),
            "You rewrite questions into retrieval queries.",
            fast=True,
            max_tokens=250,
            fallback={"queries": []},
        )
        calls += 1
        if isinstance(data, dict):
            queries += [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]

    if state.get("missing"):
        queries.append(state["missing"])

    seen, unique = set(), []
    for q in queries:
        key = q.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(q)
    return {"queries": unique[:4], "loops": state.get("loops", 0) + 1, "llm_calls": calls}


def _retrieve(state: QAState) -> QAState:
    store = get_store()
    k = TOP_K if state.get("loops", 1) == 1 else TOP_K + 4
    hits = store.multi_search(state["queries"], k=k, doc_ids=state.get("doc_ids") or None)
    context = "\n\n".join(
        f"[S{i}] (p.{h['page_start']}, {h['section_title']})\n{h['text']}"
        for i, h in enumerate(hits, start=1)
    )
    return {"hits": hits, "context": context}


def _grade(state: QAState) -> QAState:
    hits = state.get("hits", [])
    if not hits:
        return {"sufficient": False, "missing": state["question"]}
    if state.get("loops", 1) > MAX_RETRIEVAL_LOOPS:
        return {"sufficient": True, "missing": ""}

    if not LLM_CONTEXT_GRADING:
        top = hits[0]["score"]
        strong = sum(1 for h in hits if h["score"] >= GRADE_STRONG_SCORE)
        ok = top >= GRADE_TOP_SCORE or strong >= 2
        return {"sufficient": ok, "missing": "" if ok else state["question"]}

    data = chat_json(
        prompts.GRADE_CONTEXT.format(question=state["question"], context=state["context"][:9000]),
        "You judge whether retrieved text answers a question.",
        fast=True,
        max_tokens=200,
        fallback={"sufficient": True, "missing": ""},
    )
    if not isinstance(data, dict):
        data = {"sufficient": True, "missing": ""}
    return {
        "sufficient": bool(data.get("sufficient", True)),
        "missing": str(data.get("missing", ""))[:300],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


def _route(state: QAState) -> Literal["plan", "answer"]:
    if state.get("sufficient", True):
        return "answer"
    if state.get("loops", 1) >= MAX_RETRIEVAL_LOOPS:
        return "answer"
    return "plan"


def _answer(state: QAState) -> QAState:
    if not state.get("hits"):
        return {
            "answer": "I could not find anything relevant in the indexed documents. "
                      "Try rephrasing, or check that the right paper is selected.",
            "sources": [],
        }
    text = chat(
        prompts.ANSWER.format(question=state["question"], context=state["context"][:12000]),
        prompts.SYSTEM_QA,
        max_tokens=900,
    )
    sources = [
        {
            "label": f"S{i}",
            "doc_id": h["doc_id"],
            "doc_title": h["doc_title"],
            "section": h["section_title"],
            "page": h["page_start"],
            "score": h["score"],
            "snippet": h["text"][:400],
            "full_text": h["text"],
            "kind": h.get("kind", "text"),
        }
        for i, h in enumerate(state["hits"], start=1)
    ]
    return {"answer": text, "sources": sources,
            "llm_calls": state.get("llm_calls", 0) + 1}


def build_qa_graph():
    g = StateGraph(QAState)
    g.add_node("plan", _plan)
    g.add_node("retrieve", _retrieve)
    g.add_node("grade", _grade)
    g.add_node("answer", _answer)

    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", _route, {"plan": "plan", "answer": "answer"})
    g.add_edge("answer", END)
    return g.compile()


_understand = None
_qa = None


def understand_graph():
    global _understand
    if _understand is None:
        _understand = build_understand_graph()
    return _understand


def qa_graph():
    global _qa
    if _qa is None:
        _qa = build_qa_graph()
    return _qa
