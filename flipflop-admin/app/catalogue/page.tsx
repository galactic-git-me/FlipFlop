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
type CatalogueScope = "bestsellers" | "all" | "curated";
type Variant = {
  id: number; listing_id?: number | string; listing_title: string; image_url?: string | null; slot_type: string;
  playbook_id: number; status: string; tier: string; display_price: number | null;
  gem_score: number; consecutive_misses: number; last_seen_at: string;
  isAmazonBestseller?: boolean; sales_velocity?: string | null;
  cheapest_market_price?: number | null; cheapest_market_url?: string | null; cheapest_market_source?: string | null;
  source_name?: string | null; channel_sources?: string[];
  price_history_listing_id?: string | null; market_lower_price?: number | null; market_median_price?: number | null; market_upper_price?: number | null;
  cpk?: string | null; watch_count?: number | null; offer_count?: number | null; sold_count?: number | null; active_count?: number | null; sell_through_rate?: number | null;
  review_average_rating?: number | null; review_count?: number | null;
  amazon_bestseller_rank?: number | null; amazon_bestseller_list?: string | null; amazon_bestseller_captured_at?: string | null;
  performance_status?: string | null; performance_model?: string | null; performance_score?: number | null;
  performance_rank?: number | null; performance_peer_count?: number | null; performance_percentile?: number | null;
  url?: string | null; condition?: string | null; delivered_price?: number | null;
  delivery_text?: string | null; delivery_postcode?: string | null;
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

const categories = ["All components", "CPU", "GPU", "Memory", "Storage", "PC Cases", "Motherboard", "Power supply", "Cooling"];
const imageTones = ["from-cyan-950 via-slate-800 to-blue-900", "from-violet-950 via-slate-800 to-indigo-900", "from-emerald-950 via-slate-800 to-teal-900", "from-amber-950 via-slate-800 to-orange-900"];

function ProductArt({ index, title, imageUrl, channelSources, currentSource }: { index: number; title: string; imageUrl?: string | null; channelSources?: string[]; currentSource?: string | null }) {
  return <div className={`relative flex h-full min-h-32 items-center justify-center overflow-hidden bg-gradient-to-br ${imageTones[index % imageTones.length]}`}>
    {imageUrl && <img src={imageUrl} alt="" className="absolute inset-0 h-full w-full object-contain mix-blend-screen" />}
    <div className="absolute inset-0 opacity-30" style={{ backgroundImage: "linear-gradient(135deg, transparent 45%, rgba(255,255,255,.22) 46%, transparent 48%), linear-gradient(45deg, transparent 45%, rgba(0,220,255,.18) 46%, transparent 48%)", backgroundSize: "28px 28px" }} />
      {!imageUrl && <div className="relative rounded-lg border border-white/20 bg-black/25 px-5 py-7 text-center shadow-2xl backdrop-blur-sm">
        <div className="mx-auto mb-2 h-8 w-16 rounded border border-cyan-200/60 bg-cyan-300/20 shadow-[0_0_24px_rgba(34,211,238,.35)]" />
        <span className="max-w-28 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/75">{title.split(" ").slice(0, 2).join(" ")}</span>
        <span className="mt-2 block text-[9px] uppercase tracking-wider text-white/45">No image captured</span>
      </div>}
    <button aria-label={`Save ${title}`} className="absolute right-2 top-2 rounded-full bg-black/50 p-1.5 text-white transition hover:bg-black/75"><Heart className="h-3.5 w-3.5" /></button>
    <div className="absolute bottom-2 right-2 rounded-md border border-white/15 bg-slate-950/80 p-1.5 shadow-lg backdrop-blur-sm"><ChannelLogos sources={channelSources} current={currentSource} /></div>
  </div>;
}

function Status({ value }: { value: string }) {
  const tone = value === "active" ? "text-emerald-300 bg-emerald-400/10 border-emerald-400/20" : value === "pending_review" ? "text-amber-300 bg-amber-400/10 border-amber-400/20" : "text-slate-400 bg-white/5 border-white/10";
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{value.replace("_", " ")}</span>;
}

function classificationLabel(value?: string | null) {
  const normalized = value?.toUpperCase();
  if (normalized === "SUPER_GEM") return "SG";
  if (normalized === "GEM") return "G";
  return value?.replace(/_/g, " ") ?? "—";
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
  const lower = v.scored_market_lower_price ?? v.market_lower_price;
  const upper = v.scored_market_upper_price ?? v.market_upper_price;
  return <div className="min-w-0" title="Market range from the matched CPK comparable listings">
    <p className="font-mono text-[10px] text-slate-500">{lower == null ? "—" : `£${lower.toFixed(0)}`}</p>
    <p className="font-mono text-sm font-semibold text-orange-200" title="Market median">{median == null ? "—" : `£${median.toFixed(0)}`}</p>
    <p className="font-mono text-[10px] text-slate-500">{upper == null ? "—" : `£${upper.toFixed(0)}`}</p>
  </div>;
}

function ReviewSummary({ variant: v }: { variant: Variant }) {
  return <div className="flex items-center gap-1.5 text-xs" title="Product review rating and review count">
    <Star className="h-3.5 w-3.5 fill-amber-300 text-amber-300" />
    <span className="font-mono font-semibold text-amber-200">{v.review_average_rating == null ? "Rating unavailable" : v.review_average_rating.toFixed(1)}</span>
    <span className="text-slate-500">({v.review_count == null ? "count unavailable" : v.review_count.toLocaleString()} reviews)</span>
  </div>;
}

function RankSummary({ variant: v }: { variant: Variant }) {
  return <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px]" title="Amazon rank is from the product category bestseller list">
    <span className="text-amber-300">Amazon <b className="font-mono">{v.amazon_bestseller_rank == null ? "—" : `#${v.amazon_bestseller_rank.toLocaleString()}`}</b></span>
    <span className="text-violet-300">Performance <b className="font-mono">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()}`}</b></span>
  </div>;
}

function PerformanceSummary({ variant: v }: { variant: Variant }) {
  return <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[10px]" title="Relative performance rank among benchmarked products">
    <span className="text-violet-300">Rank <b className="font-mono text-violet-200">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()}${v.performance_peer_count ? ` / ${v.performance_peer_count.toLocaleString()}` : ""}`}</b></span>
  </div>;
}

