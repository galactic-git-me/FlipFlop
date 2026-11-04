"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ExternalLink, Mail, RefreshCw, X } from "lucide-react";
import { api, type ManualBuild } from "@/lib/api";
import { sourcesFromBuild, type CrossListingChannel } from "@/lib/cross-listing";

const CHANNELS: { id: CrossListingChannel; label: string; color: string }[] = [
  { id: "ebay_uk", label: "eBay UK", color: "#e53238" },
  { id: "flipflop_shop", label: "FlipFlop.shop", color: "#3b82f6" },
  { id: "onbuy", label: "OnBuy", color: "#62c8ff" },
  { id: "amazon", label: "Amazon", color: "#ff9900" },
  { id: "facebook_catalog", label: "Facebook", color: "#1877f2" },
  { id: "vinted", label: "Vinted", color: "#09b1ba" },
  { id: "google_shopping", label: "Google Shopping", color: "#4285f4" },
];

type Event = Awaited<ReturnType<typeof api.emailEvents.list>>[number];
type Row = {
  build: ManualBuild;
  title: string;
  image: string | null;
  bucket: "live" | "ended" | "none";
  channels: Partial<Record<CrossListingChannel, { status: "live" | "sold" | "ended"; url: string | null }>>;
};

function channelEmailMatches(event: Event, build: ManualBuild, channel: CrossListingChannel) {
  const marketplace = (event.marketplace || "").toLowerCase();
  const aliases: Record<CrossListingChannel, string[]> = {
    ebay_uk: ["ebay", "e-bay"], flipflop_shop: ["storefront", "flipflop", "shop"],
    onbuy: ["onbuy"], amazon: ["amazon"], facebook_catalog: ["facebook", "meta"],
    vinted: ["vinted"], google_shopping: ["google"],
  };
  if (!aliases[channel].some((alias) => marketplace.includes(alias))) return false;
  if (event.manual_build_id === build.id) return true;
  const searchable = `${event.subject} ${event.summary} ${event.body || ""}`.toLowerCase();
  const listingId = channel === "ebay_uk" ? build.ebay_listing_id : null;
  return Boolean(
    (listingId && searchable.includes(listingId.toLowerCase())) ||
    (build.generated_title && searchable.includes(build.generated_title.toLowerCase())) ||
    searchable.includes(`build ${build.id}`) || searchable.includes(`build #${build.id}`)
  );
}

function saleTooltip(build: ManualBuild, channel: CrossListingChannel) {
  const address = build.buyer_address_json;
  const addressText = [address?.address_line1, address?.address_line2, address?.city, address?.state_or_province, address?.postal_code, address?.country_code]
    .filter(Boolean).join(", ");
  const soldChannel = build.ebay_order_id ? "ebay_uk" : "flipflop_shop";
  return [
    `Sold on ${CHANNELS.find((item) => item.id === channel)?.label || channel}`,
    `Customer: ${build.buyer_name || "not recorded"}`,
    `Email: ${build.customer_email || "not recorded"}`,
    `Phone: ${address?.phone || "not recorded"}`,
    `Delivery: ${addressText || "address not recorded"}`,
    `Price: ${build.sale_price_actual == null ? "not recorded" : `£${build.sale_price_actual.toFixed(2)}`}`,
    `Order: ${build.ebay_order_id || "not recorded"}`,
    `Sale recorded: ${channel === soldChannel && build.updated_at ? new Date(build.updated_at).toLocaleString("en-GB") : "time not recorded"}`,
  ].join("\n");
}

