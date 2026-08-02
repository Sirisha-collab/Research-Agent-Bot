import type { SectionBlock } from "../types";

export function StructureView({ sections }: { sections: SectionBlock[] }) {
  if (sections.length === 0) return <p className="text-sm text-muted">No sections parsed.</p>;
  const max = Math.max(...sections.map((s) => s.words), 1);
  return (
    <ul className="space-y-2">
      {sections.map((s, i) => (
        <li key={i} className="flex items-baseline gap-3">
          <span className="kicker w-24 shrink-0">{s.canonical}</span>
          <span className="flex-1 text-sm leading-snug">{s.title}</span>
          <span className="kicker w-12 text-right">p.{s.page_start}</span>
          <span className="w-28 shrink-0">
            <span
              className="block h-1 bg-accent"
              style={{ width: `${Math.max((s.words / max) * 100, 3)}%` }}
            />
          </span>
          <span className="kicker w-12 text-right">{s.words}w</span>
        </li>
      ))}
    </ul>
  );
}
