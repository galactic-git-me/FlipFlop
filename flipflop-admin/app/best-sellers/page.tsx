"use client";

import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw, Trophy } from "lucide-react";

type Category = { category: string; name: string; source_url: string; count: number; matched: number; rated: number; last_captured_at: string | null };
type Product = { asin: string; title: string; url: string | null; image_url: string | null; rank: number; cpk: string | null; marketplace_listing_count: number | null; rating: number | null; review_count: number | null; price: number | null; rrp: number | null; sales_velocity: string | null };
type Response = { categories: Category[]; selected_category: string; products: Product[] };

export default function BestSellersPage() {
  const [category, setCategory] = useState("case");
  const [data, setData] = useState<Response | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/best-sellers?category=${encodeURIComponent(category)}`, { signal: controller.signal, cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error(`Could not load bestseller data (${response.status})`);
        return response.json() as Promise<Response>;
      })
      .then(result => { setData(result); setError(null); })
      .catch(reason => { if (!controller.signal.aborted) setError(String(reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [category, refreshKey]);

  const selected = data?.categories.find(item => item.category === category);
  const fresh = selected?.last_captured_at && Date.now() - new Date(selected.last_captured_at).getTime() < 24 * 60 * 60 * 1000;

  return (
    <main className="space-y-6 p-6 text-slate-100">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold"><Trophy className="h-6 w-6 text-amber-400" /> Amazon Best Sellers</h1>
          <p className="mt-1 text-sm text-slate-400">Latest observed UK bestseller lists, with source coverage and CPK matching shown separately.</p>
        </div>
        <button type="button" onClick={() => { setLoading(true); setRefreshKey(value => value + 1); }} className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-600 px-3 py-2 text-sm hover:border-cyan-400 focus-visible:outline-2 focus-visible:outline-cyan-400"><RefreshCw className="h-4 w-4" /> Refresh view</button>
      </div>

      <div aria-label="Bestseller category" className="flex flex-wrap gap-2">
        {(data?.categories ?? ["cpu", "gpu", "ram", "storage", "motherboard", "psu", "cooler", "case"].map(key => ({ category: key, name: key.toUpperCase(), count: 0, matched: 0, rated: 0, last_captured_at: null, source_url: "" }))).map(item => (
          <button key={item.category} type="button" onClick={() => { setCategory(item.category); setLoading(true); }} aria-pressed={category === item.category} className={`cursor-pointer rounded-lg border px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-cyan-400 ${category === item.category ? "border-blue-400 bg-blue-600 text-white" : "border-slate-700 bg-slate-800 text-slate-300 hover:border-slate-500"}`}>
            {item.name} <span className="ml-1 text-xs opacity-75">{item.count}</span>
          </button>
        ))}
      </div>

      {error && <div role="alert" className="rounded-lg border border-red-500/50 bg-red-950/40 p-4 text-red-200">{error}</div>}
      {selected && <section className="flex flex-wrap items-center gap-5 rounded-xl border border-slate-700 bg-slate-800/80 p-4 text-sm" aria-label="List coverage">
        <span><strong className="text-xl text-white">{selected.count}</strong> products</span>
        <span><strong className="text-xl text-cyan-300">{selected.matched}</strong> CPK matches</span>
        <span><strong className="text-xl text-amber-300">{selected.rated}</strong> rated</span>
        <span className={fresh ? "text-emerald-300" : "text-amber-300"}>{selected.last_captured_at ? `${fresh ? "Updated" : "Stale · last updated"} ${new Date(selected.last_captured_at).toLocaleString()}` : "No scrape captured"}</span>
        <a className="ml-auto inline-flex items-center gap-1 text-cyan-300 underline hover:text-cyan-100" href={selected.source_url} target="_blank" rel="noopener noreferrer">Amazon list <ExternalLink className="h-3 w-3" /></a>
      </section>}
      {selected && selected.count < 100 && <p role="alert" className="rounded-lg border border-amber-600/50 bg-amber-950/30 p-3 text-sm text-amber-200">Incomplete source coverage: {selected.count}/100 Amazon ranks captured. Treat this list as partial until the next successful scrape.</p>}

      {loading ? <p role="status" className="text-slate-400">Loading bestseller list…</p> : !data?.products.length ? (
        <p className="rounded-xl border border-amber-600/40 bg-amber-950/20 p-6 text-amber-200">No captured products for this category. The list is not covered yet; this is not a zero-sales result.</p>
      ) : <div className="overflow-x-auto rounded-xl border border-slate-700 bg-slate-800/70">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-700/80 text-xs uppercase tracking-wide text-slate-300"><tr><th className="p-3">Rank</th><th className="p-3">Product</th><th className="p-3">Amazon price</th><th className="p-3">Rating</th><th className="p-3">Reviews</th><th className="p-3">Sales</th><th className="p-3">Marketplace listings</th><th className="p-3">CPK match</th></tr></thead>
          <tbody>{data.products.map(product => <tr key={product.asin} className="border-t border-slate-700 hover:bg-slate-700/40">
            <td className="p-3 font-bold text-amber-300">#{product.rank}</td>
            <td className="p-3"><div className="flex items-center gap-3">
              {product.image_url ? <img src={product.image_url} alt="" className="h-16 w-16 shrink-0 rounded bg-white object-contain" /> : <div className="h-16 w-16 shrink-0 rounded bg-slate-700" />}
              {product.url ? <a href={product.url} target="_blank" rel="noopener noreferrer" className="max-w-xl font-medium text-slate-100 hover:text-cyan-300 hover:underline focus-visible:outline-2 focus-visible:outline-cyan-400">{product.title}</a> : <span>{product.title}</span>}
            </div></td>
            <td className="p-3 whitespace-nowrap">{product.price != null ? `£${product.price.toFixed(2)}` : "—"}{product.rrp != null && product.price != null && product.rrp > product.price ? <span className="ml-2 text-xs text-slate-400 line-through">£{product.rrp.toFixed(2)}</span> : null}</td>
            <td className="p-3 text-amber-300">{product.rating != null ? `★ ${product.rating.toFixed(1)}` : "—"}</td>
            <td className="p-3 tabular-nums">{product.review_count?.toLocaleString() ?? "—"}</td>
            <td className="p-3 text-xs text-slate-300">{product.sales_velocity ?? "—"}</td>
            <td className="p-3 tabular-nums" title={product.cpk ? "Distinct marketplace listing IDs associated with this CPK" : "A CPK is required to count linked marketplace listings"}>
              {product.marketplace_listing_count == null ? <span className="text-slate-400">Needs CPK</span> : `${product.marketplace_listing_count} ${product.marketplace_listing_count === 1 ? "listing" : "listings"}`}
            </td>
            <td className="p-3">{product.cpk ? <span className="rounded bg-emerald-900/50 px-2 py-1 text-emerald-200">Matched</span> : <span className="rounded bg-slate-700 px-2 py-1 text-slate-300">Unmatched</span>}</td>
          </tr>)}</tbody>
        </table>
      </div>}
    </main>
  );
}
