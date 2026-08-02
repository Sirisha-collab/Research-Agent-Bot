import { useCallback, useEffect, useState } from "react";
import { Download, FileJson } from "lucide-react";
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
    if (!busy) return;
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
    await api.remove(id);
    if (active?.doc_id === id) setActive(null);
    setSelected((prev) => prev.filter((x) => x !== id));
    await refresh();
  }

  async function handleReset() {
    await api.reset();
    setActive(null);
    setSelected([]);
    setTurns([]);
    await refresh();
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

  return (
    <div className="mx-auto max-w-6xl px-5 py-8">
      <header className="border-b-2 border-ink pb-2">
        <h1 className="text-3xl font-bold tracking-tight">Research-Assistant-Bot</h1>
        <p className="kicker mt-1">read the paper · ask the paper</p>
      </header>

      <StatusBar health={health} error={healthError} />

      {notice && (
        <div className="mb-4 border border-warn/40 bg-warn/5 px-3 py-2 text-sm text-warn">
          {notice}
        </div>
      )}

      <div className="mt-4 grid gap-6 lg:grid-cols-[20rem_1fr]">
        <div className="space-y-5">
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
            <div className="border border-rule bg-surface px-6 py-16 text-center">
              <p className="kicker">no paper open</p>
              <p className="mt-2 text-muted">
                Upload a PDF, or pick one from the library on the left.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <section className="border border-rule bg-surface p-5">
                <h2 className="text-xl leading-snug font-semibold">{active.title}</h2>
                {active.authors && <p className="mt-1 text-sm text-muted italic">{active.authors}</p>}
                <div className="kicker mt-2 flex flex-wrap gap-x-3 gap-y-1">
                  <span>{active.page_count} pages</span>
                  <span>{active.n_chunks} chunks</span>
                  <span>{active.tables?.length ?? 0} tables</span>
                  <span>{active.figures?.length ?? 0} figures</span>
                  {active.elapsed_s ? <span>{active.elapsed_s}s</span> : null}
                </div>

                <div className="mt-4 border-t border-rule pt-4">
                  <h3 className="kicker mb-2">summary</h3>
                  {active.summary ? (
                    <Markdown>{active.summary}</Markdown>
                  ) : (
                    <p className="text-sm text-muted">
                      No summary was produced. Either indexing ran without the explain step, or the
                      LLM calls failed — check the API terminal.
                    </p>
                  )}
                </div>

                <div className="mt-4 flex flex-wrap gap-3 border-t border-rule pt-4">
                  <a
                    href={api.reportUrl(active.doc_id, "md")}
                    className="kicker flex items-center gap-1.5 border border-rule px-2.5 py-1.5 hover:border-accent hover:text-accent"
                  >
                    <Download className="h-3.5 w-3.5" />
                    report.md
                  </a>
                  <a
                    href={api.reportUrl(active.doc_id, "json")}
                    className="kicker flex items-center gap-1.5 border border-rule px-2.5 py-1.5 hover:border-accent hover:text-accent"
                  >
                    <FileJson className="h-3.5 w-3.5" />
                    document.json
                  </a>
                </div>
              </section>

              <section className="border border-rule bg-surface p-5">
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
