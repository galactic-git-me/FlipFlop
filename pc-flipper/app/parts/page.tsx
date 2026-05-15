"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback } from "react";
import { Package, RefreshCw, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { GroupedPart, PartCategory } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const CATEGORIES: { value: PartCategory | "all"; label: string }[] = [
  { value: "all", label: "All Parts" },
  { value: "ram", label: "RAM" },
  { value: "gpu", label: "GPU" },
  { value: "ssd", label: "Storage" },
  { value: "psu", label: "PSU" },
  { value: "cpu", label: "CPU" },
  { value: "accessory", label: "Accessories 🖱️" },
];

export default function PartsPage() {
  const [parts, setParts] = useState<GroupedPart[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeCategory, setActiveCategory] = useState<PartCategory | "all">("all");

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

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Package className="w-5 h-5 text-[var(--nf-primary)]" /> Marketplace
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Refurbed & used parts for flipping · {parts.length} tracked · prices updated daily
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Updating…" : "Refresh Prices"}
        </Button>
      </div>

      {/* Category filter */}
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

      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading parts…
        </div>
      ) : parts.length === 0 ? (
        <EmptyState
          icon={Package}
          title="No parts tracked yet"
          description='Click "Refresh Prices" to run the parts swarm — it scrapes eBay sold listings for median used prices on common upgrade components.'
          action={{ label: "Fetch Part Prices", onClick: refresh }}
        />
      ) : (
        <div className="space-y-2">
          {parts.map((part, i) => (
            <PartRow key={`${part.category}::${part.name}::${i}`} part={part} />
          ))}
        </div>
      )}
    </div>
  );
}

function PartRow({ part }: { part: GroupedPart }) {
  const bestPrice = part.cheapest_price ?? 0;

  return (
    <div className="flex items-start gap-4 p-4 rounded-md glass-card hover:border-[var(--nf-border-strong)] transition-colors">
      {/* Image */}
      <div className="w-12 h-12 rounded-lg bg-[#0a1119] border border-[#1e2d45] flex items-center justify-center flex-shrink-0 overflow-hidden mt-0.5">
        {part.image_url ? (
          <img src={part.image_url} alt="" className="w-full h-full object-cover opacity-70" />
        ) : (
          <Package className="w-5 h-5 text-slate-700" />
        )}
      </div>

      {/* Name + sources */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-slate-200">{part.name}</span>
          <span className="text-xs text-slate-600 capitalize">{part.category}</span>
        </div>

        {/* All source badges */}
        {part.all_sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-1">
            <span className="text-[10px] text-slate-600 uppercase tracking-wider self-center">Sources:</span>
            {part.all_sources.map((s, i) => (
              s.url ? (
                <a
                  key={i}
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#0a1119] border border-[#1e2d45] hover:border-[#1e3a5a] text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {s.source ?? "Unknown"}
                  {s.price != null && (
                    <span className="text-[#00dc82] font-semibold">{formatCurrency(s.price)}</span>
                  )}
                </a>
              ) : (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#0a1119] border border-[#1e2d45] text-[11px] text-slate-500"
                >
                  {s.source ?? "Unknown"}
                  {s.price != null && (
                    <span className="text-slate-400 font-semibold">{formatCurrency(s.price)}</span>
                  )}
                </span>
              )
            ))}
          </div>
        )}
      </div>

      {/* Price breakdown */}
      <div className="flex-shrink-0 flex items-center gap-4 text-xs">
        {part.price_new != null && (
          <div className="text-center">
            <div className="text-slate-600 uppercase tracking-wide mb-0.5">New</div>
            <div className="text-slate-400 font-semibold">{formatCurrency(part.price_new)}</div>
          </div>
        )}
        {part.price_used != null && (
          <div className="text-center">
            <div className="text-slate-600 uppercase tracking-wide mb-0.5">Used</div>
            <div className="text-yellow-400 font-semibold">{formatCurrency(part.price_used)}</div>
          </div>
        )}
        {part.price_refurb != null && (
          <div className="text-center">
            <div className="text-slate-600 uppercase tracking-wide mb-0.5">Refurb</div>
            <div className="text-blue-400 font-semibold">{formatCurrency(part.price_refurb)}</div>
          </div>
        )}
        {/* Best Price — always shown */}
        <div className="text-center">
          <div className="text-slate-600 uppercase tracking-wide mb-0.5">Best Price</div>
          <div className="text-[#00dc82] font-bold text-sm">{formatCurrency(bestPrice)}</div>
        </div>
      </div>

      {/* Primary source + date */}
      <div className="flex-shrink-0">
        {part.cheapest_source && (
          <SourceBadge sourceName={part.cheapest_source} url={part.cheapest_url ?? undefined} />
        )}
        {part.last_price_update && (
          <p className="text-[10px] text-slate-600 mt-1 text-right">
            {new Date(part.last_price_update).toLocaleDateString("en-GB")}
          </p>
        )}
      </div>

      {/* Link button */}
      {part.cheapest_url && (
        <a href={part.cheapest_url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
          <Button variant="outline" size="sm">
            <ExternalLink className="w-3.5 h-3.5" /> View
          </Button>
        </a>
      )}
    </div>
  );
}
