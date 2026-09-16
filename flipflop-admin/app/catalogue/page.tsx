"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown, ChevronLeft, ChevronRight, Eye, EyeOff, Filter,
  Heart, LayoutGrid, List, RefreshCw, Search, SlidersHorizontal, Star, Table2,
} from "lucide-react";
import { api } from "@/lib/api";
import { canonicalVendorKey, VENDOR_META } from "@/lib/vendors";
import { PriceHistorySparkline } from "../../components/listings/PriceHistorySparkline";
import { VendorLogo } from "../../components/VendorLogo";

type ViewMode = "table" | "listings" | "grid";
type CatalogueScope = "all" | "curated";
type Variant = {
  id: number; listing_id?: number | string; listing_title: string; image_url?: string | null; slot_type: string;
  playbook_id: number; status: string; tier: string; display_price: number;
  gem_score: number; consecutive_misses: number; last_seen_at: string;
  source_name?: string | null; channel_sources?: string[];
  price_history_listing_id?: string | null; market_lower_price?: number | null; market_median_price?: number | null; market_upper_price?: number | null;
  cpk?: string | null; watch_count?: number | null; offer_count?: number | null; sold_count?: number | null;
  review_average_rating?: number | null; review_count?: number | null;
  url?: string | null; condition?: string | null; delivered_price?: number | null;
  scored_market_lower_price?: number | null; scored_market_median_price?: number | null; scored_market_upper_price?: number | null;
  pct_offset?: number | null; classification?: string | null; decision?: string | null; confidence?: string | null; deal_score?: number | null;
  evidence_status?: string | null; evidence_reason?: string | null;
};

const fallback: Variant[] = [
  { id: 1, listing_title: "AMD Ryzen 7 5800X 8-Core Desktop Processor", slot_type: "cpu", playbook_id: 1, status: "active", tier: "high", display_price: 149.99, gem_score: 92, consecutive_misses: 0, last_seen_at: "Today", },
  { id: 2, listing_title: "Gigabyte GeForce RTX 3060 Gaming OC 12GB", slot_type: "gpu", playbook_id: 1, status: "active", tier: "mid", display_price: 229.00, gem_score: 87, consecutive_misses: 0, last_seen_at: "Today", },
  { id: 3, listing_title: "Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200MHz", slot_type: "ram", playbook_id: 2, status: "active", tier: "mid", display_price: 54.95, gem_score: 84, consecutive_misses: 0, last_seen_at: "Yesterday", },
  { id: 4, listing_title: "Samsung 980 1TB NVMe M.2 Internal SSD", slot_type: "storage", playbook_id: 2, status: "pending_review", tier: "budget", display_price: 64.50, gem_score: 78, consecutive_misses: 1, last_seen_at: "Yesterday", },
  { id: 5, listing_title: "MSI MAG B550 TOMAHAWK MAX WIFI Motherboard", slot_type: "motherboard", playbook_id: 3, status: "active", tier: "high", display_price: 119.95, gem_score: 81, consecutive_misses: 0, last_seen_at: "2 days ago", },
  { id: 6, listing_title: "be quiet! Pure Power 12 M 750W Modular PSU", slot_type: "psu", playbook_id: 3, status: "hidden", tier: "mid", display_price: 89.99, gem_score: 74, consecutive_misses: 2, last_seen_at: "3 days ago", },
];

const categories = ["All components", "CPU", "GPU", "Memory", "Storage", "Motherboard", "Power supply", "Cooling"];
const imageTones = ["from-cyan-950 via-slate-800 to-blue-900", "from-violet-950 via-slate-800 to-indigo-900", "from-emerald-950 via-slate-800 to-teal-900", "from-amber-950 via-slate-800 to-orange-900"];

