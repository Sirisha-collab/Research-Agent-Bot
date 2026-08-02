import type { Findings } from "../types";
import { Markdown } from "./Markdown";

function List({ title, items }: { title: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-6">
      <h3 className="kicker mb-2">{title}</h3>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="border-l-2 border-rule pl-3 text-sm leading-relaxed">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FindingsView({ findings }: { findings: Findings }) {
  const items = findings.findings ?? [];
  const metrics = findings.metrics ?? [];
  const empty =
    items.length === 0 &&
    metrics.length === 0 &&
    !findings.contributions?.length &&
    !findings.methods?.length;

  if (empty) return <p className="text-sm text-muted">No findings were extracted.</p>;

  return (
    <div>
      {items.length > 0 && (
        <ol className="space-y-4">
          {items.map((f, i) => (
            <li key={i} className="border-l-2 border-accent pl-3">
              <p className="font-semibold leading-snug">
                <span className="font-mono text-xs text-accent">{String(i + 1).padStart(2, "0")}</span>{" "}
                {f.finding}
              </p>
              {f.evidence && (
                <p className="mt-1 text-sm text-muted italic leading-relaxed">{f.evidence}</p>
              )}
              {f.section && <span className="kicker">{f.section}</span>}
            </li>
          ))}
        </ol>
      )}

      {metrics.length > 0 && (
        <div className="mt-7">
          <h3 className="kicker mb-2">reported numbers</h3>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {["metric", "value", "where"].map((h) => (
                  <th
                    key={h}
                    className="kicker border border-rule bg-paper px-2 py-1.5 text-left font-normal"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i}>
                  <td className="border border-rule px-2 py-1.5">{m.name}</td>
                  <td className="border border-rule px-2 py-1.5 font-mono text-xs">{m.value}</td>
                  <td className="border border-rule px-2 py-1.5 text-muted">{m.context}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <List title="contributions" items={findings.contributions} />
      <List title="methods, data and models" items={findings.methods} />
      <List title="limitations" items={findings.limitations} />
      <List title="future work" items={findings.future_work} />
    </div>
  );
}

export function TablesView({ tables }: { tables: { page: number; markdown: string; caption: string; n_rows: number; n_cols: number; accuracy: number; flavour: string }[] }) {
  if (tables.length === 0)
    return (
      <p className="text-sm text-muted">
        No tables detected. Camelot needs Ghostscript for ruled tables — see the README.
      </p>
    );
  return (
    <div className="space-y-8">
      {tables.map((t, i) => (
        <div key={i}>
          <div className="kicker mb-1">
            page {t.page} · {t.n_rows}×{t.n_cols} · {t.flavour}
            {t.accuracy ? ` · accuracy ${t.accuracy}` : ""}
          </div>
          {t.caption && <p className="mb-2 text-sm italic text-muted">{t.caption}</p>}
          <div className="overflow-x-auto">
            <Markdown>{t.markdown}</Markdown>
          </div>
        </div>
      ))}
    </div>
  );
}
