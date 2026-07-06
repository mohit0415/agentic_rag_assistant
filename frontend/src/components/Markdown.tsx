import React from "react";
import ReactMarkdown, { Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  p: ({ children }) => <p className="my-1.5 first:mt-0 last:mb-0">{children}</p>,

  strong: ({ children }) => (
    <strong className="font-semibold text-txt-pri">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,

  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="break-words text-accent underline decoration-accent/40 underline-offset-2 transition-colors hover:decoration-accent"
    >
      {children}
    </a>
  ),

  h1: ({ children }) => (
    <h1 className="mb-1.5 mt-3 text-[15px] font-semibold tracking-tight text-txt-pri">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-1.5 mt-3 text-[14px] font-semibold tracking-tight text-txt-pri">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1 mt-2.5 text-[13px] font-semibold text-txt-pri">{children}</h3>
  ),

  ul: ({ children }) => (
    <ul className="my-1.5 list-disc space-y-1 pl-5 marker:text-accent/60">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-1.5 list-decimal space-y-1 pl-5 marker:text-accent/60">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,

  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-accent/40 pl-3 italic text-txt-sec">
      {children}
    </blockquote>
  ),

  hr: () => <hr className="my-3 border-line" />,

  code: ({ inline, className, children, ...props }: any) =>
    inline ? (
      <code
        className="rounded-md border border-line bg-ink/70 px-1.5 py-0.5 font-mono text-[11px] text-accent"
        {...props}
      >
        {children}
      </code>
    ) : (
      <code
        className={`my-2 block overflow-x-auto whitespace-pre rounded-xl border border-line bg-ink/80 p-3 font-mono text-[11.5px] leading-relaxed text-[#C9D4E3] ${className ?? ""}`}
        {...props}
      >
        {children}
      </code>
    ),
  pre: ({ children }) => <pre className="my-2">{children}</pre>,

  table: ({ children }) => (
    <div className="my-2.5 overflow-x-auto rounded-xl border border-line shadow-card">
      <table className="w-full border-collapse text-[11.5px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface/90">{children}</thead>,
  th: ({ children }) => (
    <th className="whitespace-nowrap border-b border-line px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-accent">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-line/60 px-3 py-2 align-top text-txt-sec">
      {children}
    </td>
  ),
  tr: ({ children }) => (
    <tr className="transition-colors even:bg-white/[0.02] hover:bg-white/[0.04]">{children}</tr>
  ),

  img: ({ src, alt }) => (
    <img
      src={src}
      alt={alt ?? ""}
      className="my-2 max-w-full rounded-xl border border-line"
    />
  ),
};

interface MarkdownProps {
  children: string;
}

const Markdown: React.FC<MarkdownProps> = ({ children }) => (
  <div className="markdown-body">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  </div>
);

export default React.memo(Markdown);