function ProductArt({ index, title, imageUrl }: { index: number; title: string; imageUrl?: string | null }) {
  return <div className={`relative flex h-full min-h-32 items-center justify-center overflow-hidden bg-gradient-to-br ${imageTones[index % imageTones.length]}`}>
    {imageUrl && <img src={imageUrl} alt="" className="absolute inset-0 h-full w-full object-contain mix-blend-screen" />}
    <div className="absolute inset-0 opacity-30" style={{ backgroundImage: "linear-gradient(135deg, transparent 45%, rgba(255,255,255,.22) 46%, transparent 48%), linear-gradient(45deg, transparent 45%, rgba(0,220,255,.18) 46%, transparent 48%)", backgroundSize: "28px 28px" }} />
      {!imageUrl && <div className="relative rounded-lg border border-white/20 bg-black/25 px-5 py-7 text-center shadow-2xl backdrop-blur-sm">
        <div className="mx-auto mb-2 h-8 w-16 rounded border border-cyan-200/60 bg-cyan-300/20 shadow-[0_0_24px_rgba(34,211,238,.35)]" />
        <span className="max-w-28 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/75">{title.split(" ").slice(0, 2).join(" ")}</span>
        <span className="mt-2 block text-[9px] uppercase tracking-wider text-white/45">No image captured</span>
      </div>}
    <button aria-label={`Save ${title}`} className="absolute right-2 top-2 rounded-full bg-black/50 p-1.5 text-white transition hover:bg-black/75"><Heart className="h-3.5 w-3.5" /></button>
  </div>;
}

function Status({ value }: { value: string }) {
  const tone = value === "active" ? "text-emerald-300 bg-emerald-400/10 border-emerald-400/20" : value === "pending_review" ? "text-amber-300 bg-amber-400/10 border-amber-400/20" : "text-slate-400 bg-white/5 border-white/10";
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{value.replace("_", " ")}</span>;
}

function ChannelLogo({ source }: { source: string }) {
  const canonical = canonicalVendorKey(source);
  const key = canonical.startsWith("ebay_") || canonical === "ebay" ? "ebay" : canonical.includes("flipflop") ? "flipflop_shop" : canonical;
  const meta = VENDOR_META[key] ?? (key === "flipflop_shop" ? { label: "FlipFlop.shop", mark: "FF", color: "#22d3ee" } : { label: source, mark: source.slice(0, 2).toUpperCase(), color: "#64748b" });
  if (VENDOR_META[key]) return <VendorLogo vendor={key} />;
  return <span title={meta.label} aria-label={meta.label} className="inline-flex h-6 min-w-6 items-center justify-center rounded border border-white/10 bg-black/30 px-1.5 font-mono text-[9px] font-bold uppercase tracking-tight" style={{ color: meta.color }}>{meta.mark}</span>;
}

function ChannelLogos({ sources, current }: { sources?: string[]; current?: string | null }) {
  const channels = [...new Set([...(sources ?? []), ...(current ? [current] : [])])];
  return <div className="flex items-center gap-1" aria-label={`Available on ${channels.join(", ") || "no channel recorded"}`}>
    {channels.length ? channels.map(source => <ChannelLogo key={source} source={source} />) : <span className="text-[10px] text-slate-600">No channels</span>}
  </div>;
}

function MarketPrice({ variant: v }: { variant: Variant }) {
  const median = v.scored_market_median_price ?? v.market_median_price;
  return <div className="min-w-0" title="Market range from the matched CPK comparable listings">
    <p className="font-mono text-sm font-semibold text-orange-200">{median == null ? "—" : `£${median.toFixed(2)}`}</p>
    <p className="text-[10px] text-slate-500">Market median{(v.scored_market_lower_price ?? v.market_lower_price) != null && (v.scored_market_upper_price ?? v.market_upper_price) != null ? ` · £${(v.scored_market_lower_price ?? v.market_lower_price)!.toFixed(0)}–£${(v.scored_market_upper_price ?? v.market_upper_price)!.toFixed(0)}` : ""}</p>
  </div>;
}

function ReviewSummary({ variant: v }: { variant: Variant }) {
  if (v.review_average_rating == null && v.review_count == null) {
    return <div className="text-[10px] text-slate-600">No review data</div>;
  }
  return <div className="flex items-center gap-1.5 text-xs" title="Product review rating and review count">
    <Star className="h-3.5 w-3.5 fill-amber-300 text-amber-300" />
    <span className="font-mono font-semibold text-amber-200">{v.review_average_rating == null ? "—" : v.review_average_rating.toFixed(1)}</span>
    <span className="text-slate-500">({v.review_count == null ? "—" : v.review_count.toLocaleString()})</span>
  </div>;
}

