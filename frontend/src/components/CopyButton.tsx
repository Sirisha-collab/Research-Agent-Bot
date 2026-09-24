import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import clsx from "clsx";

async function writeClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    void 0;
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch {
    return false;
  }
}

export function CopyButton({
  text,
  label = "copy",
  className,
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");

  useEffect(() => {
    if (state === "idle") return;
    const timer = setTimeout(() => setState("idle"), 1800);
    return () => clearTimeout(timer);
  }, [state]);

  async function handleClick() {
    setState((await writeClipboard(text)) ? "done" : "failed");
  }

  return (
    <button
      onClick={handleClick}
      disabled={!text}
      title={state === "failed" ? "Copy failed — select the text manually" : "Copy to clipboard"}
      className={clsx(
        "kicker flex items-center gap-1.5 border px-2 py-1 transition-colors",
        state === "done"
          ? "border-accent text-accent"
          : state === "failed"
            ? "border-warn text-warn"
            : "border-rule text-muted hover:border-accent hover:text-accent",
        !text && "cursor-not-allowed opacity-40",
        className,
      )}
    >
      {state === "done" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {state === "done" ? "copied" : state === "failed" ? "copy failed" : label}
    </button>
  );
}
