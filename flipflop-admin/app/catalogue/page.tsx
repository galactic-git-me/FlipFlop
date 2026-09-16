"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown, ChevronLeft, ChevronRight, Eye, EyeOff, Filter,
  Heart, LayoutGrid, List, RefreshCw, Search, SlidersHorizontal, Table2,
} from "lucide-react";
import { api } from "@/lib/api";
import { canonicalVendorKey, VENDOR_META } from "@/lib/vendors";

type ViewMode = "table" | "listings" | "grid";
type Variant = {
  id: number; listing_id?: number; listing_title: string; image_url?: string | null; slot_type: string;
  playbook_id: number; status: string; tier: string; display_price: number;
  gem_score: number; consecutive_misses: number; last_seen_at: string;
  source_name?: string | null; channel_sources?: string[];
  cpk?: string | null; watch_count?: number | null; offer_count?: number | null; sold_count?: number | null;
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
    <div className="relative rounded-lg border border-white/20 bg-black/25 px-5 py-7 text-center shadow-2xl backdrop-blur-sm">
      <div className="mx-auto mb-2 h-8 w-16 rounded border border-cyan-200/60 bg-cyan-300/20 shadow-[0_0_24px_rgba(34,211,238,.35)]" />
      <span className="max-w-28 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/75">{title.split(" ").slice(0, 2).join(" ")}</span>
      {!imageUrl && <span className="mt-2 block text-[9px] uppercase tracking-wider text-white/45">No image captured</span>}
    </div>
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
  return <span title={meta.label} aria-label={meta.label} className="inline-flex h-6 min-w-6 items-center justify-center rounded border border-white/10 bg-black/30 px-1.5 font-mono text-[9px] font-bold uppercase tracking-tight" style={{ color: meta.color }}>{meta.mark}</span>;
}

function ChannelLogos({ sources, current }: { sources?: string[]; current?: string | null }) {
  const channels = [...new Set([...(sources ?? []), ...(current ? [current] : [])])];
  return <div className="flex items-center gap-1" aria-label={`Available on ${channels.join(", ") || "no channel recorded"}`}>
    {channels.length ? channels.map(source => <ChannelLogo key={source} source={source} />) : <span className="text-[10px] text-slate-600">No channels</span>}
  </div>;
}

