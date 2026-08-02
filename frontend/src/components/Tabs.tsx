import clsx from "clsx";
import type { ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
  badge?: number;
  content: ReactNode;
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (id: string) => void;
}) {
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 border-b border-rule">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={clsx(
              "kicker -mb-px border-b-2 px-0.5 pb-2 pt-1 transition-colors",
              tab.id === current.id
                ? "border-accent text-ink"
                : "border-transparent hover:text-ink",
            )}
          >
            {tab.label}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="ml-1.5 text-accent">{tab.badge}</span>
            )}
          </button>
        ))}
      </div>
      <div className="pt-5">{current.content}</div>
    </div>
  );
}
