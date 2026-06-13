"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  BarChart2, RefreshCw, Search, X, ExternalLink,
  Cpu, HardDrive, Server, MemoryStick, CircuitBoard,
  Wind, Zap, MonitorSpeaker, TrendingUp, TrendingDown,
  Minus, ChevronUp, ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/empty-state";
import { GroupedPart, PartCategory } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

// ── Category definitions ──────────────────────────────────────────────────────

interface CategoryDef {
  id: PartCategory | "all";
  label: string;
  icon: React.ReactNode;
  apiValue?: string;
}

const CATEGORIES: CategoryDef[] = [
  { id: "all",         label: "All Components", icon: <BarChart2 className="w-4 h-4" /> },
  { id: "gpu",         label: "Graphics Card",  icon: <MonitorSpeaker className="w-4 h-4" /> },
  { id: "cpu",         label: "Processor",      icon: <Cpu className="w-4 h-4" /> },
  { id: "case",        label: "Case",           icon: <Server className="w-4 h-4" /> },
  { id: "ram",         label: "RAM",            icon: <MemoryStick className="w-4 h-4" /> },
  { id: "motherboard", label: "Motherboard",    icon: <CircuitBoard className="w-4 h-4" /> },
  { id: "cooling",     label: "Cooling",        icon: <Wind className="w-4 h-4" /> },
  { id: "ssd",         label: "Storage",        icon: <HardDrive className="w-4 h-4" /> },
  { id: "psu",         label: "Power Supply",   icon: <Zap className="w-4 h-4" /> },
];

const CATEGORY_LABELS: Record<string, string> = {
  gpu: "GPU", cpu: "CPU", case: "Case", ram: "RAM",
  motherboard: "Mobo", cooling: "Cooling", ssd: "Storage",
  psu: "PSU", accessory: "Accessory",
};

