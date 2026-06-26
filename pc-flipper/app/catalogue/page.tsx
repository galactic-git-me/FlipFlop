"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  Cpu, HardDrive, Server, MemoryStick, CircuitBoard,
  Wind, Zap, MonitorSpeaker, Search, X, RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

type CatId = "gpu" | "cpu" | "ram" | "ssd" | "psu" | "motherboard" | "cooler";

const CATEGORIES: { id: CatId; label: string; icon: React.ReactNode }[] = [
  { id: "gpu",         label: "Graphics Card", icon: <MonitorSpeaker className="w-4 h-4" /> },
  { id: "cpu",         label: "Processor",     icon: <Cpu className="w-4 h-4" /> },
  { id: "ram",         label: "RAM",           icon: <MemoryStick className="w-4 h-4" /> },
  { id: "motherboard", label: "Motherboard",   icon: <CircuitBoard className="w-4 h-4" /> },
  { id: "cooler",      label: "Cooling",       icon: <Wind className="w-4 h-4" /> },
  { id: "ssd",         label: "Storage",       icon: <HardDrive className="w-4 h-4" /> },
  { id: "psu",         label: "Power Supply",  icon: <Zap className="w-4 h-4" /> },
];

interface CataloguePart {
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
  const [activeCategory, setActiveCategory] = useState<CatId>("gpu");
  const [parts, setParts] = useState<CataloguePart[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  const load = useCallback(async (cat: CatId) => {
    setLoading(true);
    try {
      const data = await api.parts.grouped(cat);
      setParts(data as CataloguePart[]);
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(activeCategory);
  }, [activeCategory, load]);

  const filtered = useMemo(() => {
    if (!query.trim()) return parts;
    const q = query.toLowerCase();
    return parts.filter(p => p.name.toLowerCase().includes(q));
  }, [parts, query]);

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            📦 Component Catalogue
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Real market prices from cached sources — no rate limiting
          </p>
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 border-b border-[#1e2d45] pb-4">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => { setActiveCategory(cat.id); setQuery(""); }}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border transition-all ${
              activeCategory === cat.id
                ? "bg-[#00b8ff]/10 text-[#00b8ff] border-[#00b8ff]/30"
                : "text-slate-500 border-[#1e2d45] hover:border-slate-600 hover:text-slate-300"
            }`}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
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

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading catalogue…
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title={query ? "No components match" : "No data available"}
          description={query ? `No results for "${query}"` : `No ${activeCategory} components in catalogue yet.`}
          action={query ? { label: "Clear search", onClick: () => setQuery("") } : undefined}
        />
      ) : (
        <div className="space-y-3">
          {filtered.map(part => (
            <div key={part.name} className="border border-[#1e2d45] rounded-lg p-4 hover:border-[#2a3f5a] transition-colors">
              <div className="flex gap-4">
                {/* Image */}
                {part.image_url && (
                  <img
                    src={part.image_url}
                    alt={part.name}
                    className="w-20 h-20 object-cover rounded"
                  />
                )}

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-slate-200 truncate">{part.name}</h3>

                  {/* Prices */}
                  <div className="flex gap-6 mt-2 flex-wrap text-sm">
                    {part.price_used !== null && (
                      <div>
                        <span className="text-slate-500">Used (eBay):</span>
                        <span className="text-amber-400 font-semibold ml-1">{formatCurrency(part.price_used)}</span>
                      </div>
                    )}
                    {part.price_new !== null && (
                      <div>
                        <span className="text-slate-500">New:</span>
                        <span className="text-[#00b8ff] font-semibold ml-1">{formatCurrency(part.price_new)}</span>
                      </div>
                    )}
                    {part.cheapest_price !== null && (
                      <div>
                        <span className="text-slate-500">Cheapest:</span>
                        <span className="text-[#00dc82] font-semibold ml-1">{formatCurrency(part.cheapest_price)} ({part.cheapest_source})</span>
                      </div>
                    )}
                  </div>

                  {/* Gem badge */}
                  {part.gem_classification && (
                    <div className="mt-2">
                      <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                        part.gem_classification === "super_gem"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-emerald-500/20 text-emerald-400"
                      }`}>
                        ✨ {part.gem_classification === "super_gem" ? "Super Gem" : "Gem"}
                      </span>
                    </div>
                  )}

                  {/* Last update */}
                  {part.last_price_update && (
                    <div className="text-xs text-slate-600 mt-2">
                      Updated {formatRelativeTime(new Date(part.last_price_update))}
                    </div>
                  )}

                  {/* Sources */}
                  {part.all_sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {part.all_sources.slice(0, 5).map((s, i) => (
                        <a
                          key={i}
                          href={s.url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs px-2 py-1 rounded bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 transition-colors"
                        >
                          {s.source} {s.price ? `£${s.price}` : ""}
                        </a>
                      ))}
                      {part.all_sources.length > 5 && (
                        <span className="text-xs px-2 py-1 text-slate-500">+{part.all_sources.length - 5} more</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
