"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, Check, CheckCircle2, ClipboardCopy, Download, ExternalLink,
  Filter, Link2, Loader2, PackageCheck, RefreshCw, Search, Send, ShieldCheck, X,
} from "lucide-react";
import { api, type ManualBuild } from "@/lib/api";
import {
  capabilities, sourcesFromBuild, type ChannelCapability,
  type CrossListingChannel, type CrossListingSource,
} from "@/lib/cross-listing";

const statusStyles: Record<CrossListingSource["status"], string> = {
  live: "text-emerald-300 bg-emerald-400/10 border-emerald-400/25",
  draft: "text-sky-300 bg-sky-400/10 border-sky-400/25",
  sold: "text-orange-300 bg-orange-400/10 border-orange-400/25",
  ended: "text-slate-300 bg-slate-400/10 border-slate-400/25",
  unavailable: "text-yellow-300 bg-yellow-400/10 border-yellow-400/25",
  failed: "text-red-300 bg-red-400/10 border-red-400/25",
};

const labelForStatus = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function ManualPack({ source, channel }: { source: CrossListingSource; channel: ChannelCapability }) {
  const listing = source.listing;
  const text = [
    `FLIPFLOP MANUAL LISTING PACK`, `Destination: ${channel.label}`, `Source: ${source.source === "ebay_uk" ? "eBay UK" : "FlipFlop.shop"}`,
    `Build ID: ${source.buildId}`, `SKU: ${listing.sku}`, ``, `TITLE`, listing.title, ``, `DESCRIPTION`, listing.description,
    ``, `BULLET POINTS`, ...listing.bulletPoints.map((bullet) => `- ${bullet}`), ``, `PRICE`, `${listing.currency} ${listing.price ?? "TBC"}`,
    ``, `CONDITION`, listing.condition, ``, `SPECIFICATIONS`, ...Object.entries(listing.specifications).map(([key, value]) => `${key}: ${value}`),
    ``, `WARRANTY`, listing.warranty, ``, `SHIPPING`, listing.shipping, ``, `IMAGES`, ...listing.images.map((image) => image.url),
    ``, `MANUAL STEPS`, `1. Open the seller dashboard for ${channel.label}.`, `2. Create or update the listing using the fields above.`,
    `3. Upload the images in the order shown.`, `4. Confirm the returned listing ID and URL in FlipFlop admin.`,
  ].join("\n");
  return <button className="inline-flex cursor-pointer items-center gap-1.5 rounded border border-slate-600 px-2.5 py-1.5 text-xs text-slate-200 transition-colors hover:border-emerald-400/50 hover:text-emerald-300" onClick={() => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `flipflop-${source.buildId}-${channel.channel}-manual-pack.txt`; anchor.click(); URL.revokeObjectURL(url);
  }}><Download className="h-3.5 w-3.5" /> Manual pack</button>;
}

