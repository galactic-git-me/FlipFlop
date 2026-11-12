"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Clock3, ExternalLink, RefreshCw, Search, Trophy } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Month = { key: string; label: string };
type Day = { key: string; label: string; timestamp: number };
type MonthPrice = { median: number | null; best_vendor: string | null; average: number | null; low: number | null; observations: number; vendor_medians: Record<string, number> };
type WatchedProduct = {
  cpk: string;
  mpn: string | null;
  title: string;
  url: string | null;
  image_url: string | null;
  rank: number;
  storage_type: "nvme" | "sata" | "unclassified" | null;
  months: Record<string, MonthPrice>;
  days: Record<string, MonthPrice>;
};
type WatchCategory = {
  category: "cpu" | "motherboard" | "ram" | "storage";
  name: string;
  list_name: string;
  source_url: string;
  last_captured_at: string | null;
  products: WatchedProduct[];
  unlinked_product_count: number;
  unclassified_storage_count: number;
};
type PriceWatchData = { months: Month[]; days: Day[]; categories: WatchCategory[]; generated_at: string; price_basis: string };
type CategoryKey = WatchCategory["category"];
type StorageFilter = "all" | "nvme" | "sata" | "unclassified";

const CATEGORY_TABS: Array<{ key: CategoryKey; label: string; mark: string }> = [
  { key: "cpu", label: "CPUs", mark: "CPU" },
  { key: "motherboard", label: "Motherboards", mark: "MB" },
  { key: "ram", label: "RAM", mark: "RAM" },
  { key: "storage", label: "Storage", mark: "SSD" },
];

const money = (value: number | null | undefined) => value == null ? "—" : `£${value.toFixed(2)}`;
const signedMoney = (value: number | null | undefined) => value == null ? "—" : `${value < 0 ? "−" : "+"}£${Math.abs(value).toFixed(2)}`;
const monthPrice = (product: WatchedProduct, key: string | undefined) => key ? product.months[key] : undefined;
const priceBarWidth = (value: number | null | undefined, max: number) => value == null || max <= 0 ? 0 : Math.max(2, value / max * 100);
const ramSizeGB = (title: string) => {
  const kitModules = title.match(/\b(\d+)\s*[x×]\s*(\d+)\s*GB\b/i);
  if (kitModules) return Number(kitModules[1]) * Number(kitModules[2]);
  const capacity = title.match(/\b(8|16|24|32|48|64|96|128|256)\s*GB\b/i);
  return capacity ? Number(capacity[1]) : null;
};

function monthChangeClass(value: number | null) {
  if (value == null || value === 0) return "text-slate-400";
  return value < 0 ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-400/10 text-rose-300";
}

function shortProductTitle(title: string) {
  const cpuModel = title.match(/\b(AMD\s+Ryzen\s+[3579]\s+[A-Za-z0-9-]+|Intel\s+Core\s+(?:Ultra\s+)?[3579]\s+[A-Za-z0-9-]+)/i)?.[0];
  if (cpuModel) return cpuModel.replace(/\s+/g, " ").trim();
  return title
    .replace(/\s+(?:processor|with|featuring|integrated|desktop|graphics|technology|technology,).*$/i, "")
    .split(/\s+/)
    .slice(0, 7)
    .join(" ");
}

