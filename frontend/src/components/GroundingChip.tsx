import { useState } from "react";
import { AlertTriangle, CircleDashed, ShieldCheck, ShieldQuestion } from "lucide-react";
import clsx from "clsx";
import { scoreGrounding } from "../lib/grounding";
import type { ChatTurn } from "../types";

const STYLES = {
  high: "border-accent text-accent",
  medium: "border-warn text-warn",
  low: "border-warn text-warn",
  none: "border-rule text-muted",
} as const;

export function GroundingChip({ turn }: { turn: ChatTurn }) {
  const [open, setOpen] = useState(false);
  const grounding = scoreGrounding(turn);
  const Icon =
    grounding.level === "high"
      ? ShieldCheck
      : grounding.level === "none"
        ? CircleDashed
        : grounding.level === "low"
          ? AlertTriangle
          : ShieldQuestion;

  return (
    <span className="relative inline-flex">
      <button
        onClick={() => setOpen((v) => !v)}
        title="Why this rating?"
        className={clsx(
          "kicker flex items-center gap-1.5 border px-2 py-1 transition-colors hover:opacity-80",
          STYLES[grounding.level],
        )}
      >
        <Icon className="h-3.5 w-3.5" />
        {grounding.label}
      </button>

      {open && (
        <span className="absolute top-full left-0 z-20 mt-1 block w-72 border border-rule bg-surface p-3 shadow-sm">
          <span className="kicker block">how this was judged</span>
          <ul className="mt-2 space-y-1">
            {grounding.factors.map((factor, i) => (
              <li key={i} className="border-l-2 border-rule pl-2 text-xs leading-relaxed text-muted">
                {factor}
              </li>
            ))}
          </ul>
          <span className="mt-2 block text-xs leading-relaxed text-muted">
            Based on retrieval scores and citation markers, not on whether the answer is factually
            correct. Check the passages below.
          </span>
        </span>
      )}
    </span>
  );
}
