"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  BarChart2, RefreshCw, Search, X, ExternalLink,
  Cpu, HardDrive, Server, MemoryStick, CircuitBoard,
  Wind, Zap, MonitorSpeaker, TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

type CatId = "gpu" | "cpu" | "ram" | "motherboard" | "cooler" | "ssd" | "psu";

interface CategoryDef {
  id: CatId;
  label: string;
  icon: React.ReactNode;
}

const CATEGORIES: CategoryDef[] = [
  { id: "gpu",         label: "Graphics Card", icon: <MonitorSpeaker className="w-3.5 h-3.5" /> },
  { id: "cpu",         label: "Processor",     icon: <Cpu className="w-3.5 h-3.5" /> },
  { id: "ram",         label: "RAM",           icon: <MemoryStick className="w-3.5 h-3.5" /> },
  { id: "motherboard", label: "Motherboard",   icon: <CircuitBoard className="w-3.5 h-3.5" /> },
  { id: "cooler",      label: "Cooling",       icon: <Wind className="w-3.5 h-3.5" /> },
  { id: "ssd",         label: "Storage",       icon: <HardDrive className="w-3.5 h-3.5" /> },
  { id: "psu",         label: "Power Supply",  icon: <Zap className="w-3.5 h-3.5" /> },
];

const CAT_BADGE: Record<string, string> = {
  gpu: "GPU", cpu: "CPU", ram: "RAM",
  motherboard: "Mobo", cooler: "Cooling", ssd: "Storage", psu: "PSU",
};

interface GroupedPart {
  name: string;
  category: string;
  image_url: string | null;
  cheapest_price: number | null;
  cheapest_source: string;
  price_used: number | null;
  price_new: number | null;
  last_price_update: string | null;
  all_sources: Array<{
    source: string;
    price: number | null;
    url: string | null;
    condition: string;
  }>;
  gem_classification: string | null;
}