function SourcingDetails({ variant: v }: { variant: Variant }) {
  const money = (value?: number | null) => value == null ? "—" : `£${value.toFixed(0)}`;
  const lower = v.scored_market_lower_price ?? v.market_lower_price;
  const upper = v.scored_market_upper_price ?? v.market_upper_price;
  const range = lower == null || upper == null ? "—" : `£${lower.toFixed(0)}–${upper.toFixed(0)}`;
  const variance = v.pct_offset == null ? "—" : `${v.pct_offset >= 0 ? "+" : "−"}${Math.abs(v.pct_offset).toFixed(0)}%`;
  return <div className="grid min-w-0 grid-cols-2 gap-x-3 gap-y-2 rounded-md border border-white/10 bg-black/20 px-3 py-2 text-[10px] sm:grid-cols-4 xl:grid-cols-8">
    <div className="min-w-0"><p className="text-slate-500">Condition</p><p className="mt-0.5 break-words font-semibold text-white">{v.condition ?? "—"}</p></div>
    <div className="min-w-0 xl:col-span-2"><p className="text-slate-500">Range</p><p className="mt-0.5 whitespace-nowrap font-mono text-slate-200">{range}</p></div>
    <div className="min-w-0"><p className="text-slate-500">Median</p><p className="mt-0.5 break-words font-mono text-orange-200">{money(v.scored_market_median_price ?? v.market_median_price)}</p></div>
    <div className="min-w-0"><p className="text-slate-500">vMed</p><p className={`mt-0.5 break-words font-mono font-semibold ${v.pct_offset != null && v.pct_offset < 0 ? "text-emerald-300" : "text-slate-200"}`}>{variance}</p></div>
    <div className="min-w-0"><p className="text-slate-500">Class</p><p className="mt-0.5 break-words font-semibold uppercase text-amber-200">{classificationLabel(v.classification)}</p></div>
    <div className="min-w-0"><p className="text-slate-500">Decision</p><p className="mt-0.5 break-words font-semibold uppercase text-emerald-300">{v.decision?.replace(/_/g, " ") ?? "—"}</p></div>
    <div className="min-w-0"><p className="text-slate-500">Score</p><p className="mt-0.5 font-mono font-semibold text-white">{v.deal_score == null ? "—" : v.deal_score.toFixed(1)}</p></div>
  </div>;
}

