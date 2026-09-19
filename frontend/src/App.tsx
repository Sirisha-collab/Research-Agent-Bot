import { useCallback, useEffect, useState } from "react";
import { Download, FileJson, FileText, X } from "lucide-react";
import { api } from "./api";
import type { ChatTurn, DocumentDetail, DocumentSummary, Health } from "./types";
import { StatusBar } from "./components/StatusBar";
import { UploadPanel } from "./components/UploadPanel";
import { Library } from "./components/Library";
import { Tabs } from "./components/Tabs";
import { Markdown } from "./components/Markdown";
import { FindingsView, TablesView } from "./components/FindingsView";
import { FiguresView } from "./components/FiguresView";
import { StructureView } from "./components/StructureView";
import { AskPanel } from "./components/AskPanel";

const PHASES = ["uploading", "extracting text", "reading tables", "embedding", "summarising"];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [active, setActive] = useState<DocumentDetail | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState(PHASES[0]);
  const [notice, setNotice] = useState<string | null>(null);
  const [tab, setTab] = useState("explanation");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [asking, setAsking] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [h, d] = await Promise.all([api.health(), api.documents()]);
      setHealth(h);
      setDocs(d);
      setHealthError(null);
    } catch {
      setHealthError(
        `Backend unreachable at ${api.base}. Start it with: uvicorn backend.main:app --port 8000`,
      );
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!busy) {
      setPhase(PHASES[0]);
      return;
    }
    let i = 0;
    const timer = setInterval(() => {
      i = Math.min(i + 1, PHASES.length - 1);
      setPhase(PHASES[i]);
    }, 6000);
    return () => clearInterval(timer);
  }, [busy]);

  async function handleUpload(file: File, understand: boolean) {
    setBusy(true);
    setPhase(PHASES[0]);
    setNotice(null);
    try {
      const doc = await api.ingest(file, understand);
      setActive(doc);
      setTurns([]);
      setTab(doc.explanation ? "explanation" : "structure");
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function openDoc(id: string) {
    try {
      const doc = await api.document(id);
      setActive(doc);
      setTurns([]);
      setTab(doc.explanation ? "explanation" : "structure");
      setNotice(null);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleAsk(question: string) {
    setAsking(true);
    setTurns((prev) => [...prev, { role: "user", content: question }]);
    try {
      const res = await api.ask(question, selected);
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          rounds: res.retrieval_rounds,
        },
      ]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: err instanceof Error ? err.message : String(err) },
      ]);
    } finally {
      setAsking(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.remove(id);
      if (active?.doc_id === id) setActive(null);
      setSelected((prev) => prev.filter((x) => x !== id));
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleReset() {
    try {
      await api.reset();
      setActive(null);
      setSelected([]);
      setTurns([]);
      await refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : String(err));
    }
  }

  const tabs = [
    {
      id: "explanation",
      label: "explanation",
      content: active?.explanation ? (
        <Markdown>{active.explanation}</Markdown>
      ) : (
        <p className="text-sm text-muted">No explanation produced.</p>
      ),
    },
    {
      id: "findings",
      label: "findings",
      badge: active?.findings?.findings?.length ?? 0,
      content: <FindingsView findings={active?.findings ?? {}} />,
    },
    {
      id: "tables",
      label: "tables",
      badge: active?.tables?.length ?? 0,
      content: <TablesView tables={active?.tables ?? []} />,
    },
    {
      id: "figures",
      label: "figures",
      badge: active?.figures?.length ?? 0,
      content: <FiguresView docId={active?.doc_id ?? ""} figures={active?.figures ?? []} />,
    },
    {
      id: "structure",
      label: "structure",
      content: <StructureView sections={active?.sections ?? []} />,
    },
    {
      id: "ask",
      label: "ask",
      content: (
        <AskTab
          turns={turns}
          asking={asking}
          suggestions={active?.followups ?? []}
          onAsk={handleAsk}
          onReset={() => setTurns([])}
          enabled={docs.length > 0}
        />
      ),
    },
  ];

  const stats = active
    ? [
        `${active.page_count} pages`,
        `${active.n_chunks} chunks`,
        `${active.tables?.length ?? 0} tables`,
        `${active.figures?.length ?? 0} figures`,
        active.elapsed_s ? `${active.elapsed_s}s` : null,
      ].filter((x): x is string => Boolean(x))
    : [];

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <header className="relative pb-4">
        <h1 className="text-4xl font-bold tracking-tight text-balance">Research-Assistant-Bot</h1>
        <p className="kicker mt-1.5 text-muted">read the paper · ask the paper</p>
        <div className="mt-4 h-0.5 w-full bg-gradient-to-r from-ink via-ink/30 to-transparent" />
      </header>

      <StatusBar health={health} error={healthError} />

      {notice && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-warn/40 bg-warn/5 px-4 py-3 text-sm text-warn shadow-sm">
          <p className="min-w-0 flex-1 break-words">{notice}</p>
          <button
            type="button"
            aria-label="close"
            onClick={() => setNotice(null)}
            className="-m-1 shrink-0 rounded p-1 opacity-60 transition hover:bg-warn/10 hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="mt-5 grid items-start gap-6 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-5 lg:sticky lg:top-8">
          <UploadPanel onSubmit={handleUpload} busy={busy} phase={phase} />
          <Library
            docs={docs}
            selected={selected}
            activeId={active?.doc_id ?? null}
            onToggle={(id) =>
              setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
            }
            onOpen={openDoc}
            onRefresh={refresh}
            onDelete={handleDelete}
            onReset={handleReset}
          />
        </div>

        <main className="min-w-0">
          {!active ? (
            <div className="rounded-xl border border-dashed border-rule bg-surface/60 px-6 py-20 text-center">
              <FileText className="mx-auto h-9 w-9 text-muted/50" strokeWidth={1.25} />
              <p className="kicker mt-4">no paper open</p>
              <p className="mx-auto mt-2 max-w-xs text-sm text-muted text-balance">
                Upload a PDF, or pick one from the library on the left.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <section className="overflow-hidden rounded-xl border border-rule bg-surface shadow-sm">
                <div className="border-l-2 border-accent p-5 sm:p-6">
                  <h2 className="text-xl leading-snug font-semibold text-balance">{active.title}</h2>
                  {active.authors && (
                    <p className="mt-1.5 text-sm text-muted italic">{active.authors}</p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {stats.map((s) => (
                      <span
                        key={s}
                        className="kicker rounded-full border border-rule bg-bg/40 px-2.5 py-0.5 text-muted"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="border-t border-rule px-5 py-5 sm:px-6">
                  <h3 className="kicker mb-2.5 text-muted">summary</h3>
                  {active.summary ? (
                    <Markdown>{active.summary}</Markdown>
                  ) : (
                    <p className="text-sm text-muted">
                      No summary was produced. Either indexing ran without the explain step, or the
                      LLM calls failed — check the API terminal.
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap gap-2.5 border-t border-rule bg-bg/30 px-5 py-4 sm:px-6">
                  <a
                    href={api.reportUrl(active.doc_id, "md")}
                    className="kicker group flex items-center gap-1.5 rounded-md border border-rule bg-surface px-3 py-1.5 transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent"
                  >
                    <Download className="h-3.5 w-3.5 transition-transform group-hover:translate-y-0.5" />
                    report.md
                  </a>
                  <a
                    href={api.reportUrl(active.doc_id, "json")}
                    className="kicker group flex items-center gap-1.5 rounded-md border border-rule bg-surface px-3 py-1.5 transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent"
                  >
                    <FileJson className="h-3.5 w-3.5 transition-transform group-hover:translate-y-0.5" />
                    document.json
                  </a>
                </div>
              </section>

              <section className="rounded-xl border border-rule bg-surface p-5 shadow-sm sm:p-6">
                <Tabs tabs={tabs} active={tab} onChange={setTab} />
              </section>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function AskTab({
  turns,
  asking,
  suggestions,
  onAsk,
  onReset,
  enabled,
}: {
  turns: ChatTurn[];
  asking: boolean;
  suggestions: string[];
  onAsk: (q: string) => void;
  onReset: () => void;
  enabled: boolean;
}) {
  if (!enabled) return <p className="text-sm text-muted">Index a paper before asking questions.</p>;
  return (
    <AskPanel
      turns={turns}
      busy={asking}
      suggestions={suggestions}
      onAsk={onAsk}
      onReset={onReset}
    />
  );
}
