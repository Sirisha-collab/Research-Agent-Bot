import { useRef, useState } from "react";
import { FileUp, Loader2, Upload } from "lucide-react";
import clsx from "clsx";

export function UploadPanel({
  onSubmit,
  busy,
  phase,
}: {
  onSubmit: (file: File, understand: boolean) => void;
  busy: boolean;
  phase: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [understand, setUnderstand] = useState(true);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function take(list: FileList | null) {
    const next = list?.[0];
    if (next && next.name.toLowerCase().endsWith(".pdf")) setFile(next);
  }

  return (
    <section className="border border-rule bg-surface p-4">
      <h2 className="kicker mb-3">upload</h2>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          take(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "flex cursor-pointer flex-col items-center justify-center gap-2 border border-dashed px-4 py-7 text-center transition-colors",
          dragging ? "border-accent bg-accent-soft" : "border-rule hover:border-accent",
        )}
      >
        <FileUp className="h-5 w-5 text-muted" />
        {file ? (
          <span className="font-mono text-xs break-all text-ink">{file.name}</span>
        ) : (
          <span className="kicker">drop a pdf or click</span>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => take(e.target.files)}
        />
      </div>

      <label className="mt-3 flex cursor-pointer items-start gap-2 text-sm text-muted">
        <input
          type="checkbox"
          checked={understand}
          onChange={(e) => setUnderstand(e.target.checked)}
          className="mt-1 accent-accent"
        />
        <span>
          Explain and summarise after indexing
          <span className="block font-mono text-[0.68rem] uppercase tracking-widest">
            uncheck to index only
          </span>
        </span>
      </label>

      <button
        disabled={!file || busy}
        onClick={() => file && onSubmit(file, understand)}
        className={clsx(
          "mt-4 flex w-full items-center justify-center gap-2 border px-3 py-2 font-mono text-xs uppercase tracking-widest transition-colors",
          !file || busy
            ? "cursor-not-allowed border-rule text-muted"
            : "border-accent bg-accent text-surface hover:bg-ink hover:border-ink",
        )}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
        {busy ? phase : "read this paper"}
      </button>
    </section>
  );
}