export default function CataloguePage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [view, setView] = useState<ViewMode>("grid");
  const [scope, setScope] = useState<CatalogueScope>("bestsellers");
  const [category, setCategory] = useState("All components");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (scope === "bestsellers") {
        const bestsellerCategories: Record<string, string> = {
          CPU: "cpu", GPU: "gpu", Memory: "ram", Storage: "storage",
          "PC Cases": "case", Motherboard: "motherboard", "Power supply": "psu", Cooling: "cooler",
        };
        const categoryKeys = category === "All components"
          ? Object.values(bestsellerCategories)
          : [bestsellerCategories[category]].filter(Boolean);
        const responses = await Promise.all(categoryKeys.map(async key => {
          const response = await fetch(`/api/best-sellers?category=${encodeURIComponent(key)}`, { cache: "no-store" });
          if (!response.ok) throw new Error(`Could not load ${key} bestseller data (${response.status})`);
          return await response.json() as { products: Array<Record<string, unknown>> };
        }));
        const products = responses.flatMap(result => result.products);
        setVariants(products.map((row, index) => ({
          id: index + 1,
          listing_id: String(row.asin ?? index),
          listing_title: String(row.title ?? "Untitled Amazon product"),
          image_url: (row.image_url as string | null) ?? null,
          slot_type: String(row.category ?? "other"),
          playbook_id: 0,
          status: "active",
          tier: "bestseller",
          display_price: typeof row.price === "number" ? row.price : null,
          gem_score: 0,
          consecutive_misses: 0,
          last_seen_at: String(row.captured_at ?? ""),
          isAmazonBestseller: true,
          sales_velocity: (row.sales_velocity as string | null) ?? null,
          source_name: "Amazon",
          channel_sources: ["Amazon", ...((row.marketplace_sources as string[] | undefined) ?? [])],
          cpk: (row.cpk as string | null) ?? null,
          amazon_bestseller_rank: Number(row.rank),
          amazon_bestseller_list: String(row.list_name ?? row.category ?? "Amazon Best Sellers"),
          amazon_bestseller_captured_at: String(row.captured_at ?? ""),
          review_average_rating: (row.rating as number | null) ?? null,
          review_count: (row.review_count as number | null) ?? null,
          market_lower_price: (row.market_low as number | null) ?? null,
          market_median_price: (row.market_median as number | null) ?? null,
          market_upper_price: (row.market_high as number | null) ?? null,
          cheapest_market_price: (row.cheapest_market_price as number | null) ?? null,
          cheapest_market_url: (row.cheapest_market_url as string | null) ?? null,
          cheapest_market_source: (row.cheapest_market_source as string | null) ?? null,
          performance_rank: (row.performance_rank as number | null) ?? null,
          performance_peer_count: (row.performance_peer_count as number | null) ?? null,
          url: (row.url as string | null) ?? null,
          deal_score: null,
          classification: "AMAZON BESTSELLER",
        })));
      } else if (scope === "all") {
        // Let the API select its own runtime environment. The admin can be
        // served locally while pointing at either the DEV API or the live
        // production API, so a browser-side env flag can be stale or belong
        // to a different process. The backend already resolves DEV/LIVE from
        // FLIPFLOP_RUNTIME_ENV at the point where the data is queried.
        const raw = await api.gemRadar.scoredListingsLatestRun(undefined, 500) as Array<Record<string, unknown>>;
        setVariants(raw.map((row, index) => ({
          id: Number(row.id ?? index), listing_id: String(row.listing_id ?? row.id ?? index),
          listing_title: String(row.title ?? "Untitled listing"), image_url: (row.image_url as string | null) ?? null,
          slot_type: String(row.category ?? "other"), playbook_id: 0, status: "active", tier: String(row.classification ?? "unclassified"),
          display_price: Number(row.actual_price ?? row.delivered_price ?? 0), gem_score: Number(row.deal_score ?? 0) * 10,
          consecutive_misses: 0, last_seen_at: String(row.listing_observed_at ?? ""), source_name: (row.source as string | null) ?? "unknown",
          channel_sources: row.source ? [String(row.source)] : [], price_history_listing_id: String(row.listing_id ?? row.id ?? index),
          scored_market_lower_price: (row.market_lower_price as number | null) ?? null, scored_market_median_price: (row.market_median_price as number | null) ?? null,
          scored_market_upper_price: (row.market_upper_price as number | null) ?? null, pct_offset: (row.pct_offset as number | null) ?? null,
          watch_count: (row.watch_count as number | null) ?? null, offer_count: null, sold_count: (row.sold_listing_count as number | null) ?? null, active_count: (row.active_count as number | null) ?? null, sell_through_rate: (row.sell_through_rate as number | null) ?? (row.sell_through_rate_pct as number | null) ?? null,
          review_average_rating: (row.review_average_rating as number | null) ?? null, review_count: (row.review_count as number | null) ?? null,
          amazon_bestseller_rank: (row.amazon_bestseller_rank as number | null) ?? null, amazon_bestseller_list: (row.amazon_bestseller_list as string | null) ?? null, amazon_bestseller_captured_at: (row.amazon_bestseller_captured_at as string | null) ?? null,
          performance_status: (row.performance_status as string | null) ?? null, performance_model: (row.performance_model as string | null) ?? null,
          performance_score: (row.performance_score as number | null) ?? null, performance_rank: (row.performance_rank as number | null) ?? null,
          performance_peer_count: (row.performance_peer_count as number | null) ?? null, performance_percentile: (row.performance_percentile as number | null) ?? null,
          url: (row.url as string | null) ?? null, condition: (row.condition as string | null) ?? null, delivered_price: (row.delivered_price as number | null) ?? null,
          delivery_text: (row.delivery_text as string | null) ?? null, delivery_postcode: (row.delivery_postcode as string | null) ?? null,
          classification: classificationLabel((row.classification as string | null) ?? null), decision: (row.decision as string | null) ?? null,
          confidence: (row.confidence as string | null) ?? null, deal_score: (row.deal_score as number | null) ?? null,
          evidence_status: (row.evidence_status as string | null) ?? null, evidence_reason: (row.evidence_reason as string | null) ?? null,
        })));
      } else {
        const curated = await api.catalogue.variants(status === "all" ? {} : { status }) as Variant[];
        setVariants(curated.map(v => ({ ...v, classification: classificationLabel(v.classification) })));
      }
      setPage(1);
    }
    catch { setVariants(fallback); }
    finally { setLoading(false); }
  }, [scope, status, category]);
  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => variants.filter(v => {
    const matchesQuery = !query || v.listing_title.toLowerCase().includes(query.toLowerCase());
    const categoryKeys: Record<string, string[]> = { CPU: ["cpu"], GPU: ["gpu"], Memory: ["ram"], Storage: ["storage"], "PC Cases": ["case"], Motherboard: ["motherboard"], "Power supply": ["psu"], Cooling: ["cooler"] };
    const categoryKey = categoryKeys[category] ?? [category.toLowerCase().replace(" ", "_")];
    const matchesCategory = category === "All components" || categoryKey.includes(v.slot_type.toLowerCase());
    return matchesQuery && matchesCategory;
  }).sort((a, b) => {
    if (scope === "bestsellers") {
      return (a.amazon_bestseller_rank ?? Number.MAX_SAFE_INTEGER) - (b.amazon_bestseller_rank ?? Number.MAX_SAFE_INTEGER)
        || a.listing_title.localeCompare(b.listing_title);
    }
    const scoreA = a.deal_score ?? a.gem_score / 10;
    const scoreB = b.deal_score ?? b.gem_score / 10;
    return scoreB - scoreA || a.listing_title.localeCompare(b.listing_title);
  }), [variants, query, category, scope]);
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const pagedVisible = visible.slice((page - 1) * pageSize, page * pageSize);

  return <div className="catalogue-page min-h-full overflow-x-clip bg-[#05080d] p-4 text-slate-100 sm:p-6">
    <div className="mx-auto max-w-[1500px]">
      <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div><p className="mb-1 font-mono text-[10px] uppercase tracking-[0.24em] text-cyan-400">FlipFlop / Inventory intelligence</p><h1 className="text-2xl font-bold tracking-tight text-white">Catalogue</h1><p className="mt-1 text-sm text-slate-400">Browse Amazon-ranked components with review evidence and market coverage.</p></div>
        <div className="flex flex-wrap items-center gap-2"><button onClick={() => void load()} className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 text-xs text-slate-300 transition hover:border-cyan-400/40 hover:text-white"><RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} /> Refresh</button><button className="inline-flex h-9 items-center gap-2 rounded-md bg-cyan-400 px-3 text-xs font-bold text-slate-950 transition hover:bg-cyan-300"><SlidersHorizontal className="h-3.5 w-3.5" /> Manage filters</button></div>
      </div>

      <div className="grid items-start gap-3 lg:grid-cols-[110px_minmax(0,1fr)]">
        <aside className="rounded-lg border border-white/10 bg-[#0b1119] p-3 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-wider text-white">Category</span><ChevronDown className="h-3.5 w-3.5 text-slate-500" /></div>
          <div className="space-y-1">{categories.map(item => <button key={item} onClick={() => setCategory(item)} className={`flex w-full items-center justify-between rounded px-2 py-2 text-left text-xs transition ${category === item ? "bg-cyan-400/10 font-semibold text-cyan-300" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><span>{item}</span>{item === "All components" && <span className="text-[10px] text-slate-600">{variants.length}</span>}</button>)}</div>
          {scope !== "bestsellers" && <><div className="my-4 border-t border-white/10" /><div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Listing health</div>
          {[["Active", "active"], ["Needs review", "pending_review"], ["Hidden", "hidden"]].map(([label, value]) => <button key={value} onClick={() => setStatus(value)} className="flex w-full items-center gap-2 py-1.5 text-left text-xs text-slate-400 hover:text-white"><span className={`h-2 w-2 rounded-full ${value === "active" ? "bg-emerald-400" : value === "pending_review" ? "bg-amber-400" : "bg-slate-500"}`} />{label}</button>)}</>}

        </aside>

        <div className="min-w-0">
          <section className="sticky top-4 z-20 -mx-1 mb-3 min-w-0 rounded-lg bg-[#05080d]/95 px-1 pb-1 pt-1 backdrop-blur-md">
          <div className="mb-2 flex items-center gap-2"><span className="text-xs font-semibold text-slate-400">Scope</span>{([['bestsellers','Amazon Best Sellers'],['all','All listings'],['curated','Curated catalogue']] as const).map(([value,label]) => <button key={value} onClick={() => { setScope(value); setPage(1); }} className={`rounded-full border px-3 py-1 text-[10px] transition ${scope === value ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-300" : "border-white/10 text-slate-500 hover:text-white"}`}>{label}</button>)}<span className="text-[10px] text-slate-600">{scope === "bestsellers" ? "Official Amazon category ranks, review ratings and review counts" : scope === "all" ? "Current active market listings" : "GEM/SUPER_GEM products mapped to build slots"}</span></div>
            <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-[#0b1119] p-3 shadow-xl shadow-black/20 md:flex-row md:items-center">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/20 px-3 text-slate-500 focus-within:border-cyan-400/60"><Search className="h-4 w-4 shrink-0" /><span className="sr-only">Search catalogue</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search components, models or titles" className="h-9 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600" /></label>
            <div className="flex items-center gap-2">{scope !== "bestsellers" && <select value={status} onChange={e => setStatus(e.target.value)} className="h-9 rounded-md border border-white/10 bg-[#111923] px-2 text-xs text-slate-300 outline-none"><option value="all">All statuses</option><option value="active">Active</option><option value="pending_review">Needs review</option><option value="hidden">Hidden</option></select>}<button className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs text-slate-300 hover:border-cyan-400/40"><Filter className="h-3.5 w-3.5" /> Filters</button></div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2"><span className="mr-1 text-xs text-slate-500">Popular:</span>{["CPU", "GPU", "DDR4", "NVMe", "AM4"].map(chip => <button key={chip} onClick={() => setQuery(chip)} className="cursor-pointer rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] text-slate-300 transition hover:border-cyan-400/50 hover:text-cyan-300">{chip}</button>)}</div>
          </section>

          <div className="mb-3 flex flex-col gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center sm:justify-between"><div><span className="text-sm font-semibold text-white">{visible.length.toLocaleString()} results</span><span className="ml-2 text-xs text-slate-500">Sorted by {scope === "bestsellers" ? "Amazon Best Sellers rank" : "deal score"} · showing {pagedVisible.length.toLocaleString()}</span></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">View</span><div className="flex overflow-hidden rounded-md border border-white/10 bg-[#0b1119]">{([["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"]] as const).map(([value, Icon, label]) => <button key={value} onClick={() => setView(value)} aria-pressed={view === value} className={`inline-flex cursor-pointer items-center gap-1.5 px-3 py-2 text-[11px] transition ${view === value ? "bg-cyan-400 text-slate-950" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div></div></div>

          {scope === "bestsellers" ? (view === "table" ? <BestsellerTableView variants={pagedVisible} /> : <div className={view === "grid" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{pagedVisible.map((v, index) => <BestsellerCard key={v.listing_id ?? v.id} variant={v} index={index} compact={view === "listings"} />)}</div>) : (view === "table" ? <TableView variants={pagedVisible} /> : <div className={view === "grid" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{pagedVisible.map((v, index) => <ListingCard key={v.id} variant={v} index={index} compact={view === "listings"} />)}</div>)}
          {!loading && visible.length === 0 && <div className="rounded-lg border border-dashed border-white/10 py-16 text-center text-sm text-slate-500">No catalogue matches. Try clearing the search or filters.</div>}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>Showing {visible.length ? ((page - 1) * pageSize + 1).toLocaleString() : 0}–{Math.min(page * pageSize, visible.length).toLocaleString()} of {visible.length.toLocaleString()} {scope === "bestsellers" ? "products" : "listings"}</span><div className="flex items-center gap-2"><label className="flex items-center gap-1.5">Per page<select aria-label="Listings per page" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }} className="rounded border border-white/10 bg-[#111923] px-2 py-1 text-xs text-slate-300 outline-none"><option value={50}>50</option><option value={100}>100</option><option value={200}>200</option></select></label><div className="flex items-center gap-1"><button aria-label="Previous catalogue page" disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))} className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"><ChevronLeft className="h-3.5 w-3.5" /></button><span className="px-2 text-slate-300">{page} / {pageCount}</span><button aria-label="Next catalogue page" disabled={page >= pageCount} onClick={() => setPage(p => Math.min(pageCount, p + 1))} className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30"><ChevronRight className="h-3.5 w-3.5" /></button></div></div></div>
        </div>
      </div>
    </div>
  </div>;
}

function ListingCard({ variant: v, index, compact }: { variant: Variant; index: number; compact: boolean }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <article className={`overflow-hidden rounded-lg border border-cyan-400/25 bg-[#0b1119] transition hover:border-cyan-400/50 ${compact ? "flex flex-col sm:flex-row" : ""}`}>
    <div className={`relative flex shrink-0 items-center justify-center overflow-hidden bg-gradient-to-br ${imageTones[index % imageTones.length]} ${compact ? "h-32 w-full sm:h-auto sm:min-h-full sm:w-52" : "h-36 w-full"}`}>
      {v.image_url && <img src={v.image_url} alt="" className="absolute inset-0 h-full w-full object-contain mix-blend-screen" />}
      {!v.image_url && <span className="text-xs uppercase tracking-widest text-white/50">No image captured</span>}
      <span className="absolute left-2 top-2 rounded-md border border-amber-300/30 bg-slate-950/85 px-2 py-1 font-mono text-xs font-bold text-amber-300">{v.amazon_bestseller_rank == null ? v.source_name ?? "Listing" : `Amazon #${v.amazon_bestseller_rank.toLocaleString()}`}</span>
    </div>
    <div className="grid min-w-0 flex-1 gap-x-5 gap-y-3 p-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
      <div className="min-w-0 sm:col-span-2 xl:col-span-4 2xl:col-span-7"><p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400">{v.amazon_bestseller_list ?? v.slot_type} · {v.listing_id}</p>{v.url ? <a href={v.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-sm font-semibold leading-snug text-white hover:text-cyan-300 hover:underline">{v.listing_title}</a> : <p className="line-clamp-2 text-sm font-semibold text-white">{v.listing_title}</p>}</div>
      <div><p className="text-base font-bold text-white">{v.display_price == null ? "—" : `£${v.display_price.toFixed(2)}`}</p><p className="text-[10px] text-slate-500">Price · {v.source_name ?? "—"}</p></div>
      <div className="flex items-center gap-2"><PriceHistorySparkline listingId={v.price_history_listing_id ?? String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /><span className="text-[10px] text-slate-500">History</span></div>
      <div><MarketPrice variant={v} /><p className="text-[10px] text-slate-500">Low / median / high</p></div>
      <div><p className="text-sm font-semibold text-orange-300">{v.classification?.replace(/_/g, " ") ?? "—"}</p><p className="text-[10px] text-slate-500">Class</p></div>
      <div><p className="text-sm font-semibold text-amber-300">{v.evidence_status ?? "—"}</p><p className="text-[10px] text-slate-500">Evidence</p></div>
      <div><p className="font-mono text-sm font-semibold">{v.deal_score == null ? "—" : v.deal_score.toFixed(1)}</p><p className="text-[10px] text-slate-500">Score</p></div>
      <div><p className="font-mono text-sm font-semibold text-amber-300">{v.amazon_bestseller_rank == null ? "—" : `#${v.amazon_bestseller_rank.toLocaleString()}`}</p><p className="text-[10px] text-slate-500">Amazon BSR</p></div>
      <div><p className="font-mono text-sm text-violet-300">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()} / ${v.performance_peer_count?.toLocaleString() ?? "—"}`}</p><p className="text-[10px] text-slate-500">Performance</p></div>
      <div><p className="font-mono text-sm">{metric(v.sold_count)}</p><p className="text-[10px] text-slate-500">Sold (90d)</p></div>
      <div><p className="font-mono text-sm text-amber-200">{v.review_average_rating == null ? "—" : `★ ${v.review_average_rating.toFixed(1)}`} ({v.review_count?.toLocaleString() ?? "—"})</p><p className="text-[10px] text-slate-500">Stars (reviews)</p></div>
      <div><p className="text-sm font-semibold text-slate-200">{v.condition ?? "—"}</p><p className="text-[10px] text-slate-500">Condition · {v.status}</p></div>
    </div>
  </article>;
}

function TableView({ variants }: { variants: Variant[] }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#0b1119]"><table className="w-full min-w-[1600px] text-left text-xs"><thead className="border-b border-white/10 bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-400"><tr><th className="px-3 py-3">Source</th><th className="px-3 py-3">Title</th><th className="px-3 py-3">Condition</th><th className="px-3 py-3 text-right">Price</th><th className="px-3 py-3">History</th><th className="px-3 py-3 text-right">Low</th><th className="px-3 py-3 text-right">Median</th><th className="px-3 py-3 text-right">High</th><th className="px-3 py-3">Class</th><th className="px-3 py-3">Evidence</th><th className="px-3 py-3 text-right">Score</th><th className="px-3 py-3 text-right">Amazon BSR</th><th className="px-3 py-3 text-right">Performance</th><th className="px-3 py-3 text-right">Sold (90d)</th><th className="px-3 py-3 text-right">Stars (reviews)</th></tr></thead><tbody>{variants.map(v => <tr key={v.id} className="border-b border-white/5 transition last:border-0 hover:bg-white/[0.03]"><td className="px-3 py-2"><ChannelLogos sources={v.channel_sources} current={v.source_name} /></td><td className="max-w-[400px] px-3 py-2"><a href={v.url ?? undefined} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium text-white hover:text-cyan-300 hover:underline">{v.listing_title}</a><span className="mt-1 block text-[9px] text-slate-500">{v.slot_type} · {v.listing_id}</span></td><td className="px-3 py-2"><span className="rounded bg-emerald-500/20 px-2 py-1 text-emerald-300">{v.condition ?? "—"}</span></td><td className="px-3 py-2 text-right font-semibold text-white">{v.display_price == null ? "—" : `£${v.display_price.toFixed(2)}`}</td><td className="px-2 py-2"><PriceHistorySparkline listingId={v.price_history_listing_id ?? String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /></td><td className="px-3 py-2 text-right font-mono">{v.scored_market_lower_price == null ? "—" : `£${v.scored_market_lower_price.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{v.scored_market_median_price == null ? "—" : `£${v.scored_market_median_price.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{v.scored_market_upper_price == null ? "—" : `£${v.scored_market_upper_price.toFixed(0)}`}</td><td className="px-3 py-2"><span className="rounded bg-orange-500/20 px-2 py-1 text-orange-300">{v.classification?.replace(/_/g, " ") ?? "—"}</span></td><td className="px-3 py-2"><span className="rounded bg-amber-500/10 px-2 py-1 text-amber-300">{v.evidence_status ?? "—"}</span></td><td className="px-3 py-2 text-right font-mono font-semibold">{v.deal_score == null ? "—" : v.deal_score.toFixed(1)}</td><td className="px-3 py-2 text-right font-mono text-amber-300">{v.amazon_bestseller_rank == null ? "—" : `#${v.amazon_bestseller_rank.toLocaleString()}`}</td><td className="px-3 py-2 text-right font-mono text-violet-300">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()} / ${v.performance_peer_count?.toLocaleString() ?? "—"}`}</td><td className="px-3 py-2 text-right font-mono">{metric(v.sold_count)}</td><td className="px-3 py-2 text-right text-amber-200">{v.review_average_rating == null ? "—" : `★ ${v.review_average_rating.toFixed(1)}`} ({v.review_count?.toLocaleString() ?? "—"})</td></tr>)}</tbody></table></div>;
}

function BestsellerTableView({ variants }: { variants: Variant[] }) {
  return <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#0b1119]"><table className="w-full min-w-[1600px] text-left text-xs"><thead className="border-b border-white/10 bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-400"><tr><th className="px-3 py-3">Source</th><th className="px-3 py-3">Title</th><th className="px-3 py-3">Condition</th><th className="px-3 py-3 text-right">Price</th><th className="px-3 py-3">History</th><th className="px-3 py-3 text-right">Low</th><th className="px-3 py-3 text-right">Median</th><th className="px-3 py-3 text-right">High</th><th className="px-3 py-3">Class</th><th className="px-3 py-3">Evidence</th><th className="px-3 py-3 text-right">Score</th><th className="px-3 py-3 text-right">Amazon BSR</th><th className="px-3 py-3 text-right">Performance</th><th className="px-3 py-3 text-right">Sold (90d)</th><th className="px-3 py-3 text-right">Stars (reviews)</th></tr></thead><tbody>{variants.map(v => <tr key={v.listing_id ?? v.id} className="border-b border-white/5 transition last:border-0 hover:bg-white/[0.03]"><td className="px-3 py-2"><ChannelLogos sources={v.channel_sources} /></td><td className="max-w-[400px] px-3 py-2"><a href={v.cheapest_market_url ?? v.url ?? undefined} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium text-white hover:text-cyan-300 hover:underline">{v.listing_title}</a><span className="mt-1 block text-[9px] text-slate-500">{v.amazon_bestseller_list} · ASIN {v.listing_id}</span></td><td className="px-3 py-2"><span className="rounded bg-emerald-500/20 px-2 py-1 text-emerald-300">New</span></td><td className="px-3 py-2 text-right font-semibold text-white">{v.cheapest_market_price == null ? "—" : `£${v.cheapest_market_price.toFixed(2)}`}<span className="block text-[9px] text-slate-500">{v.cheapest_market_source ?? "No matched offer"}</span></td><td className="px-2 py-2"><PriceHistorySparkline listingId={String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /></td><td className="px-3 py-2 text-right font-mono">{v.market_lower_price == null ? "—" : `£${v.market_lower_price.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{v.market_median_price == null ? "—" : `£${v.market_median_price.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{v.market_upper_price == null ? "—" : `£${v.market_upper_price.toFixed(0)}`}</td><td className="px-3 py-2"><span className="rounded bg-orange-500/20 px-2 py-1 text-orange-300">AMAZON</span></td><td className="px-3 py-2"><span className="rounded bg-amber-500/10 px-2 py-1 text-amber-300">{v.cpk ? "Matched" : "Limited"}</span></td><td className="px-3 py-2 text-right font-mono">—</td><td className="px-3 py-2 text-right font-mono text-amber-300">#{v.amazon_bestseller_rank?.toLocaleString() ?? "—"}</td><td className="px-3 py-2 text-right font-mono text-violet-300">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()} / ${v.performance_peer_count?.toLocaleString() ?? "—"}`}</td><td className="px-3 py-2 text-right font-mono">—</td><td className="px-3 py-2 text-right text-amber-200">{v.review_average_rating == null ? "—" : `★ ${v.review_average_rating.toFixed(1)}`} ({v.review_count?.toLocaleString() ?? "—"})</td></tr>)}</tbody></table></div>;
}

function BestsellerCard({ variant: v, index, compact }: { variant: Variant; index: number; compact: boolean }) {
  return <article className={`overflow-hidden rounded-lg border border-white/10 bg-[#0b1119] transition hover:border-cyan-400/40 ${compact ? "flex flex-col sm:flex-row" : ""}`}>
    <div className={`relative flex items-center justify-center overflow-hidden bg-gradient-to-br ${imageTones[index % imageTones.length]} ${compact ? "h-32 w-full sm:h-auto sm:min-h-full sm:w-52" : "h-40"}`}>
      {v.image_url && <img src={v.image_url} alt="" className="absolute inset-0 h-full w-full object-contain mix-blend-screen" />}
      {!v.image_url && <span className="text-xs uppercase tracking-widest text-white/50">No image captured</span>}
      <span className="absolute left-2 top-2 rounded-md border border-amber-300/30 bg-slate-950/85 px-2 py-1 font-mono text-xs font-bold text-amber-300">#{v.amazon_bestseller_rank?.toLocaleString() ?? "—"} - {v.amazon_bestseller_list ?? v.slot_type}</span>
    </div>
    <div className="grid min-w-0 flex-1 gap-x-5 gap-y-3 p-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
      <div className="min-w-0 sm:col-span-2 xl:col-span-4 2xl:col-span-7"><p className="mb-1 text-[10px] uppercase tracking-wider text-cyan-400">{v.amazon_bestseller_list} · ASIN {v.listing_id}</p><a href={v.cheapest_market_url ?? v.url ?? undefined} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-sm font-semibold text-white hover:text-cyan-300 hover:underline">{v.listing_title}</a></div>
      <div><p className="text-base font-bold text-white">{v.cheapest_market_price == null ? "—" : `£${v.cheapest_market_price.toFixed(2)}`}</p><p className="text-[10px] text-slate-500">Price · {v.cheapest_market_source ?? "no matched offer"}</p></div>
      <div className="flex items-center gap-2"><PriceHistorySparkline listingId={String(v.listing_id ?? v.id)} listingTitle={v.listing_title} /><span className="text-[10px] text-slate-500">History</span></div>
      <div><div className="flex gap-3"><span className="font-mono text-[10px]">{v.market_lower_price == null ? "—" : `£${v.market_lower_price.toFixed(0)}`}</span><span className="font-mono text-sm text-orange-200">{v.market_median_price == null ? "—" : `£${v.market_median_price.toFixed(0)}`}</span><span className="font-mono text-[10px]">{v.market_upper_price == null ? "—" : `£${v.market_upper_price.toFixed(0)}`}</span></div><p className="text-[10px] text-slate-500">Low / median / high</p></div>
      <div><p className="text-sm font-semibold text-orange-300">AMAZON</p><p className="text-[10px] text-slate-500">Class</p></div>
      <div><p className="text-sm font-semibold text-amber-300">{v.cpk ? "Matched" : "Limited"}</p><p className="text-[10px] text-slate-500">Evidence · {v.marketplace_listing_count?.toLocaleString() ?? "—"} listings</p></div>
      <div><p className="font-mono text-sm text-slate-300">—</p><p className="text-[10px] text-slate-500">Score</p></div>
      <div><p className="font-mono text-sm font-semibold text-amber-300">#{v.amazon_bestseller_rank?.toLocaleString() ?? "—"}</p><p className="text-[10px] text-slate-500">Amazon BSR</p></div>
      <div><p className="font-mono text-sm text-violet-300">{v.performance_rank == null ? "—" : `#${v.performance_rank.toLocaleString()} / ${v.performance_peer_count?.toLocaleString() ?? "—"}`}</p><p className="text-[10px] text-slate-500">Performance</p></div>
      <div><p className="font-mono text-sm text-slate-300">—</p><p className="text-[10px] text-slate-500">Sold (90d)</p></div>
      <div><ReviewSummary variant={v} /><p className="text-[10px] text-slate-500">Stars (reviews)<