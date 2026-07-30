"""LangGraph orchestration.

Two graphs:

  understand_graph   map/reduce over sections -> summary -> plain explanation -> findings
  qa_graph           plan -> retrieve -> grade -> (broaden and retry) -> answer

The Q&A graph has a real loop: if the grader says the retrieved excerpts don't
cover the question, it goes back and searches again with widened queries, up to
MAX_RETRIEVAL_LOOPS times, before answering with whatever it has.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.config import MAX_RETRIEVAL_LOOPS, TOP_K
from backend.core import prompts
from backend.core.llm import LLMError, chat, chat_json
from backend.core.vectorstore import get_store

log = logging.getLogger(__name__)

MAX_SECTION_CHARS = 6000
PRIORITY_SECTIONS = ["abstract", "introduction", "method", "data", "results",
                     "discussion", "limitations", "conclusion"]


# ===========================================================================
# 1. Understanding graph (runs once per uploaded PDF)
# ===========================================================================
class UnderstandState(TypedDict, total=False):
    doc_id: str
    title: str
    sections: list[dict[str, Any]]
    section_notes: list[dict[str, str]]
    notes_blob: str
    summary: str
    explanation: str
    findings: dict[str, Any]
    followups: list[str]
    errors: list[str]


def _pick_sections(state: UnderstandState) -> UnderstandState:
    """Rank sections so the important ones get summarised first (and always)."""
    sections = [s for s in state["sections"] if s.get("text")]
    order = {k: i for i, k in enumerate(PRIORITY_SECTIONS)}

    def rank(s: dict[str, Any]) -> tuple[int, int]:
        return (order.get(s.get("canonical", "other"), 50), -len(s["text"]))

    ranked = sorted(sections, key=rank)[:12]
    ranked.sort(key=lambda s: s.get("page_start", 0))
    return {"sections": ranked, "errors": state.get("errors", [])}


def _summarise_sections(state: UnderstandState) -> UnderstandState:
    notes: list[dict[str, str]] = []
    errors = list(state.get("errors", []))
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
        except LLMError as exc:
            errors.append(f"section '{section['title']}': {exc}")
            note = text[:900]
        notes.append({"section": section["title"], "note": note})
    blob = "\n\n".join(f"[{n['section']}]\n{n['note']}" for n in notes)
    return {"section_notes": notes, "notes_blob": blob[:14000], "errors": errors}


def _write_summary(state: UnderstandState) -> UnderstandState:
    text = chat(
        prompts.FINAL_SUMMARY.format(
            rules=prompts.PLAIN_ENGLISH_RULES, title=state["title"], notes=state["notes_blob"]
        ),
        prompts.SYSTEM_SUMMARISER,
        max_tokens=700,
    )
    return {"summary": text}


def _write_explanation(state: UnderstandState) -> UnderstandState:
    text = chat(
        prompts.SIMPLE_EXPLANATION.format(
            rules=prompts.PLAIN_ENGLISH_RULES, title=state["title"], notes=state["notes_blob"]
        ),
        prompts.SYSTEM_SUMMARISER,
        max_tokens=1100,
    )
    return {"explanation": text}


def _extract_findings(state: UnderstandState) -> UnderstandState:
    data = chat_json(
        prompts.KEY_FINDINGS.format(title=state["title"], notes=state["notes_blob"]),
        prompts.SYSTEM_SUMMARISER,
        max_tokens=1400,
        fallback={"findings": [], "contributions": [], "limitations": [],
                  "future_work": [], "methods": [], "metrics": []},
    )
    if not isinstance(data, dict):
        data = {"findings": [], "contributions": [], "limitations": [],
                "future_work": [], "methods": [], "metrics": []}
    return {"findings": data}


def _suggest_followups(state: UnderstandState) -> UnderstandState:
    data = chat_json(
        prompts.FOLLOWUP_QUESTIONS.format(summary=state.get("summary", "")[:2500]),
        prompts.SYSTEM_SUMMARISER,
        fast=True,
        max_tokens=300,
        fallback={"questions": []},
    )
    qs = (data or {}).get("questions", []) if isinstance(data, dict) else []
    return {"followups": [q for q in qs if isinstance(q, str)][:4]}


def build_understand_graph():
    g = StateGraph(UnderstandState)
    g.add_node("pick_sections", _pick_sections)
    g.add_node("summarise_sections", _summarise_sections)
    g.add_node("write_summary", _write_summary)
    g.add_node("write_explanation", _write_explanation)
    g.add_node("extract_findings", _extract_findings)
    g.add_node("suggest_followups", _suggest_followups)

    g.add_edge(START, "pick_sections")
    g.add_edge("pick_sections", "summarise_sections")
    g.add_edge("summarise_sections", "write_summary")
    g.add_edge("write_summary", "write_explanation")
    g.add_edge("write_explanation", "extract_findings")
    g.add_edge("extract_findings", "suggest_followups")
    g.add_edge("suggest_followups", END)
    return g.compile()


# ===========================================================================
# 2. Q&A graph (self-correcting RAG)
# ===========================================================================
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
    answer: str
    sources: list[dict[str, Any]]


def _plan(state: QAState) -> QAState:
    question = state["question"]
    data = chat_json(
        prompts.QUERY_PLAN.format(question=question),
        "You rewrite questions into retrieval queries.",
        fast=True,
        max_tokens=250,
        fallback={"queries": [question]},
    )
    queries = [question]
    if isinstance(data, dict):
        queries += [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]
    if state.get("missing"):
        queries.append(state["missing"])
    seen, unique = set(), []
    for q in queries:
        if q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)
    return {"queries": unique[:4], "loops": state.get("loops", 0) + 1}


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
    if not state.get("hits"):
        return {"sufficient": False, "missing": state["question"]}
    if state.get("loops", 1) > MAX_RETRIEVAL_LOOPS:
        return {"sufficient": True, "missing": ""}
    data = chat_json(
        prompts.GRADE_CONTEXT.format(question=state["question"], context=state["context"][:9000]),
        "You judge whether retrieved text answers a question.",
        fast=True,
        max_tokens=200,
        fallback={"sufficient": True, "missing": ""},
    )
    if not isinstance(data, dict):
        data = {"sufficient": True, "missing": ""}
    return {"sufficient": bool(data.get("sufficient", True)),
            "missing": str(data.get("missing", ""))[:300]}


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
        }
        for i, h in enumerate(state["hits"], start=1)
    ]
    return {"answer": text, "sources": sources}


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