export default function PriceWatchPage() {
  const [data, setData] = useState<PriceWatchData | null>(null);
  const [categoryKey, setCategoryKey] = useState<CategoryKey>("cpu");
  const [storageFilter, setStorageFilter] = useState<StorageFilter>("all");
  const [ramSizeFilter, setRamSizeFilter] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [rankLimits, setRankLimits] = useState<Record<CategoryKey, 10 | 100>>({ cpu: 10, motherboard: 10, ram: 100, storage: 100 });
  const rankLimit = rankLimits[categoryKey];
  const setRankLimit = (value: 10 | 100) => setRankLimits((current) => ({ ...current, [categoryKey]: value }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    else setLoading(true);
    try {
      const response = await fetch("/api/pricewatch", { cache: "no-store" });
      if (!response.ok) throw new Error(`PriceWatch returned HTTP ${response.status}`);
      setData(await response.json() as PriceWatchData);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load vendor price history.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const currentCategory = data?.categories.find((category) => category.category === categoryKey);
  const filteredProducts = useMemo(() => {
    let products = currentCategory?.products ?? [];
    if (categoryKey === "storage" && storageFilter !== "all") products = products.filter((product) => product.storage_type === storageFilter);
    if (categoryKey === "ram" && ramSizeFilter != null) products = products.filter((product) => ramSizeGB(product.title) === ramSizeFilter);
    if (query.trim()) {
      const term = query.toLowerCase();
      products = products.filter((product) => `${product.title} ${product.cpk} ${product.mpn ?? ""} ${product.rank}`.toLowerCase().includes(term));
    }
    return products;
  }, [categoryKey, currentCategory, query, ramSizeFilter, storageFilter]);

  const ramSizes = [...new Set((currentCategory?.category === "ram" ? currentCategory.products : []).map((product) => ramSizeGB(product.title)).filter((size): size is number => size != null))].sort((a, b) => a - b);
  const storageCounts = {
    all: currentCategory?.products.length ?? 0,
    nvme: currentCategory?.products.filter((product) => product.storage_type === "nvme").length ?? 0,
    sata: currentCategory?.products.filter((product) => product.storage_type === "sata").length ?? 0,
    unclassified: currentCategory?.products.filter((product) => product.storage_type === "unclassified").length ?? 0,
  };

  const chartProducts = (currentCategory?.products ?? [])
    .filter((product) => (categoryKey !== "storage" || storageFilter === "all" || product.storage_type === storageFilter) && (categoryKey !== "ram" || ramSizeFilter == null || ramSizeGB(product.title) === ramSizeFilter) && product.rank <= rankLimit)
    .map((product) => ({ product, latestPrice: [...(data?.days ?? [])].reverse().map((day) => product.days[day.key]?.median).find((price): price is number => price != null) ?? null }))
    .sort((a, b) => (b.latestPrice ?? -Infinity) - (a.latestPrice ?? -Infinity) || a.product.rank - b.product.rank)
    .map(({ product }) => product);
  const chartRows = (data?.days ?? []).map((day) => {
    const row: Record<string, string | number | null> = { timestamp: day.timestamp };
    for (const product of chartProducts) row[product.cpk] = product.days[day.key]?.median ?? null;
    return row;
  }).filter((row) => chartProducts.some((product) => typeof row[product.cpk] === "number"));
  const tableMonths = (data?.months ?? []).filter((month) => filteredProducts.some((product) => monthPrice(product, month.key)?.median != null));
  const currentMonth = tableMonths[tableMonths.length - 1];
  const previousMonth = tableMonths[tableMonths.length - 2];
  const priceBarMax = Math.max(0, ...filteredProducts.flatMap((product) => [
    ...tableMonths.map((month) => monthPrice(product, month.key)?.median ?? null),
    monthPrice(product, previousMonth?.key)?.average ?? null,
    monthPrice(product, previousMonth?.key)?.low ?? null,
    monthPrice(product, currentMonth?.key)?.average ?? null,
    monthPrice(product, currentMonth?.key)?.low ?? null,
  ].filter((value): value is number => value != null && Number.isFinite(value))));
  const latestCapture = currentCategory?.last_captured_at
    ? new Date(currentCategory.last_captured_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })
    : null;
  return <main className="min-h-full bg-[#05080d] p-4 text-slate-100 sm:p-6">
    <div className="mx-auto max-w-[1800px] space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-cyan-400">FlipFlop / Market intelligence</p>
          <h1 className="mt-1 flex items-center gap-2 text-3xl font-semibold text-white"><Activity className="h-7 w-7 text-cyan-300" />PriceWatch</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">Amazon Best Sellers identify products; CPK and verified MPN links combine Amazon and other vendor price history.</p>
        </div>
        <button type="button" onClick={() => void load(true)} disabled={refreshing || loading} className="inline-flex items-center gap-2 rounded-md border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:border-cyan-400/50 disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />Refresh data
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="PriceWatch summary">
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">Product discovery list</p><p className="mt-1 text-lg font-semibold text-white">{currentCategory?.list_name ?? "—"}</p></div>
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">Linked / waiting for identity</p><p className="mt-1 text-2xl font-semibold text-cyan-200">{currentCategory?.products.length ?? 0} <span className="text-sm text-slate-500">/ {currentCategory?.unlinked_product_count ?? 0}</span></p></div>
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="flex items-center gap-1.5 text-xs text-slate-400"><Clock3 className="h-3.5 w-3.5" />Latest Best Sellers capture</p><p className="mt-1 text-sm font-medium text-white">{latestCapture ?? "No capture available"}</p></div>
      </section>

      {error && <div role="alert" className="rounded-lg border border-rose-400/30 bg-rose-950/25 p-3 text-sm text-rose-200">{error}</div>}

      <nav className="flex flex-wrap gap-2" aria-label="PriceWatch categories">
        {CATEGORY_TABS.map((tab) => {
          const active = tab.key === categoryKey;
          const count = data?.categories.find((item) => item.category === tab.key)?.products.length ?? 0;
          return <button key={tab.key} type="button" onClick={() => { setCategoryKey(tab.key); setQuery(""); }} aria-pressed={active} className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${active ? "border-cyan-300/60 bg-cyan-300/10 text-cyan-100" : "border-slate-700 bg-slate-950/60 text-slate-400 hover:text-white"}`}><span className="font-mono text-[10px] font-bold">{tab.mark}</span>{tab.label}<span className="text-[10px] opacity-60">{count}</span></button>;
        })}
      </nav>

      {categoryKey === "ram" && <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/50 p-3" role="group" aria-label="RAM capacity">
        <span className="mr-1 text-xs text-slate-500">RAM capacity</span>
        <button type="button" onClick={() => setRamSizeFilter(null)} aria-pressed={ramSizeFilter === null} className={`rounded-full border px-3 py-1 text-xs ${ramSizeFilter === null ? "border-cyan-300/50 bg-cyan-300/10 text-cyan-100" : "border-slate-700 text-slate-400 hover:text-white"}`}>All sizes</button>
        {ramSizes.map((size) => <button key={size} type="button" onClick={() => setRamSizeFilter(size)} aria-pressed={ramSizeFilter === size} className={`rounded-full border px-3 py-1 text-xs ${ramSizeFilter === size ? "border-cyan-300/50 bg-cyan-300/10 text-cyan-100" : "border-slate-700 text-slate-400 hover:text-white"}`}>{size}GB</button>)}
      </div>}

      {categoryKey === "storage" && <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/50 p-3">
        <span className="mr-1 text-xs text-slate-500">Storage interface</span>
        {([ ["all", "All storage"], ["nvme", "NVMe"], ["sata", "SATA"], ["unclassified", "Unclassified"] ] as const).map(([key, label]) => <button key={key} type="button" onClick={() => setStorageFilter(key)} aria-pressed={storageFilter === key} className={`rounded-full border px-3 py-1 text-xs ${storageFilter === key ? "border-cyan-300/50 bg-cyan-300/10 text-cyan-100" : "border-slate-700 text-slate-400 hover:text-white"}`}>{label} · {storageCounts[key]}</button>)}
        <span className="text-[10px] text-slate-500">Amazon’s broad internal SSD list is classified from product titles; ambiguous titles stay in Unclassified.</span>
      </div>}

      <section className="overflow-hidden rounded-xl border border-slate-700 bg-[#0b1119]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 p-4">
          <div><h2 className="flex items-center gap-2 text-lg font-semibold text-white"><Trophy className="h-4 w-4 text-amber-300" />{currentCategory?.name ?? "Amazon products"} · {categoryKey === "storage" ? (storageFilter === "all" ? "All storage types" : storageFilter.toUpperCase()) : "Amazon Best Sellers"}</h2>
            <p className="mt-1 text-xs text-slate-500">{currentCategory?.last_captured_at ? `Captured ${latestCapture}` : "No bestseller capture has been recorded yet."}{currentCategory?.source_url && <> · <a href={currentCategory.source_url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline">Open Amazon list <ExternalLink className="inline h-3 w-3" /></a></>}</p></div>
          <label className="flex min-w-64 items-center gap-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-400"><Search className="h-4 w-4" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search model, MPN or CPK" className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500" /></label>
        </div>

        <div className="border-b border-slate-800 bg-slate-950/50 px-4 py-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Lowest vendor median trends</h3><p className="mt-1 text-[10px] text-slate-500">Daily median by CPK-linked product, from the earliest captured price through today.</p></div><div className="flex items-center gap-2"><div role="group" aria-label="Amazon Best Sellers chart range" className="inline-flex overflow-hidden rounded-md border border-slate-700"><button type="button" onClick={() => setRankLimit(10)} aria-pressed={rankLimit === 10} className={"px-3 py-1.5 text-xs " + (rankLimit === 10 ? "bg-cyan-300/15 text-cyan-100" : "text-slate-400 hover:text-white")}>Top 10</button><button type="button" onClick={() => setRankLimit(100)} aria-pressed={rankLimit === 100} className={"border-l border-slate-700 px-3 py-1.5 text-xs " + (rankLimit === 100 ? "bg-cyan-300/15 text-cyan-100" : "text-slate-400 hover:text-white")}>Top 100</button></div><span className="text-[10px] text-slate-500">{chartProducts.length} products</span></div></div>
          {chartProducts.length && chartRows.some((row) => chartProducts.some((product) => typeof row[product.cpk] === "number")) ? <div className="h-[360px] w-full">
            <ResponsiveContainer width="100%" height="100%"><LineChart data={chartRows} margin={{ top: 8, right: 18, left: 8, bottom: 4 }}>
              <CartesianGrid stroke="#263344" strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" type="number" scale="time" domain={data?.days.length ? [data.days[0].timestamp, data.days[data.days.length - 1].timestamp] : ["dataMin", "dataMax"]} tickCount={9} tickFormatter={(value: number) => new Date(value).toLocaleDateString("en-GB", { day: "2-digit", month: "short" })} tick={{ fill: "#94a3b8", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#475569" }} />
              <YAxis width={68} tick={{ fill: "#94a3b8", fontSize: 10 }} tickFormatter={(value: number) => `£${value}`} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
              <Tooltip contentStyle={{ backgroundColor: "#0b1119", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }} labelStyle={{ color: "#cbd5e1" }} labelFormatter={(value) => new Date(Number(value)).toLocaleDateString("en-GB", { dateStyle: "medium" })} formatter={(value) => [money(typeof value === "number" ? value : null), "Daily median"]} />
              <Legend height={52} wrapperStyle={{ fontSize: 9, overflowY: "auto" }} formatter={(value, entry) => {
                const product = chartProducts.find((item) => item.cpk === entry.dataKey);
                return product?.url
                  ? <a href={product.url} target="_blank" rel="noreferrer" title={product.title} className="text-slate-300 hover:text-cyan-300 hover:underline">{value}</a>
                  : <span className="text-slate-300" title={product?.title}>{value}</span>;
              }} />
              {chartProducts.map((product) => <Line key={product.cpk} type="linear" dataKey={product.cpk} name={"#" + product.rank + " " + shortProductTitle(product.title)} stroke={"hsl(" + ((product.rank * 137.508) % 360) + " 72% 62%)"} strokeWidth={rankLimit === 10 ? 2 : 1.35} dot={false} activeDot={{ r: 3 }} connectNulls isAnimationActive={false} />)}
            </LineChart></ResponsiveContainer>
          </div> : <div className="flex h-40 items-center justify-center text-xs text-slate-500">No daily price observations for the selected products yet.</div>}
        </div>

        {loading ? <div className="p-8 text-center text-sm text-slate-400">Loading captured Amazon prices…</div> : filteredProducts.length ? <div className="overflow-x-auto">
          <table className="w-full min-w-[2250px] border-collapse text-left text-xs">
            <thead className="sticky top-0 z-10 bg-slate-800 text-[10px] uppercase tracking-wide text-slate-200">
              <tr className="border-b border-slate-700"><th className="px-3 py-2" colSpan={3}>Best Sellers product matched to canonical identity</th><th className="px-2 py-2 text-center" colSpan={tableMonths.length}>Lowest vendor median by month</th><th className="px-2 py-2 text-center" colSpan={7}>Current and prior month comparison · {previousMonth?.label ?? "—"} → {currentMonth?.label ?? "—"}</th></tr>
              <tr className="border-b border-slate-700 bg-slate-800/95"><th className="min-w-[430px] px-3 py-3">Product / MPN / CPK</th><th className="w-16 px-3 py-3 text-right">Rank</th>
                {tableMonths.map((month) => <th key={month.key} className="min-w-24 border-l border-slate-700 px-2 py-3 text-right">{month.label}</th>)}
                <th className="min-w-24 border-l border-slate-700 px-2 py-3 text-right">Avg {previousMonth?.label ?? "Prior"}</th><th className="min-w-24 px-2 py-3 text-right">Low {previousMonth?.label ?? "Prior"}</th><th className="min-w-24 border-l border-slate-700 px-2 py-3 text-right">Avg {currentMonth?.label ?? "Current"} MTD</th><th className="min-w-24 px-2 py-3 text-right">Low {currentMonth?.label ?? "Current"} MTD</th><th className="min-w-28 px-2 py-3 text-right">Low change MoM</th><th className="min-w-28 px-2 py-3 text-right">Change vs first month</th><th className="min-w-28 px-2 py-3 text-right">Change vs first (%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredProducts.map((product) => {
                const prior = monthPrice(product, previousMonth?.key);
                const current = monthPrice(product, currentMonth?.key);
                const lowChange = prior?.low != null && current?.low != null ? current.low - prior.low : null;
                const firstObserved = tableMonths.map((month) => monthPrice(product, month.key)?.median).find((value): value is number => value != null) ?? null;
                const changeVsFirst = firstObserved != null && current?.median != null ? current.median - firstObserved : null;
                const percentVsFirst = firstObserved != null && firstObserved > 0 && changeVsFirst != null ? changeVsFirst / firstObserved * 100 : null;
                return <tr key={product.cpk} className="hover:bg-slate-800/40">
                  <td className="max-w-[500px] px-3 py-2"><div className="flex items-center gap-2">{product.image_url && <img src={product.image_url} alt="" className="h-9 w-9 shrink-0 rounded bg-slate-900 object-contain" />}<div className="min-w-0"><a href={product.url ?? undefined} target="_blank" rel="noreferrer" title={product.title} className="line-clamp-2 font-medium text-slate-100 hover:text-cyan-300 hover:underline">{shortProductTitle(product.title)}</a><span className="font-mono text-[10px] text-slate-500">{product.mpn ? `MPN ${product.mpn} · ` : ""}CPK {product.cpk}</span></div></div></td>
                  <td className="px-3 py-2 text-right font-mono text-slate-400">#{product.rank}</td>
                  {tableMonths.map((month, index) => {
                    const value = monthPrice(product, month.key)?.median ?? null;
                    const previousValue = index > 0 ? monthPrice(product, tableMonths[index - 1].key)?.median ?? null : null;
                    const tone = value != null && previousValue != null ? monthChangeClass(value - previousValue) : "text-slate-300";
                    return <td key={month.key} className={`relative overflow-hidden border-l border-slate-800/70 px-2 py-2 text-right font-mono ${tone}`} title={`${monthPrice(product, month.key)?.best_vendor ?? "No vendor"} lowest vendor median; ${monthPrice(product, month.key)?.observations ?? 0} price observations`}><span aria-hidden="true" className="absolute inset-y-1 left-1 rounded-sm bg-cyan-400/15" style={{ width: `${priceBarWidth(value, priceBarMax)}%` }} /> <span className="relative z-10">{money(value)}</span>{monthPrice(product, month.key)?.best_vendor && <span className="relative z-10 block text-[9px] text-slate-500">{monthPrice(product, month.key)?.best_vendor}</span>}</td>;
                  })}
                  <td className="relative overflow-hidden border-l border-slate-800 px-2 py-2 text-right font-mono text-slate-300"><span aria-hidden="true" className="absolute inset-y-1 left-1 rounded-sm bg-slate-400/15" style={{ width: `${priceBarWidth(prior?.average, priceBarMax)}%` }} /><span className="relative z-10">{money(prior?.average)}</span></td><td className="relative overflow-hidden px-2 py-2 text-right font-mono text-slate-300"><span aria-hidden="true" className="absolute inset-y-1 left-1 rounded-sm bg-slate-400/15" style={{ width: `${priceBarWidth(prior?.low, priceBarMax)}%` }} /><span className="relative z-10">{money(prior?.low)}</span></td><td className="relative overflow-hidden border-l border-slate-800 px-2 py-2 text-right font-mono font-semibold text-cyan-100"><span aria-hidden="true" className="absolute inset-y-1 left-1 rounded-sm bg-cyan-400/15" style={{ width: `${priceBarWidth(current?.average, priceBarMax)}%` }} /><span className="relative z-10">{money(current?.average)}</span></td><td className="relative overflow-hidden px-2 py-2 text-right font-mono font-semibold text-cyan-100"><span aria-hidden="true" className="absolute inset-y-1 left-1 rounded-sm bg-cyan-400/15" style={{ width: `${priceBarWidth(current?.low, priceBarMax)}%` }} /><span className="relative z-10">{money(current?.low)}</span></td>
                  <td className={`px-2 py-2 text-right font-mono ${monthChangeClass(lowChange)}`} title="Current month lowest vendor median minus previous month's lowest vendor median">{signedMoney(lowChange)}</td><td className={`px-2 py-2 text-right font-mono ${changeVsFirst == null ? "text-slate-500" : changeVsFirst > 0 ? "bg-rose-400/10 text-rose-300" : changeVsFirst < 0 ? "bg-emerald-400/10 text-emerald-300" : "text-slate-300"}`}>{signedMoney(changeVsFirst)}</td><td className={`px-2 py-2 text-right font-mono ${percentVsFirst != null && percentVsFirst > 0 ? "bg-rose-400/10 text-rose-300" : "text-slate-300"}`}>{percentVsFirst == null ? "—" : `${percentVsFirst > 0 ? "+" : ""}${percentVsFirst.toFixed(1)}%`}</td>
                </tr>;
              })}
            </tbody>
          </table>
        </div> : <div className="p-12 text-center"><Trophy className="mx-auto h-8 w-8 text-slate-700" /><p className="mt-3 text-sm font-medium text-slate-300">{currentCategory?.last_captured_at ? "No linked products match this filter." : "No Amazon Best Sellers capture is available for this category yet."}</p><p className="mt-1 text-xs text-slate-500">Products appear here when the Best Sellers capture resolves a CPK; vendor medians use the existing linked price observations.</p></div>}

        <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 px-4 py-3 text-[10px] leading-4 text-slate-500"><span>Each monthly figure is the lowest median among Amazon and trusted linked vendors. Amazon Best Sellers captures and CPK-linked new-condition marketplace observations are included; Temu and Vinted are excluded. {data?.price_basis}</span><span>Latest Best Sellers capture: {latestCapture ?? "none"}</span></footer>
      </section>
    </div>
  </main>;
}
