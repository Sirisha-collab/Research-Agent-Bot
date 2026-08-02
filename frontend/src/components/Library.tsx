import { RefreshCw, Trash2, X } from "lucide-react";
import clsx from "clsx";
import type { DocumentSummary } from "../types";

export function Library({
  docs,
  selected,
  activeId,
  onToggle,
  onOpen,
  onRefresh,
  onDelete,
  onReset,
}: {
  docs: DocumentSummary[];
  selected: string[];
  activeId: string | null;
  onToggle: (id: string) => void;
  onOpen: (id: string) => void;
  onRefresh: () => void;
  onDelete: (id: string) => void;
  onReset: () => void;
}) {
  return (
    <section className="border border-rule bg-surface p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="kicker">library · {docs.length}</h2>
        <div className="flex gap-2">
          <button onClick={onRefresh} title="Refresh" className="text-muted hover:text-ink">
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <button onClick={onReset} title="Clear index" className="text-muted hover:text-warn">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {docs.length === 0 ? (
        <p className="text-sm text-muted">Nothing indexed yet.</p>
      ) : (
        <ul className="scrollbar-thin max-h-80 space-y-1 overflow-y-auto pr-1">
          {docs.map((doc) => (
            <li
              key={doc.doc_id}
              className={clsx(
                "group flex items-start gap-2 border-l-2 py-1.5 pl-2",
                doc.doc_id === activeId ? "border-accent bg-accent-soft" : "border-transparent",
              )}
            >
              <input
                type="checkbox"
                checked={selected.includes(doc.doc_id)}
                onChange={() => onToggle(doc.doc_id)}
                className="mt-1 accent-accent"
              />
              <button onClick={() => onOpen(doc.doc_id)} className="flex-1 text-left">
                <span className="block text-sm leading-snug">{doc.title.slice(0, 90)}</span>
                <span className="kicker">
                  {doc.page_count}p · {doc.n_chunks} chunks · {doc.n_tables} tables
                </span>
              </button>
              <button
                onClick={() => onDelete(doc.doc_id)}
                className="mt-1 text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:text-warn"
                title="Remove"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="kicker mt-3">
        {selected.length === 0 ? "questions search everything" : `questions scoped to ${selected.length}`}
      </p>
    </section>
  );
}
