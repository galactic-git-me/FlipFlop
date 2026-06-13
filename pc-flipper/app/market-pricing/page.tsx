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

// ── Slicers ───────────────────────────────────────────────────────────────────

interface SlicerDef {
  id: string;
  label: string;
  options: string[];
  match: (name: string, val: string) => boolean;
}

const CATEGORY_SLICERS: Partial<Record<CatId, SlicerDef[]>> = {
  ram: [
    {
      id: "type",
      label: "Type",
      options: ["DDR4", "DDR5"],
      match: (name, val) => name.toUpperCase().includes(val),
    },
    {
      id: "capacity",
      label: "Capacity",
      options: ["8GB", "16GB", "32GB", "64GB", "128GB"],
      match: (name, val) => new RegExp(`\\b${val}\\b`, "i").test(name),
    },
  ],
  gpu: [
    {
      id: "brand",
      label: "Brand",
      options: ["NVIDIA", "AMD"],
      match: (name, val) => {
        const u = name.toUpperCase();
        if (val === "NVIDIA") return u.includes("RTX") || u.includes("GTX") || u.includes("GEFORCE") || u.includes("NVIDIA");
        if (val === "AMD")    return u.includes("RADEON") || / RX /.test(u) || u.startsWith("AMD ");
        return false;
      },
    },
    {
      id: "vram",
      label: "VRAM",
      options: ["4GB", "6GB", "8GB", "12GB", "16GB", "24GB"],
      match: (name, val) => new RegExp(`\\b${val}\\b`, "i").test(name),
    },
  ],
  cpu: [
    {
      id: "brand",
      label: "Brand",
      options: ["Intel", "AMD"],
      match: (name, val) => name.toUpperCase().includes(val.toUpperCase()),
    },
    {
      id: "gen",
      label: "Platform",
      options: ["LGA1700", "LGA1851", "AM4", "AM5"],
      match: (name, val) => name.toUpperCase().includes(val.toUpperCase()),
    },
  ],
  ssd: [
    {
      id: "interface",
      label: "Interface",
      options: ["NVMe", "SATA", "M.2"],
      match: (name, val) => name.toUpperCase().includes(val.toUpperCase()),
    },
    {
      id: "capacity",
      label: "Capacity",
      options: ["250GB", "500GB", "512GB", "1TB", "2TB", "4TB"],
      match: (name, val) => new RegExp(`\\b${val}\\b`, "i").test(name),
    },
  ],
  motherboard: [
    {
      id: "socket",
      label: "Socket",
      options: ["AM4", "AM5", "LGA1700", "LGA1851"],
      match: (name, val) => name.toUpperCase().includes(val.toUpperCase()),
    },
    {
      id: "form_factor",
      label: "Form Factor",
      options: ["ATX", "mATX", "ITX"],
      match: (name, val) => {
        const u = name.toUpperCase();
        if (val === "mATX") return u.includes("MATX") || u.includes("MICRO-ATX") || u.includes("MICRO ATX");
        if (val === "ITX")  return /\bITX\b/.test(u);
        if (val === "ATX")  return /\bATX\b/.test(u) && !u.includes("MATX") && !/\bITX\b/.test(u) && !u.includes("MICRO");
        return false;
      },
    },
  ],
  psu: [
    {
      id: "wattage",
      label: "Wattage",
      options: ["550W", "650W", "750W", "850W", "1000W", "1200W"],
      match: (name, val) => new RegExp(`\\b${val}\\b`, "i").test(name),
    },
    {
      id: "rating",
      label: "Efficiency",
      options: ["Gold", "Platinum", "Titanium"],
      match: (name, val) => name.toUpperCase().includes(val.toUpperCase()),
    },
  ],
  cooling: [
    {
      id: "type",
      label: "Type",
      options: ["AIO", "Air"],
      match: (name, val) => {
        const u = name.toUpperCase();
        if (val === "AIO") return u.includes("AIO") || u.includes("LIQUID") || u.includes("WATER");
        if (val === "Air") return !u.includes("AIO") && !u.includes("LIQUID") && !u.includes("WATER");
        return false;
      },
    },
    {
      id: "size",
      label: "Radiator",
      options: ["120mm", "240mm", "280mm", "360mm"],
      match: (name, val) => name.includes(val),
    },
  ],
  case: [
    {
      id: "form_factor",
      label: "Size",
      options: ["Full Tower", "Mid Tower", "Mini ITX", "mATX"],
      match: (name, val) => name.toLowerCase().includes(val.toLowerCase()),
    },
  ],
};