export default function CrossListingPage() {
  const [items, setItems] = useState<CrossListingSource[]>([]);
  const [builds, setBuilds] = useState<Record<number, ManualBuild>>({});
  const [connected, setConnected] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [destinations, setDestinations] = useState<CrossListingChannel[]>([]);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | "ebay_uk" | "flipflop_shop">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | CrossListingSource["status"]>("all");
  const [sort, setSort] = useState<"updated" | "price" | "title">("updated");
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftPrice, setDraftPrice] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [results, setResults] = useState<Array<{ channel: string; status: string; message: string; url?: string }>>([]);

  const channelCapabilities = useMemo(() => capabilities(connected), [connected]);
  const selectedItems = items.filter((item) => selected.has(item.id));
  const filtered = useMemo(() => items.filter((item) => {
    const matchesQuery = !query || `${item.title} ${item.externalId} ${item.buildId}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (sourceFilter === "all" || item.source === sourceFilter) && (statusFilter === "all" || item.status === statusFilter);
  }).sort((a, b) => sort === "title" ? a.title.localeCompare(b.title) : sort === "price" ? (b.price ?? 0) - (a.price ?? 0) : b.updatedAt.localeCompare(a.updatedAt)), [items, query, sourceFilter, statusFilter, sort]);
  const review = reviewId ? items.find((item) => item.id === reviewId) ?? null : null;

  const refresh = useCallback(async () => {
    setRefreshing(true); setError(null);
    try {
      const [summary, ebay] = await Promise.all([api.manualBuilds.list(), api.ebayOAuth.status().catch(() => ({ connected: false }))]);
      const detailResults = await Promise.allSettled(summary.map((build) => api.manualBuilds.get(build.id)));
      const nextBuilds: Record<number, ManualBuild> = {};
      const nextItems: CrossListingSource[] = [];
      const nextWarnings: string[] = [];
      detailResults.forEach((result, index) => {
        if (result.status === "fulfilled") { nextBuilds[result.value.id] = result.value; nextItems.push(...sourcesFromBuild(result.value)); }
        else nextWarnings.push(`Build ${summary[index]?.id ?? "unknown"} could not be refreshed.`);
      });
      setBuilds(nextBuilds); setItems(nextItems); setWarnings(nextWarnings); setConnected(ebay.connected); setRefreshedAt(new Date().toISOString());
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load source listings."); }
    finally { setRefreshing(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const toggleAll = () => setSelected((current) => {
    const next = new Set(current); const allSelected = filtered.length > 0 && filtered.every((item) => next.has(item.id));
    filtered.forEach((item) => allSelected ? next.delete(item.id) : next.add(item.id)); return next;
  });
  const toggleDestination = (channel: CrossListingChannel) => setDestinations((current) => current.includes(channel) ? current.filter((item) => item !== channel) : [...current, channel]);

  const openReview = (item: CrossListingSource) => { setReviewId(item.id); setDraftTitle(item.listing.title); setDraftDescription(item.listing.description); setDraftPrice(item.listing.price == null ? "" : String(item.listing.price)); };
  const saveReview = () => { if (!review) return; setItems((current) => current.map((item) => item.id === review.id ? { ...item, listing: { ...item.listing, title: draftTitle, description: draftDescription, price: draftPrice ? Number(draftPrice) : null }, title: draftTitle, price: draftPrice ? Number(draftPrice) : null } : item)); setReviewId(null); };

  const downloadSelectedPacks = () => { if (!selectedItems.length || !destinations.length) return; selectedItems.forEach((item) => destinations.forEach((destination) => { const capability = channelCapabilities.find((entry) => entry.channel === destination); if (!capability || capability.mode === "api") return; const text = `${item.listing.title}\n${item.listing.description}\n${item.listing.images.map((image) => image.url).join("\n")}`; const url = URL.createObjectURL(new Blob([text], { type: "text/plain" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `flipflop-${item.buildId}-${destination}.txt`; anchor.click(); URL.revokeObjectURL(url); })); };

  const publish = async () => {
    if (!selectedItems.length || !destinations.length) return;
    setPublishing(true); setResults([]);
    const nextResults: Array<{ channel: string; status: string; message: string; url?: string }> = [];
    for (const item of selectedItems) for (const destination of destinations) {
      const capability = channelCapabilities.find((entry) => entry.channel === destination);
      if (!capability) continue;
      if (capability.mode !== "api") { nextResults.push({ channel: capability.label, status: "manual_action_required", message: capability.note }); continue; }
      const build = builds[item.buildId];
      try {
        if (destination === "ebay_uk") {
          const result = await api.manualBuilds.postToEbay(item.buildId, { price: item.listing.price ?? 0, condition: item.listing.condition, publish: true });
          nextResults.push({ channel: capability.label, status: result.success ? "published" : "failed", message: result.success ? "eBay accepted the publish request." : result.error ?? "eBay did not publish the listing.", url: result.url });
        } else if (destination === "flipflop_shop" && build) {
          const result = await api.manualBuilds.listOnStorefront(item.buildId, item.listing.price ?? 0);
          nextResults.push({ channel: capability.label, status: "published", message: "Linked to the existing storefront product.", url: result.storefront_url });
        }
      } catch (cause) { nextResults.push({ channel: capability.label, status: "failed", message: cause instanceof Error ? cause.message : "Provider request failed." }); }
    }
    setResults(nextResults); setPublishing(false); await refresh();
  };

  return <div className="mx-auto min-h-full max-w-[1500px] space-y-5 p-4 md:p-6 lg:p-8">
    <header className="flex flex-col justify-between gap-4 border-b border-slate-700/70 pb-5 lg:flex-row lg:items-end">
      <div><div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-emerald-300"><Link2 className="h-4 w-4" /> Inventory synchronisation</div><h1 className="text-3xl font-semibold text-white">Cross-listing</h1><p className="mt-1 max-w-3xl text-sm text-slate-400">Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.</p></div>
      <button onClick={() => void refresh()} disabled={refreshing} className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-600 bg-slate-900/70 px-4 py-2.5 text-sm text-slate-100 transition-colors hover:border-emerald-400/60 hover:text-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> {refreshing ? "Refreshing…" : "Refresh listings"}</button>
    </header>

    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">{channelCapabilities.map((channel) => <div key={channel.channel} className="rounded-lg border border-slate-700/80 bg-[#0d1521]/90 p-3"><div className="flex items-center justify-between gap-2"><span className="text-sm font-medium text-white">{channel.label}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${channel.mode === "api" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : channel.mode === "requires_approval" ? "border-yellow-400/30 bg-yellow-400/10 text-yellow-300" : "border-slate-600 bg-slate-800 text-slate-300"}`}>{channel.mode === "api" ? "API" : labelForStatus(channel.mode)}</span></div><p className="mt-2 text-xs leading-5 text-slate-400">{channel.note}</p></div>)}</section>

    {warnings.length > 0 && <div className="flex items-start gap-3 rounded-lg border border-yellow-400/30 bg-yellow-400/10 p-3 text-sm text-yellow-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" /><div><div className="font-medium">Partial refresh</div>{warnings.map((warning) => <div key={warning} className="text-xs text-yellow-200/80">{warning}</div>)}</div></div>}
    {error && <div className="flex items-center justify-between gap-3 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100"><span>{error}</span><button onClick={() => void refresh()} className="cursor-pointer underline">Retry</button></div>}

    <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 shadow-2xl shadow-black/10">
      <div className="flex flex-col gap-3 border-b border-slate-700/70 p-4 xl:flex-row xl:items-center"><div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" /><input aria-label="Search listings" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, build ID or external ID…" className="w-full rounded-md border border-slate-700 bg-slate-900/80 py-2 pl-9 pr-3 text-sm text-white outline-none transition-colors focus:border-emerald-400/60" /></div><div className="flex flex-wrap gap-2"><select aria-label="Source filter" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="all">All sources</option><option value="ebay_uk">eBay UK</option><option value="flipflop_shop">FlipFlop.shop</option></select><select aria-label="Status filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="all">All statuses</option>{Object.keys(statusStyles).map((status) => <option key={status} value={status}>{labelForStatus(status)}</option>)}</select><select aria-label="Sort listings" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="updated">Recently updated</option><option value="price">Highest price</option><option value="title">Title</option></select></div></div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 text-xs"><button onClick={toggleAll} className="inline-flex cursor-pointer items-center gap-2 text-slate-200 hover:text-emerald-300"><span className={`flex h-4 w-4 items-center justify-center rounded border ${filtered.length > 0 && filtered.every((item) => selected.has(item.id)) ? "border-emerald-400 bg-emerald-400 text-slate-950" : "border-slate-600"}`}>{filtered.length > 0 && filtered.every((item) => selected.has(item.id)) && <Check className="h-3 w-3" />}</span>Select all filtered ({filtered.length})</button><span className="text-slate-500">{selectedItems.length} selected · {refreshedAt ? `refreshed ${new Date(refreshedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "not refreshed"}</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[880px] text-left text-sm"><thead className="bg-slate-900/60 text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="w-12 px-4 py-3" /><th className="px-4 py-3">Listing</th><th className="px-4 py-3">Source</th><th className="px-4 py-3">Price / stock</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Updated</th><th className="px-4 py-3" /></tr></thead><tbody className="divide-y divide-slate-800/80">{filtered.map((item) => <tr key={item.id} className={`transition-colors hover:bg-slate-800/30 ${selected.has(item.id) ? "bg-emerald-400/[0.04]" : ""}`}><td className="px-4 py-3"><button aria-label={`Select ${item.title}`} onClick={() => setSelected((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })} className={`flex h-4 w-4 cursor-pointer items-center justify-center rounded border ${selected.has(item.id) ? "border-emerald-400 bg-emerald-400 text-slate-950" : "border-slate-600"}`}>{selected.has(item.id) && <Check className="h-3 w-3" />}</button></td><td className="max-w-[370px] px-4 py-3"><div className="flex items-center gap-3"><div className="h-11 w-14 overflow-hidden rounded border border-slate-700 bg-slate-900">{item.imageUrl ? <img src={item.imageUrl} alt="" className="h-full w-full object-cover" /> : <PackageCheck className="m-3 h-5 w-5 text-slate-600" />}</div><div className="min-w-0"><div className="truncate font-medium text-slate-100">{item.title}</div><div className="mt-1 text-xs text-slate-500">Build {item.buildId} · {item.externalId}</div></div></div></td><td className="px-4 py-3 text-slate-300">{item.source === "ebay_uk" ? "eBay UK" : "FlipFlop.shop"}</td><td className="px-4 py-3 text-slate-200">{item.price == null ? "TBC" : `£${item.price.toFixed(2)}`}<div className="text-xs text-slate-500">Qty {item.quantity} · {item.condition}</div></td><td className="px-4 py-3"><span className={`rounded-full border px-2 py-1 text-[11px] ${statusStyles[item.status]}`}>{labelForStatus(item.status)}</span></td><td className="px-4 py-3 text-xs text-slate-500">{new Date(item.updatedAt).toLocaleDateString("en-GB")}</td><td className="px-4 py-3 text-right"><button onClick={() => openReview(item)} className="cursor-pointer rounded border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-emerald-400/50 hover:text-emerald-300">Review</button></td></tr>)}</tbody></table>{!refreshing && filtered.length === 0 && <div className="px-6 py-16 text-center"><Filter className="mx-auto h-7 w-7 text-slate-600" /><p className="mt-3 text-sm text-slate-300">No source listings match this view.</p><p className="mt-1 text-xs text-slate-500">Only listings returned by the connected eBay/storefront integrations are shown.</p></div>}{refreshing && <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading source listings…</div>}</div>
    </section>

    <section className="sticky bottom-3 z-20 rounded-xl border border-emerald-400/20 bg-[#0b121d]/95 p-4 shadow-2xl shadow-black/30 backdrop-blur"><div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"><div className="min-w-0 flex-1"><div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wider text-slate-400"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Destination workflow</div><div className="flex flex-wrap gap-2">{channelCapabilities.map((channel) => <button key={channel.channel} onClick={() => toggleDestination(channel.channel)} className={`cursor-pointer rounded-md border px-3 py-2 text-xs transition-colors ${destinations.includes(channel.channel) ? "border-emerald-400/60 bg-emerald-400/10 text-emerald-200" : "border-slate-700 text-slate-400 hover:border-slate-500"}`}><span className="mr-1.5">{destinations.includes(channel.channel) ? "✓" : "○"}</span>{channel.label}</button>)}</div><div className="mt-2 text-xs text-slate-500">{selectedItems.length} source listing{selectedItems.length === 1 ? "" : "s"} × {destinations.length} destination{destinations.length === 1 ? "" : "s"} = {selectedItems.length * destinations.length} job{selectedItems.length * destinations.length === 1 ? "" : "s"}. Manual-only destinations remain manual_action_required.</div></div><div className="flex flex-wrap gap-2"><button onClick={downloadSelectedPacks} disabled={!selectedItems.length || !destinations.length} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-600 px-3 py-2.5 text-xs text-slate-200 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"><ClipboardCopy className="h-4 w-4" /> Download manual packs</button><button onClick={() => { if (selectedItems.length && destinations.length && window.confirm(`Confirm ${selectedItems.length * destinations.length} cross-listing job(s)? API destinations may create or update live listings.`)) void publish(); }} disabled={publishing || !selectedItems.length || !destinations.length} className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-emerald-400 px-4 py-2.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40">{publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{publishing ? "Submitting…" : "Review & submit"}</button></div></div></section>

    {results.length > 0 && <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4"><h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-emerald-300" /> Batch results</h2><div className="space-y-2">{results.map((result, index) => <div key={`${result.channel}-${index}`} className="flex flex-col gap-1 rounded border border-slate-800 bg-slate-900/50 p-3 text-xs md:flex-row md:items-center md:justify-between"><div><span className="font-medium text-slate-200">{result.channel}</span><span className={`ml-2 ${result.status === "failed" ? "text-red-300" : result.status === "manual_action_required" ? "text-yellow-300" : "text-emerald-300"}`}>{labelForStatus(result.status)}</span><div className="mt-1 text-slate-400">{result.message}</div></div>{result.url && <a href={result.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-300 hover:underline">View listing <ExternalLink className="h-3 w-3" /></a>}</div>)}</div></section>}

    {review && <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/75 p-3 backdrop-blur-sm md:items-center"><div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-slate-700 bg-[#0e1724] p-5 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><div className="text-xs uppercase tracking-wider text-emerald-300">Payload review · {review.source === "ebay_uk" ? "eBay UK" : "FlipFlop.shop"}</div><h2 className="mt-1 text-xl font-semibold text-white">{review.title}</h2><p className="mt-1 text-xs text-slate-500">Canonical build {review.buildId} · edits are local to this review until saved.</p></div><button aria-label="Close review" onClick={() => setReviewId(null)} className="cursor-pointer rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-5 w-5" /></button></div><div className="mt-5 grid gap-4 md:grid-cols-2"><label className="text-xs text-slate-400">Title<input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} maxLength={80} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400/60" /><span className="mt-1 block text-right text-[10px] text-slate-500">{draftTitle.length}/80</span></label><label className="text-xs text-slate-400">Price (GBP)<input type="number" min="0" step="0.01" value={draftPrice} onChange={(event) => setDraftPrice(event.target.value)} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400/60" /></label></div><label className="mt-2 block text-xs text-slate-400">Description<textarea value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} rows={8} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm leading-6 text-slate-200 outline-none focus:border-emerald-400/60" /><span className="mt-1 block text-right text-[10px] text-slate-500">{draftDescription.length} characters</span></label><div className="mt-4 rounded-lg border border-slate-700/80 bg-slate-900/50 p-3"><div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Copied and transformed</div><div className="grid gap-2 text-xs text-slate-300 md:grid-cols-2"><div>✓ {review.listing.images.length} public image URL{review.listing.images.length === 1 ? "" : "s"}</div><div>✓ {Object.keys(review.listing.specifications).length} specification fields</div><div>✓ Shared price, stock and condition</div><div>⚠ Platform category and item specifics require destination validation</div></div></div><div className="mt-5 flex flex-wrap justify-end gap-2"><ManualPack source={{ ...review, listing: { ...review.listing, title: draftTitle, description: draftDescription, price: draftPrice ? Number(draftPrice) : null } }} channel={channelCapabilities[0]} /><button onClick={() => setReviewId(null)} className="cursor-pointer rounded-md border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-slate-400">Cancel</button><button onClick={saveReview} className="cursor-pointer rounded-md bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300">Save review edits</button></div></div></div>}
  </div>;
}