export default function CataloguePage() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [view, setView] = useState<ViewMode>("listings");
  const [category, setCategory] = useState("All components");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { setVariants((await api.catalogue.variants(status === "all" ? {} : { status })) as Variant[]); }
    catch { setVariants(fallback); }
    finally { setLoading(false); }
  }, [status]);
  useEffect(() => { void load(); }, [load]);

  const visible = useMemo(() => variants.filter(v => {
    const matchesQuery = !query || v.listing_title.toLowerCase().includes(query.toLowerCase());
    const matchesCategory = category === "All components" || v.slot_type.toLowerCase() === category.toLowerCase().replace(" ", "_");
    return matchesQuery && matchesCategory;
  }), [variants, query, category]);

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
            <div className="flex flex-col gap-3 rounded-lg border border-white/10 bg-[#0b1119] p-3 shadow-xl shadow-black/20 md:flex-row md:items-center">
            <label className="flex min-w-0 flex-1 items-center gap-2 rounded-md border border-white/10 bg-black/20 px-3 text-slate-500 focus-within:border-cyan-400/60"><Search className="h-4 w-4 shrink-0" /><span className="sr-only">Search catalogue</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search components, models or titles" className="h-9 min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-600" /></label>
            <div className="flex items-center gap-2"><select value={status} onChange={e => setStatus(e.target.value)} className="h-9 rounded-md border border-white/10 bg-[#111923] px-2 text-xs text-slate-300 outline-none"><option value="all">All statuses</option><option value="active">Active</option><option value="pending_review">Needs review</option><option value="hidden">Hidden</option></select><button className="inline-flex h-9 items-center gap-2 rounded-md border border-white/10 px-3 text-xs text-slate-300 hover:border-cyan-400/40"><Filter className="h-3.5 w-3.5" /> Filters</button></div>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2"><span className="mr-1 text-xs text-slate-500">Popular:</span>{["CPU", "GPU", "DDR4", "NVMe", "AM4"].map(chip => <button key={chip} onClick={() => setQuery(chip)} className="cursor-pointer rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-[10px] text-slate-300 transition hover:border-cyan-400/50 hover:text-cyan-300">{chip}</button>)}</div>
          </section>

          <div className="mb-3 flex flex-col gap-3 border-b border-white/10 pb-3 sm:flex-row sm:items-center sm:justify-between"><div><span className="text-sm font-semibold text-white">{visible.length.toLocaleString()} results</span><span className="ml-2 text-xs text-slate-500">Sorted by gem score</span></div><div className="flex items-center gap-3"><span className="text-xs text-slate-500">View</span><div className="flex overflow-hidden rounded-md border border-white/10 bg-[#0b1119]">{([["table", Table2, "Table"], ["listings", List, "Listings"], ["grid", LayoutGrid, "Grid"]] as const).map(([value, Icon, label]) => <button key={value} onClick={() => setView(value)} aria-pressed={view === value} className={`inline-flex cursor-pointer items-center gap-1.5 px-3 py-2 text-[11px] transition ${view === value ? "bg-cyan-400 text-slate-950" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><Icon className="h-3.5 w-3.5" />{label}</button>)}</div></div></div>

          {view === "table" ? <TableView variants={visible} /> : <div className={view === "grid" ? "grid gap-3 sm:grid-cols-2 xl:grid-cols-3" : "space-y-3"}>{visible.map((v, index) => <ListingCard key={v.id} variant={v} index={index} compact={view === "listings"} />)}</div>}
          {!loading && visible.length === 0 && <div className="rounded-lg border border-dashed border-white/10 py-16 text-center text-sm text-slate-500">No catalogue matches. Try clearing the search or filters.</div>}
          <div className="mt-6 flex items-center justify-between text-xs text-slate-500"><span>Showing {visible.length} of {variants.length} catalogue opportunities</span><div className="flex items-center gap-1"><button aria-label="Previous catalogue page" className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white"><ChevronLeft className="h-3.5 w-3.5" /></button><span className="px-2 text-slate-300">1</span><button aria-label="Next catalogue page" className="cursor-pointer rounded border border-white/10 p-1.5 hover:text-white"><ChevronRight className="h-3.5 w-3.5" /></button></div></div>
        </div>
      </div>
    </div>
  </div>;
}

function ListingCard({ variant: v, index, compact }: { variant: Variant; index: number; compact: boolean }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <article className={`overflow-hidden rounded-lg border border-white/10 bg-[#0b1119] transition hover:border-cyan-400/40 hover:shadow-[0_0_24px_rgba(34,211,238,.08)] ${compact ? "flex flex-col sm:flex-row" : ""}`}><div className={compact ? "w-full shrink-0 sm:w-52" : ""}><ProductArt index={index} title={v.slot_type} imageUrl={v.image_url} /></div><div className="min-w-0 flex-1 p-3"><div className="mb-2 flex items-start justify-between gap-3"><div className="min-w-0"><p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-400">{v.tier} tier · {v.slot_type}</p><h2 className="line-clamp-2 text-sm font-semibold leading-snug text-white">{v.listing_title}</h2></div><Status value={v.status} /></div><div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2"><div><p className="text-xl font-bold text-white">£{v.display_price.toFixed(2)}</p><p className="text-[10px] text-slate-500">Buy-in display price</p></div><div><p className="font-mono text-sm font-bold text-emerald-300">{v.gem_score.toFixed(0)}<span className="text-[10px] font-normal text-slate-500"> / 100</span></p><p className="text-[10px] text-slate-500">Gem score</p></div><div className="text-xs text-slate-400"><span className="text-emerald-300">Live</span> · Seen {v.last_seen_at}</div></div><div className="mt-3 grid grid-cols-3 gap-2 rounded-md border border-cyan-400/10 bg-cyan-400/[0.03] px-3 py-2"><div><p className="font-mono text-sm font-semibold text-cyan-200">{metric(v.watch_count)}</p><p className="text-[10px] text-slate-500">Watches</p></div><div title="Number of matched listings with Best Offer enabled"><p className="font-mono text-sm font-semibold text-amber-200">{metric(v.offer_count)}</p><p className="text-[10px] text-slate-500">Offers enabled</p></div><div title="Distinct matched sold comps observed in the last 90 days"><p className="font-mono text-sm font-semibold text-emerald-200">{metric(v.sold_count)}</p><p className="text-[10px] text-slate-500">Sold · 90d</p></div></div><div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2"><ChannelLogos sources={v.channel_sources} current={v.source_name} /><button className="inline-flex items-center gap-1 text-[11px] font-semibold text-cyan-300 hover:text-cyan-200"><Eye className="h-3.5 w-3.5" /> View listing</button></div></div></article>;
}

function TableView({ variants }: { variants: Variant[] }) {
  const metric = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString();
  return <div className="overflow-x-auto rounded-lg border border-white/10 bg-[#0b1119]"><table className="w-full min-w-[980px] text-left text-xs"><thead className="border-b border-white/10 bg-white/[0.03] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-3">Listing</th><th className="px-3 py-3">Category</th><th className="px-3 py-3">Status</th><th className="px-3 py-3 text-right">Price</th><th className="px-3 py-3 text-right">Gem score</th><th className="px-3 py-3 text-right">Watches</th><th className="px-3 py-3 text-right">Offers</th><th className="px-3 py-3 text-right">Sold · 90d</th><th className="px-3 py-3 text-right">Last seen</th><th className="px-4 py-3" /></tr></thead><tbody>{variants.map(v => <tr key={v.id} className="border-b border-white/5 transition last:border-0 hover:bg-white/[0.03]"><td className="max-w-[420px] px-4 py-3"><p className="truncate font-medium text-white">{v.listing_title}</p><p className="mt-1 text-[10px] uppercase text-slate-600">{v.tier} tier · #{v.id}</p></td><td className="px-3 py-3 text-slate-400">{v.slot_type}</td><td className="px-3 py-3"><Status value={v.status} /></td><td className="px-3 py-3 text-right font-semibold text-white">£{v.display_price.toFixed(2)}</td><td className="px-3 py-3 text-right font-mono font-bold text-emerald-300">{v.gem_score.toFixed(0)}</td><td className="px-3 py-3 text-right font-mono text-cyan-200">{metric(v.watch_count)}</td><td className="px-3 py-3 text-right font-mono text-amber-200">{metric(v.offer_count)}</td><td className="px-3 py-3 text-right font-mono text-emerald-200">{metric(v.sold_count)}</td><td className="px-3 py-3 text-right text-slate-500">{v.last_seen_at}</td><td className="px-4 py-3 text-right"><button aria-label={`Toggle visibility for ${v.listing_title}`} className="cursor-pointer rounded p-1.5 text-slate-500 hover:bg-white/10 hover:text-white">{v.status === "active" ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}</button></td></tr>)}</tbody></table></div>;
}
