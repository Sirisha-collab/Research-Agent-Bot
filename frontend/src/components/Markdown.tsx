import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

const CITE_PREFIX = "#cite-";

export function Markdown({
  children,
  className,
  onCitationClick,
}: {
  children: string;
  className?: string;
  onCitationClick?: (label: string) => void;
}) {
  const linkified = onCitationClick
    ? children.replace(/\[(S\d+)\](?!\()/g, (_m, label) => `[${label}](${CITE_PREFIX}${label})`)
    : children;

  return (
    <div className={clsx("md", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={
          onCitationClick
            ? {
                a({ href, children: inner, ...rest }) {
                  if (href && href.startsWith(CITE_PREFIX)) {
                    const label = href.slice(CITE_PREFIX.length);
                    return (
                      <button
                        type="button"
                        onClick={() => onCitationClick(label)}
                        title={`Open the page this came from (${label})`}
                        className="mx-0.5 border-b border-dotted border-accent font-mono text-[0.78em] text-accent align-baseline hover:bg-accent-soft"
                      >
                        [{label}]
                      </button>
                    );
                  }
                  return (
                    <a href={href} {...rest}>
                      {inner}
                    </a>
                  );
                },
              }
            : undefined
        }
      >
        {linkified}
      </ReactMarkdown>
    </div>
  );
}