const SORT_OPTIONS = [
  { value: "name",       label: "Name A→Z" },
  { value: "used_asc",   label: "Used price ↑" },
  { value: "used_desc",  label: "Used price ↓" },
  { value: "new_asc",    label: "New price ↑" },
  { value: "new_desc",   label: "New price ↓" },
  { value: "spread_desc",label: "Spread ↓" },
  { value: "updated",    label: "Recently updated" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MarketPricingPage() {
  const [activeCat, setActiveCat]   = useState<PartCategory | "all">("all");
  const [parts, setParts]           = useState<GroupedPart[]>([]);
  const [loading, setLoading]       = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery]           = useState("");
  const [sortBy, setSortBy]         = useState("name");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch all non-accessory parts in one call; filter client-side for instant tab switches
      const data = (await api.parts.grouped(undefined)) as GroupedPart[];
      setParts(data.filter(p => p.category !== "accessory"));
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await api.swarms.trigger("upgrade_parts");
      await load();
    } catch {
      /* noop */
    } finally {
      setRefreshing(false);
    }
  };

  const displayed = useMemo(() => {
    let list = parts;

    // Category filter
    if (activeCat !== "all") {
      list = list.filter(p => p.category === activeCat);
    }

    // Search
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q));
    }

    // Sort
    list = [...list].sort((a, b) => {
      switch (sortBy) {
        case "used_asc":   return (a.price_used  ?? Infinity) - (b.price_used  ?? Infinity);
        case "used_desc":  return (b.price_used  ?? -1)       - (a.price_used  ?? -1);
        case "new_asc":    return (a.price_new   ?? Infinity) - (b.price_new   ?? Infinity);
        case "new_desc":   return (b.price_new   ?? -1)       - (a.price_new   ?? -1);
        case "spread_desc": {
          const sa = (a.price_new ?? 0) - (a.price_used ?? 0);
          const sb = (b.price_new ?? 0) - (b.price_used ?? 0);
          return sb - sa;
        }
        case "updated": {
          const ta = a.last_price_update ? new Date(a.last_price_update).getTime() : 0;
          const tb = b.last_price_update ? new Date(b.last_price_update).getTime() : 0;
          return tb - ta;
        }
        default: return a.name.localeCompare(b.name);
      }
    });

    return list;
  }, [parts, activeCat, query, sortBy]);

  // Stats for the active view
  const stats = useMemo(() => {
    const withBoth = displayed.filter(p => p.price_used != null && p.price_new != null);
    const avgSpread = withBoth.length
      ? withBoth.reduce((s, p) => s + (p.price_new! - p.price_used!), 0) / withBoth.length
      : null;
    return { total: displayed.length, withBoth: withBoth.length, avgSpread };
  }, [displayed]);

  return (
    <div className="flex h-full min-h-0">
      {/* ── Left category nav ── */}
      <aside className="w-52 flex-shrink-0 border-r border-[#1e2d45] p-3 flex flex-col gap-1">
        <p className="text-[10px] text-slate-600 uppercase tracking-widest px-2 pt-1 pb-2 font-mono">
          Category
        </p>
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveCat(cat.id)}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left w-full ${
              activeCat === cat.id
                ? "bg-[#00b8ff]/10 text-[#00b8ff] border border-[#00b8ff]/25"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] border border-transparent"
            }`}
          >
            <span className={activeCat === cat.id ? "text-[#00b8ff]" : "text-slate-500"}>
              {cat.icon}
            </span>
            {cat.label}
          </button>
        ))}
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 min-w-0 p-6 space-y-5 overflow-auto">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
              <BarChart2 className="w-5 h-5" /> Market Pricing
            </h1>
            <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
              Used market prices (eBay sold) vs new market prices (DropReference · BargainHardware · Temu)
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing…" : "Refresh Prices"}
          </Button>
        </div>

        {/* Summary pills */}
        {!loading && displayed.length > 0 && (
          <div className="flex flex-wrap gap-3">
            <StatPill label="Parts shown"   value={String(stats.total)} color="slate" />
            <StatPill label="Both prices"   value={String(stats.withBoth)} color="green" />
            {stats.avgSpread != null && (
              <StatPill
                label="Avg new premium"
                value={formatCurrency(stats.avgSpread)}
                color={stats.avgSpread >= 0 ? "blue" : "amber"}
              />
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
            {SORT_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
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
            action={query ? { label: "Clear search", onClick: () => setQuery("") } : { label: "Refresh Now", onClick: refresh }}
          />
        ) : (
          <div className="rounded-xl border border-[#1e2d45] overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_80px_130px_130px_100px_160px_80px] gap-0 bg-[#0a1119] border-b border-[#1e2d45] px-4 py-2">
              <ColHeader label="Component" />
              <ColHeader label="Type" />
              <ColHeader label="Used price" color="amber" hint="eBay sold / BIN used" />
              <ColHeader label="New price"  color="blue"  hint="DropRef · BargainHW · Temu" />
              <ColHeader label="Spread"     hint="New − Used" />
              <ColHeader label="Sources" />
              <ColHeader label="Updated" />
            </div>

            {/* Rows */}
            <div className="divide-y divide-[#0f1a28]">
              {displayed.map((part, i) => (
                <PricingRow key={`${part.category}::${part.name}::${i}`} part={part} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: string; color: "slate" | "green" | "blue" | "amber" }) {
  const colors = {
    slate: "bg-slate-800/60 border-slate-700/40 text-slate-300",
    green: "bg-[#00dc82]/8 border-[#00dc82]/20 text-[#00dc82]",
    blue:  "bg-[#00b8ff]/8 border-[#00b8ff]/20 text-[#00b8ff]",
    amber: "bg-amber-500/8 border-amber-500/20 text-amber-400",
  };
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono ${colors[color]}`}>
      <span className="text-slate-500">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  );
}

function ColHeader({ label, color, hint }: { label: string; color?: "amber" | "blue"; hint?: string }) {
  const colorCls = color === "amber" ? "text-amber-400/80" : color === "blue" ? "text-[#00b8ff]/80" : "text-slate-500";
  return (
    <div className="flex flex-col gap-0.5">
      <span className={`text-[10px] font-semibold uppercase tracking-wider ${colorCls}`}>{label}</span>
      {hint && <span className="text-[9px] text-slate-700 leading-none">{hint}</span>}
    </div>
  );
}

