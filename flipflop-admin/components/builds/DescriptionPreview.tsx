"use client";

import DOMPurify from "dompurify";

interface Props {
  html: string | null | undefined;
}

// Sanitize HTML for safe rendering, with styling support
const sanitizeHtml = (html: string) =>
  DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "h1", "h2", "h3", "h4", "h5", "h6",
      "p", "ul", "ol", "li", "blockquote",
      "strong", "b", "em", "i", "u", "a",
      "br", "hr", "span", "div", "table", "tr", "td", "th", "tbody", "thead",
    ],
    ALLOWED_ATTR: ["style", "href", "target", "rel", "class"],
  });

export function DescriptionPreview({ html }: Props) {
  if (!html) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6 text-center text-slate-400">
        No description yet. Generate a listing to create one.
      </div>
    );
  }

  return (
    <div
      className="prose prose-invert max-w-none rounded-lg border border-slate-700 bg-slate-800/50 p-6 text-slate-200"
      dangerouslySetInnerHTML={{
        __html: sanitizeHtml(html),
      }}
      style={{
        "--tw-prose-headings": "#e2e8f0",
        "--tw-prose-a": "#3b82f6",
        "--tw-prose-links": "#3b82f6",
        "--tw-prose-strong": "#f1f5f9",
        "--tw-prose-code": "#e2e8f0",
      } as React.CSSProperties}
    />
  );
}
