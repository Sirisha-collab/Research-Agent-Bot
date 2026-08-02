import type { AskResponse, DocumentDetail, DocumentSummary, Health } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      void 0;
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

function withTimeout(ms: number): AbortSignal {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), ms);
  return controller.signal;
}

export const api = {
  base: BASE,

  health(): Promise<Health> {
    return fetch(`${BASE}/health`, { signal: withTimeout(8000) }).then(parse<Health>);
  },

  documents(): Promise<DocumentSummary[]> {
    return fetch(`${BASE}/documents`).then(parse<DocumentSummary[]>);
  },

  document(id: string): Promise<DocumentDetail> {
    return fetch(`${BASE}/documents/${id}`).then(parse<DocumentDetail>);
  },

  ingest(file: File, understand: boolean): Promise<DocumentDetail> {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/ingest?understand=${understand}`, {
      method: "POST",
      body: form,
      signal: withTimeout(1000 * 60 * 20),
    }).then(parse<DocumentDetail>);
  },

  ask(question: string, docIds: string[]): Promise<AskResponse> {
    return fetch(`${BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, doc_ids: docIds }),
      signal: withTimeout(1000 * 60 * 5),
    }).then(parse<AskResponse>);
  },

  remove(id: string): Promise<{ deleted: string }> {
    return fetch(`${BASE}/documents/${id}`, { method: "DELETE" }).then(parse<{ deleted: string }>);
  },

  reset(): Promise<{ status: string }> {
    return fetch(`${BASE}/reset`, { method: "POST" }).then(parse<{ status: string }>);
  },

  figureUrl(docId: string, figureId: string): string {
    return `${BASE}/documents/${docId}/figures/${figureId}`;
  },

  reportUrl(docId: string, format: "md" | "json"): string {
    return `${BASE}/documents/${docId}/report?format=${format}`;
  },
};