function PricingRow({ part }: { part: GroupedPart }) {
  const used   = part.price_used;
  const newP   = part.price_new;
  const spread = newP != null && used != null ? newP - used : null;

  const spreadColor = spread == null ? "text-slate-600"
    : spread > 50  ? "text-[#00b8ff]"
    : spread > 0   ? "text-slate-400"
    : "text-amber-400";

  const SpreadIcon = spread == null ? Minus : spread > 0 ? TrendingUp : spread < 0 ? TrendingDown : Minus;

  // Deduplicate sources to show which feed provided each price
  const usedSources = part.all_sources.filter(s => s.condition === "used" && s.price != null);
  const newSources  = part.all_sources.filter(s => s.condition === "new"  && s.price != null);

  return (
    <div className="grid grid-cols-[1fr_80px_130px_130px_100px_160px_80px] gap-0 px-4 py-3 hover:bg-white/[0.02] transition-colors items-center group">

      {/* Name */}
      <div className="flex items-center gap-2.5 min-w-0 pr-4">
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

      {/* Category */}
      <div>
        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#0a1119] border border-[#1e2d45] text-slate-400">
          {CATEGORY_LABELS[part.category] ?? part.category}
        </span>
      </div>

      {/* Used price */}
      <div>
        {used != null ? (
          <div className="flex flex-col gap-0.5">
            <span className="text-amber-400 font-bold text-sm">{formatCurrency(used)}</span>
            {usedSources[0] && (
              <span className="text-[9px] text-slate-600 leading-none">{usedSources[0].source}</span>
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
            <span className="text-[#00b8ff] font-bold text-sm">{formatCurrency(newP)}</span>
            {newSources[0] && (
              <span className="text-[9px] text-slate-600 leading-none">{newSources[0].source}</span>
            )}
          </div>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      {/* Spread */}
      <div className={`flex items-center gap-1 ${spreadColor}`}>
        <SpreadIcon className="w-3.5 h-3.5 flex-shrink-0" />
        {spread != null ? (
          <span className="text-sm font-semibold">
            {spread > 0 ? "+" : ""}{formatCurrency(spread)}
          </span>
        ) : (
          <span className="text-slate-700 text-xs">—</span>
        )}
      </div>

      {/* All sources */}
      <div className="flex flex-wrap gap-1">
        {part.all_sources.slice(0, 4).map((s, i) =>
          s.url ? (
            <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] transition-colors hover:border-[#1e3a5a] hover:text-slate-200 ${
                s.condition === "new"
                  ? "bg-[#00b8ff]/5 border-[#00b8ff]/15 text-[#00b8ff]/70"
                  : "bg-amber-500/5 border-amber-500/15 text-amber-400/70"
              }`}
            >
              {s.source}
              {s.price != null && <span className="opacity-70">{formatCurrency(s.price)}</span>}
              <ExternalLink className="w-2 h-2 opacity-40" />
            </a>
          ) : (
            <span key={i}
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] ${
                s.condition === "new"
                  ? "bg-[#00b8ff]/5 border-[#00b8ff]/15 text-[#00b8ff]/70"
                  : "bg-amber-500/5 border-amber-500/15 text-amber-400/70"
              }`}
            >
              {s.source}
              {s.price != null && <span className="opacity-70">{formatCurrency(s.price)}</span>}
            </span>
          )
        )}
        {part.all_sources.length > 4 && (
          <span className="px-1.5 py-0.5 rounded border border-[#1e2d45] text-[9px] text-slate-600">
            +{part.all_sources.length - 4}
          </span>
        )}
      </div>

      {/* Last updated */}
      <div className="text-[10px] text-slate-700 text-right">
        {part.last_price_update
          ? formatRelativeTime(new Date(part.last_price_update))
          : "—"}
      </div>
    </div>
  );
}
