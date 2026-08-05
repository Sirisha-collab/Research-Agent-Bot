# Update: expandable citations + BibTeX export

Unzip at the project root, overwriting the eight files. No new dependencies. Restart the
API; the web dev server hot-reloads.

## Files

| File | Change |
| --- | --- |
| `backend/core/graph.py` | replace — source payload now carries `full_text` and `kind` |
| `backend/schemas.py` | replace — `Source` gains `full_text`, `kind` |
| `backend/core/citations.py` | new — BibTeX builder |
| `backend/main.py` | replace — adds `GET /library/bibtex` |
| `web/src/types.ts` | replace — `Source` type updated |
| `web/src/api.ts` | replace — adds `bibtexUrl()` |
| `web/src/components/AskPanel.tsx` | replace — expandable passages, cited highlighting |
| `web/src/components/Library.tsx` | replace — export button |

## Feature 1: cited passage in context

The answer text contains `[S1]`-style markers. The panel now parses those, so:

- Passages the model actually cited are pulled to the top, tinted, and their label shown in
  accent. Retrieved-but-unused passages sink below in grey — useful signal about whether
  retrieval or generation is at fault when an answer is thin.
- The summary line reads "3 of 6 passages cited" instead of a flat count, and auto-opens
  when three or fewer were used.
- Each passage has **show full passage · N words**, expanding the 400-character snippet to
  the whole chunk. Table chunks render as markdown tables rather than raw pipe text.

This needed a backend change after all: `graph.py` was truncating with `h["text"][:400]`
before serialising, so the full chunk never reached the client. It now sends both.

## Feature 2: BibTeX export

`GET /library/bibtex` returns `library.bib`. Optional `?doc_ids=a,b,c` scopes the export;
the button sends whichever papers are ticked, or the whole library when none are.

Fields are assembled from what the extractor already found:

- **DOI** and **arXiv id** — regex-matched from the first 4000 characters during parsing
- **year** — from PDF creation metadata, or inferred from the arXiv id prefix (`2305.xxxxx`
  is 2023), or a four-digit year in the title
- **author** — the first-page author line, split on commas and "and", filtered to plausible
  names
- **key** — `surnameYEARtitleword`, deduplicated with a/b/c suffixes
- entry type is `@article` when a DOI or arXiv id exists, `@misc` otherwise

LaTeX-escapes `& % $ # _ { } ~ ^` so titles with ampersands or percentages compile.

Example output:

```bibtex
@article{vaswani2017attention,
  title = {Attention Is All You Need},
  author = {A Vaswani and N Shazeer},
  year = {2017},
  eprint = {1706.03762},
  archivePrefix = {arXiv},
  journal = {arXiv preprint arXiv:1706.03762},
  note = {Indexed from attn.pdf}
}
```

**Accuracy caveat, and it matters.** These fields are heuristics over PDF text, not a
metadata lookup. Author lines get mangled by affiliation footnotes and symbols; venue and
page numbers are absent entirely; papers without a DOI or arXiv id often get no year. The
export header says as much in a comment. Treat it as a starting point that saves typing,
not a citation you can paste into a submission unchecked.

If you want real accuracy later, the DOI is the hook: one call to
`https://api.crossref.org/works/{doi}/transform/application/x-bibtex` returns the
publisher's own BibTeX. That's roughly 15 lines in `citations.py` plus a network dependency,
and it only helps for papers that have a DOI.
