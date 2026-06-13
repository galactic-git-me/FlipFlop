"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  BarChart2, RefreshCw, Search, X, ExternalLink,
  Cpu, HardDrive, Server, MemoryStick, CircuitBoard,
  Wind, Zap, MonitorSpeaker, TrendingUp, TrendingDown, Minus,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { GroupedPart, PartCategory } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

// ── Category definitions ──────────────────────────────────────────────────────

type CatId = PartCategory | "all";

interface CategoryDef {
  id: CatId;
  label: string;
  icon: React.ReactNode;
}

const CATEGORIES: CategoryDef[] = [
  { id: "all",         label: "All",          icon: <BarChart2 className="w-3.5 h-3.5" /> },
  { id: "gpu",         label: "Graphics Card", icon: <MonitorSpeaker className="w-3.5 h-3.5" /> },
  { id: "cpu",         label: "Processor",     icon: <Cpu className="w-3.5 h-3.5" /> },
  { id: "ram",         label: "RAM",           icon: <MemoryStick className="w-3.5 h-3.5" /> },
  { id: "motherboard", label: "Motherboard",   icon: <CircuitBoard className="w-3.5 h-3.5" /> },
  { id: "cooling",     label: "Cooling",       icon: <Wind className="w-3.5 h-3.5" /> },
  { id: "ssd",         label: "Storage",       icon: <HardDrive className="w-3.5 h-3.5" /> },
  { id: "psu",         label: "Power Supply",  icon: <Zap className="w-3.5 h-3.5" /> },
  { id: "case",        label: "Case",          icon: <Server className="w-3.5 h-3.5" /> },
];

const CAT_BADGE: Record<string, string> = {
  gpu: "GPU", cpu: "CPU", case: "Case", ram: "RAM",
  motherboard: "Mobo", cooling: "Cooling", ssd: "Storage", psu: "PSU",
};

