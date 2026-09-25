import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, RotateCcw, Send } from "lucide-react";
import clsx from "clsx";
import { Markdown } from "./Markdown";
import type { ChatTurn, Source } from "../types";

function Slip({ source, cited }: { source: Source; cited: boolean }) {
  const [open, setOpen] = useState(false);
  const snippet = source.snippet ?? "";
  const body = source.full_text || snippet;
  const truncated = body.trim().length > snippet.trim().length;
  const shown = open ? body : snippet;
  const wordCount = body.trim().split(/\s+/).filter(Boolean).length;
  const title = source.doc_title ?? "";

  return (
    <div
      className={clsx(
        "border-l-2 py-1 pl-3",
        cited ? "border-accent bg-accent-soft/40" : "border-rule",
      )}
    >
      <div className="kicker flex flex-wrap items-center gap-x-2">
        <span className={cited ? "text-accent" : undefined}>[{source.label}]</span>
        <span title={title}>{title.length > 44 ? `${title.slice(0, 44)}…` : title}</span>
        <span>· {source.section}</span>
        <span>· p.{source.page}</span>
        <span>· sim {source.score}</span>
        {source.kind !== "text" && <span className="text-accent">· {source.kind}</span>}
      </div>

      {source.kind === "table" ? (
        <div className="mt-1 overflow-x-auto text-sm">
          <Markdown>{shown}</Markdown>
        </div>
      ) : (
        <p className="mt-0.5 text-sm leading-relaxed text-muted">
          {shown}
          {!open && truncated ? "…" : ""}
        </p>
      )}

      {truncated && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="kicker mt-1 flex items-center gap-1 hover:text-accent"
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {open ? "show less" : `show full passage · ${wordCount} words`}
        </button>
      )}
    </div>
  );
}

// Handles [S1], [S1][S2] and [S1, S2] — the model does not always emit one label per bracket.
function citedLabels(answer: string): Set<string> {
  const found = new Set<string>();
  for (const group of answer.matchAll(/\[([^\]]+)\]/g)) {
    for (const label of group[1].matchAll(/S\d+/g)) found.add(label[0]);
  }
  return found;
}

export function AskPanel({
  turns,
  busy,
  suggestions,
  onAsk,
  onReset,
}: {
  turns: ChatTurn[];
  busy: boolean;
  suggestions: string[];
  onAsk: (question: string) => void;
  onReset: () => void;
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastContent = turns[turns.length - 1]?.content ?? "";

  // Pin to the bottom only if the reader is already there — otherwise a streaming
  // answer yanks them away from a passage they are reading.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom < 160) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [turns.length, lastContent, busy]);

  function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    onAsk(trimmed);
  }

  function submit() {
    if (!draft.trim() || busy) return;
    ask(draft);
    setDraft("");
  }

  return (
    <div className="flex h-[32rem] min-h-0 flex-col">
      <div
        ref={scrollRef}
        className="scrollbar-thin min-h-0 flex-1 space-y-5 overflow-y-auto pr-2"
      >
        {turns.length === 0 && !busy && (
          <p className="text-sm text-muted">
            Ask something specific: what baseline did they compare against, how large was the
            dataset, what do they admit they cannot do.
          </p>
        )}

        {turns.map((turn, i) => {
          if (turn.role === "user") {
            return (
              <p key={i} className="border-l-2 border-ink pl-3 font-semibold leading-snug">
                {turn.content}
              </p>
            );
          }
          const cited = citedLabels(turn.content);
          const sources = turn.sources ?? [];
          const usedCount = sources.filter((s) => cited.has(s.label)).length;
          return (
            <div key={i}>
              <Markdown>{turn.content}</Markdown>
              {sources.length > 0 && (
                <details className="mt-2" open={usedCount > 0 && usedCount <= 3}>
                  <summary className="kicker cursor-pointer hover:text-ink">
                    {usedCount > 0
                      ? `${usedCount} of ${sources.length} passages cited`
                      : `${sources.length} passages retrieved`}
                    {" · "}
                    {turn.rounds ?? 1} round{(turn.rounds ?? 1) > 1 ? "s" : ""}
                  </summary>
                  <div className="mt-2 space-y-3">
                    {[...sources]
                      .sort(
                        (a, b) =>
                          Number(cited.has(b.label)) - Number(cited.has(a.label)),
                      )
                      .map((s) => (
                        <Slip key={s.label} source={s} cited={cited.has(s.label)} />
                      ))}
                  </div>
                </details>
              )}
            </div>
          );
        })}

        {busy && (
          <div className="kicker working flex items-center gap-2" aria-live="polite">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            retrieving and grading
          </div>
        )}
      </div>

      {suggestions.length > 0 && turns.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              disabled={busy}
              onClick={() => ask(s)}
              className={clsx(
                "border px-2 py-1 text-left text-xs",
                busy
                  ? "cursor-not-allowed border-rule text-muted"
                  : "border-rule hover:border-accent hover:text-accent",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-end gap-2 border-t border-rule pt-3">
        <textarea
          value={draft}
          rows={2}
          aria-label="Ask a question about the paper"
          placeholder="What dataset did they evaluate on?"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            // isComposing guards IME input — Enter mid-composition commits the
            // candidate, it does not send the question.
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          className="flex-1 resize-none border border-rule bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          type="button"
          onClick={submit}
          disabled={busy || !draft.trim()}
          className={clsx(
            "flex items-center gap-1.5 border px-3 py-2 font-mono text-xs uppercase tracking-widest",
            busy || !draft.trim()
              ? "cursor-not-allowed border-rule text-muted"
              : "border-accent bg-accent text-surface hover:border-ink hover:bg-ink",
          )}
        >
          <Send className="h-3.5 w-3.5" />
          ask
        </button>
        <button
          type="button"
          onClick={onReset}
          title="New conversation"
          aria-label="New conversation"
          className="p-2 text-muted hover:text-ink"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
