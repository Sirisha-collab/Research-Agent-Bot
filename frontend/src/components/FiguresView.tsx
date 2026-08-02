import { useState } from "react";
import { api } from "../api";
import type { FigureBlock } from "../types";

export function FiguresView({ docId, figures }: { docId: string; figures: FigureBlock[] }) {
  const [zoom, setZoom] = useState<FigureBlock | null>(null);

  if (figures.length === 0) return <p className="text-sm text-muted">No figures extracted.</p>;

  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {figures.map((fig) => (
          <figure key={fig.id} className="border border-rule bg-surface p-2">
            <button onClick={() => setZoom(fig)} className="block w-full">
              <img
                src={api.figureUrl(docId, fig.id)}
                alt={fig.caption || `figure on page ${fig.page}`}
                loading="lazy"
                className="h-32 w-full bg-paper object-contain"
              />
            </button>
            <figcaption className="kicker mt-2 line-clamp-2">
              {fig.caption || `page ${fig.page}`}
            </figcaption>
          </figure>
        ))}
      </div>

      {zoom && (
        <div
          onClick={() => setZoom(null)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 p-8"
        >
          <div className="max-h-full max-w-3xl overflow-auto bg-surface p-4">
            <img src={api.figureUrl(docId, zoom.id)} alt={zoom.caption} className="w-full" />
            <p className="mt-3 text-sm text-muted">{zoom.caption || `page ${zoom.page}`}</p>
          </div>
        </div>
      )}
    </>
  );
}
