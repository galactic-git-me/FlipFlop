"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback, useMemo } from "react";
import { Package, RefreshCw, ExternalLink, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { GroupedPart, PartCategory } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const CATEGORIES: { value: PartCategory | "all"; label: string }[] = [
  { value: "all",       label: "All Parts"       },
  { value: "cpu",       label: "CPU"             },
  { value: "gpu",       label: "GPU"             },
  { value: "ram",       label: "RAM"             },
  { value: "ssd",       label: "Storage"         },
  { value: "psu",       label: "PSU"             },
  { value: "accessory", label: "Accessories 🖱️"  },
];

export default function PartsPage() {
  const [parts, setParts]               = useState<GroupedPart[]>([]);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const [activeCategory, setActiveCategory] = useState<PartCategory | "all">("all");
  const [query, setQuery]               = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = activeCategory !== "all" ? activeCategory : undefined;
      const data = await api.parts.grouped(params) as GroupedPart[];
      setParts(data);
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, [activeCategory]);

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      if (activeCategory === "accessory") {
        await api.swarms.trigger("accessories");
      } else {
        await api.swarms.trigger("upgrade_parts");
      }
      await load();
    } catch { } finally { setRefreshing(false); }
  };

  // Fuzzy search — case-insensitive substring match on name
  const filtered = useMemo(() => {
    if (!query.trim()) return parts;
    const q = query.toLowerCase();
    return parts.filter(p => p.name.toLowerCase().includes(q));
  }, [parts, query]);

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Package className="w-5 h-5 text-[var(--nf-primary)]" /> Marketplace
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Refurbed &amp; used parts for flipping · {filtered.length}{query ? ` of ${parts.length}` : ""} tracked · prices updated daily
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Updating…" : "Refresh Prices"}
        </Button>
      </div>

      {/* Search + category filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Fuzzy search */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search parts…"
            className="w-full pl-9 pr-8 py-2 rounded-lg bg-[#0a1119] border border-[#1e2d45] text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-[#00dc82]/40 focus:ring-1 focus:ring-[#00dc82]/20 transition-colors"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Category tabs */}
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map(cat => (
            <button
              key={cat.value}
              onClick={() => setActiveCategory(cat.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                activeCategory === cat.value
                  ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                  : "text-slate-500 border-[#1e2d45] hover:border-slate-600 hover:text-slate-400"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading parts…
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Package}
          title={query ? "No parts match your search" : "No parts tracked yet"}
          description={
            query
              ? `No parts found for "${query}". Try a different search term.`
              : 'Click "Refresh Prices" to run the parts swarm — it scrapes eBay sold listings for median used prices on common upgrade components.'
          }
          action={query ? { label: "Clear Search", onClick: () => setQuery("") } : { label: "Fetch Part Prices", onClick: refresh }}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((part, i) => (
            <PartCard key={`${part.category}::${part.name}::${i}`} part={part} />
          ))}
        </div>
      )}
    </div>
  );
}

function PartCard({ part }: { part: GroupedPart }) {
  const bestPrice = part.cheapest_price ?? 0;

  return (
    <div className="flex flex-col rounded-xl glass-card hover:border-[var(--nf-border-strong)] transition-colors overflow-hidden">
      {/* Image */}
      <div className="w-full h-36 bg-[#070d14] border-b border-[#1e2d45] flex items-center justify-center overflow-hidden">
        {part.image_url ? (
          <img src={part.image_url} alt={part.name} className="w-full h-full object-cover opacity-80" />
        ) : (
          <Package className="w-10 h-10 text-slate-700" />
        )}
      </div>

      {/* Body */}
      <div className="flex flex-col flex-1 p-3 gap-2">
        {/* Name + category */}
        <div>
          <p className="text-sm font-semibold text-slate-100 leading-snug line-clamp-2">{part.name}</p>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider mt-0.5">{part.category}</p>
        </div>

        {/* Price breakdown */}
        <div className="grid grid-cols-2 gap-1.5 text-xs">
          {part.price_new != null && (
            <div className="rounded-md bg-black/20 border border-white/5 px-2 py-1">
              <div className="text-slate-600 text-[9px] uppercase tracking-wide">New</div>
              <div className="text-slate-400 font-semibold">{formatCurrency(part.price_new)}</div>
            </div>
          )}
          {part.price_used != null && (
            <div className="rounded-md bg-black/20 border border-white/5 px-2 py-1">
              <div className="text-slate-600 text-[9px] uppercase tracking-wide">Used</div>
              <div className="text-yellow-400 font-semibold">{formatCurrency(part.price_used)}</div>
            </div>
          )}
          {part.price_refurb != null && (
            <div className="rounded-md bg-black/20 border border-white/5 px-2 py-1">
              <div className="text-slate-600 text-[9px] uppercase tracking-wide">Refurb</div>
              <div className="text-blue-400 font-semibold">{formatCurrency(part.price_refurb)}</div>
            </div>
          )}
          <div className="rounded-md bg-[#00dc82]/5 border border-[#00dc82]/20 px-2 py-1">
            <div className="text-slate-600 text-[9px] uppercase tracking-wide">Best</div>
            <div className="text-[#00dc82] font-bold">{formatCurrency(bestPrice)}</div>
          </div>
        </div>

        {/* Sources */}
        {part.all_sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-1">
            {part.all_sources.slice(0, 4).map((s, i) =>
              s.url ? (
                <a
                  key={i}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#0a1119] border border-[#1e2d45] hover:border-[#1e3a5a] text-[10px] text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {s.source}
                  {s.price != null && <span className="text-[#00dc82]">{formatCurrency(s.price)}</span>}
                </a>
              ) : (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#0a1119] border border-[#1e2d45] text-[10px] text-slate-500"
                >
                  {s.source}
                  {s.price != null && <span className="text-slate-400">{formatCurrency(s.price)}</span>}
                </span>
              )
            )}
          </div>
        )}

        {/* Footer: source badge + link */}
        <div className="flex items-center justify-between mt-1 pt-2 border-t border-white/[0.04]">
          <div className="flex flex-col gap-0.5">
            {part.cheapest_source && (
              <SourceBadge sourceName={part.cheapest_source} url={part.cheapest_url ?? undefined} />
            )}
            {part.last_price_update && (
              <p className="text-[9px] text-slate-700">
                {new Date(part.last_price_update).toLocaleDateString("en-GB")}
              </p>
            )}
          </div>
          {part.cheapest_url && (
            <a href={part.cheapest_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm">
                <ExternalLink className="w-3 h-3" /> View
              </Button>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
