"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import {
  Package, RefreshCw, ExternalLink, Search, X,
  Gem, Zap, SlidersHorizontal, ArrowUpDown, PlusCircle,
  ChevronLeft, ChevronRight, Copy, LayoutList, LayoutGrid, type LucideIcon,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { SellerBadge } from "@/components/seller-badge";
import { AuctionBadge, AuctionPriceDisplay } from "@/components/auction-display";
import { EmptyState } from "@/components/empty-state";
import { ManualSubmitModal } from "@/components/manual-submit-modal";
import { GroupedPart, Listing, Classification, CLASSIFICATION_CONFIG } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";

// ── Tab definitions ────────────────────────────────────────────────────────────

type MarketTab = "opportunities" | "components" | "cases" | "accessories";

const TABS: { id: MarketTab; label: string; icon: string }[] = [
  { id: "opportunities", label: "Flip Opportunities", icon: "💎" },
  { id: "components",    label: "Components",         icon: "🔧" },
  { id: "cases",         label: "PC Cases",           icon: "🖥️"  },
  { id: "accessories",   label: "Accessories",        icon: "🖱️"  },
];

// ── Page ───────────────────────────────────────────────────────────────────────

export default function MarketplacePage() {
  const [activeTab, setActiveTab] = useState<MarketTab>("opportunities");

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
          <Package className="w-5 h-5 text-[var(--nf-primary)]" /> Marketplace
        </h1>
        <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
          Browse flip opportunities and the full parts catalogue
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-2 border-b border-[#1e2d45] pb-0">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-all -mb-px ${
              activeTab === tab.id
                ? "border-[#00dc82] text-[#00dc82]"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "opportunities" && <FlipOpportunitiesTab />}
      {activeTab === "components"    && <CatalogueTab />}
      {activeTab === "cases"         && <PartsTab category="cases"      key="cases"      />}
      {activeTab === "accessories"   && <PartsTab category="accessories" key="accessories" />}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// FLIP OPPORTUNITIES TAB
// ══════════════════════════════════════════════════════════════════════════════

const CLASS_FILTERS: (Classification | "all")[] = [
  "all", "amazing_gem", "gem", "already_flipped", "no_profit", "overpriced",
];

const SELLER_TYPE_OPTIONS = [
  { value: "all",         label: "All sellers" },
  { value: "private",     label: "👤 Private"  },
  { value: "flipper",     label: "🔄 Flipper"  },
  { value: "shop",        label: "🏪 Shop"     },
  { value: "refurb_shop", label: "🔧 Refurb"  },
];

const SORT_OPTIONS = [
  { value: "gem_score",        label: "Flippability ↓" },
  { value: "estimated_profit", label: "Profit ↓"       },
  { value: "price",            label: "Price ↑"        },
  { value: "first_seen_at",    label: "Newest first"   },
];

const PAGE_SIZES = [20, 50, 100];

function FlipOpportunitiesTab() {
  const [classFilter, setClassFilter]     = useState<Classification | "all">("all");
  const [search, setSearch]               = useState("");
  const [minProfit, setMinProfit]         = useState("");
  const [maxPrice, setMaxPrice]           = useState("");
  const [sourceFilter, setSourceFilter]   = useState("all");
  const [sellerTypeFilter, setSellerTypeFilter] = useState("all");
  const [sortBy, setSortBy]               = useState("gem_score");
  const [filtersOpen, setFiltersOpen]     = useState(false);
  const [page, setPage]                   = useState(1);
  const [pageSize, setPageSize]           = useState(20);
  const [listings, setListings]           = useState<Listing[]>([]);
  const [total, setTotal]                 = useState(0);
  const [sources, setSources]             = useState<string[]>([]);
  const [loading, setLoading]             = useState(true);
  const [triggering, setTriggering]       = useState(false);
  const [flippingId, setFlippingId]       = useState<number | null>(null);
  const [showManualSubmit, setShowManualSubmit] = useState(false);
  const [viewMode, setViewMode]           = useState<"list" | "grid">("list");

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 350);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  useEffect(() => {
    const id = setTimeout(() => setPage(1), 0);
    return () => clearTimeout(id);
  }, [classFilter, minProfit, maxPrice, sourceFilter, sellerTypeFilter, sortBy]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {
        sort_by: sortBy,
        sort_desc: sortBy === "price" ? "false" : "true",
        limit: String(pageSize),
        offset: String((page - 1) * pageSize),
        status: "active",
      };
      if (classFilter !== "all") params.classification = classFilter;
      if (debouncedSearch)       params.search = debouncedSearch;
      if (minProfit)             params.min_profit = minProfit;
      if (maxPrice)              params.max_price = maxPrice;
      if (sourceFilter !== "all") params.source_name = sourceFilter;

      const data = await api.listings.list(params) as Listing[];
      const filtered = sellerTypeFilter === "all"
        ? data
        : data.filter(l => l.seller_type === sellerTypeFilter);

      setListings(filtered);
      setTotal(prev => page === 1 ? (data.length < pageSize ? data.length : prev || data.length * 3) : prev);

      if (page === 1 && sources.length === 0) {
        const all = await api.listings.list({ limit: "500", status: "active" }) as Listing[];
        setSources([...new Set(all.map(l => l.source_name))].sort());
      }
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  }, [classFilter, debouncedSearch, minProfit, maxPrice, sourceFilter, sellerTypeFilter, sortBy, page, pageSize, sources.length]);

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, [load]);

  const trigger = async () => {
    setTriggering(true);
    try { await api.swarms.trigger("flip_opportunities"); await load(); }
    catch { } finally { setTriggering(false); }
  };

  const handleFlip = async (listing: Listing) => {
    setFlippingId(listing.id);
    try { await api.flips.create({ listing_id: listing.id }); window.location.href = "/flips"; }
    catch { setFlippingId(null); }
  };

  const hasAdvancedFilters = minProfit || maxPrice || sourceFilter !== "all" || sellerTypeFilter !== "all";
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      <ManualSubmitModal
        open={showManualSubmit}
        onClose={() => setShowManualSubmit(false)}
        onSuccess={() => { setShowManualSubmit(false); load(); }}
      />

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-sm text-slate-500 font-mono">
          {listings.length} listings · sorted by {SORT_OPTIONS.find(o => o.value === sortBy)?.label}
        </p>
        <div className="flex items-center gap-2">
          {/* List / Grid toggle */}
          <div className="flex items-center rounded-lg border border-[#1e2d45] overflow-hidden">
            <button
              onClick={() => setViewMode("list")}
              title="List view"
              className={`p-1.5 transition-colors ${viewMode === "list" ? "bg-[#00dc82]/15 text-[#00dc82]" : "text-slate-500 hover:text-slate-300"}`}
            >
              <LayoutList className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              title="Grid view"
              className={`p-1.5 transition-colors ${viewMode === "grid" ? "bg-[#00dc82]/15 text-[#00dc82]" : "text-slate-500 hover:text-slate-300"}`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>
          <Button
            variant="ghost" size="sm"
            onClick={() => setFiltersOpen(o => !o)}
            className={hasAdvancedFilters ? "text-[#00dc82] border-[#00dc82]/30 border" : ""}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Filters
            {hasAdvancedFilters && <Badge variant="success" className="ml-1 text-[9px] px-1 py-0">active</Badge>}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setShowManualSubmit(true)}>
            <PlusCircle className="w-3.5 h-3.5" /> Submit Manually
          </Button>
          <Button variant="secondary" size="sm" onClick={trigger} disabled={triggering}>
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            {triggering ? "Scanning…" : "Scan Sources"}
          </Button>
        </div>
      </div>

      {/* Classification tabs */}
      <div className="flex flex-wrap gap-2">
        {CLASS_FILTERS.map(cls => {
          const cfg = cls !== "all" ? CLASSIFICATION_CONFIG[cls] : null;
          return (
            <button key={cls} onClick={() => setClassFilter(cls)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                classFilter === cls
                  ? "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                  : "text-slate-500 border-[#1e2d45] hover:border-slate-600 hover:text-slate-400"
              }`}
            >
              {cls === "all" ? "All" : `${cfg?.emoji} ${cfg?.label}`}
            </button>
          );
        })}
      </div>

      {/* Search + sort */}
      <div className="flex gap-2 items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search title, CPU, GPU, location…"
            className="w-full pl-10 pr-4 py-2.5 bg-[#0d1320] border border-[#1e2d45] rounded-xl text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50 transition-colors"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-1 bg-[#0d1320] border border-[#1e2d45] rounded-xl px-2">
          <ArrowUpDown className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}
            className="bg-transparent py-2.5 pr-1 text-xs text-slate-300 outline-none">
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* Advanced filters */}
      {filtersOpen && (
        <div className="bg-[#0d1a2a] border border-white/[0.06] rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Min profit (£)</label>
            <input type="number" value={minProfit} onChange={e => setMinProfit(e.target.value)} placeholder="e.g. 50"
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50" />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Max buy price (£)</label>
            <input type="number" value={maxPrice} onChange={e => setMaxPrice(e.target.value)} placeholder="e.g. 300"
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50" />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Source</label>
            <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 outline-none focus:border-[#00dc82]/50">
              <option value="all">All sources</option>
              {sources.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Seller type</label>
            <select value={sellerTypeFilter} onChange={e => setSellerTypeFilter(e.target.value)}
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 outline-none focus:border-[#00dc82]/50">
              {SELLER_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {hasAdvancedFilters && (
            <div className="col-span-full flex justify-end">
              <button onClick={() => { setMinProfit(""); setMaxPrice(""); setSourceFilter("all"); setSellerTypeFilter("all"); }}
                className="text-[10px] text-slate-500 hover:text-red-400 transition-colors">
                × Clear all filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : listings.length === 0 ? (
        <EmptyState icon={Gem} title="No listings found"
          description="Try adjusting your filters, or run a scan to discover fresh opportunities."
          action={{ label: "Run Scan Now", onClick: trigger }} />
      ) : (
        <>
          {viewMode === "list" ? (
            <div className="space-y-3">
              {listings.map(listing => (
                <ListingRow key={listing.id} listing={listing} onFlip={handleFlip} flippingId={flippingId} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {listings.map(listing => (
                <ListingCard key={listing.id} listing={listing} onFlip={handleFlip} flippingId={flippingId} />
              ))}
            </div>
          )}
          {/* Pagination */}
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Page {page}{totalPages > 1 ? ` of ${totalPages}` : ""}</span>
              <select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}
                className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-400 outline-none focus:border-[#00dc82]/50">
                {PAGE_SIZES.map(n => <option key={n} value={n}>{n} / page</option>)}
              </select>
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" disabled={page === 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1).map(p => (
                <button key={p} onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-lg text-xs transition-colors ${
                    page === p ? "bg-[#00dc82]/20 text-[#00dc82] font-semibold" : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                  }`}>
                  {p}
                </button>
              ))}
              <Button variant="ghost" size="sm" disabled={listings.length < pageSize} onClick={() => setPage(p => p + 1)}>
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Listing grid card ─────────────────────────────────────────────────────────

function ListingCard({ listing: l, onFlip, flippingId }: {
  listing: Listing; onFlip: (l: Listing) => void; flippingId: number | null;
}) {
  const profit = l.estimated_profit ?? 0;
  const profitColor = profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400";
  const cfg = l.classification ? CLASSIFICATION_CONFIG[l.classification] : null;

  return (
    <div className={`relative rounded-xl overflow-hidden hover:border-[var(--nf-border-strong)] transition-colors h-64 flex flex-col group border ${
      l.classification === "amazing_gem" ? "border-cyan-400/25" :
      l.classification === "gem" ? "border-emerald-400/20" : "border-[#1e2d45]"
    }`}>
      {/* Full-card background image */}
      {l.image_urls[0] ? (
        <img src={l.image_urls[0]} alt={l.title} className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" loading="lazy" />
      ) : (
        <div className="absolute inset-0 bg-[#070d14] flex items-center justify-center opacity-10">
          <Gem className="w-10 h-10 text-slate-300" />
        </div>
      )}

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/97 via-black/55 to-black/20" />

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full p-3">

        {/* Top: classification + score */}
        <div className="flex items-start justify-between gap-2">
          {cfg && (
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold border backdrop-blur-sm ${cfg.color} ${cfg.bg}`}>
              {cfg.emoji} {cfg.label}
            </span>
          )}
          <div className="ml-auto">
            <FlippabilityScore score={l.gem_score} size="sm" listing={l} />
          </div>
        </div>

        {/* Bottom */}
        <div className="mt-auto space-y-2">
          <p className="text-sm font-semibold text-white leading-snug line-clamp-2 drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">{l.title}</p>

          <div className="flex flex-wrap gap-1 text-[10px]">
            {l.cpu && <span className="bg-black/60 backdrop-blur-sm border border-white/10 rounded px-1.5 py-0.5 text-white/70 font-mono">{l.cpu}</span>}
            {l.gpu && <span className="bg-emerald-500/20 backdrop-blur-sm border border-emerald-400/30 rounded px-1.5 py-0.5 text-emerald-300">{l.gpu}</span>}
            {l.ram_gb && <span className="bg-black/60 backdrop-blur-sm border border-white/10 rounded px-1.5 py-0.5 text-white/60">{l.ram_gb}GB</span>}
            {l.location && <span className="bg-black/60 backdrop-blur-sm border border-white/10 rounded px-1.5 py-0.5 text-white/50">📍 {l.location}</span>}
          </div>

          <div className="flex items-end justify-between">
            <div>
              <div className="text-[9px] text-white/50 uppercase">Buy</div>
              <div className="text-white font-bold text-sm font-mono">{formatCurrency(l.price ?? 0)}</div>
            </div>
            <div className={`text-right ${profitColor}`}>
              <div className="text-[9px] text-white/50 uppercase">Profit</div>
              <div className="font-black text-lg font-mono leading-none drop-shadow-[0_1px_4px_rgba(0,0,0,1)]">{profit > 0 ? "+" : ""}{formatCurrency(profit)}</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <SourceBadge sourceName={l.source_name} url={l.url} />
            <div className="flex items-center gap-1 ml-auto">
              <a href={l.url} target="_blank" rel="noopener noreferrer">
                <Button variant="secondary" size="sm"><ExternalLink className="w-3 h-3" /></Button>
              </a>
              <Button variant="primary" size="sm" disabled={flippingId === l.id} onClick={() => onFlip(l)}>
                {flippingId === l.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                Flip
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Listing row card ──────────────────────────────────────────────────────────

function ListingRow({ listing: l, onFlip, flippingId }: {
  listing: Listing; onFlip: (l: Listing) => void; flippingId: number | null;
}) {
  const profit = l.estimated_profit ?? 0;
  const profitColor = profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400";
  const gemSignals = l.gem_signals ?? [];
  const isAuction = l.listing_type === "auction";
  const alternatives = l.alternatives ?? [];

  return (
    <Card className={
      l.classification === "amazing_gem" ? "border-cyan-400/25" :
      l.classification === "gem" ? "border-emerald-400/20" : ""
    }>
      <CardContent className="p-0">
        <div className="flex items-stretch">
          <div className="w-28 flex-shrink-0 bg-[#080f1a] rounded-l-xl overflow-hidden" style={{ minHeight: 100 }}>
            {l.image_urls[0] ? (
              <img src={l.image_urls[0]} alt={l.title} className="w-full h-full object-contain" loading="lazy" />
            ) : (
              <div className="w-full h-full flex items-center justify-center opacity-15">
                <Gem className="w-6 h-6 text-slate-400" />
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0 p-3 flex items-center gap-4">
            <div className="flex-shrink-0">
              <FlippabilityScore score={l.gem_score} size="lg" listing={l} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap mb-1">
                <ClassificationBadge classification={l.classification} />
                <AuctionBadge listing={l} />
                {gemSignals.slice(0, 3).map(s => (
                  <span key={s} className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-[#00dc82]/8 text-[#00dc82] text-[10px] font-medium border border-[#00dc82]/20">
                    💎 {s}
                  </span>
                ))}
              </div>
              <h3 className="text-sm font-semibold text-slate-100 leading-snug mb-1 line-clamp-1">{l.title}</h3>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500 mb-1.5">
                {l.cpu && <span className="font-mono text-slate-400">{l.cpu}</span>}
                {l.ram_gb && <span>{l.ram_gb}GB {l.ram_type ?? "RAM"}</span>}
                {l.gpu ? <span className="text-emerald-400">{l.gpu}</span> : <span className="text-red-400/70">No GPU</span>}
                {l.storage_gb ? <span>{l.storage_gb}GB {l.storage_type?.toUpperCase() ?? "SSD"}</span> : <span className="text-yellow-400/70">No Storage</span>}
                {l.location && <span>📍 {l.location}</span>}
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                {l.seller_name && <span className="text-[10px] text-slate-500 truncate max-w-28" title={l.seller_name}>{l.seller_name}</span>}
                <SellerBadge listing={l} />
                {l.listed_at && <span className="text-[10px] text-slate-600">Listed {formatRelativeTime(new Date(l.listed_at))}</span>}
                <span className="text-[10px] text-slate-700">Found {formatRelativeTime(new Date(l.first_seen_at))}</span>
              </div>
            </div>
            <div className="flex-shrink-0 flex flex-col items-end gap-1.5">
              <SourceBadge sourceName={l.source_name} url={l.url} />
              {(l.resale_comp_count ?? 0) > 0 && (
                <span className="text-[9px] text-[#00dc82]/70">{l.resale_comp_count} live comps</span>
              )}
            </div>
            <div className="flex-shrink-0 text-right min-w-32">
              <div className="text-[10px] text-slate-500 mb-0.5">{isAuction ? "Auction" : "Buy price"}</div>
              <AuctionPriceDisplay listing={l} />
              <div className="text-[10px] text-slate-500 mt-1.5">Resale est.</div>
              <div className="text-sm font-semibold text-slate-300">{formatCurrency(l.estimated_resale ?? 0)}</div>
              {l.resale_low != null && l.resale_high != null && l.resale_low !== l.resale_high && (
                <div className="text-[9px] text-slate-600">{formatCurrency(l.resale_low)}–{formatCurrency(l.resale_high)}</div>
              )}
              <div className={`text-base font-black mt-1 ${profitColor}`}>{profit > 0 ? "+" : ""}{formatCurrency(profit)}</div>
              <div className="text-[10px] text-slate-600">est. profit</div>
            </div>
            <div className="flex-shrink-0 flex flex-col gap-2 min-w-20">
              <Button variant="primary" size="sm" disabled={flippingId === l.id} onClick={() => onFlip(l)}>
                {flippingId === l.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                Flip
              </Button>
              <a href={l.url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm" className="w-full justify-center">
                  <ExternalLink className="w-3.5 h-3.5" /> View
                </Button>
              </a>
            </div>
          </div>
          {alternatives.length > 0 && (
            <div className="px-3 pb-2.5 flex items-center gap-2 flex-wrap border-t border-white/[0.04] pt-2">
              <span className="text-[10px] text-slate-600 flex items-center gap-1 flex-shrink-0">
                <Copy className="w-2.5 h-2.5" /> Also listed on
              </span>
              {alternatives.map(alt => (
                <a key={alt.id} href={alt.url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[#0d1a2a] border border-[#1e2d45] text-[10px] text-slate-400 hover:border-amber-400/40 hover:text-amber-300 transition-colors">
                  {alt.source_name}
                  <span className="text-amber-400/80 font-semibold">£{alt.price.toFixed(0)}</span>
                  <ExternalLink className="w-2 h-2 opacity-50" />
                </a>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// CANONICAL COMPONENT CATALOGUE (live price tracker per model)
// ══════════════════════════════════════════════════════════════════════════════

type LivePriceRow = {
  model: string;
  tier: "budget" | "mid" | "high" | "ultra";
  new_price: number | null;
  new_count: number;
  used_median: number | null;
  used_count: number;
  used_cheapest_price: number | null;
  used_cheapest_url: string | null;
  used_cheapest_title: string | null;
  used_cheapest_image: string | null;
  discount_pct: number | null;
  gem_classification: "super_gem" | "gem" | null;
};

const CAT_TABS = [
  { id: "gpu",         label: "GPU",         emoji: "🎮" },
  { id: "cpu",         label: "CPU",         emoji: "⚡" },
  { id: "ram",         label: "RAM",         emoji: "💾" },
  { id: "ssd",         label: "SSD",         emoji: "💿" },
  { id: "psu",         label: "PSU",         emoji: "🔌" },
  { id: "motherboard", label: "Motherboard", emoji: "🔧" },
  { id: "cooler",      label: "Cooler",      emoji: "❄️" },
] as const;

type CatId = typeof CAT_TABS[number]["id"];

const TIER_COLORS: Record<string, string> = {
  budget: "text-slate-400",
  mid:    "text-blue-400",
  high:   "text-purple-400",
  ultra:  "text-amber-400",
};

const TIER_BG: Record<string, string> = {
  budget: "bg-slate-700/30 border-slate-600/30",
  mid:    "bg-blue-900/20 border-blue-700/30",
  high:   "bg-purple-900/20 border-purple-700/30",
  ultra:  "bg-amber-900/20 border-amber-700/30",
};

function LiveComponentCard({ row }: { row: LivePriceRow }) {
  const isSuperGem = row.gem_classification === "super_gem";
  const isGem      = row.gem_classification === "gem" || isSuperGem;

  return (
    <div className={`flex flex-col rounded-xl border overflow-hidden transition-colors hover:border-opacity-60 ${
      isSuperGem ? "border-cyan-400/35 shadow-[0_2px_20px_rgba(34,211,238,0.10)]" :
      isGem      ? "border-emerald-400/30 shadow-[0_2px_16px_rgba(52,211,153,0.08)]" :
      "border-[#1e2d45]"
    } bg-[#080f1c]`}>

      {/* Image area */}
      <div className="relative w-full h-36 bg-[#040912] overflow-hidden">
        {row.used_cheapest_image ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={row.used_cheapest_image}
            alt={row.model}
            className="w-full h-full object-contain opacity-85"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-10 h-10 text-slate-700" />
          </div>
        )}

        {/* Gem badge */}
        {isGem && (
          <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md backdrop-blur-sm border text-[9px] font-bold uppercase tracking-wider ${
            isSuperGem
              ? "bg-cyan-400/25 border-cyan-400/50 text-cyan-200"
              : "bg-emerald-400/25 border-emerald-400/50 text-emerald-200"
          }`}>
            <Zap className={`w-2.5 h-2.5 ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`} />
            {isSuperGem ? "Super Gem" : "Gem"}
          </div>
        )}

        {/* Discount badge */}
        {row.discount_pct != null && (
          <div className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-black ${
            isSuperGem ? "bg-cyan-400/20 text-cyan-300" :
            isGem      ? "bg-emerald-400/15 text-emerald-300" :
            "bg-slate-700/60 text-slate-400"
          }`}>
            -{row.discount_pct.toFixed(0)}%
          </div>
        )}

        {/* Tier chip */}
        <div className={`absolute bottom-2 left-2 px-1.5 py-0.5 rounded border text-[9px] font-mono uppercase tracking-wider ${TIER_BG[row.tier] || "bg-slate-800/60 border-slate-600/30 text-slate-400"} ${TIER_COLORS[row.tier] || "text-slate-400"}`}>
          {row.tier}
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-col flex-1 p-3 gap-2.5">
        <p className="text-sm font-semibold text-slate-100 leading-snug line-clamp-2">{row.model}</p>

        {/* Price breakdown — this IS the gem justification */}
        <div className="space-y-1.5">
          {/* Used median (market average) */}
          {row.used_median != null && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500 font-mono">Market avg ({row.used_count} listings)</span>
              <span className="text-xs text-slate-300 font-mono">£{row.used_median.toFixed(0)}</span>
            </div>
          )}

          {/* New price */}
          {row.new_price != null && (
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500 font-mono">New ({row.new_count} listings)</span>
              <span className="text-xs text-slate-400 font-mono">£{row.new_price.toFixed(0)}</span>
            </div>
          )}

          {/* Best deal */}
          {row.used_cheapest_price != null && (
            <div className={`flex items-center justify-between rounded px-2 py-1 -mx-0.5 ${
              isGem
                ? isSuperGem ? "bg-cyan-400/8" : "bg-emerald-400/8"
                : "bg-white/[0.03]"
            }`}>
              <span className={`text-[10px] font-mono font-semibold ${
                isSuperGem ? "text-cyan-400" : isGem ? "text-emerald-400" : "text-slate-400"
              }`}>
                Best deal
                {row.discount_pct != null && (
                  <span className="ml-1 opacity-80">(-{row.discount_pct.toFixed(0)}% vs avg)</span>
                )}
              </span>
              {row.used_cheapest_url ? (
                <a
                  href={row.used_cheapest_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`text-xs font-mono font-bold inline-flex items-center gap-0.5 hover:underline ${
                    isSuperGem ? "text-cyan-300" : isGem ? "text-emerald-300" : "text-slate-300"
                  }`}
                >
                  £{row.used_cheapest_price.toFixed(0)}
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              ) : (
                <span className={`text-xs font-mono font-bold ${
                  isSuperGem ? "text-cyan-300" : isGem ? "text-emerald-300" : "text-slate-300"
                }`}>
                  £{row.used_cheapest_price.toFixed(0)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Listing title */}
        {row.used_cheapest_title && (
          <p className="text-[9px] text-slate-600 line-clamp-2 font-mono italic mt-auto">
            {row.used_cheapest_title}
          </p>
        )}

        {(!row.used_median && !row.new_price) && (
          <p className="text-[10px] text-slate-700 font-mono mt-auto">No listings found yet</p>
        )}
      </div>
    </div>
  );
}

// ── Paste scanner types ─────────────────────────────────────────────────────

type PasteItem = {
  name: string;
  category: string;
  price: number;
  condition: string;
  verdict: "GEM" | "GOOD" | "REJECT";
  market_price_estimate: number;
  confidence: number;
  reasoning: string;
  gem_classification: "super_gem" | "gem" | null;
  source: string;
};

type PasteResult = {
  parsed: number;
  kept: number;
  gems: number;
  super_gems: number;
  model_used: string;
  items: PasteItem[];
  error?: string;
};

function PasteScanner({ onGemsSaved }: { onGemsSaved: () => void }) {
  const [open, setOpen]         = useState(false);
  const [text, setText]         = useState("");
  const [source, setSource]     = useState("eBay UK");
  const [scanning, setScanning] = useState(false);
  const [result, setResult]     = useState<PasteResult | null>(null);

  const scan = async () => {
    if (!text.trim()) return;
    setScanning(true);
    setResult(null);
    try {
      const res = await fetch("/api/parts/paste-scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source }),
      });
      const data = await res.json();
      setResult(data);
      if (data.gems > 0) onGemsSaved();
    } catch {
      setResult({ parsed: 0, kept: 0, gems: 0, super_gems: 0, model_used: "", items: [], error: "Request failed" });
    } finally {
      setScanning(false);
    }
  };

  const gems    = result?.items.filter(i => i.verdict === "GEM")  || [];
  const goods   = result?.items.filter(i => i.verdict === "GOOD") || [];
  const rejects = result?.items.filter(i => i.verdict === "REJECT") || [];

  return (
    <div className="rounded-xl border border-[#1e2d45] overflow-hidden">
      {/* Header toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#080f1c] hover:bg-[#0c1526] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">📋</span>
          <span className="text-sm font-mono font-medium text-slate-300">Paste Scanner</span>
          <span className="text-xs text-slate-600 font-mono">— paste eBay search results to find gems</span>
        </div>
        <span className="text-slate-600 text-xs font-mono">{open ? "▲ close" : "▼ open"}</span>
      </button>

      {open && (
        <div className="p-4 border-t border-[#1e2d45] space-y-4">
          {/* Source selector + textarea */}
          <div className="flex gap-3 items-start">
            <div className="flex flex-col gap-1 shrink-0">
              <label className="text-[10px] text-slate-600 font-mono uppercase">Source</label>
              <select
                value={source}
                onChange={e => setSource(e.target.value)}
                className="text-xs font-mono bg-[#0c1526] border border-[#1e2d45] rounded-lg px-2 py-1.5 text-slate-300"
              >
                <option>eBay UK</option>
                <option>Gumtree</option>
                <option>Facebook Marketplace</option>
                <option>BargainHardware</option>
                <option>Preloved</option>
                <option>Manual</option>
              </select>
            </div>
            <div className="flex-1 flex flex-col gap-1">
              <label className="text-[10px] text-slate-600 font-mono uppercase">Paste search results text</label>
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                placeholder={"Paste raw text from eBay or any marketplace search page here…\n\nTip: select all on the search results page (Ctrl+A), copy, paste here. The AI will extract component listings automatically."}
                rows={8}
                className="w-full text-xs font-mono bg-[#0c1526] border border-[#1e2d45] rounded-lg px-3 py-2 text-slate-300 placeholder-slate-700 resize-y focus:outline-none focus:border-[#1e3a5a]"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={scan}
              disabled={scanning || !text.trim()}
              className="font-mono"
            >
              {scanning ? (
                <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Scanning…</>
              ) : (
                "🔍 Find Gems"
              )}
            </Button>
            {result && !result.error && (
              <span className="text-xs font-mono text-slate-400">
                Parsed <b className="text-slate-200">{result.parsed}</b> components
                {result.gems > 0 && (
                  <>, found <b className="text-emerald-400">{result.gems} gem{result.gems !== 1 ? "s" : ""}</b>
                  {result.super_gems > 0 && <> (<b className="text-cyan-400">{result.super_gems} super gem{result.super_gems !== 1 ? "s" : ""}</b>)</>}
                  </>
                )}
                {result.gems === 0 && result.parsed > 0 && <>, <span className="text-slate-600">no gems found</span></>}
                <span className="text-slate-700 ml-2">via {result.model_used}</span>
              </span>
            )}
            {result?.error && <span className="text-xs text-red-400 font-mono">{result.error}</span>}
          </div>

          {/* Results breakdown */}
          {result && !result.error && result.parsed > 0 && (
            <div className="space-y-2">
              {/* Gems */}
              {gems.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-mono text-emerald-500 uppercase tracking-wider px-1">
                    💎 Gems — added to catalogue
                  </div>
                  {gems.map((item, i) => (
                    <div key={i} className="flex items-start gap-3 px-3 py-2 bg-emerald-950/20 border border-emerald-800/30 rounded-lg">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2">
                          {item.gem_classification === "super_gem" && (
                            <span className="text-[10px] text-cyan-400 font-bold">⚡ SUPER</span>
                          )}
                          <span className="text-sm font-mono text-slate-200 truncate">{item.name}</span>
                          <span className="text-xs font-mono text-emerald-400 font-bold">£{item.price.toFixed(0)}</span>
                          <span className="text-[10px] text-slate-600">vs £{item.market_price_estimate.toFixed(0)} market</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5 italic line-clamp-1">{item.reasoning}</p>
                      </div>
                      <span className="text-[10px] font-mono text-slate-600 uppercase shrink-0">{item.category}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Good deals */}
              {goods.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-mono text-blue-500 uppercase tracking-wider px-1">
                    ✓ Good deals — saved
                  </div>
                  {goods.map((item, i) => (
                    <div key={i} className="flex items-start gap-3 px-3 py-2 bg-blue-950/10 border border-blue-800/20 rounded-lg">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2">
                          <span className="text-sm font-mono text-slate-300 truncate">{item.name}</span>
                          <span className="text-xs font-mono text-blue-400">£{item.price.toFixed(0)}</span>
                          <span className="text-[10px] text-slate-600">vs £{item.market_price_estimate.toFixed(0)} market</span>
                        </div>
                        <p className="text-[10px] text-slate-500 mt-0.5 italic line-clamp-1">{item.reasoning}</p>
                      </div>
                      <span className="text-[10px] font-mono text-slate-600 uppercase shrink-0">{item.category}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Rejected items — collapsed summary */}
              {rejects.length > 0 && (
                <details className="text-[10px] font-mono text-slate-700">
                  <summary className="cursor-pointer hover:text-slate-600 px-1">
                    {rejects.length} item{rejects.length !== 1 ? "s" : ""} rejected (not gems or not PC components)
                  </summary>
                  <div className="mt-1 pl-3 space-y-0.5">
                    {rejects.map((item, i) => (
                      <div key={i} className="text-slate-700">
                        {item.name || "(unidentified)"} — {item.reasoning?.slice(0, 80)}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          {result && !result.error && result.parsed === 0 && (
            <p className="text-xs text-slate-600 font-mono">
              No PC component listings found in the pasted text. Try pasting from an eBay search results page.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function CatalogueTab() {
  const [liveRows, setLiveRows]     = useState<LivePriceRow[] | null>(null);
  const [loading, setLoading]       = useState(false);
  const [activeCategory, setActiveCategory] = useState<CatId>("gpu");
  const [tierFilter, setTierFilter] = useState<string>("all");

  // Client-side cache so tab switches don't re-trigger a 15s scrape
  const cache = useRef<Partial<Record<CatId, LivePriceRow[]>>>({});

  const load = useCallback(async (cat: CatId, forceRefresh = false) => {
    if (!forceRefresh && cache.current[cat]) {
      setLiveRows(cache.current[cat]!);
      return;
    }
    setLoading(true);
    setLiveRows(null);
    try {
      const qs = forceRefresh ? `?category=${cat}&refresh=true` : `?category=${cat}`;
      const res = await fetch(`/api/parts/live-prices${qs}`);
      if (res.ok) {
        const data: LivePriceRow[] = await res.json();
        cache.current[cat] = data;
        setLiveRows(data);
      }
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(activeCategory); }, [activeCategory, load]);

  const handleCategoryChange = (cat: CatId) => {
    setActiveCategory(cat);
    setTierFilter("all");
  };

  const rows = useMemo(() => {
    if (!liveRows) return [];
    return tierFilter === "all" ? liveRows : liveRows.filter(r => r.tier === tierFilter);
  }, [liveRows, tierFilter]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500 font-mono">
          {loading
            ? "Fetching live prices from eBay and retailers…"
            : liveRows
              ? `${rows.length} models · live prices fetched`
              : "Select a category to fetch live prices"
          }
        </p>
        <Button
          variant="secondary" size="sm"
          onClick={() => void load(activeCategory, true)}
          disabled={loading}
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Fetching…" : "Refresh Live"}
        </Button>
      </div>

      {/* Paste scanner */}
      <PasteScanner onGemsSaved={() => {}} />

      {/* Category sub-tabs */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {CAT_TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleCategoryChange(tab.id)}
            className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-mono font-medium whitespace-nowrap transition-all ${
              activeCategory === tab.id
                ? "bg-[var(--nf-primary)]/15 text-[var(--nf-primary)] border border-[var(--nf-primary)]/30"
                : "text-slate-500 hover:text-slate-300 border border-transparent"
            }`}
          >
            <span>{tab.emoji}</span> {tab.label}
            {cache.current[tab.id] && (
              <span className="ml-1 text-[10px] opacity-60">
                ({cache.current[tab.id]!.length})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tier filter */}
      <div className="flex gap-2 items-center">
        <span className="text-xs text-slate-600 font-mono">Tier:</span>
        {["all", "budget", "mid", "high", "ultra"].map(t => (
          <button
            key={t}
            onClick={() => setTierFilter(t)}
            className={`px-2.5 py-0.5 rounded-full text-xs font-mono transition-all ${
              tierFilter === t
                ? "bg-slate-700 text-slate-200"
                : "text-slate-600 hover:text-slate-400"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Price table */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-[var(--nf-primary)]" />
          <div className="text-center">
            <p className="text-slate-300 text-sm font-mono">Fetching live prices…</p>
            <p className="text-slate-600 text-xs mt-1 font-mono">
              Scraping eBay BIN listings and UK retail sites
            </p>
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[#1e2d45]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2d45] bg-[#0a1628]">
                <th className="text-left px-4 py-3 text-xs text-slate-500 font-mono font-medium">Product</th>
                <th className="text-center px-3 py-3 text-xs text-slate-500 font-mono font-medium">Tier</th>
                <th className="text-right px-3 py-3 text-xs text-slate-500 font-mono font-medium">RRP</th>
                <th className="text-right px-3 py-3 text-xs text-slate-500 font-mono font-medium">eBay Price</th>
                <th className="text-right px-4 py-3 text-xs text-slate-500 font-mono font-medium">Lowest Found</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-600 font-mono text-sm">
                    {liveRows
                      ? "No models match this filter"
                      : "Select a category — prices will be fetched live"
                    }
                  </td>
                </tr>
              ) : rows.map((row, i) => {
                const goodDeal = row.ebay_used && row.rrp && row.ebay_used < row.rrp * 0.65;
                return (
                  <tr
                    key={row.model}
                    className={`border-b border-[#1e2d45] transition-colors ${
                      goodDeal
                        ? "bg-emerald-950/15 hover:bg-emerald-950/25"
                        : i % 2 === 0 ? "bg-[#080f1c] hover:bg-[#0c1526]" : "hover:bg-[#0c1526]"
                    }`}
                  >
                    {/* Product */}
                    <td className="px-4 py-2.5">
                      <span className={`font-mono text-sm ${row.ebay_used ? "text-slate-200" : "text-slate-500"}`}>
                        {row.model}
                      </span>
                    </td>

                    {/* Tier */}
                    <td className="px-3 py-2.5 text-center">
                      <span className={`text-[10px] font-mono uppercase tracking-wider ${TIER_COLORS[row.tier] || "text-slate-500"}`}>
                        {row.tier}
                      </span>
                    </td>

                    {/* RRP */}
                    <td className="px-3 py-2.5 text-right">
                      {row.rrp ? (
                        <div className="inline-flex items-baseline gap-1">
                          <span className="font-mono text-sm text-slate-400">£{row.rrp.toFixed(0)}</span>
                          {row.rrp_source && (
                            <span className="text-[9px] text-slate-600 font-mono">{row.rrp_source}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>

                    {/* eBay Price */}
                    <td className="px-3 py-2.5 text-right">
                      {row.ebay_used ? (
                        <div className="inline-flex flex-col items-end gap-0.5">
                          {row.ebay_url ? (
                            <a
                              href={row.ebay_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-mono text-sm text-slate-300 hover:text-slate-100 hover:underline"
                            >
                              £{row.ebay_used.toFixed(0)}
                            </a>
                          ) : (
                            <span className="font-mono text-sm text-slate-300">£{row.ebay_used.toFixed(0)}</span>
                          )}
                          {row.rrp && (
                            <span className="text-[9px] text-slate-600 font-mono">
                              {Math.round((1 - row.ebay_used / row.rrp) * 100)}% off RRP
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-600 text-xs">—</span>
                      )}
                    </td>

                    {/* Lowest Found */}
                    <td className="px-4 py-2.5 text-right">
                      <LowestPriceCell
                        price={row.lowest_price}
                        url={row.lowest_url}
                        title={row.lowest_title}
                        source={row.lowest_source}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Legend */}
      {!loading && liveRows && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-600 font-mono">
          <span>RRP = UK new retail (Scan/Overclockers, or AI estimate)</span>
          <span>eBay Price = cheapest live BIN used listing</span>
          <span>Lowest Found = absolute cheapest — hover for preview, click to open</span>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// PARTS CATALOGUE TABS (Components / PC Cases / Accessories)
// ══════════════════════════════════════════════════════════════════════════════

type PartsTabCategory = "components" | "cases" | "accessories";

const PARTS_TAB_CONFIG: Record<PartsTabCategory, {
  apiCategory: string | undefined;
  filterCategory?: string;
  swarm: string;
  icon: LucideIcon;
  emptyTitle: string;
  emptyDesc: string;
}> = {
  components: {
    apiCategory: undefined,          // backend returns all-except-cases
    filterCategory: "accessory",     // exclude accessories from this view
    swarm: "upgrade_parts",
    icon: Package,
    emptyTitle: "No components tracked yet",
    emptyDesc: 'Click "Refresh Prices" to scrape eBay sold listings for median component prices.',
  },
  cases: {
    apiCategory: "case",
    swarm: "cases",
    icon: Package,
    emptyTitle: "No PC cases tracked yet",
    emptyDesc: 'Click "Refresh Prices" to fetch current case prices from eBay.',
  },
  accessories: {
    apiCategory: "accessory",
    swarm: "accessories",
    icon: Package,
    emptyTitle: "No accessories tracked yet",
    emptyDesc: 'Click "Refresh Prices" to fetch current accessory prices from eBay.',
  },
};

type GemFilter = "all" | "gem" | "super_gem";

function PartsTab({ category }: { category: PartsTabCategory }) {
  const cfg = PARTS_TAB_CONFIG[category];
  const [parts, setParts]         = useState<GroupedPart[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery]         = useState("");
  const [gemFilter, setGemFilter] = useState<GemFilter>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.parts.grouped(cfg.apiCategory) as GroupedPart[];
      // For "components" tab, strip out accessories (they have their own tab)
      const filtered = cfg.filterCategory
        ? data.filter(p => p.category !== cfg.filterCategory)
        : data;
      setParts(filtered);
    } catch {
      setParts([]);
    } finally {
      setLoading(false);
    }
  }, [cfg]);

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try { await api.swarms.trigger(cfg.swarm); await load(); }
    catch { } finally { setRefreshing(false); }
  };

  const gemCounts = useMemo(() => ({
    gem: parts.filter(p => (p.gem_classification === "gem" || p.gem_classification === "super_gem") && p.claude_verdict !== "REJECT").length,
    super_gem: parts.filter(p => p.gem_classification === "super_gem" && p.claude_verdict !== "REJECT").length,
  }), [parts]);

  const filtered = useMemo(() => {
    let result = parts;
    if (gemFilter === "super_gem") result = result.filter(p => p.gem_classification === "super_gem" && p.claude_verdict !== "REJECT");
    else if (gemFilter === "gem") result = result.filter(p => (p.gem_classification === "gem" || p.gem_classification === "super_gem") && p.claude_verdict !== "REJECT");
    if (query.trim()) {
      const q = query.toLowerCase();
      result = result.filter(p => p.name.toLowerCase().includes(q));
    }
    return result;
  }, [parts, query, gemFilter]);

  return (
    <div className="space-y-4">
      {/* Gem filter chips */}
      {category === "components" && (
        <div className="flex gap-2 flex-wrap">
          {([
            { value: "all",       label: "All parts" },
            { value: "gem",       label: `💎 Gems (${gemCounts.gem})` },
            { value: "super_gem", label: `⚡ Super Gems (${gemCounts.super_gem})` },
          ] as { value: GemFilter; label: string }[]).map(f => (
            <button
              key={f.value}
              onClick={() => setGemFilter(f.value)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                gemFilter === f.value
                  ? f.value === "super_gem"
                    ? "bg-cyan-500/15 text-cyan-300 border-cyan-400/40"
                    : f.value === "gem"
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-400/40"
                      : "bg-[#00dc82]/10 text-[#00dc82] border-[#00dc82]/30"
                  : "text-slate-500 border-[#1e2d45] hover:border-slate-600 hover:text-slate-400"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
          <input
            type="text" value={query} onChange={e => setQuery(e.target.value)}
            placeholder="Search parts…"
            className="w-full pl-9 pr-8 py-2 rounded-lg bg-[#0a1119] border border-[#1e2d45] text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-[#00dc82]/40 focus:ring-1 focus:ring-[#00dc82]/20 transition-colors"
          />
          {query && (
            <button onClick={() => setQuery("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <p className="text-xs text-slate-600 font-mono">
            {filtered.length}{query ? ` of ${parts.length}` : ""} items
          </p>
          <Button variant="secondary" size="sm" onClick={refresh} disabled={refreshing}>
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Updating…" : "Refresh Prices"}
          </Button>
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={cfg.icon}
          title={query ? "No parts match your search" : cfg.emptyTitle}
          description={query ? `No parts found for "${query}". Try a different search term.` : cfg.emptyDesc}
          action={query ? { label: "Clear Search", onClick: () => setQuery("") } : { label: "Fetch Prices", onClick: refresh }}
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

// ── Part card ─────────────────────────────────────────────────────────────────

function PartCard({ part }: { part: GroupedPart }) {
  const bestPrice = part.cheapest_good_price ?? part.cheapest_price ?? 0;
  const isSuperGem = part.gem_classification === "super_gem";
  const isGem = part.gem_classification === "gem" || isSuperGem;
  const aiVerified = part.claude_verdict === "GEM" || part.claude_verdict === "GOOD";
  const aiRejected = part.claude_verdict === "REJECT";
  // Only show gem badge if rule-based AND not AI-rejected
  const showGemBadge = isGem && !aiRejected;

  return (
    <div className={`flex flex-col rounded-xl glass-card hover:border-[var(--nf-border-strong)] transition-colors overflow-hidden ${
      showGemBadge && isSuperGem ? "border-cyan-400/30 shadow-[0_2px_16px_rgba(34,211,238,0.08)]" :
      showGemBadge ? "border-emerald-400/20 shadow-[0_2px_16px_rgba(52,211,153,0.06)]" : ""
    }`}>
      {/* Image */}
      <div className="w-full h-36 bg-[#070d14] border-b border-[#1e2d45] flex items-center justify-center overflow-hidden relative">
        {part.image_url ? (
          <img src={part.image_url} alt={part.name} className="w-full h-full object-contain opacity-80" />
        ) : (
          <Package className="w-10 h-10 text-slate-700" />
        )}
        {/* Gem badge overlay */}
        {showGemBadge && (
          <div className={`absolute top-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md backdrop-blur-sm border text-[9px] font-bold uppercase tracking-wider ${
            isSuperGem
              ? "bg-cyan-400/20 border-cyan-400/40 text-cyan-200"
              : "bg-emerald-400/20 border-emerald-400/40 text-emerald-200"
          }`}>
            <Zap className={`w-2.5 h-2.5 ${isSuperGem ? "text-cyan-300" : "text-emerald-300"}`} />
            {isSuperGem ? "Super Gem" : "Gem"}
          </div>
        )}
        {/* Pending AI badge for rule-based gems not yet evaluated */}
        {isGem && !aiVerified && !aiRejected && (
          <div className="absolute bottom-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-slate-700/60 border border-slate-500/30 text-[8px] text-slate-400 uppercase tracking-wide">
            ⏳ AI pending
          </div>
        )}
        {/* AI verified badge */}
        {showGemBadge && aiVerified && (
          <div className="absolute bottom-2 left-2 flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-violet-500/20 border border-violet-400/40 text-[8px] text-violet-300 uppercase tracking-wide">
            ✓ AI verified
          </div>
        )}
        {/* Discount score */}
        {showGemBadge && part.gem_score != null && (
          <div className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-black ${
            isSuperGem ? "bg-cyan-400/15 text-cyan-300" : "bg-emerald-400/15 text-emerald-300"
          }`}>
            -{part.gem_score.toFixed(0)}% vs median
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-col flex-1 p-3 gap-2">
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
          <div className={`rounded-md px-2 py-1 ${isGem ? (isSuperGem ? "bg-cyan-400/8 border border-cyan-400/20" : "bg-emerald-400/8 border border-emerald-400/20") : "bg-[#00dc82]/5 border border-[#00dc82]/20"}`}>
            <div className="text-slate-600 text-[9px] uppercase tracking-wide">{part.cheapest_good_price ? "Best (trusted)" : "Best"}</div>
            <div className={`font-bold ${isSuperGem ? "text-cyan-300" : isGem ? "text-emerald-300" : "text-[#00dc82]"}`}>{formatCurrency(bestPrice)}</div>
          </div>
        </div>

        {/* Sources */}
        {part.all_sources.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-1">
            {part.all_sources.slice(0, 4).map((s, i) =>
              s.url ? (
                <a key={i} href={s.url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#0a1119] border border-[#1e2d45] hover:border-[#1e3a5a] text-[10px] text-slate-400 hover:text-slate-200 transition-colors">
                  {s.source}
                  {s.price != null && <span className="text-[#00dc82]">{formatCurrency(s.price)}</span>}
                </a>
              ) : (
                <span key={i} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#0a1119] border border-[#1e2d45] text-[10px] text-slate-500">
                  {s.source}
                  {s.price != null && <span className="text-slate-400">{formatCurrency(s.price)}</span>}
                </span>
              )
            )}
          </div>
        )}

        {/* AI reasoning */}
        {part.claude_reasoning && showGemBadge && (
          <p className="text-[9px] text-slate-500 italic line-clamp-2 border-t border-white/[0.04] pt-1.5">
            {part.claude_reasoning}
          </p>
        )}

        {/* Footer */}
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
