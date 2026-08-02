import { AlertTriangle, Check, Loader2 } from "lucide-react";
import type { Health } from "../types";

export function StatusBar({ health, error }: { health: Health | null; error: string | null }) {
  if (error) {
    return (
      <div className="flex items-center gap-2 border border-warn/40 bg-warn/5 px-3 py-2">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warn" />
        <span className="kicker text-warn">{error}</span>
      </div>
    );
  }
  if (!health) {
    return (
      <div className="flex items-center gap-2 px-1 py-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" />
        <span className="kicker">contacting api</span>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 py-2">
      <span className="kicker flex items-center gap-1.5">
        {health.api_key_configured ? (
          <Check className="h-3.5 w-3.5 text-accent" />
        ) : (
          <AlertTriangle className="h-3.5 w-3.5 text-warn" />
        )}
        {health.llm_provider} / {health.llm_model}
      </span>
      <span className="kicker">{health.embedding_model}</span>
      <span className="kicker">
        {health.indexed_documents} docs · {health.indexed_chunks} chunks
      </span>
      {!health.api_key_configured && (
        <span className="kicker text-warn">no api key in .env</span>
      )}
    </div>
  );
}
