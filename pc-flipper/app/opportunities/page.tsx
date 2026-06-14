"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Gem, RefreshCw, ExternalLink, Zap, Search, SlidersHorizontal,
  ChevronLeft, ChevronRight, ArrowUpDown, X, PlusCircle, Copy,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ClassificationBadge } from "@/components/classification-badge";
import { FlippabilityScore } from "@/components/flippability-score";
import { SourceBadge } from "@/components/source-badge";
import { EmptyState } from "@/components/empty-state";
import { SellerBadge } from "@/components/seller-badge";
import { AuctionBadge, AuctionPriceDisplay } from "@/components/auction-display";
import { Listing, Classification, CLASSIFICATION_CONFIG } from "@/lib/types";
import { api } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { ManualSubmitModal } from "@/components/manual-submit-modal";

// ── Constants ─────────────────────────────────────────────────────────────────

const CLASS_FILTERS: (Classification | "all")[] = [
  "all", "amazing_gem", "gem", "already_flipped", "no_profit", "overpriced",
];

const SELLER_TYPE_OPTIONS = [
  { value: "all",        label: "All sellers" },
  { value: "private",    label: "👤 Private"   },
  { value: "flipper",    label: "🔄 Flipper"   },
  { value: "shop",       label: "🏪 Shop"      },
  { value: "refurb_shop",label: "🔧 Refurb"   },
];

const SORT_OPTIONS = [
  { value: "gem_score",         label: "Flippability ↓" },
  { value: "estimated_profit",  label: "Profit ↓"       },
  { value: "price",             label: "Price ↑"         },
  { value: "first_seen_at",     label: "Newest first"    },
];

const PAGE_SIZES = [20, 50, 100];

// ── Main page ─────────────────────────────────────────────────────────────────