function SourcingDetails({ variant: v }: { variant: Variant }) {
  const money = (value?: number | null) => value == null ? "—" : `£${value.toFixed(2)}`;
  const variance = v.pct_offset == null ? "—" : `${v.pct_offset >= 0 ? "+" : "−"}${Math.abs(v.pct_offset).toFixed(0)}%`;
  return <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-[10px] sm:grid-cols-4 xl:grid-cols-9">
    <div><p className="text-slate-500">Condition</p><p className="mt-0.5 font-semibold text-white">{v.condition ?? "—"}</p></div>
    <div><p className="text-slate-500">Low</p><p className="mt-0.5 font-mono text-slate-200">{money(v.scored_market_lower_price ?? v.market_lower_price)}</p></div>
    <div><p className="text-slate-500">Median</p><p className="mt-0.5 font-mono text-orange-200">{money(v.scored_market_median_price ?? v.market_median_price)}</p></div>
    <div><p className="text-slate-500">High</p><p className="mt-0.5 font-mono text-slate-200">{money(v.scored_market_upper_price ?? v.market_upper_price)}</p></div>
    <div><p className="text-slate-500">Vs median</p><p className={`mt-0.5 font-mono font-semibold ${v.pct_offset != null && v.pct_offset < 0 ? "text-emerald-300" : "text-slate-200"}`}>{variance}</p></div>
    <div><p className="text-slate-500">Class</p><p className="mt-0.5 font-semibold uppercase text-amber-200">{v.classification?.replace(/_/g, " ") ?? "—"}</p></div>
    <div><p className="text-slate-500">Decision</p><p className="mt-0.5 font-semibold uppercase text-emerald-300">{v.decision?.replace(/_/g, " ") ?? "—"}</p></div>
    <div><p className="text-slate-500">Score</p><p className="mt-0.5 font-mono font-semibold text-white">{v.deal_score == null ? "—" : v.deal_score.toFixed(1)}</p></div>
    <div title={v.evidence_reason ?? undefined}><p className="text-slate-500">Evidence</p><p className="mt-0.5 font-semibold text-cyan-300">{v.evidence_status?.replace(/_/g, " ") ?? "Why?"}</p></div>
  </div>;
}

