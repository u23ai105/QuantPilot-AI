import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { visit } from "unist-util-visit";

import { cn } from "@/lib/utils";

/**
 * Canonical citation format emitted inline by the RAG agent:
 *   [Source: <filename>, Page: <n>]
 *
 * This remark plugin splits any matching text node into a custom `citation`
 * mdast node whose `hName` routes it to the `cite-chip` entry in the
 * components map below, so citations render as a styled inline badge instead
 * of raw bracketed text. Matching at the mdast level (rather than regexing the
 * final string) keeps it robust across paragraph / formatting boundaries.
 */
const CITATION_RE = /\[Source:\s*([^,\]]+),\s*Page:\s*(\d+)\]/g;

function remarkCitations() {
  return (tree: unknown) => {
    // `visit` is loosely typed here to avoid pulling in @types/mdast just for
    // this one plugin; the node shape we touch (`value`, `children`) is stable.
    visit(tree as never, "text", (node: any, index: number | undefined, parent: any) => {
      if (!parent || index === undefined) return;
      const value: string = node.value;
      CITATION_RE.lastIndex = 0;
      if (!CITATION_RE.test(value)) return;

      CITATION_RE.lastIndex = 0;
      const replacement: any[] = [];
      let last = 0;
      let match: RegExpExecArray | null;
      while ((match = CITATION_RE.exec(value)) !== null) {
        if (match.index > last) {
          replacement.push({ type: "text", value: value.slice(last, match.index) });
        }
        const filename = match[1].trim();
        const page = match[2];
        replacement.push({
          type: "citation",
          data: { hName: "cite-chip", hProperties: { "data-filename": filename, "data-page": page } },
          children: [{ type: "text", value: `${filename} · p.${page}` }],
        });
        last = match.index + match[0].length;
      }
      if (last < value.length) {
        replacement.push({ type: "text", value: value.slice(last) });
      }
      parent.children.splice(index, 1, ...replacement);
      return index + replacement.length; // continue past the inserted nodes
    });
  };
}

// Element renderers styled with the app's existing CSS-variable tokens so the
// output matches the dark-first theme without relying on @tailwindcss/typography.
// `node` is intentionally not destructured/spread onto DOM elements (avoids
// React's "unknown prop" warning and the noUnusedLocals rule).
const markdownComponents = {
  h1: ({ children }: any) => <h1 className="mt-3 text-base font-semibold text-foreground first:mt-0">{children}</h1>,
  h2: ({ children }: any) => <h2 className="mt-3 text-base font-semibold text-foreground first:mt-0">{children}</h2>,
  h3: ({ children }: any) => <h3 className="mt-3 text-sm font-semibold text-foreground first:mt-0">{children}</h3>,
  h4: ({ children }: any) => <h4 className="mt-2 text-sm font-semibold text-foreground first:mt-0">{children}</h4>,
  p: ({ children }: any) => <p className="leading-relaxed text-foreground">{children}</p>,
  ul: ({ children }: any) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }: any) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }: any) => <li className="leading-relaxed text-foreground">{children}</li>,
  strong: ({ children }: any) => <strong className="font-semibold text-foreground">{children}</strong>,
  em: ({ children }: any) => <em className="italic">{children}</em>,
  a: ({ href, children }: any) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-ai underline underline-offset-2 hover:text-ai/80">
      {children}
    </a>
  ),
  blockquote: ({ children }: any) => (
    <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">{children}</blockquote>
  ),
  hr: () => <hr className="border-border/50" />,
  code: ({ className, children }: any) => {
    const isBlock = /language-/.test(className || "");
    return isBlock ? (
      <code className={cn("font-mono", className)}>{children}</code>
    ) : (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{children}</code>
    );
  },
  pre: ({ children }: any) => <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">{children}</pre>,
  table: ({ children }: any) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }: any) => <th className="border border-border/50 px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }: any) => <td className="border border-border/50 px-2 py-1">{children}</td>,
  // Custom node produced by remarkCitations
  "cite-chip": ({ children }: any) => (
    <span className="inline-flex items-center rounded bg-ai/10 px-1.5 py-0.5 align-baseline text-xs font-medium text-ai">
      {children}
    </span>
  ),
};

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="space-y-2 text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkCitations]} components={markdownComponents as Components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
