
PLAIN_ENGLISH_RULES = (
    "Write for a smart person who is NOT in this field. "
    "Expand every acronym the first time. Replace jargon with the plain word. "
    "Use short sentences. Never say 'the paper demonstrates a novel framework' - "
    "say what it actually does."
)

SYSTEM_SUMMARISER = (
    "You are a research analyst who explains papers to non-specialists. "
    "You only use the text you are given. If something is not in the text, you say so. "
    "You never invent numbers, citations, or author claims."
)

SYSTEM_QA = (
    "You are a research assistant answering questions strictly from provided excerpts "
    "of a paper. Every factual sentence must be traceable to an excerpt. "
    "If the excerpts do not contain the answer, say so plainly instead of guessing."
)

SECTION_SUMMARY = """Summarise this section of a research paper in 2-4 sentences.
Keep concrete details: numbers, dataset names, model names, comparisons.
Drop filler and citation lists.

Paper: {title}
Section: {section}

TEXT:
{text}

SUMMARY:"""

FINAL_SUMMARY = """Below are section-by-section notes from one research paper.
Write a connected summary of the whole paper in 180-260 words.

{rules}

Cover, in this order: the problem, what the authors did, what they found, and what
it means. Plain prose - no headings, no bullet points, no preamble like "This paper".

Paper title: {title}
Notes:
{notes}

SUMMARY:"""

SIMPLE_EXPLANATION = """Explain this paper to someone with no background in the field.

{rules}

Use exactly this structure with these four markdown headings:

### The problem
2-3 sentences on what was broken or unknown before this work.

### What they did
3-4 sentences on the approach, in everyday language. One analogy is welcome if it fits.

### What they found
3-4 sentences on the results, including the key numbers where the notes give them.

### Why it matters
2-3 sentences on who should care and what changes because of this.

Paper title: {title}
Notes from the paper:
{notes}
"""

KEY_FINDINGS = """From the notes below, extract the paper's concrete findings.

Return JSON of this exact shape:
{{"findings": [{{"finding": "one sentence, plain English, include the number if there is one",
                 "evidence": "the phrase from the notes that supports it",
                 "section": "results | method | discussion | conclusion | abstract"}}],
  "contributions": ["short phrase", "..."],
  "limitations": ["short phrase", "..."],
  "future_work": ["short phrase", "..."],
  "methods": ["dataset / model / technique names actually used"],
  "metrics": [{{"name": "e.g. accuracy", "value": "e.g. 91.4%", "context": "on which dataset or baseline"}}]}}

Rules: 3-7 findings. Only what the notes support. Empty list if a category is absent.
Never invent a number.

Paper title: {title}
Notes:
{notes}
"""

QUERY_PLAN = """A user asked a question about a research paper. Write 3 short search
queries that would retrieve the passages needed to answer it. Vary the wording:
one close to the question, one using the technical vocabulary a paper would use,
one about the surrounding context.

Return JSON: {{"queries": ["...", "...", "..."]}}

Question: {question}"""

GRADE_CONTEXT = """Decide whether these excerpts are enough to answer the question.

Question: {question}

EXCERPTS:
{context}

Return JSON: {{"sufficient": true or false, "missing": "what is still needed, or empty string"}}"""

ANSWER = """Answer the question using only the excerpts below.

Rules:
- Cite the excerpt you used after each claim, like [S2]. Multiple sources: [S1][S3].
- If the excerpts only partly answer it, answer that part and say what is missing.
- If they do not answer it at all, say: "The paper does not appear to cover this."
- Plain English. Keep technical terms only when they are the actual subject, and gloss them.
- 2-6 sentences unless the question needs a list.

Question: {question}

EXCERPTS:
{context}

ANSWER:"""

FOLLOWUP_QUESTIONS = """Given this paper summary, suggest 4 short questions a reader
would naturally want to ask next. They must be answerable from the paper itself.

Return JSON: {{"questions": ["...", "...", "...", "..."]}}

Summary:
{summary}"""


SYNTHESIS = """You are given notes from one research paper. Produce every part of the
analysis in a single JSON object.

{rules}

Return JSON with exactly these keys:

{{"summary": "180-260 words of connected prose covering the problem, what the authors did,
              what they found, and what it means. No headings, no bullets, no preamble.",
  "explanation": "markdown using exactly these four headings in this order:
                  '### The problem' (2-3 sentences on what was broken or unknown),
                  '### What they did' (3-4 sentences, everyday language, one analogy if it fits),
                  '### What they found' (3-4 sentences with the key numbers),
                  '### Why it matters' (2-3 sentences on who should care)",
  "findings": {{"findings": [{{"finding": "one sentence, plain English, include the number if there is one",
                              "evidence": "the phrase from the notes that supports it",
                              "section": "results | method | discussion | conclusion | abstract"}}],
                "contributions": ["short phrase"],
                "limitations": ["short phrase"],
                "future_work": ["short phrase"],
                "methods": ["dataset / model / technique names actually used"],
                "metrics": [{{"name": "e.g. accuracy", "value": "e.g. 91.4%",
                              "context": "on which dataset or baseline"}}]}},
  "followups": ["4 short questions a reader would ask next, answerable from this paper"]}}

Rules: 3-7 findings. Only what the notes support. Empty list where a category is absent.
Never invent a number, a citation, or an author claim.

Paper title: {title}
Notes:
{notes}
"""
