"use client";

import { useEffect, useMemo, useState } from "react";
import { LayoutGrid, List, RefreshCw, Search, Table2, Trophy } from "lucide-react";
import { canonicalVendorKey, VENDOR_META } from "@/lib/vendors";
import { VendorLogo } from "../../components/VendorLogo";
import { PriceHistorySparkline } from "../../components/listings/PriceHistorySparkline";

type ViewMode = "table" | "listings" | "grid";
type Category = { category: string; name: string; source_url: string; count: number; matched: number; rated: number; last_captured_at: string | null };
type Product = {
  asin: string;
  title: string;
  url: string | null;
  image_url: string | null;
  category: string;
  rank: number;
  cpk: string | null;
  marketplace_listing_count: number | null;
  marketplace_sources: string[];
  market_low: number | null;
  market_median: number | null;
  market_high: number | null;
  cheapest_market_price: number | null;
  cheapest_market_url: string | null;
  cheapest_market_source: string | null;
  rating: number | null;
  review_count: number | null;
  price: number | null;
  rrp: number | null;
  sales_velocity: string | null;
};
type Response = { categories: Category[]; selected_category: string; products: Product[] };

const CATEGORY_KEYS = ["cpu", "gpu", "ram", "storage", "motherboard", "psu", "cooler", "case"];
const IMAGE_TONES = ["from-cyan-950 via-slate-800 to-blue-900", "from-violet-950 via-slate-800 to-indigo-900", "from-emerald-950 via-slate-800 to-teal-900", "from-amber-950 via-slate-800 to-orange-900"];

function vendorKeys(sources: string[] = []) {
  return [...new Set(sources.map(canonicalVendorKey))];
}

function VendorMarks({ sources }: { sources: string[] }) {
  const vendors = vendorKeys(sources);
  const shown = vendors.slice(0, 4);
  return <div className="flex flex-wrap items-center gap-1" title={vendors.map(key => VENDOR_META[key]?.label ?? key).join(", ") || "No matched marketplaces"}>
    {vendors.length ? <>{shown.map(key => VENDOR_META[key]
      ? <VendorLogo key={key} vendor={key} />
      : <span key={key} className="inline-flex h-6 min-w-6 items-center justify-center rounded border border-white/10 bg-black/30 px-1.5 font-mono text-[9px] font-bold uppercase text-slate-300">{key.slice(0, 2)}</span>)}{vendors.length > shown.length && <span className="text-[9px] text-slate-400">+{vendors.length - shown.length}</span>}</>
      : <span className="text-[10px] text-slate-600">No matched vendors</span>}
  </div>;
}

function VendorSummary({ product }: { product: Product }) {
  const count = vendorKeys(product.marketplace_sources).length;
  return <div className="min-w-0" title="Distinct marketplace sources with listings linked to this CPK">
    {product.cpk && <VendorMarks sources={product.marketplace_sources} />}
    <p className="mt-1 text-[10px] font-semibold text-cyan-300">{product.cpk ? `${count} ${count === 1 ? "vendor" : "vendors"}` : "Needs CPK"}</p>
  </div>;
}

function ProductArt({ product, index, compact = false }: { product: Product; index: number; compact?: boolean }) {
  return <div className={`relative flex items-center justify-center overflow-hidden bg-gradient-to-br ${IMAGE_TONES[index % IMAGE_TONES.length]} ${compact ? "h-28 w-full sm:h-full sm:min-h-36 sm:w-48" : "h-44 w-full"}`}>
    {product.image_url && <img src={product.image_url} alt="" className="absolute inset-0 h-full w-full object-contain mix-blend-screen" />}
    <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "linear-gradient(135deg, transparent 45%, rgba(255,255,255,.22) 46%, transparent 48%), linear-gradient(45deg, transparent 45%, rgba(0,220,255,.18) 46%, transparent 48%)", backgroundSize: "28px 28px" }} />
    {!product.image_url && <div className="relative rounded-lg border border-white/20 bg-black/25 px-5 py-6 text-center shadow-2xl backdrop-blur-sm"><div className="mx-auto mb-2 h-8 w-16 rounded border border-cyan-200/60 bg-cyan-300/20" /><span className="block max-w-32 text-[10px] font-semibold uppercase tracking-wider text-white/75">{product.title.split(" ").slice(0, 3).join(" ")}</span><span className="mt-1 block text-[9px] uppercase text-white/45">No image captured</span></div>}
    <span className="absolute left-2 top-2 rounded-md border border-amber-300/30 bg-slate-950/85 px-2 py-1 font-mono text-xs font-bold text-amber-300">#{product.rank}</span>
    <div className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md border border-white/15 bg-slate-950/85 px-2 py-1 shadow-lg backdrop-blur-sm">{product.cpk ? <><VendorMarks sources={product.marketplace_sources} /><span className="pl-1 text-[10px] font-semibold text-cyan-200">{vendorKeys(product.marketplace_sources).length} vendors</span></> : <span className="text-[10px] font-semibold text-amber-300">Needs CPK</span>}</div>
  </div>;
}

