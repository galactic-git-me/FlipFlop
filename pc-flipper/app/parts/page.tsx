"use client";

import { useEffect, useState } from "react";
import { Package, RefreshCw, ExternalLink, TrendingDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { Part, PartCategory } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const CATEGORIES: { value: PartCategory | "all"; label: string }[] = [
  { value: "all", label: "All Parts" },
  { value: "ram", label: "RAM" },
  { value: "gpu", label: "GPU" },
  { value: "ssd", label: "Storage" },
  { value: "psu", label: "PSU" },
  { value: "cpu", label: "CPU" },
];

const CONDITION_COLORS = {
  new: "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/25",
  used: "bg-yellow-400/10 text-yellow-400 border-yellow-400/25",
  refurb: "bg-blue-400/10 text-blue-400 border-blue-400/25",
};

export default function PartsPage() {
  const [parts, setParts] = useState<Part[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeCategory, setActiveCategory] = useState<PartCategory | "all">("all");

  const load = async () => {
    setLoading(true);
    try {
      const params = activeCategory !== "all" ? activeCategory : undefined;
      const data = await api.parts.list(params) as Part[];
      setParts(data);
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [activeCategory]);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.swarms.trigger("upgrade_parts"); await load(); } catch { } finally { setRefreshing(false); }
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-400" /> Upgrade Parts
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
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
          {parts.map(part => (
            <PartRow key={part.id} part={part} />
          ))}
        </div>
      )}
    </div>
  );
}

function PartRow({ part }: { part: Part }) {
  const bestPrice = part.price_used ?? part.price_refurb ?? part.price_new ?? part.price ?? 0;

  return (
    <div className="flex items-center gap-4 p-4 rounded-xl bg-[#0d1320] border border-[#1e2d45] hover:border-[#1e3a5a] transition-colors">
      {/* Image */}
      <div className="w-12 h-12 rounded-lg bg-[#0a1119] border border-[#1e2d45] flex items-center justify-center flex-shrink-0 overflow-hidden">
        {part.image_url ? (
          <img src={part.image_url} alt="" className="w-full h-full object-cover opacity-70" />
        ) : (
          <Package className="w-5 h-5 text-slate-700" />
        )}
      </div>

      {/* Name + specs */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-semibold text-slate-200">{part.name}</span>
          {part.brand && <span className="text-xs text-slate-500">· {part.brand}</span>}
        </div>
        {part.specs && <p className="text-xs text-slate-500 font-mono">{part.specs}</p>}
      </div>

      {/* Condition badge */}
      <div className="flex-shrink-0">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border ${CONDITION_COLORS[part.condition ?? "used"]}`}>
          {(part.condition ?? "used").toUpperCase()}
        </span>
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
            <div className="text-[#00dc82] font-bold">{formatCurrency(part.price_used)}</div>
          </div>
        )}
        {part.price_refurb != null && (
          <div className="text-center">
            <div className="text-slate-600 uppercase tracking-wide mb-0.5">Refurb</div>
            <div className="text-blue-400 font-semibold">{formatCurrency(part.price_refurb)}</div>
          </div>
        )}
      </div>

      {/* Source — prominent with link */}
      <div className="flex-shrink-0">
        <SourceBadge sourceName={part.source_site ?? "Unknown"} url={part.source_url} />
        {part.last_price_update && (
          <p className="text-[10px] text-slate-600 mt-1 text-right">
            {new Date(part.last_price_update).toLocaleDateString("en-GB")}
          </p>
        )}
      </div>

      {/* Link button */}
      {part.source_url && (
        <a href={part.source_url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
          <Button variant="outline" size="sm">
            <ExternalLink className="w-3.5 h-3.5" /> View
          </Button>
        </a>
      )}
    </div>
  );
}