const SORT_OPTIONS = [
  { value: "name",        label: "Name A→Z"        },
  { value: "used_desc",   label: "Used price ↓"    },
  { value: "used_asc",    label: "Used price ↑"    },
  { value: "new_desc",    label: "New price ↓"     },
  { value: "new_asc",     label: "New price ↑"     },
  { value: "spread_desc", label: "Spread ↓"        },
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
  const [slicerSel, setSlicerSel]   = useState<Record<string, string | null>>({});

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

  const activeCatSlicers = activeCat !== "all" ? (CATEGORY_SLICERS[activeCat] ?? []) : [];

  const toggleSlicer = (slicerId: string, val: string) => {
    const key = `${activeCat}::${slicerId}`;
    setSlicerSel(prev => ({ ...prev, [key]: prev[key] === val ? null : val }));
  };

  const displayed = useMemo(() => {
    let list = activeCat === "all" ? parts : parts.filter(p => p.category === activeCat);
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q));
    }
    for (const slicer of activeCatSlicers) {
      const val = slicerSel[`${activeCat}::${slicer.id}`] ?? null;
      if (val) list = list.filter(p => slicer.match(p.name, val));
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parts, activeCat, query, sortBy, slicerSel, activeCatSlicers]);

  const withBoth  = displayed.filter(p => p.price_used != null && p.price_new != null);
  const avgSpread = withBoth.length
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

      {/* Slicers */}
      {activeCatSlicers.length > 0 && (
        <div className="flex flex-wrap gap-x-6 gap-y-2.5 pb-3 border-b border-[#1e2d45]">
          {activeCatSlicers.map(slicer => {
            const key = `${activeCat}::${slicer.id}`;
            const selected = slicerSel[key] ?? null;
            return (
              <div key={slicer.id} className="flex items-center gap-2.5">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-600 whitespace-nowrap w-16 text-right">
                  {slicer.label}
                </span>
                <div className="flex flex-wrap gap-1">
                  {slicer.options.map(opt => (
                    <button
                      key={opt}
                      onClick={() => toggleSlicer(slicer.id, opt)}
                      className={`px-2.5 py-1 rounded text-xs font-medium border transition-all ${
                        selected === opt
                          ? "bg-[#00dc82]/15 text-[#00dc82] border-[#00dc82]/40"
                          : "text-slate-500 border-[#1a2535] hover:border-slate-600 hover:text-slate-300"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
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

      {/* Grid */}
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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {displayed.map((part, i) => (
            <PricingCard key={`${part.category}::${part.name}::${i}`} part={part} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

function PricingCard({ part }: { part: GroupedPart }) {
  const used   = part.price_used;
  const newP   = part.price_new;
  const spread = newP != null && used != null ? newP - used : null;

  const spreadColor = spread == null ? "text-slate-600"
    : spread > 50  ? "text-[#00b8ff]"
    : spread > 0   ? "text-slate-400"
    : spread === 0 ? "text-slate-500"
    : "text-amber-400";

  const SpreadIcon = spread == null || spread === 0 ? Minus
    : spread > 0 ? TrendingUp : TrendingDown;

  const usedSrc = part.all_sources.find(s => s.condition === "used" && s.price != null);
  const newSrc  = part.all_sources.find(s => s.condition === "new"  && s.price != null);

  return (
    <div className="rounded-xl border border-[#1e2d45] bg-[#080f1a] flex flex-col overflow-hidden hover:border-[#2a3f5a] transition-colors">

      {/* Name + image + badge */}
      <div className="p-3 flex items-start gap-3 border-b border-[#0c1520]">
        {part.image_url ? (
          <img
            src={part.image_url}
            alt={part.name}
            className="w-12 h-12 object-contain rounded bg-[#050b12] flex-shrink-0 border border-white/5 p-0.5"
          />
        ) : (
          <div className="w-12 h-12 rounded bg-[#050b12] flex-shrink-0 border border-white/5" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm text-slate-200 font-medium leading-snug line-clamp-2" title={part.name}>
            {part.name}
          </p>
          <span className="mt-1 inline-block px-1.5 py-0.5 rounded text-[9px] font-semibold bg-[#0a1119] border border-[#1e2d45] text-slate-500 uppercase tracking-wide">
            {CAT_BADGE[part.category] ?? part.category}
          </span>
        </div>
      </div>

      {/* Used / New prices */}
      <div className="grid grid-cols-2 divide-x divide-[#0c1520]">
        <div className="p-3 flex flex-col gap-0.5">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-amber-500/60">Used</span>
          {used != null ? (
            <>
              <span className="text-amber-400 font-bold text-base font-mono leading-none">{formatCurrency(used)}</span>
              {usedSrc?.source && <span className="text-[9px] text-slate-700 mt-0.5">{usedSrc.source}</span>}
            </>
          ) : (
            <span className="text-slate-700 text-sm font-mono">—</span>
          )}
        </div>
        <div className="p-3 flex flex-col gap-0.5">
          <span className="text-[9px] font-semibold uppercase tracking-wider text-[#00b8ff]/60">New</span>
          {newP != null ? (
            <>
              <span className="text-[#00b8ff] font-bold text-base font-mono leading-none">{formatCurrency(newP)}</span>
              {newSrc?.source && <span className="text-[9px] text-slate-700 mt-0.5">{newSrc.source}</span>}
            </>
          ) : (
            <span className="text-slate-700 text-sm font-mono">—</span>
          )}
        </div>
      </div>

      {/* Footer: spread + source chips */}
      <div className="px-3 py-2 border-t border-[#0c1520] flex items-center justify-between gap-2 mt-auto">
        <div className={`flex items-center gap-1 ${spreadColor}`}>
          <SpreadIcon className="w-3 h-3 flex-shrink-0" />
          {spread != null ? (
            <span className="text-xs font-semibold font-mono">
              {spread > 0 ? "+" : ""}{formatCurrency(spread)}
            </span>
          ) : (
            <span className="text-xs text-slate-700">—</span>
          )}
        </div>
        <div className="flex flex-wrap gap-1 justify-end">
          {part.all_sources.slice(0, 3).map((s, i) => {
            const chip = (
              <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[8px] border ${
                s.condition === "new"
                  ? "bg-[#00b8ff]/5 border-[#00b8ff]/15 text-[#00b8ff]/60"
                  : "bg-amber-500/5 border-amber-500/15 text-amber-400/60"
              }`}>
                {s.source?.split(" ")[0]}
                {s.url && <ExternalLink className="w-2 h-2 opacity-40 ml-0.5" />}
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
            <span className="px-1.5 py-0.5 rounded border border-[#1e2d45] text-[8px] text-slate-600">
              +{part.all_sources.length - 3}
            </span>
          )}
        </div>
      </div>

      {part.last_price_update && (
        <div className="px-3 pb-2 text-[9px] text-slate-700 text-right -mt-1">
          {formatRelativeTime(new Date(part.last_price_update))}
        </div>
      )}
    </div>
  );
}
