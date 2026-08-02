import { useEffect, useRef, useState } from "react";
import { Loader2, RotateCcw, Send } from "lucide-react";
import clsx from "clsx";
import { Markdown } from "./Markdown";
import type { ChatTurn, Source } from "../types";

function Slip({ source }: { source: Source }) {
  return (
    <div className="border-l-2 border-accent py-1 pl-3">
      <div className="kicker">
        [{source.label}] {source.doc_title.slice(0, 48)} · {source.section} · p.{source.page} · sim{" "}
        {source.score}
      </div>
      <p className="mt-0.5 text-sm leading-relaxed text-muted">{source.snippet}…</p>
    </div>
  );
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
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns.length, busy]);

  function submit() {
    const question = draft.trim();
    if (!question || busy) return;
    onAsk(question);
    setDraft("");
  }

  return (
    <div className="flex h-[32rem] flex-col">
      <div className="scrollbar-thin flex-1 space-y-5 overflow-y-auto pr-2">
        {turns.length === 0 && (
          <p className="text-sm text-muted">
            Ask something specific: what baseline did they compare against, how large was the
            dataset, what do they admit they cannot do.
          </p>
        )}

        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <p key={i} className="border-l-2 border-ink pl-3 font-semibold leading-snug">
              {turn.content}
            </p>
          ) : (
            <div key={i}>
              <Markdown>{turn.content}</Markdown>
              {turn.sources && turn.sources.length > 0 && (
                <details className="mt-2">
                  <summary className="kicker cursor-pointer hover:text-ink">
                    {turn.sources.length} sources · {turn.rounds ?? 1} retrieval round
                    {(turn.rounds ?? 1) > 1 ? "s" : ""}
                  </summary>
                  <div className="mt-2 space-y-3">
                    {turn.sources.map((s) => (
                      <Slip key={s.label} source={s} />
                    ))}
                  </div>
                </details>
              )}
            </div>
          ),
        )}

        {busy && (
          <div className="kicker working flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            retrieving and grading
          </div>
        )}
        <div ref={endRef} />
      </div>

      {suggestions.length > 0 && turns.length === 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onAsk(s)}
              className="border border-rule px-2 py-1 text-left text-xs hover:border-accent hover:text-accent"
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
          placeholder="What dataset did they evaluate on?"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          className="flex-1 resize-none border border-rule bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
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
        <button onClick={onReset} title="New conversation" className="p-2 text-muted hover:text-ink">
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