export default function LiveBuildsPage() {
  const [builds, setBuilds] = useState<ManualBuild[]>([]);
  const [schedules, setSchedules] = useState<Awaited<ReturnType<typeof api.crossListing.schedules>>>([]);
  const [events, setEvents] = useState<Awaited<ReturnType<typeof api.emailEvents.list>>>([]);
  const [segments, setSegments] = useState<Awaited<ReturnType<typeof api.curatedBuilds.list>>["segments"]>([]);
  const [tab, setTab] = useState<"live" | "ended">("live");
  const [activeEvent, setActiveEvent] = useState<{ row: Row; channel: CrossListingChannel } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkCheck, setLinkCheck] = useState<{ checked: number; ended: number; inconclusive: number } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, emailEvents, curated] = await Promise.all([
        api.manualBuilds.list(), api.emailEvents.list(), api.curatedBuilds.list(),
      ]);
      const checkedLinks = await api.crossListing.checkLinks().catch(() => null);
      setLinkCheck(checkedLinks);
      const channelSchedules = await api.crossListing.schedules();
      const results = await Promise.allSettled(summary.map((item) => api.manualBuilds.get(item.id)));
      setBuilds(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
      setSchedules(channelSchedules);
      setEvents(emailEvents);
      setSegments(curated.segments);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load live builds.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const rows = useMemo(() => builds.map((build): Row => {
    const sources = sourcesFromBuild(build);
    const channels: Row["channels"] = {};
    const ebay = sources.find((source) => source.source === "ebay_uk");
    const shop = sources.find((source) => source.source === "flipflop_shop");
    const saleChannel: CrossListingChannel = build.ebay_order_id ? "ebay_uk" : "flipflop_shop";
    if (ebay && ebay.status !== "unavailable") channels.ebay_uk = { status: build.status === "sold" ? saleChannel === "ebay_uk" ? "sold" : "ended" : ebay.status === "live" ? "live" : ebay.status === "ended" ? "ended" : "ended", url: ebay.url };
    if (shop && shop.status !== "unavailable") channels.flipflop_shop = { status: build.status === "sold" ? saleChannel === "flipflop_shop" ? "sold" : "ended" : shop.status === "live" ? "live" : "ended", url: shop.url };
    for (const schedule of schedules.filter((item) => item.build_id === build.id)) {
      const channel = schedule.channel as CrossListingChannel;
      if (!CHANNELS.some((item) => item.id === channel)) continue;
      const status = build.status === "sold"
        ? channel === saleChannel ? "sold" : "ended"
        : ["published", "active", "live"].includes(schedule.status.toLowerCase()) ? "live" : "ended";
      channels[channel] = { status, url: schedule.listing_url || null };
    }
    if (build.status === "sold" && !Object.values(channels).some((channel) => channel?.status === "sold")) {
      channels[saleChannel] = { status: "sold", url: saleChannel === "ebay_uk" ? build.ebay_listing_url : null };
    }
    const title = build.generated_title || build.name;
    const sourcesWithLive = Object.values(channels).some((channel) => channel?.status === "live");
    const sourcesWithEnded = Object.values(channels).some((channel) => channel?.status === "ended" || channel?.status === "sold");
    return { build, title, image: build.hero_photo_url || sources[0]?.imageUrl || null, channels, bucket: sourcesWithLive ? "live" : sourcesWithEnded ? "ended" : "none" };
  }).filter((row) => row.bucket === tab), [builds, schedules, tab]);

  const eventRows = activeEvent ? events.filter((event) => channelEmailMatches(event, activeEvent.row.build, activeEvent.channel)) : [];

  return <main className="space-y-5 p-6 text-slate-100">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300">Marketplace monitoring</p><h1 className="mt-1 text-3xl font-semibold">Live Builds</h1><p className="mt-1 text-sm text-slate-400">Listings currently selling, completed sales and ended channel listings.</p>{linkCheck && <p className="mt-1 text-xs text-slate-500">Link check: {linkCheck.checked} checked · {linkCheck.ended} confirmed ended · {linkCheck.inconclusive} inconclusive</p>}</div>
      <button onClick={() => void refresh()} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm hover:border-emerald-400/50"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh &amp; check links</button>
    </div>
    <div className="flex gap-2 border-b border-slate-800">
      {([["live", "LIVE"], ["ended", "SOLD / ENDED"]] as const).map(([id, label]) => <button key={id} onClick={() => setTab(id)} className={`border-b-2 px-4 py-3 text-xs font-semibold tracking-wider ${tab === id ? "border-emerald-400 text-emerald-300" : "border-transparent text-slate-500 hover:text-slate-200"}`}>{label}</button>)}
    </div>
    {error && <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</p>}
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-[#0b121d]/90">
      <table className="w-full min-w-[1780px] text-left text-sm">
        <thead className="bg-slate-900/70 text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-3">Listing</th>{CHANNELS.map((channel) => <th key={channel.id} className="border-l border-slate-800 px-3 py-3 text-center" style={{ color: channel.color }}>{channel.label}</th>)}<th className="border-l border-slate-800 px-3 py-3 text-center">eBay watchers / basket</th><th className="border-l border-slate-800 px-3 py-3 text-center">Shop page views</th></tr></thead>
        <tbody className="divide-y divide-slate-800/80">{rows.map((row) => <tr key={row.build.id} className="hover:bg-slate-800/30">
          <td className="max-w-[340px] px-4 py-3"><div className="flex items-center gap-3">{row.image ? <img src={row.image} alt="" className="h-11 w-11 rounded object-cover" /> : <div className="h-11 w-11 rounded bg-slate-800" />}<div className="min-w-0">{(row.channels.ebay_uk?.url || row.channels.flipflop_shop?.url) ? <a href={row.channels.ebay_uk?.url || row.channels.flipflop_shop?.url || undefined} target="_blank" rel="noreferrer" className="block truncate font-medium hover:text-emerald-300">{row.title}<ExternalLink className="ml-1 inline h-3 w-3" /></a> : <span className="block truncate font-medium">{row.title}</span>}<span className="text-xs text-slate-500">Build {row.build.id} · {row.build.status}</span></div></div></td>
          {CHANNELS.map((channel) => { const state = row.channels[channel.id]; const messages = events.filter((event) => channelEmailMatches(event, row.build, channel.id)); const sold = state?.status === "sold"; const live = state?.status === "live"; const tip = sold ? saleTooltip(row.build, channel.id) : live ? `Confirmed live on ${channel.label}` : state?.status === "ended" ? `Ended on ${channel.label}` : `Not listed on ${channel.label}`; return <td key={channel.id} className="border-l border-slate-800/60 px-3 py-3 text-center"><div className="flex min-h-12 flex-col items-center justify-center gap-1"><span title={tip} aria-label={tip} className={`inline-flex h-7 w-7 items-center justify-center rounded-full border ${sold ? "border-blue-400/50 bg-blue-400/10 text-blue-300" : live ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300" : "border-slate-700 text-slate-600"}`}>{live || sold ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}</span><button title={`Show ${messages.length} matching marketplace email events`} onClick={() => setActiveEvent({ row, channel: channel.id })} className="inline-flex items-center gap-1 text-[10px] text-slate-400 hover:text-emerald-300"><Mail className="h-3 w-3" />{messages.length}</button></div></td>; })}
          <td className="border-l border-slate-800 px-3 py-3 text-center text-slate-500" title="eBay watcher and basket counts are not currently collected for owned listings.">—</td><td className="border-l border-slate-800 px-3 py-3 text-center text-slate-500" title="FlipFlop.shop page views are not currently tracked here.">—</td>
        </tr>)}{!loading && rows.length === 0 && <tr><td colSpan={10} className="p-12 text-center text-slate-500">No {tab === "live" ? "live" : "sold or ended"} builds found.</td></tr>}</tbody>
      </table>
    </div>
    <section className="space-y-3 rounded-xl border border-slate-800 bg-[#0b121d]/90 p-4">
      <div><h2 className="text-lg font-semibold">Curated build segments</h2><p className="mt-1 text-xs text-slate-400">One row per customer type and budget segment. These are curated storefront offers, not individual physical builds.</p></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-900/70 text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-3">Segment</th><th className="border-l border-slate-800 px-4 py-3 text-center">FlipFlop.shop</th><th className="border-l border-slate-800 px-4 py-3">Availability</th><th className="border-l border-slate-800 px-4 py-3 text-right">Selling price</th><th className="border-l border-slate-800 px-4 py-3">Updated</th></tr></thead><tbody className="divide-y divide-slate-800/80">{segments.map((segment) => <tr key={segment.id} className="hover:bg-slate-800/30"><td className="px-4 py-3"><div className="font-medium">{segment.customer_type} · {segment.budget_level}</div><div className="text-xs text-slate-500">Segment {segment.id}</div></td><td className="border-l border-slate-800 px-4 py-3 text-center"><span title={segment.is_live ? "Curated segment is live on FlipFlop.shop" : "Curated segment is not live on FlipFlop.shop"} className={`inline-flex h-7 w-7 items-center justify-center rounded-full border ${segment.is_live ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-300" : "border-slate-700 text-slate-600"}`}>{segment.is_live ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}</span></td><td className="border-l border-slate-800 px-4 py-3 text-slate-300">{segment.availability_status.replaceAll("_", " ")}</td><td className="border-l border-slate-800 px-4 py-3 text-right">{segment.selling_price == null ? "—" : `£${segment.selling_price.toFixed(2)}`}</td><td className="border-l border-slate-800 px-4 py-3 text-xs text-slate-500">{segment.updated_at ? new Date(segment.updated_at).toLocaleString("en-GB") : "—"}</td></tr>)}{segments.length === 0 && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No curated segments found.</td></tr>}</tbody></table></div>
    </section>
    {activeEvent && <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget) setActiveEvent(null); }}><section role="dialog" aria-modal="true" aria-label={`${activeEvent.channel} email events`} className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-xl border border-slate-700 bg-[#0b121d] p-5 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold">{CHANNELS.find((item) => item.id === activeEvent.channel)?.label} email events</h2><p className="mt-1 text-xs text-slate-400">{activeEvent.row.title} · Build {activeEvent.row.build.id}</p></div><button onClick={() => setActiveEvent(null)} className="rounded p-2 text-slate-400 hover:bg-slate-800" aria-label="Close"><X className="h-4 w-4" /></button></div><div className="mt-4 space-y-2">{eventRows.map((event) => <a key={event.id} href={`/email-events/${event.id}`} className="block rounded-lg border border-slate-800 p-3 hover:border-emerald-400/40"><div className="flex justify-between gap-3"><strong className="text-sm">{event.subject || "(no subject)"}</strong><span className="shrink-0 text-xs text-slate-500">{event.received_at ? new Date(event.received_at).toLocaleString("en-GB") : ""}</span></div><p className="mt-1 text-xs text-slate-400">{event.summary}</p><p className="mt-2 text-[10px] text-slate-500">{event.marketplace || "Unknown marketplace"} · {event.sender} · {event.event_type}</p></a>)}{eventRows.length === 0 && <p className="rounded-lg border border-slate-800 p-8 text-center text-sm text-slate-500">No email events could be reliably matched to this listing.</p>}</div></section></div>}
  </main>;
}