const SORT_OPTIONS = [
  { value: "name",        label: "Name A→Z"       },
  { value: "used_desc",   label: "Used price ↓"   },
  { value: "used_asc",    label: "Used price ↑"   },
  { value: "new_desc",    label: "New price ↓"    },
  { value: "new_asc",     label: "New price ↑"    },
  { value: "spread_desc", label: "Spread ↓"       },
  { value: "updated",     label: "Recently updated" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MarketPricingPage() {
  const [activeCat, setActiveCat]   = useState<CatId>("all");
  const [parts, setParts]           = useState<GroupedPart[]>([]);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery]           = useState("");
  const [sortBy, setSortBy]         = useState("name");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = (await api.parts.grouped(undefined)) as GroupedPart[];
      setParts(data.filter(p => p.category !== "accessory"));
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.swarms.trigger("upgrade_parts"); await load(); }
    catch { /* noop */ }
    finally { setRefreshing(false); }
  };

  const displayed = useMemo(() => {
    let list = activeCat === "all" ? parts : parts.filter(p => p.category === activeCat);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q));
    }
    return [...list].sort((a, b) => {
      switch (sortBy) {
        case "used_asc":    return (a.price_used ?? Infinity) - (b.price_used ?? Infinity);
        case "used_desc":   return (b.price_used ?? -1)       - (a.price_used ?? -1);
        case "new_asc":     return (a.price_new  ?? Infinity) - (b.price_new  ?? Infinity);
        case "new_desc":    return (b.price_new  ?? -1)       - (a.price_new  ?? -1);
        case "spread_desc": {
          const sa = (a.price_new ?? 0) - (a.price_used ?? 0);
          const sb = (b.price_new ?? 0) - (b.price_used ?? 0);
          return sb - sa;
        }
        case "updated": {
          const ta = a.last_price_update ? +new Date(a.last_price_update) : 0;
          const tb = b.last_price_update ? +new Date(b.last_price_update) : 0;
          return tb - ta;
        }
        default: return a.name.localeCompare(b.name);
      }
    });
  }, [parts, activeCat, query, sortBy]);

  const withBoth   = displayed.filter(p => p.price_used != null && p.price_new != null);
  const avgSpread  = withBoth.length
    ? withBoth.reduce((s, p) => s + (p.price_new! - p.price_used!), 0) / withBoth.length
    : null;

  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-[var(--nf-primary)]" /> Market Pricing
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Used market (eBay sold) vs new market (DropReference · BargainHardware · Temu) — all categories
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing…" : "Refresh Prices"}
        </Button>
      </div>

      {/* Category pills */}
      <div className="flex flex-wrap gap-2 border-b border-[#1e2d45] pb-4">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveCat(cat.id)}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border transition-all ${
              activeCat === cat.id
                ? "bg-[#00b8ff]/10 text-[#00b8ff] border-[#00b8ff]/30"
                : "text-slate-500 border-[#1e2d45] hover:border-slate-600 hover:text-slate-300"
            }`}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      {/* Summary strip */}
      {!loading && displayed.length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs font-mono">
          <span className="px-3 py-1.5 rounded-lg bg-[#0a1119] border border-[#1e2d45] text-slate-400">
            <span className="text-slate-600">Showing </span>
            <span className="text-slate-200 font-bold">{displayed.length}</span>
            <span className="text-slate-600"> parts</span>
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-[#00dc82]/8 border border-[#00dc82]/20 text-[#00dc82]">
            <span className="text-slate-500">Both prices </span>
            <span className="font-bold">{withBoth.length}</span>
          </span>
          {avgSpread != null && (
            <span className={`px-3 py-1.5 rounded-lg border font-bold ${
              avgSpread >= 0
                ? "bg-[#00b8ff]/8 border-[#00b8ff]/20 text-[#00b8ff]"
                : "bg-amber-500/8 border-amber-500/20 text-amber-400"
            }`}>
              <span className="text-slate-500 font-normal">Avg new premium </span>
              {formatCurrency(avgSpread)}
            </span>
          )}
        </div>
      )}

      {/* Toolbar */}
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
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="bg-[#0d1320] border border-[#1e2d45] rounded-xl px-3 py-2.5 text-xs text-slate-300 outline-none focus:border-[#00dc82]/50 transition-colors"
        >
          {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-24 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading market data…
        </div>
      ) : displayed.length === 0 ? (
        <EmptyState
          icon={BarChart2}
          title={query ? "No components match your search" : "No market data yet"}
          description={query ? `No results for "${query}".` : 'Click "Refresh Prices" to pull current market data.'}
          action={query
            ? { label: "Clear search", onClick: () => setQuery("") }
            : { label: "Refresh Now",  onClick: refresh }}
        />
      ) : (
        <div className="rounded-xl border border-[#1e2d45] overflow-hidden">
          {/* Column headers */}
          <div className="grid grid-cols-[1fr_72px_128px_128px_96px_1fr_76px] bg-[#080f1a] border-b border-[#1e2d45] px-4 py-2.5 gap-2">
            <ColHead label="Component" />
            <ColHead label="Type" />
            <ColHead label="Used price"  sub="eBay sold / BIN used"           color="amber" />
            <ColHead label="New price"   sub="DropRef · BargainHW · Temu"      color="blue"  />
            <ColHead label="Spread"      sub="New − Used" />
            <ColHead label="Sources" />
            <ColHead label="Updated" />
          </div>

          {/* Rows */}
          <div className="divide-y divide-[#0c1520]">
            {displayed.map((part, i) => (
              <PricingRow key={`${part.category}::${part.name}::${i}`} part={part} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function ColHead({ label, sub, color }: { label: string; sub?: string; color?: "amber" | "blue" }) {
  const cls = color === "amber" ? "text-amber-400/80"
            : color === "blue"  ? "text-[#00b8ff]/80"
            : "text-slate-500";
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`text-[10px] font-semibold uppercase tracking-wider ${cls}`}>{label}</span>
      {sub && <span className="text-[9px] text-slate-700 leading-none">{sub}</span>}
    </div>
  );
}

function PricingRow({ part }: { part: GroupedPart }) {
  const used   = part.price_used;
  const newP   = part.price_new;
  const spread = newP != null && used != null ? newP - used : null;

  const spreadCls = spread == null ? "text-slate-600"
    : spread >  50 ? "text-[#00b8ff]"
    : spread >   0 ? "text-slate-400"
    : spread === 0 ? "text-slate-500"
    : "text-amber-400";

  const SpreadIcon = spread == null || spread === 0 ? Minus
    : spread > 0 ? TrendingUp : TrendingDown;

  const usedSrc = part.all_sources.find(s => s.condition === "used" && s.price != null);
  const newSrc  = part.all_sources.find(s => s.condition === "new"  && s.price != null);

  return (
    <div className="grid grid-cols-[1fr_72px_128px_128px_96px_1fr_76px] px-4 py-3 gap-2 hover:bg-white/[0.015] transition-colors items-center">

      {/* Name + thumbnail */}
      <div className="flex items-center gap-2.5 min-w-0 pr-2">
        {part.image_url ? (
          <img src={part.image_url} alt={part.name}
            className="w-8 h-8 object-contain rounded bg-[#070d14] flex-shrink-0 border border-white/5"
          />
        ) : (
          <div className="w-8 h-8 rounded bg-[#070d14] flex-shrink-0 border border-white/5" />
        )}
        <span className="text-sm text-slate-200 font-medium leading-snug truncate" title={part.name}>
          {part.name}
        </span>
      </div>

      {/* Category badge */}
      <div>
        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#0a1119] border border-[#1e2d45] text-slate-400 whitespace-nowrap">
          {CAT_BADGE[part.category] ?? part.category}
        </span>
      </div>

      {/* Used price */}
      <div>
        {used != null ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-amber-400 font-bold text-sm font-mono">{formatCurrency(used)}</span>
            {usedSrc?.source && (
              <span className="text-[9px] text-slate-600">{usedSrc.source}</span>
            )}
          </div>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      {/* New price */}
      <div>
        {newP != null ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-[#00b8ff] font-bold text-sm font-mono">{formatCurrency(newP)}</span>
            {newSrc?.source && (
              <span className="text-[9px] text-slate-600">{newSrc.source}</span>
            )}
          </div>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      {/* Spread */}
      <div className={`flex items-center gap-1 ${spreadCls}`}>
        <SpreadIcon className="w-3.5 h-3.5 flex-shrink-0" />
        {spread != null ? (
          <span className="text-sm font-semibold font-mono">
            {spread > 0 ? "+" : ""}{formatCurrency(spread)}
          </span>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      {/* Source chips */}
      <div className="flex flex-wrap gap-1">
        {part.all_sources.slice(0, 4).map((s, i) => {
          const chip = (
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] ${
              s.condition === "new"
                ? "bg-[#00b8ff]/5 border-[#00b8ff]/15 text-[#00b8ff]/70"
                : "bg-amber-500/5 border-amber-500/15 text-amber-400/70"
            }`}>
              {s.source}
              {s.price != null && <span className="opacity-80 font-mono">{formatCurrency(s.price)}</span>}
              {s.url && <ExternalLink className="w-2 h-2 opacity-40" />}
            </span>
          );
          return s.url ? (
            <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
               className="hover:opacity-100 opacity-90 transition-opacity">
              {chip}
            </a>
          ) : <span key={i}>{chip}</span>;
        })}
        {part.all_sources.length > 4 && (
          <span className="px-1.5 py-0.5 rounded border border-[#1e2d45] text-[9px] text-slate-600">
            +{part.all_sources.length - 4}
          </span>
        )}
      </div>

      {/* Last updated */}
      <div className="text-[10px] text-slate-700 text-right whitespace-nowrap">
        {part.last_price_update
          ? formatRelativeTime(new Date(part.last_price_update))
          : "—"}
      </div>
    </div>
  );
}