export default function OpportunitiesPage() {
  // Filter state
  const [classFilter, setClassFilter] = useState<Classification | "all">("all");
  const [search, setSearch] = useState("");
  const [minProfit, setMinProfit] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sellerTypeFilter, setSellerTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("gem_score");
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Data
  const [listings, setListings] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [sources, setSources] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [flippingId, setFlippingId] = useState<number | null>(null);
  const [showManualSubmit, setShowManualSubmit] = useState(false);

  // Debounce search
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 350);
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current); };
  }, [search]);

  // Reset page when filters change
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

      // Client-side seller_type filter (not yet in backend API)
      const filtered = sellerTypeFilter === "all"
        ? data
        : data.filter(l => l.seller_type === sellerTypeFilter);

      setListings(filtered);
      // Approximate total — backend returns up to pageSize, use length heuristic
      setTotal(prev => page === 1 ? (data.length < pageSize ? data.length : prev || data.length * 3) : prev);

      // Collect unique sources for dropdown (first load only)
      if (page === 1 && sources.length === 0) {
        const allSources = await api.listings.list({ limit: "500", status: "active" }) as Listing[];
        const uniqueSources = [...new Set(allSources.map(l => l.source_name))].sort();
        setSources(uniqueSources);
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
    try {
      await api.flips.create({ listing_id: listing.id });
      window.location.href = "/flips";
    } catch { setFlippingId(null); }
  };

  const hasAdvancedFilters = minProfit || maxPrice || sourceFilter !== "all" || sellerTypeFilter !== "all";
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="p-6 space-y-5">
      <ManualSubmitModal
        open={showManualSubmit}
        onClose={() => setShowManualSubmit(false)}
        onSuccess={() => { setShowManualSubmit(false); load(); }}
      />
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Gem className="w-5 h-5 text-[var(--nf-primary)]" /> Sourcing
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            {listings.length} listings shown · sorted by {SORT_OPTIONS.find(o => o.value === sortBy)?.label}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
            <PlusCircle className="w-3.5 h-3.5" />
            Submit Manually
          </Button>
          <Button variant="secondary" size="sm" onClick={trigger} disabled={triggering}>
            <RefreshCw className={`w-3.5 h-3.5 ${triggering ? "animate-spin" : ""}`} />
            {triggering ? "Scanning…" : "Scan Sources"}
          </Button>
        </div>
      </div>

      {/* ── Classification tabs ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {CLASS_FILTERS.map(cls => {
          const cfg = cls !== "all" ? CLASSIFICATION_CONFIG[cls] : null;
          return (
            <button
              key={cls}
              onClick={() => setClassFilter(cls)}
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

      {/* ── Search + sort row ───────────────────────────────────────────────── */}
      <div className="flex gap-2 items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search title, CPU, GPU, location…"
            className="w-full pl-10 pr-4 py-2.5 bg-[#0d1320] border border-[#1e2d45] rounded-xl text-sm text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
        <div className="flex items-center gap-1 bg-[#0d1320] border border-[#1e2d45] rounded-xl px-2">
          <ArrowUpDown className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="bg-transparent py-2.5 pr-1 text-xs text-slate-300 outline-none"
          >
            {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* ── Advanced filters panel ──────────────────────────────────────────── */}
      {filtersOpen && (
        <div className="bg-[#0d1a2a] border border-white/[0.06] rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {/* Min profit */}
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Min profit (£)</label>
            <input
              type="number"
              value={minProfit}
              onChange={e => setMinProfit(e.target.value)}
              placeholder="e.g. 50"
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
            />
          </div>
          {/* Max price */}
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Max buy price (£)</label>
            <input
              type="number"
              value={maxPrice}
              onChange={e => setMaxPrice(e.target.value)}
              placeholder="e.g. 300"
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#00dc82]/50"
            />
          </div>
          {/* Source */}
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Source</label>
            <select
              value={sourceFilter}
              onChange={e => setSourceFilter(e.target.value)}
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
            >
              <option value="all">All sources</option>
              {sources.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {/* Seller type */}
          <div>
            <label className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 block">Seller type</label>
            <select
              value={sellerTypeFilter}
              onChange={e => setSellerTypeFilter(e.target.value)}
              className="w-full bg-[#0a1119] border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 outline-none focus:border-[#00dc82]/50"
            >
              {SELLER_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {/* Clear filters */}
          {hasAdvancedFilters && (
            <div className="col-span-full flex justify-end">
              <button
                onClick={() => {
                  setMinProfit(""); setMaxPrice("");
                  setSourceFilter("all"); setSellerTypeFilter("all");
                }}
                className="text-[10px] text-slate-500 hover:text-red-400 transition-colors"
              >
                × Clear all filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Results ─────────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : listings.length === 0 ? (
        <EmptyState
          icon={Gem}
          title="No listings found"
          description="Try adjusting your filters, or run a scan to discover fresh opportunities."
          action={{ label: "Run Scan Now", onClick: trigger }}
        />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {listings.map(listing => (
              <ListingGridCard
                key={listing.id}
                listing={listing}
                onFlip={handleFlip}
                flippingId={flippingId}
              />
            ))}
          </div>

          {/* ── Pagination ───────────────────────────────────────────────────── */}
          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">
                Page {page}{totalPages > 1 ? ` of ${totalPages}` : ""}
              </span>
              <select
                value={pageSize}
                onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}
                className="bg-[#0d1a2a] border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-400 outline-none focus:border-[#00dc82]/50"
              >
                {PAGE_SIZES.map(n => <option key={n} value={n}>{n} / page</option>)}
              </select>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost" size="sm"
                disabled={page === 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </Button>
              {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => i + 1)
                .map(p => (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`w-7 h-7 rounded-lg text-xs transition-colors ${
                      page === p
                        ? "bg-[#00dc82]/20 text-[#00dc82] font-semibold"
                        : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                    }`}
                  >
                    {p}
                  </button>
                ))}
              <Button
                variant="ghost" size="sm"
                disabled={listings.length < pageSize}
                onClick={() => setPage(p => p + 1)}
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Listing Grid Card ────────────────────────────────────────────────────────

function ListingGridCard({
  listing: l,
  onFlip,
  flippingId,
}: {
  listing: Listing;
  onFlip: (l: Listing) => void;
  flippingId: number | null;
}) {
  const profit = l.estimated_profit ?? 0;
  const profitColor =
    profit > 100 ? "text-[#00dc82]" : profit > 0 ? "text-amber-400" : "text-red-400";
  const gemSignals = l.gem_signals ?? [];
  const isAuction = l.listing_type === "auction";

  return (
    <div className={`relative rounded-xl border overflow-hidden flex flex-col h-72 group ${
      l.classification === "amazing_gem" ? "border-cyan-400/25"
      : l.classification === "gem" ? "border-emerald-400/20"
      : "border-[#1e2d45]"
    }`}>
      {/* Full-card background image */}
      {l.image_urls[0] ? (
        <img
          src={l.image_urls[0]}
          alt={l.title}
          className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />
      ) : (
        <div className="absolute inset-0 bg-[#080f1a] flex items-center justify-center opacity-10">
          <Gem className="w-12 h-12 text-slate-400" />
        </div>
      )}

      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/97 via-black/55 to-black/20" />

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full p-3">

        {/* Top: score + badges */}
        <div className="flex items-start justify-between gap-2">
          <FlippabilityScore score={l.gem_score} size="sm" listing={l} />
          <div className="flex gap-1 flex-wrap">
            <ClassificationBadge classification={l.classification} />
            <AuctionBadge listing={l} />
          </div>
        </div>

        {/* Bottom section */}
        <div className="mt-auto space-y-2">
          {/* Title */}
          <h3 className="text-xs font-semibold text-white line-clamp-2 leading-snug drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">
            {l.title}
          </h3>

          {/* Specs chips */}
          <div className="flex flex-wrap gap-1 text-[10px]">
            {l.cpu && <span className="bg-black/60 backdrop-blur-sm border border-white/10 rounded px-1.5 py-0.5 text-white/70 font-mono">{l.cpu.slice(0, 20)}</span>}
            {l.gpu
              ? <span className="bg-emerald-500/20 backdrop-blur-sm border border-emerald-400/30 rounded px-1.5 py-0.5 text-emerald-300">{l.gpu.slice(0, 15)}</span>
              : <span className="bg-red-500/15 backdrop-blur-sm border border-red-400/20 rounded px-1.5 py-0.5 text-red-300/70">No GPU</span>}
            {l.ram_gb && <span className="bg-black/60 backdrop-blur-sm border border-white/10 rounded px-1.5 py-0.5 text-white/60">{l.ram_gb}GB</span>}
          </div>

          {/* Pricing */}
          <div className="flex items-end justify-between gap-2">
            <div>
              <div className="text-[9px] text-white/50 uppercase tracking-wide">Buy · Resale</div>
              <div className="text-white/80 font-semibold text-xs font-mono">
                {formatCurrency(l.price)} · {formatCurrency(l.estimated_resale ?? 0)}
              </div>
            </div>
            <div className={`text-right ${profitColor}`}>
              <div className="text-[9px] text-white/50 uppercase tracking-wide">Profit</div>
              <div className="font-black text-lg font-mono leading-none drop-shadow-[0_1px_4px_rgba(0,0,0,1)]">
                {profit > 0 ? "+" : ""}{formatCurrency(profit)}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant="primary" size="sm"
              className="flex-1 h-8 justify-center"
              disabled={flippingId === l.id}
              onClick={() => onFlip(l)}
            >
              {flippingId === l.id ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              Flip
            </Button>
            <a href={l.url} target="_blank" rel="noopener noreferrer">
              <Button variant="secondary" size="sm" className="h-8 px-3">
                <ExternalLink className="w-3 h-3" />
              </Button>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