export default function CataloguePage() {
  const [activeCat, setActiveCat] = useState<CatId>("gpu");
  const [parts, setParts] = useState<GroupedPart[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const load = useCallback(async (cat: CatId) => {
    setLoading(true);
    try {
      const data = await api.parts.grouped(cat);
      setParts(data as GroupedPart[]);
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(activeCat);
  }, [activeCat, load]);

  const displayed = useMemo(() => {
    let list = parts;
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q));
    }
    return list.sort((a, b) => a.name.localeCompare(b.name));
  }, [parts, query]);

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-[var(--nf-primary)]" /> Component Catalogue
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Real market prices from cached sources — no rate limiting
          </p>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 border-b border-[#1e2d45] pb-0">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveCat(cat.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-all -mb-px ${
              activeCat === cat.id
                ? "border-[#00dc82] text-[#00dc82]"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      {/* Search toolbar */}
      <div className="flex gap-2 items-center flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search components…"
            className="w-full pl-10 pr-8 py-2.5 bg-[#0d1320] border border-[#1e2d45] rounded-xl text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50 transition-colors"
          />
          {query && (
            <button onClick={() => setQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Summary strip */}
      {!loading && displayed.length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs font-mono">
          <span className="px-3 py-1.5 rounded-lg bg-[#0a1119] border border-[#1e2d45] text-slate-400">
            <span className="text-slate-600">Showing </span>
            <span className="text-slate-200 font-bold">{displayed.length}</span>
            <span className="text-slate-600"> components</span>
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-[#00dc82]/8 border border-[#00dc82]/20 text-[#00dc82]">
            <span className="text-slate-500">Both prices </span>
            <span className="font-bold">{displayed.filter(p => p.price_used && p.price_new).length}</span>
          </span>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading catalogue…
        </div>
      ) : displayed.length === 0 ? (
        <EmptyState
          icon={BarChart2}
          title={query ? "No components match your search" : "No data available"}
          description={query ? `No results for "${query}".` : "No data available yet."}
          action={query ? { label: "Clear search", onClick: () => setQuery("") } : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {displayed.map((part, i) => (
            <ComponentCard key={`${part.name}::${i}`} part={part} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Card Component ────────────────────────────────────────────────────────────

function ComponentCard({ part }: { part: GroupedPart }) {
  const used = part.price_used;
  const newP = part.price_new;
  const spread = newP != null && used != null ? newP - used : null;

  const spreadColor = spread == null ? "text-slate-400"
    : spread > 50  ? "text-[#00b8ff]"
    : spread > 0   ? "text-slate-300"
    : spread === 0 ? "text-slate-400"
    : "text-amber-400";

  const SpreadIcon = spread == null || spread === 0 ? Minus
    : spread > 0 ? TrendingUp : TrendingDown;

  const usedSrc = part.all_sources.find(s => s.condition === "used" && s.price != null);
  const newSrc  = part.all_sources.find(s => s.condition === "new"  && s.price != null);

  return (
    <div className="relative rounded-xl border border-[#1e2d45] overflow-hidden hover:border-[#2a3f5a] transition-colors h-56 flex flex-col group">

      {/* Full-card background image */}
      {part.image_url ? (
        <img
          src={part.image_url}
          alt={part.name}
          className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
      ) : (
        <div className="absolute inset-0 bg-[#080f1a]" />
      )}

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/60 to-black/25" />

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full p-3">

        {/* Top row: category badge + spread */}
        <div className="flex items-center justify-between gap-2">
          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-black/60 backdrop-blur-sm border border-white/15 text-white uppercase tracking-wide">
            {CAT_BADGE[part.category] ?? part.category}
          </span>
          <div className={`flex items-center gap-1 ${spreadColor} bg-black/60 backdrop-blur-sm rounded px-1.5 py-0.5`}>
            <SpreadIcon className="w-2.5 h-2.5 flex-shrink-0" />
            {spread != null ? (
              <span className="text-[10px] font-semibold font-mono">
                {spread > 0 ? "+" : ""}{formatCurrency(spread)}
              </span>
            ) : (
              <span className="text-[10px]">—</span>
            )}
          </div>
        </div>

        {/* Bottom: name + prices */}
        <div className="mt-auto">
          <p className="text-sm font-semibold text-white leading-snug line-clamp-2 mb-2.5 drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">
            {part.name}
          </p>

          {/* Prices row */}
          <div className="flex items-end justify-between gap-2">
            <div>
              <div className="text-[9px] font-semibold uppercase tracking-wider text-amber-400/80 mb-0.5">Used</div>
              {used != null ? (
                <>
                  <div className="text-amber-400 font-black text-lg font-mono leading-none drop-shadow-[0_1px_4px_rgba(0,0,0,1)]">{formatCurrency(used)}</div>
                  {usedSrc?.source && <div className="text-[9px] text-white/40 mt-0.5">{usedSrc.source}</div>}
                </>
              ) : (
                <div className="text-white/30 text-base font-mono">—</div>
              )}
            </div>
            <div className="text-right">
              <div className="text-[9px] font-semibold uppercase tracking-wider text-[#00b8ff]/80 mb-0.5">New</div>
              {newP != null ? (
                <>
                  <div className="text-[#00b8ff] font-black text-lg font-mono leading-none drop-shadow-[0_1px_4px_rgba(0,0,0,1)]">{formatCurrency(newP)}</div>
                  {newSrc?.source && <div className="text-[9px] text-white/40 mt-0.5 text-right">{newSrc.source}</div>}
                </>
              ) : (
                <div className="text-white/30 text-base font-mono">—</div>
              )}
            </div>
          </div>

          {/* Source chips */}
          <div className="flex flex-wrap gap-1 mt-2">
            {part.all_sources.slice(0, 3).map((s, i) => {
              const chip = (
                <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[8px] border backdrop-blur-sm ${
                  s.condition === "new"
                    ? "bg-[#00b8ff]/10 border-[#00b8ff]/20 text-[#00b8ff]/80"
                    : "bg-amber-500/10 border-amber-500/20 text-amber-400/80"
                }`}>
                  {s.source?.split(" ")[0]}
                  {s.url && <ExternalLink className="w-2 h-2 opacity-60 ml-0.5" />}
                </span>
              );
              return s.url ? (
                <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                   className="hover:opacity-100 opacity-80 transition-opacity">
                  {chip}
                </a>
              ) : <span key={i}>{chip}</span>;
            })}
            {part.all_sources.length > 3 && (
              <span className="px-1.5 py-0.5 rounded border border-white/10 bg-black/40 text-[8px] text-white/40">
                +{part.all_sources.length - 3}
              </span>
            )}
            {part.last_price_update && (
              <span className="ml-auto text-[8px] text-white/30">
                {formatRelativeTime(new Date(part.last_price_update))}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