function MarketRange({ product }: { product: Product }) {
  const money = (value: number | null) => value == null ? "—" : `£${value.toFixed(0)}`;
  return <div className="min-w-24" title="Market price range from marketplace listings matched to this CPK">
    <p className="font-mono text-[10px] text-slate-500">{money(product.market_low)}</p>
    <p className="font-mono text-sm font-semibold text-orange-200">{money(product.market_median)}</p>
    <p className="font-mono text-[10px] text-slate-500">{money(product.market_high)}</p>
  </div>;
}

function MatchBadge({ product }: { product: Product }) {
  return product.cpk
    ? <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-300">Matched</span>
    : <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-300">Unmatched</span>;
}

function ProductCard({ product, index, compact }: { product: Product; index: number; compact: boolean }) {
  const title = product.url
    ? <a href={product.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 text-sm font-semibold leading-snug text-white hover:text-cyan-300 hover:underline">{product.title}</a>
    : <h2 className="line-clamp-2 text-sm font-semibold leading-snug text-white">{product.title}</h2>;
  return <article className={`overflow-hidden rounded-lg border border-white/10 bg-[#0b1119] transition-colors hover:border-cyan-400/40 ${compact ? "flex flex-col sm:flex-row" : ""}`}>
    <ProductArt product={product} index={index} compact={compact} />
    <div className="min-w-0 flex-1 p-3">
      <div className="mb-2 flex items-start justify-between gap-3"><div className="min-w-0"><p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400">{product.category} · ASIN {product.asin}</p>{title}</div><MatchBadge product={product} /></div>
      <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-3">
        <div><p className="text-xl font-bold text-white">{product.price == null ? "—" : `£${product.price.toFixed(2)}`}</p><p className="text-[10px] text-slate-500">Amazon price</p></div>
        {product.rrp != null && product.price != null && product.rrp > product.price && <div><p className="text-sm text-slate-400 line-through">£{product.rrp.toFixed(2)}</p><p className="text-[10px] text-slate-500">RRP</p></div>}
        <div><MarketRange product={product} /><p className="text-[10px] text-slate-500">Market low / median / high</p></div>
        <div><p className="font-mono text-sm font-bold text-amber-200">{product.rating == null ? "—" : `★ ${product.rating.toFixed(1)}`}</p><p className="text-[10px] text-slate-500">{product.review_count == null ? "No reviews" : `${product.review_count.toLocaleString()} reviews`}</p></div>
        <div><p className="font-mono text-sm font-semibold text-cyan-200">{product.cpk ? (product.marketplace_listing_count ?? 0).toLocaleString() : "—"}</p><p className="text-[10px] text-slate-500">Marketplace listings</p></div>
        <div><p className="text-sm text-slate-200">{product.sales_velocity ?? "—"}</p><p className="text-[10px] text-slate-500">Amazon sales</p></div>
      </div>
    </div>
  </article>;
}

function TableView({ products }: { products: Product[] }) {
  return <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#0b1119]"><table className="w-full min-w-[1320px] text-left text-xs">
    <thead className="border-b border-white/10 bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-500"><tr>
      <th className="px-3 py-3">Source</th><th className="px-3 py-3">Title</th><th className="px-3 py-3">Condition</th><th className="px-3 py-3 text-right">Price</th><th className="px-3 py-3">History</th><th className="px-3 py-3 text-right">Low</th><th className="px-3 py-3 text-right">Median</th><th className="px-3 py-3 text-right">High</th><th className="px-3 py-3">Class</th><th className="px-3 py-3">Evidence</th><th className="px-3 py-3 text-right">Score</th><th className="px-3 py-3 text-right">Amazon BSR</th><th className="px-3 py-3 text-right">Performance</th><th className="px-3 py-3 text-right">Sold (90d)</th><th className="px-3 py-3 text-right">Stars (reviews)</th>
    </tr></thead><tbody>{products.map(product => <tr key={`${product.category}:${product.asin}`} className="border-b border-white/5 transition last:border-0 hover:bg-white/[0.03]">
      <td className="px-3 py-2"><VendorMarks sources={["amazon", ...product.marketplace_sources]} /></td><td className="max-w-[390px] px-3 py-2"><a href={product.cheapest_market_url ?? product.url ?? undefined} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium text-white hover:text-cyan-300 hover:underline">{product.title}</a></td>
      <td className="px-3 py-2"><span className="rounded bg-emerald-500/20 px-2 py-1 text-emerald-300">new</span></td><td className="px-3 py-2 text-right font-semibold text-white">{product.cheapest_market_price == null ? "—" : `£${product.cheapest_market_price.toFixed(2)}`}<span className="block text-[9px] text-slate-500">{product.cheapest_market_source ?? "—"}</span></td><td className="px-2 py-2"><PriceHistorySparkline listingId={product.asin} listingTitle={product.title} /></td>
      <td className="px-3 py-2 text-right font-mono">{product.market_low == null ? "—" : `£${product.market_low.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{product.market_median == null ? "—" : `£${product.market_median.toFixed(0)}`}</td><td className="px-3 py-2 text-right font-mono">{product.market_high == null ? "—" : `£${product.market_high.toFixed(0)}`}</td>
      <td className="px-3 py-2"><span className="rounded bg-orange-500/20 px-2 py-1 text-orange-300">AMAZON</span></td><td className="px-3 py-2"><span className="rounded bg-amber-500/10 px-2 py-1 text-amber-300">{product.cpk ? "Matched" : "Limited"}</span></td><td className="px-3 py-2 text-right font-mono">—</td><td className="px-3 py-2 text-right font-mono text-amber-300">#{product.rank}</td><td className="px-3 py-2 text-right font-mono text-violet-300">—</td><td className="px-3 py-2 text-right font-mono">—</td><td className="px-3 py-2 text-right text-amber-200">{product.rating == null ? "—" : `★ ${product.rating.toFixed(1)}`} ({product.review_count?.toLocaleString() ?? "—"})</td>
    </tr>)}</tbody></table></div>;
}

export default function BestSellersPage() {
  const [category, setCategory] = useState("all");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewMode>("grid");
  const [data, setData] = useState<Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      try {
        const selectedCategories = category === "all" ? CATEGORY_KEYS : [category];
        const responses = await Promise.all(selectedCategories.map(async key => {
          const response = await fetch(`/api/best-sellers?category=${encodeURIComponent(key)}`, { signal: controller.signal, cache: "no-store" });
          if (!response.ok) throw new Error(`Could not load bestseller data (${response.status})`);
          return await response.json() as Response;
        }));
        const products = responses.flatMap(result => result.products).sort((a, b) => CATEGORY_KEYS.indexOf(a.category) - CATEGORY_KEYS.indexOf(b.category) || a.rank - b.rank);
        setData({ categories: responses[0]?.categories ?? [], selected_category: category, products });
        setError(null);
        setPage(1);
      } catch (reason) {
        if (!controller.signal.aborted) setError(String(reason));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    return () => controller.abort();
  }, [category, refreshKey]);

  const visible = useMemo(() => data?.products.filter(product => !query || `${product.title} ${product.asin} ${product.category}`.toLowerCase().includes(query.toLowerCase())) ?? [], [data, query]);
  const pageCount = Math.max(1, Math.ceil(visible.length / pageSize));
  const paged = visible.slice((page - 1) * pageSize, page * pageSize);
  const summaries = data?.categories ?? [];
  const countByCategory = new Map(summaries.map(item => [item.category, item.count]));
  const matchedCount = visible.filter(product => product.cpk).length;

  return <div className="catalogue-page min-h-full overflow-x-clip bg-[#05080d] p-4 text-slate-100 sm:p-6"><div className="mx-auto max-w-[1500px]">
    <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"><div><p className="mb-1 font-mono text-[10px] uppercase tracking-[0.24em] text-cyan-400">FlipFlop / Product discovery</p><h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-white"><Trophy className="h-5 w-5 text-amber-300" />Amazon Best Sellers</h1><p className="mt-1 text-sm text-slate-400">Browse Amazon’s latest component bestseller lists and their matched marketplace coverage.</p></div><button type="button" onClick={() => setRefreshKey(value => value + 1)} className="inline-flex h-9 items-center gap-2 self-start rounded-md border border-white/10 bg-white/5 px-3 text-xs text-slate-300 transition hover:border-cyan-400/40 hover:text-white xl:self-auto"><RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />Refresh</button></div>

    <div className="grid items-start gap-3 lg:grid-cols-[150px_minmax(0,1fr)]">
      <aside className="rounded-lg border border-white/10 bg-[#0b1119] p-3 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto"><div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-wider text-white">Category</span></div><div className="space-y-1">
        <button type="button" onClick={() => setCategory("all")} className={`flex w-full cursor-pointer items-center justify-between rounded px-2 py-2 text-left text-xs transition ${category === "all" ? "bg-cyan-400/10 font-semibold text-cyan-300" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><span>All components</span><span className="text-[10px] text-slate-600">{summaries.reduce((total, item) => total + item.count, 0).toLocaleString()}</span></button>
        {summaries.map(item => <button key={item.category} type="button" onClick={() => setCategory(item.category)} className={`flex w-full cursor-pointer items-center justify-between rounded px-2 py-2 text-left text-xs capitalize transition ${category === item.category ? "bg-cyan-400/10 font-semibold text-cyan-300" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><span>{item.name}</span><span className="text-[10px] text-slate-600">{countByCategory.get(item.category)?.toLocaleString() ?? 0}</span></button>)}
      </div><div className="my-4 border-t border-white/10" /><div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Current coverage</div><p className="text-xs text-slate-400">{matchedCount.toLocaleString()} of {visible.length.toLocaleString()} visible products have a CPK match.</p></aside>

      <div className="min-w-0"><section className="sticky top-4 z-20 -mx-1 mb-3 min-w-0 rounded-lg bg-[#05080d]/95 px-1 pb-1 pt-1 backdrop-blur-md"><div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-[#0b1119] p-3 shadow-xl shadow-black/20 md:flex-row md:items-center"><label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/20 px-3 text-slate-500 focus-within:border-cyan-400/60"><Search className="h-4 w-4 shrink-0" /><span className="sr-only">Search best sellers</span><input value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Search products, models or ASIN" className="h-9 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600" /></label><span className="text-xs text-slate-500">Latest captured rankings</span></div><div className="mt-3 flex flex-wrap items-center gap-2"><span className="mr-1 text-xs text-slate-500">Popular:</span>{["CPU", "GPU", "RAM", "Storage"].map(chip => <button key={chip} type="button" onClick={() => { setQuery(chip); setPage(1); }} className="cursor-pointer rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] text-slate-300 transition hover:border-cyan-400/50 hover:text-cyan-300">{chip}</button>)}<button type="button" onClick={() => { setQuery(""); setCategory("all"); }} className="cursor-pointer rounded-full border border-white/10 px-3 py-1 text-[10px] text-slate-500 hover:text-white">Clear</button></div></section>

        {error && <div role="alert" className="mb-3 rounded-lg border border-red-500/30 bg-red-950/30 p-3 text-sm text-red-200">{error}</div>}
        <div className="mb-3 flex flex-col gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center sm:justify-between"><div><span className="text-sm font-semibold text-white">{visible.length.toLocaleString()} results</span><span className="ml-2 text-xs text-slate-500">{matchedCount.toLocaleString()} CPK matched · showing {paged.length.toLocaleString()}</span></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">View</span><div className="flex overflow-hidden rounded-md border border-white/10 bg-[#0b1119]">{([["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"]] as const).map(([value, Icon, label]) => <button key={value} type="button" onClick={() => setView(value)} aria-pressed={view === value} className={`inline-flex cursor-pointer items-center gap-1.5 px-3 py-2 text-[11px] transition ${view === value ? "bg-cyan-400 text-slate-950" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div></div></div>

        {loading ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }, (_, index) => <div key={index} className="h-72 animate-pulse rounded-lg border border-white/10 bg-[#0b1119]" />)}</div> : visible.length === 0 ? <div className="rounded-lg border border-dashed border-white/10 py-16 text-center text-sm text-slate-500">No best sellers found. Try another category or search.</div> : view === "table" ? <TableView products={paged} /> : <div className={view === "grid" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{paged.map((product, index) => <ProductCard key={`${product.category}:${product.asin}`} product={product} index={index} compact={view === "listings"} />)}</div>}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>Showing {visible.length ? ((page - 1) * pageSize + 1).toLocaleString() : 0}–{Math.min(page * pageSize, visible.length).toLocaleString()} of {visible.length.toLocaleString()} products</span><div className="flex items-center gap-2"><label className="flex items-center gap-1.5">Per page<select aria-label="Products per page" value={pageSize} onChange={event => { setPageSize(Number(event.target.value)); setPage(1); }} className="rounded border border-white/10 bg-[#111923] px-2 py-1 text-xs text-slate-300 outline-none"><option value={50}>50</option><option value={100}>100</option><option value={200}>200</option></select></label><div className="flex items-center gap-1"><button aria-label="Previous best sellers page" disabled={page <= 1} onClick={() => setPage(value => Math.max(1, value - 1))} className="cursor-pointer rounded border border-white/10 px-2 py-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30">Previous</button><span className="px-2 text-slate-300">{page} / {pageCount}</span><button aria-label="Next best sellers page" disabled={page >= pageCount} onClick={() => setPage(value => Math.min(pageCount, value + 1))} className="cursor-pointer rounded border border-white/10 px-2 py-1.5 hover:text-white disabled:cursor-not-allowed disabled:opacity-30">Next</button></div></div></div>
      </div>
    </div>
  </div></div>;
}