export default function CataloguePage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [view, setView] = useState<ViewMode>("listings");
  const [scope, setScope] = useState<CatalogueScope>("all");
  const [category, setCategory] = useState("All components");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (scope === "all") {
        const raw = await api.gemRadar.scoredListingsLatestRun(process.env.NEXT_PUBLIC_FLIPFLOP_ENV === "live" ? "LIVE" : "DEV") as Array<Record<string, unknown>>;
        setVariants(raw.map((row, index) => ({
          id: Number(row.id ?? index), listing_id: String(row.listing_id ?? row.id ?? index),
          listing_title: String(row.title ?? "Untitled listing"), image_url: (row.image_url as string | null) ?? null,
          slot_type: String(row.category ?? "other"), playbook_id: 0, status: "active", tier: String(row.classification ?? "unclassified"),
          display_price: Number(row.actual_price ?? row.delivered_price ?? 0), gem_score: Number(row.deal_score ?? 0) * 10,
          consecutive_misses: 0, last_seen_at: String(row.listing_observed_at ?? ""), source_name: (row.source as string | null) ?? "unknown",
          channel_sources: row.source ? [String(row.source)] : [], price_history_listing_id: String(row.listing_id ?? row.id ?? index),
          scored_market_lower_price: (row.market_lower_price as number | null) ?? null, scored_market_median_price: (row.market_median_price as number | null) ?? null,
          scored_market_upper_price: (row.market_upper_price as number | null) ?? null, pct_offset: (row.pct_offset as number | null) ?? null,
          watch_count: (row.watch_count as number | null) ?? null, offer_count: null, sold_count: (row.sold_listing_count as number | null) ?? null,
          url: (row.url as string | null) ?? null, condition: (row.condition as string | null) ?? null, delivered_price: (row.delivered_price as number | null) ?? null,
          classification: (row.classification as string | null) ?? null, decision: (row.decision as string | null) ?? null,
          confidence: (row.confidence as string | null) ?? null, deal_score: (row.deal_score as number | null) ?? null,
          evidence_status: (row.evidence_status as string | null) ?? null, evidence_reason: (row.evidence_reason as string | null) ?? null,
        })));
      } else {
        setVariants((await api.catalogue.variants(status === "all" ? {} : { status })) as Variant[]);
      }
      setPage(1);
    }
    catch { setVariants(fallback); }
    finally { setLoading(false); }
  }, [scope, status]);
  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => variants.filter(v => {
    const matchesQuery = !query || v.listing_title.toLowerCase().includes(query.toLowerCase());
    const matchesCategory = category === "All components" || v.slot_type.toLowerCase() === category.toLowerCase().replace(" ", "_");
    return matchesQuery && matchesCategory;
  }), [variants, query, category]);
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const pagedVisible = visible.slice((page - 1) * pageSize, page * pageSize);

  return <div className="min-h-full bg-[#05080d] p-4 text-slate-100 sm:p-6">
    <div className="mx-auto max-w-[1500px]">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div><p className="mb-1 font-mono text-[10px] uppercase tracking-[0.24em] text-cyan-400">FlipFlop / Inventory intelligence</p><h1 className="text-2xl font-bold tracking-tight text-white">Catalogue</h1><p className="mt-1 text-sm text-slate-400">Browse, compare and manage your retained component opportunities.</p></div>
        <div className="flex flex-wrap items-center gap-2"><button onClick={() => void load()} className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-xs text-slate-300 transition hover:border-cyan-400/40 hover:text-white"><RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} /> Refresh</button><button className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan-400 px-3 text-xs font-bold text-slate-950 transition hover:bg-cyan-300"><SlidersHorizontal className="h-3.5 w-3.5" /> Manage filters</button></div>
      </div>

      <div className="grid items-start gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="rounded-lg border border-white/10 bg-[#0b1119] p-3 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-wider text-white">Category</span><ChevronDown className="h-3.5 w-3.5 text-slate-500" /></div>
          <div className="space-y-1">{categories.map(item => <button key={item} onClick={() => setCategory(item)} className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-xs transition ${category === item ? "bg-cyan-400/10 font-semibold text-cyan-300" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><span>{item}</span>{item === "All components" && <span className="text-[10px] text-slate-600">{variants.length}</span>}</button>)}</div>
          <div className="my-4 border-t border-white/10" /><div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Listing health</div>
          {[["Active", "active"], ["Needs review", "pending_review"], ["Hidden", "hidden"]].map(([label, value]) => <button key={value} onClick={() => setStatus(value)} className="flex w-full items-center gap-2 py-1.5 text-left text-xs text-slate-400 hover:text-white"><span className={`h-2 w-2 rounded-full ${value === "active" ? "bg-emerald-400" : value === "pending_review" ? "bg-amber-400" : "bg-slate-500"}`} />{label}</button>)}
        </aside>

        <div className="min-w-0">
          <section className="sticky top-4 z-20 -mx-1 mb-3 min-w-0 rounded-lg bg-[#05080d]/95 px-1 pb-1 pt-1 backdrop-blur-md">
            <div className="mb-2 flex items-center gap-2"><span className="text-xs font-semibold text-slate-400">Scope</span>{([['all','All listings'],['curated','Curated catalogue']] as const).map(([value,label]) => <button key={value} onClick={() => { setScope(value); setPage(1); }} className={`rounded-full border px-3 py-1 text-[10px] transition ${scope === value ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-300" : "border-white/10 text-slate-500 hover:text-white"}`}>{label}</button>)}<span className="text-[10px] text-slate-600">{scope === "all" ? "Current DEV scan results" : "GEM/SUPER_GEM products mapped to build slots"}</span></div>
            <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-[#0b1119] p-3 shadow-xl shadow-black/20 md:flex-row md:items-center">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/20 px-3 text-slate-500 focus-within:border-cyan-400/60"><Search className="h-4 w-4 shrink-0" /><span className="sr-only">Search catalogue</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search components, models or titles" className="h-9 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600" /></label>
            <div className="flex items-center gap-2"><select value={status} onChange={e => setStatus(e.target.value)} className="h-9 rounded-md border border-white/10 bg-[#111923] px-2 text-xs text-slate-300 outline-none"><option value="all">All statuses</option><option value="active">Active</option><option value="pending_review">Needs review</option><option value="hidden">Hidden</option></select><button className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs text-slate-300 hover:border-cyan-400/40"><Filter className="h-3.5 w-3.5" /> Filters</button></div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2"><span className="mr-1 text-xs text-slate-500">Popular:</span>{["CPU", "GPU", "DDR4", "NVMe", "AM4"].map(chip => <button key={chip} onClick={() => setQuery(chip)} className="cursor-pointer rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] text-slate-300 transition hover:border-cyan-400/50 hover:text-cyan-300">{chip}</button>)}</div>
          </section>

          <div className="mb-3 flex flex-col gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center sm:justify-between"><div><span className="text-sm font-semibold text-white">{visible.length.toLocaleString()} results</span><span className="ml-2 text-xs text-slate-500">Sorted by gem score · showing {pagedVisible.length.toLocaleString()}</span></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">View</span><div className="flex overflow-hidden rounded-md border border-white/10 bg-[#0b1119]">{([["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"]] as const).map(([value, Icon, label]) => <button key={value} onClick={() => setView(value)} aria-pressed={view === value} className={`inline-flex cursor-pointer items-center gap-1.5 px-3 py-2 text-[11px] transition ${view === value ? "bg-cyan-400 text-slate-950" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div></div></div>

          {view === "table" ? <TableView variants={pagedVisible} /> : <div className={view === "grid" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{pagedVisible.map((v, index) => <ListingCard key={v.id} variant={v} index={index} compact={view === "listings"} />)}</div>}
          {!loading && visible.length === 0 && <div className="rounded-lg border border-dashed border-white/10 py-16 text-center text-sm text-slate-500">No catalogue matches. Try clearing the search or filters.</div>}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>Showing {visible.length ? ((page - 1) * pageSize + 1).toLocaleString() : 0}–{Math.min(page * pageSize, visible.length).toLocaleString()} of {visible.length.toLocaleString()} listings</span><div className="flex items-center gap-2"><label className="flex items-center gap-1.5">Per page<select aria-label="Listings per page" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }} className="rounded border border-white/10 bg-[#111923] px-2 py-1 text-xs text-slate-300 outline-none"><option value={50}>50</option><option value={100}>100</option><option value={200}>200</option></select></label><div className="flex items-center gap-1"><button aria-label="Previous catalogue page" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"><ChevronLeft className="h-3.5 w-3.5" /></button><span className="px-2 text-slate-300">{page} / {pageCount}</span><button aria-label="Next catalogue page" disabled={page >= pageCount} onClick={() => setPage(p => Math.min(pageCount, p + 1))} className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"><ChevronRight className="h-3.5 w-3.5" /></button></div></div></div>
        </div>
      </div>
    </div>
  </div>;
}

function ListingCard({ variant: v, index, compact }: { variant: Variant; index: number; compact: boolean }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <article className={`overflow-hidden rounded-lg border border-white/10 bg-[#0b1119] transition hover:border-cyan-400/40 hover:shadow-[0_0_24px_rgba(34,211,238,.08)] ${compact ? "flex flex-col sm:flex-row" : ""}`}>
    <div className={compact ? "w-full shrink-0 sm:w-52" : ""}><ProductArt index={index} title={v.slot_type} imageUrl={v.image_url} /></div>
    <div className="min-w-0 flex-1 p-3">
      <div className="mb-2 flex items-start justify-between gap-3"><div className="min-w-0"><p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400">{v.tier} tier · {v.slot_type}</p><h2 className="line-clamp-2 text-sm font-semibold leading-snug text-white">{v.listing_title}</h2></div><Status value={v.status} /></div>
      <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2"><div><p className="text-xl font-bold text-white">£{(v.delivered_price ?? v.display_price).toFixed(2)}</p><p className="text-[10px] text-slate-500">Listing price</p></div><MarketPrice variant={v} /><div><p className="font-mono text-sm font-bold text-emerald-300">{v.deal_score == null ? v.gem_score.toFixed(0) : v.deal_score.toFixed(1)}<span className="text-[10px] font-normal text-slate-500"> / {v.deal_score == null ? "100" : "10"}</span></p><p className="text-[10px] text-slate-500">Score</p></div><div><ReviewSummary variant={v} /><p className="text-[10px] text-slate-500">Reviews</p></div></div>
      <div className="mt-3"><SourcingDetails variant={v} /></div>
      <div className="mt-3 flex items-center gap-3 rounded-md border border-blue-400/10 bg-blue-400/[0.03] px-3 py-2"><PriceHistorySparkline listingId={v.price_history_listing_id ?? String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /><span className="text-[10px] text-slate-500">Blue: listing · orange: CPK market · click for details</span></div>
      <div className="mt-3 grid grid-cols-3 gap-2 rounded-md border border-cyan-400/10 bg-cyan-400/[0.03] px-3 py-2"><div><p className="font-mono text-sm font-semibold text-cyan-200">{metric(v.watch_count)}</p><p className="text-[10px] text-slate-500">Watches</p></div><div title="Number of matched listings with Best Offer enabled"><p className="font-mono text-sm font-semibold text-amber-200">{metric(v.offer_count)}</p><p className="text-[10px] text-slate-500">Offers enabled</p></div><div title="Distinct matched sold comps observed in the last 90 days"><p className="font-mono text-sm font-semibold text-emerald-200">{metric(v.sold_count)}</p><p className="text-[10px] text-slate-500">Sold · 90d</p></div></div>
      <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2"><ChannelLogos sources={v.channel_sources} current={v.source_name} />{v.url ? <a href={v.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[11px] font-semibold text-cyan-300 hover:text-cyan-200"><Eye className="h-3.5 w-3.5" /> View listing</a> : null}</div>
    </div>
  </article>;
}

function TableView({ variants }: { variants: Variant[] }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#0b1119]"><table className="w-full min-w-[1390px] text-left text-xs"><thead className="border-b border-white/10 bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-3">Listing</th><th className="px-3 py-3">Category</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Channels</th><th className="px-3 py-3 text-right">Price</th><th className="px-3 py-3 text-right">Gem score</th><th className="px-3 py-3 text-center">Price trend</th><th className="px-3 py-3 text-right">Market median</th><th className="px-3 py-3 text-right">Reviews</th><th className="px-3 py-3 text-right">Watches</th><th className="px-3 py-3 text-right">Offers</th><th className="px-3 py-3 text-right">Sold · 90d</th><th className="px-3 py-3 text-right">Last seen</th><th className="px-4 py-3" /></tr></thead><tbody>{variants.map(v => <tr key={v.id} className="border-b border-white/5 transition last:border-0 hover:bg-white/[0.03]"><td className="max-w-[420px] px-4 py-3"><p className="truncate font-medium text-white">{v.listing_title}</p><p className="mt-1 text-[10px] uppercase text-slate-600">{v.tier} tier · #{v.id}</p></td><td className="px-3 py-3 text-slate-400">{v.slot_type}</td><td className="px-3 py-3"><Status value={v.status} /></td><td className="px-3 py-3"><ChannelLogos sources={v.channel_sources} current={v.source_name} /></td><td className="px-3 py-3 text-right font-semibold text-white">£{v.display_price.toFixed(2)}</td><td className="px-3 py-3 text-right font-mono font-bold text-emerald-300">{v.gem_score.toFixed(0)}</td><td className="px-3 py-3"><PriceHistorySparkline listingId={v.price_history_listing_id ?? String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /></td><td className="px-3 py-3 text-right"><MarketPrice variant={v} /></td><td className="px-3 py-3 text-right"><ReviewSummary variant={v} /></td><td className="px-3 py-3 text-right font-mono text-cyan-200">{metric(v.watch_count)}</td><td className="px-3 py-3 text-right font-mono text-amber-200">{metric(v.offer_count)}</td><td className="px-3 py-3 text-right font-mono text-emerald-200">{metric(v.sold_count)}</td><td className="px-3 py-3 text-right text-slate-500">{v.last_seen_at}</td><td className="px-4 py-3 text-right"><button aria-label={`Toggle visibility for ${v.listing_title}`} className="cursor-pointer rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-white">{v.status === "active" ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}</button></td></tr>)}</tbody></table></div>;
}
