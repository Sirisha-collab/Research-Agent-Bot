import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, X } from "lucide-react";
import clsx from "clsx";
import { api } from "../api";

export interface PdfTarget {
  docId: string;
  title: string;
  page: number;
  pageCount: number;
  label?: string;
  section?: string;
}

export function PdfViewer({
  target,
  onClose,
  onPageChange,
}: {
  target: PdfTarget;
  onClose: () => void;
  onPageChange: (page: number) => void;
}) {
  const [failed, setFailed] = useState(false);
  const src = api.pdfUrl(target.docId, target.page);
  const max = target.pageCount || 9999;

  useEffect(() => {
    setFailed(false);
  }, [target.docId]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside
      className="fixed top-0 right-0 z-40 flex h-screen w-full flex-col border-l border-rule bg-surface shadow-lg sm:w-[30rem] lg:w-[34rem]"
      aria-label="Source PDF"
    >
      <header className="flex items-start gap-2 border-b border-rule px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm leading-snug font-semibold">{target.title}</p>
          <p className="kicker">
            {target.label ? `${target.label} · ` : ""}
            page {target.page}
            {target.pageCount ? ` of ${target.pageCount}` : ""}
            {target.section ? ` · ${target.section}` : ""}
          </p>
        </div>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          title="Open in a new tab"
          className="p-1 text-muted hover:text-accent"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
        <button onClick={onClose} title="Close" className="p-1 text-muted hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </header>

      {failed ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm text-muted">
            This browser would not display the PDF inline. Open it in a new tab instead.
          </p>
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="kicker border border-rule px-2.5 py-1.5 hover:border-accent hover:text-accent"
          >
            open page {target.page}
          </a>
        </div>
      ) : (
        <iframe
          key={src}
          src={src}
          title={`${target.title}, page ${target.page}`}
          onError={() => setFailed(true)}
          className="flex-1 border-0 bg-paper"
        />
      )}

      <footer className="flex items-center justify-between gap-2 border-t border-rule px-3 py-2">
        <button
          onClick={() => onPageChange(Math.max(1, target.page - 1))}
          disabled={target.page <= 1}
          className={clsx(
            "kicker flex items-center gap-1 border px-2 py-1",
            target.page <= 1
              ? "cursor-not-allowed border-rule text-muted opacity-40"
              : "border-rule hover:border-accent hover:text-accent",
          )}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          prev
        </button>
        <span className="kicker">physical page, not printed number</span>
        <button
          onClick={() => onPageChange(Math.min(max, target.page + 1))}
          disabled={target.page >= max}
          className={clsx(
            "kicker flex items-center gap-1 border px-2 py-1",
            target.page >= max
              ? "cursor-not-allowed border-rule text-muted opacity-40"
              : "border-rule hover:border-accent hover:text-accent",
          )}
        >
          next
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </footer>
    </aside>
  );
}
