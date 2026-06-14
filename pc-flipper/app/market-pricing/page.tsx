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

      {/* Gradient overlay — dark at bottom for legibility */}
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
