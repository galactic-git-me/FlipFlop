import { ExternalLink } from "lucide-react";
import { SOURCE_FAVICON } from "@/lib/types";

interface Props {
  sourceName: string;
  url?: string | null;
  className?: string;
}

export function SourceBadge({ sourceName, url, className }: Props) {
  const favicon = SOURCE_FAVICON[sourceName];
  const inner = (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[#0a1119] border border-[#1e2d45] text-xs text-slate-400 font-medium hover:border-[#00dc82]/40 hover:text-slate-300 transition-colors ${className ?? ""}`}>
      {favicon && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={favicon} alt="" className="w-3 h-3 rounded-sm" onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
      )}
      {sourceName}
      {url && <ExternalLink className="w-2.5 h-2.5 opacity-60" />}
    </span>
  );

  if (url) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
        {inner}
      </a>
    );
  }
  return inner;
}
