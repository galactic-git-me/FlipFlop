"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Clock3,
  ExternalLink,
  Inbox,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Tag,
} from "lucide-react";
import { api, type ManualBuild } from "@/lib/api";

type Channel = "ebay_uk" | "flipflop_shop" | "onbuy" | "amazon" | "facebook_catalog" | "vinted" | "google_shopping";
type ListingSchedule = Awaited<ReturnType<typeof api.crossListing.schedules>>[number];
type PublishEvent = Awaited<ReturnType<typeof api.crossListing.actions>>[number];
type EmailEvent = Awaited<ReturnType<typeof api.emailEvents.list>>[number];
type EbayActivity = Awaited<ReturnType<typeof api.liveBuilds.ebayActivity>>;

type Vendor = {
  channel: Channel;
  label: string;
  mark: string;
  activeClass: string;
};

const vendors: Vendor[] = [
  { channel: "ebay_uk", label: "eBay UK", mark: "e", activeClass: "bg-[#e53238] text-white" },
  { channel: "flipflop_shop", label: "FlipFlop.shop", mark: "F", activeClass: "bg-emerald-400 text-slate-950" },
  { channel: "onbuy", label: "OnBuy", mark: "O", activeClass: "bg-[#f5c400] text-slate-950" },
  { channel: "amazon", label: "Amazon", mark: "a", activeClass: "bg-[#232f3e] text-[#ff9900]" },
  { channel: "facebook_catalog", label: "Facebook Marketplace", mark: "f", activeClass: "bg-[#0866ff] text-white" },
  { channel: "vinted", label: "Vinted", mark: "V", activeClass: "bg-[#09b1ba] text-white" },
  { channel: "google_shopping", label: "Google Shopping", mark: "G", activeClass: "bg-white text-[#4285f4]" },
];

type VendorState = { active: boolean; status: string; url?: string | null };
type LiveCard = { build: ManualBuild; channels: Record<Channel, VendorState> };

function scheduleChannel(value: string): Channel | null {
  const normalized: Record<string, Channel> = {
    ebay: "ebay_uk",
    ebay_uk: "ebay_uk",
    storefront: "flipflop_shop",
    flipflop_shop: "flipflop_shop",
    facebook: "facebook_catalog",
    facebook_marketplace: "facebook_catalog",
    facebook_catalog: "facebook_catalog",
    onbuy: "onbuy",
    amazon: "amazon",
    vinted: "vinted",
    google_shopping: "google_shopping",
  };
  return normalized[value] ?? null;
}

function channelStates(build: ManualBuild, schedules: ListingSchedule[]): Record<Channel, VendorState> {
  const latest = new Map<Channel, ListingSchedule>();
  for (const schedule of schedules) {
    if (schedule.build_id !== build.id) continue;
    const channel = scheduleChannel(schedule.channel);
    const previous = channel ? latest.get(channel) : undefined;
    if (channel && (!previous || (schedule.updated_at ?? "") > (previous.updated_at ?? ""))) latest.set(channel, schedule);
  }
  const result = {} as Record<Channel, VendorState>;
  for (const vendor of vendors) {
    if (vendor.channel === "ebay_uk") {
      const active = build.ebay_live === true || build.ebay_listing_status === "active";
      result[vendor.channel] = { active, status: active ? "Live" : build.ebay_listing_status === "unknown" ? "Unverified" : "Not listed", url: build.ebay_listing_url };
      continue;
    }
    if (vendor.channel === "flipflop_shop") {
      const active = build.storefront_live === true;
      result[vendor.channel] = { active, status: active ? "Live" : "Not listed", url: build.storefront_product_id ? `https://theflipflop.shop/builds/${build.storefront_product_id}` : null };
      continue;
    }
    const listing = latest.get(vendor.channel);
    const status = listing?.status ?? "not_listed";
    const submitted = vendor.channel === "google_shopping" && status === "published";
    result[vendor.channel] = {
      active: status === "published" && !submitted,
      status: submitted ? "Submitted; Google review pending" : status.replaceAll("_", " "),
      url: listing?.listing_url ?? null,
    };
  }
  return result;
}

function eventLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value?: string | null) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

export default function LiveBuildsPage() {
  const [cards, setCards] = useState<LiveCard[]>([]);
  const [schedules, setSchedules] = useState<ListingSchedule[]>([]);
  const [events, setEvents] = useState<PublishEvent[]>([]);
  const [emails, setEmails] = useState<EmailEvent[]>([]);
  const [ebay, setEbay] = useState<EbayActivity>({ connected: false, messages: [], offers: [] });
  const [browserJobs, setBrowserJobs] = useState<Awaited<ReturnType<typeof api.crossListing.browserJobs>>>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actionKey, setActionKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [counterDrafts, setCounterDrafts] = useState<Record<string, string>>({});

  const refresh = useCallback(async (activityOnly = false) => {
    setError(null);
    setNotice(null);
    if (activityOnly) setRefreshing(true);
    else setLoading(true);
    try {
      const [summary, nextSchedules, nextEvents, nextEmails, nextEbay, nextJobs] = await Promise.all([
        activityOnly ? Promise.resolve(null) : api.manualBuilds.list(),
        api.crossListing.schedules(),
        api.crossListing.actions(),
        api.emailEvents.list(),
        api.liveBuilds.ebayActivity(),
        api.crossListing.browserJobs(),
      ]);
      if (summary) {
        const details = await Promise.allSettled(summary.map((item) => api.manualBuilds.get(item.id)));
        const nextCards: LiveCard[] = [];
        for (const detail of details) {
          if (detail.status !== "fulfilled") continue;
          const build = detail.value;
          const channels = channelStates(build, nextSchedules);
          if (Object.values(channels).some((state) => state.active)) nextCards.push({ build, channels });
        }
        setCards(nextCards);
      } else {
        setCards((current) => current.map((card) => ({ ...card, channels: channelStates(card.build, nextSchedules) })));
      }
      setSchedules(nextSchedules);
      setEvents(nextEvents);
      setEmails(nextEmails);
      setEbay(nextEbay);
      setBrowserJobs(nextJobs);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load live builds and activity.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const filtered = useMemo(() => cards.filter(({ build }) =>
    !query || `${build.name} ${build.generated_title ?? ""} ${build.id}`.toLowerCase().includes(query.toLowerCase())
  ), [cards, query]);
  const activeListings = cards.reduce((count, card) => count + Object.values(card.channels).filter((state) => state.active).length, 0);
  const linkedEmails = emails.filter((event) => event.manual_build_id != null);
  const unmatchedEmails = emails.filter((event) => event.manual_build_id == null).slice(0, 8);

  const sendEbayReply = async (buildId: number, messageId: string) => {
    const key = `${buildId}:${messageId}`;
    const body = replyDrafts[key]?.trim();
    if (!body || !window.confirm("Send this reply to the eBay buyer?")) return;
    setActionKey(key);
    try {
      const result = await api.liveBuilds.replyToEbayMessage(buildId, messageId, body);
      setNotice(result.message);
      setReplyDrafts((current) => ({ ...current, [key]: "" }));
      await refresh(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not send the eBay reply."); }
    finally { setActionKey(null); }
  };

  const queueInboxCheck = async (buildId: number, channel: string) => {
    const key = `${buildId}:${channel}:inbox_check`;
    setActionKey(key);
    try {
      const result = await api.liveBuilds.queueVendorInboxCheck(buildId, channel);
      setNotice(`${channel} inbox check queued as job ${result.id}. It will run when the authenticated Chrome worker is online.`);
      await refresh(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not queue the vendor inbox check."); }
    finally { setActionKey(null); }
  };

  const queueInboxReply = async (buildId: number, channel: string, messageId: string, sender: string) => {
    const key = `${buildId}:${messageId}`;
    const body = replyDrafts[key]?.trim();
    if (!body || !window.confirm(`Queue this reply to ${sender} on ${channel}? The authenticated Chrome worker will send this exact text.`)) return;
    setActionKey(key);
    try {
      const result = await api.liveBuilds.queueVendorInboxReply({ build_id: buildId, channel, message_id: messageId, body });
      setNotice(`Reply queued as job ${result.id}; the worker must confirm it in the vendor thread.`);
      setReplyDrafts((current) => ({ ...current, [key]: "" }));
      await refresh(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not queue the vendor reply."); }
    finally { setActionKey(null); }
  };

  const respondToOffer = async (offer: EbayActivity["offers"][number], action: "Accept" | "Decline" | "Counter") => {
    const key = `${offer.build_id}:${offer.best_offer_id}`;
    const counter = Number(counterDrafts[key]);
    if (action === "Counter" && (!Number.isFinite(counter) || counter <= 0)) {
      setError("Enter a valid counter price before sending the counter-offer.");
      return;
    }
    const detail = action === "Counter" ? ` with £${counter.toFixed(2)}` : "";
    if (!window.confirm(`${action} the £${offer.price.toFixed(2)} eBay offer${detail}?`)) return;
    setActionKey(key);
    try {
      const result = await api.liveBuilds.respondToEbayOffer(offer.build_id, {
        best_offer_id: offer.best_offer_id,
        action,
        ...(action === "Counter" ? { counter_price: counter } : {}),
      });
      setNotice(result.message);
      await refresh(true);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not respond to the eBay offer."); }
    finally { setActionKey(null); }
  };

  return (
    <main className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Sales floor</p>
          <h1 className="mt-1 text-3xl font-semibold text-white">Live Builds</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">Builds currently available for sale, the vendor channels carrying each one, and the customer activity recorded against them.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading || refreshing} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-600 px-3 py-2 text-sm text-slate-200 hover:border-emerald-400/50 disabled:cursor-wait disabled:opacity-60">
          {loading || refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh builds and inbox
        </button>
      </header>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Live build summary">
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">Builds for sale</p><p className="mt-1 text-2xl font-semibold text-white">{cards.length}</p></div>
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">Active vendor listings</p><p className="mt-1 text-2xl font-semibold text-emerald-300">{activeListings}</p></div>
        <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">Open eBay activity</p><p className="mt-1 text-2xl font-semibold text-cyan-200">{ebay.messages.length + ebay.offers.length}</p></div>
      </section>

      {error && <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-950/30 p-3 text-sm text-red-200"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-950/25 p-3 text-sm text-emerald-200">{notice}</div>}
      {ebay.message && <div className="rounded-lg border border-amber-400/30 bg-amber-950/20 p-3 text-sm text-amber-100">eBay: {ebay.message}</div>}

      <label className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2.5 text-slate-400">
        <Search className="h-4 w-4" />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search builds by name or ID…" className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-500" />
      </label>

      {loading ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-slate-800 bg-slate-950/40 py-16 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" />Loading live inventory…</div>
      ) : filtered.length ? (
        <section className="grid gap-5 md:grid-cols-2 2xl:grid-cols-3" aria-label="Live build cards">
          {filtered.map(({ build, channels }) => {
            const image = build.hero_photo_url ?? build.photos?.find((photo) => photo.kind === "photo")?.url ?? null;
            const buildEmails = linkedEmails.filter((event) => event.manual_build_id === build.id).slice(0, 3);
            const buildEvents = events.filter((event) => event.build_id === build.id).slice(0, 4);
            const allBuildEvents = events.filter((event) => event.build_id === build.id);
            const browserMessages = allBuildEvents.filter((event) => event.event_type === "customer_message_received");
            const buildMessages = ebay.messages.filter((message) => message.build_id === build.id);
            const buildOffers = ebay.offers.filter((offer) => offer.build_id === build.id);
            const liveCount = Object.values(channels).filter((state) => state.active).length;
            return (
              <article key={build.id} className="overflow-hidden rounded-xl border border-slate-700/80 bg-[#0b121d]/95 shadow-lg shadow-black/20">
                <div className="relative aspect-[16/9] bg-slate-900">
                  {image ? <img src={image} alt={`${build.name} product`} className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-sm text-slate-500">No product photo</div>}
                  <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-slate-950 via-slate-950/90 to-transparent px-3 pb-3 pt-10">
                    <div className="flex items-center gap-1.5" aria-label="Vendor listing status">
                      {vendors.map((vendor) => {
                        const state = channels[vendor.channel];
                        const waiting = !state.active && state.status !== "not listed";
                        return (
                          <span key={vendor.channel} title={`${vendor.label}: ${state.status}`} aria-label={`${vendor.label}: ${state.status}`} className={`relative flex h-7 min-w-7 items-center justify-center rounded-full border border-white/10 px-1.5 text-xs font-bold shadow ${state.active ? vendor.activeClass : waiting ? "bg-amber-400/20 text-amber-200" : "bg-slate-700/80 text-slate-400"}`}>
                            {vendor.mark}
                            {state.url && <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-white ring-1 ring-slate-950" />}
                          </span>
                        );
                      })}
                    </div>
                    <span className="rounded-full border border-emerald-300/25 bg-slate-950/80 px-2.5 py-1 text-[11px] font-medium text-emerald-200">For sale · {liveCount} channel{liveCount === 1 ? "" : "s"}</span>
                  </div>
                </div>
                <div className="space-y-4 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-base font-semibold text-white">{build.generated_title || build.name}</h2>
                      <p className="mt-1 text-xs text-slate-500">Build {build.id} · {build.components?.length ?? 0} components</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-lg font-semibold text-emerald-200">{build.ebay_price != null ? `£${build.ebay_price.toFixed(2)}` : "Price not saved"}</p>
                      <Link href={`/builds/${build.id}`} className="mt-1 inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200">Build details <ArrowUpRight className="h-3 w-3" /></Link>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {vendors.map((vendor) => {
                      const state = channels[vendor.channel];
                      return <div key={vendor.channel} className="flex min-w-0 items-center gap-2 rounded-md border border-slate-800 bg-slate-950/50 px-2 py-1.5" title={state.status}>
                        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${state.active ? vendor.activeClass : state.status !== "not listed" ? "bg-amber-400/20 text-amber-200" : "bg-slate-800 text-slate-500"}`}>{vendor.mark}</span>
                        <span className={`truncate text-[11px] ${state.active ? "text-slate-200" : "text-slate-500"}`}>{vendor.label}</span>
                        {state.url && <a href={state.url} target="_blank" rel="noreferrer" aria-label={`Open ${vendor.label} listing`} className="ml-auto shrink-0 text-slate-500 hover:text-cyan-300"><ExternalLink className="h-3 w-3" /></a>}
                      </div>;
                    })}
                  </div>

                  <div className="space-y-3 border-t border-slate-800 pt-3">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-300"><MessageCircle className="h-4 w-4 text-cyan-300" />Customer messages</h3>
                      <span className="text-[11px] text-slate-500">{buildMessages.length} unanswered eBay · {buildEmails.length} linked emails</span>
                    </div>
                    {vendors.filter((vendor) => ["onbuy", "facebook_catalog", "vinted", "amazon"].includes(vendor.channel) && channels[vendor.channel].active).map((vendor) => {
                      const lastJob = browserJobs.find((job) => job.build_id === build.id && job.channel === vendor.channel && job.operation.startsWith("inbox_"));
                      const key = `${build.id}:${vendor.channel}:inbox_check`;
                      return <div key={vendor.channel} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2">
                        <span className="text-xs text-slate-300">{vendor.label} inbox · {lastJob ? `${lastJob.status.replaceAll("_", " ")} · ${lastJob.message || lastJob.operation}` : "not checked yet"}</span>
                        <button type="button" onClick={() => void queueInboxCheck(build.id, vendor.channel)} disabled={!!actionKey} className="cursor-pointer rounded border border-cyan-300/30 px-2.5 py-1 text-xs text-cyan-200 disabled:opacity-50">{actionKey === key ? "Queueing…" : "Check inbox"}</button>
                      </div>;
                    })}
                    {browserMessages.map((event) => {
                      const message = (event.metadata?.message ?? {}) as Record<string, string>;
                      const key = `${build.id}:${message.message_id}`;
                      return <div key={event.id} className="rounded-lg border border-cyan-400/20 bg-cyan-950/15 p-3">
                        <div className="flex items-center justify-between gap-2 text-xs"><span className="font-medium text-cyan-100">{message.sender || "Vendor buyer"} · {event.channel}</span><span className="shrink-0 text-slate-500">{formatDate(message.received_at || event.created_at)}</span></div>
                        <p className="mt-1 text-xs font-medium text-slate-200">{message.subject || "Customer message"}</p>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-400">{message.body}</p>
                        {message.thread_url && <a href={message.thread_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-[10px] text-cyan-300">Open vendor conversation <ExternalLink className="h-3 w-3" /></a>}
                        <div className="mt-3 space-y-2">
                          <textarea aria-label={`Reply to ${message.sender || "vendor buyer"}`} value={replyDrafts[key] ?? ""} onChange={(event) => setReplyDrafts((current) => ({ ...current, [key]: event.target.value }))} maxLength={2000} rows={2} placeholder="Write a reply…" className="w-full resize-y rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-cyan-400" />
                          <div className="flex justify-end"><button type="button" onClick={() => void queueInboxReply(build.id, event.channel, message.message_id, message.sender || "the buyer")} disabled={!replyDrafts[key]?.trim() || !!actionKey} className="cursor-pointer rounded-md bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">Queue reply</button></div>
                        </div>
                      </div>;
                    })}
                    {buildMessages.map((message) => {
                      const key = `${build.id}:${message.message_id}`;
                      return <div key={key} className="rounded-lg border border-cyan-400/20 bg-cyan-950/15 p-3">
                        <div className="flex justify-between gap-2 text-xs"><span className="font-medium text-cyan-100">{message.sender}</span><span className="shrink-0 text-slate-500">{formatDate(message.received_at)}</span></div>
                        <p className="mt-1 text-xs font-medium text-slate-200">{message.subject}</p>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-400">{message.body}</p>
                        {message.response_enabled ? <div className="mt-3 space-y-2">
                          <textarea aria-label={`Reply to ${message.sender}`} value={replyDrafts[key] ?? ""} onChange={(event) => setReplyDrafts((current) => ({ ...current, [key]: event.target.value }))} maxLength={2000} rows={2} placeholder="Write a reply…" className="w-full resize-y rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white outline-none focus:border-cyan-400" />
                          <div className="flex justify-between gap-2"><span className="text-[10px] text-slate-500">Sent to the buyer in eBay messages.</span><button type="button" onClick={() => void sendEbayReply(build.id, message.message_id)} disabled={!replyDrafts[key]?.trim() || actionKey === key} className="cursor-pointer rounded-md bg-cyan-400 px-3 py-1.5 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-40">{actionKey === key ? "Sending…" : "Reply"}</button></div>
                        </div> : <p className="mt-2 text-[11px] text-amber-200">eBay has disabled replies to this question.</p>}
                      </div>;
                    })}
                    {buildOffers.map((offer) => {
                      const key = `${build.id}:${offer.best_offer_id}`;
                      return <div key={key} className="rounded-lg border border-amber-400/20 bg-amber-950/15 p-3">
                        <div className="flex items-center justify-between gap-2"><span className="flex items-center gap-2 text-xs font-medium text-amber-100"><Tag className="h-3.5 w-3.5" />Offer from {offer.buyer}</span><span className="text-sm font-semibold text-white">£{offer.price.toFixed(2)}</span></div>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <input aria-label={`Counter price for offer from ${offer.buyer}`} value={counterDrafts[key] ?? ""} onChange={(event) => setCounterDrafts((current) => ({ ...current, [key]: event.target.value }))} type="number" min="0.01" step="0.01" placeholder="Counter £" className="w-28 rounded border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white" />
                          <button type="button" onClick={() => void respondToOffer(offer, "Counter")} disabled={actionKey === key} className="cursor-pointer rounded border border-amber-300/30 px-2.5 py-1.5 text-xs text-amber-100 disabled:opacity-50">Counter</button>
                          <button type="button" onClick={() => void respondToOffer(offer, "Accept")} disabled={actionKey === key} className="cursor-pointer rounded bg-emerald-400 px-2.5 py-1.5 text-xs font-semibold text-slate-950 disabled:opacity-50">Accept</button>
                          <button type="button" onClick={() => void respondToOffer(offer, "Decline")} disabled={actionKey === key} className="cursor-pointer rounded border border-slate-600 px-2.5 py-1.5 text-xs text-slate-300 disabled:opacity-50">Decline</button>
                        </div>
                      </div>;
                    })}
                    {!buildMessages.length && !browserMessages.length && !buildOffers.length && !buildEmails.length && <p className="rounded-md border border-slate-800 bg-slate-950/40 p-3 text-xs text-slate-500">No linked customer messages or vendor email events have been recorded for this build.</p>}
                    {buildEmails.map((event) => <Link key={event.id} href={`/email-events/${event.id}`} className="block rounded-md border border-slate-800 bg-slate-950/45 p-3 hover:border-slate-600">
                      <div className="flex items-center justify-between gap-2 text-xs"><span className="truncate font-medium text-slate-200">{event.subject || eventLabel(event.event_type)}</span><span className="shrink-0 text-slate-500">{formatDate(event.received_at)}</span></div>
                      <p className="mt-1 text-xs text-slate-400">{event.summary}</p><span className="mt-2 inline-block text-[10px] uppercase text-slate-500">{event.marketplace || "Marketplace email"} · Open email event</span>
                    </Link>)}
                    {buildEvents.map((event) => <div key={event.id} className="flex items-start justify-between gap-3 border-l border-slate-700 pl-3 text-xs">
                      <div><p className="font-medium text-slate-300">{eventLabel(event.event_type)} · {event.channel}</p><p className="mt-0.5 text-slate-500">{event.message}</p></div><span className="shrink-0 text-[10px] text-slate-600">{formatDate(event.created_at)}</span>
                    </div>)}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-950/50 py-16 text-center">
          <Inbox className="mx-auto h-8 w-8 text-slate-600" />
          <p className="mt-3 text-sm font-medium text-slate-300">{query ? "No live builds match that search." : "No builds are confirmed live for sale."}</p>
          <p className="mt-1 text-xs text-slate-500">This page includes eBay and storefront listings verified as live, plus vendor listings recorded as published.</p>
        </div>
      )}

      {!!unmatchedEmails.length && <section className="rounded-xl border border-slate-700/70 bg-slate-950/55 p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Clock3 className="h-4 w-4 text-amber-300" />Marketplace emails not matched to a build</h2>
        <p className="mt-1 text-xs text-slate-500">These emails need an exact build match before they appear on a card.</p>
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {unmatchedEmails.map((event) => <Link key={event.id} href={`/email-events/${event.id}`} className="rounded-lg border border-slate-800 p-3 hover:border-slate-600"><div className="flex justify-between gap-3 text-xs"><span className="truncate font-medium text-slate-200">{event.subject || "Marketplace email"}</span><span className="shrink-0 text-slate-500">{formatDate(event.received_at)}</span></div><p className="mt-1 text-xs text-slate-400">{event.summary}</p><p className="mt-2 text-[10px] uppercase text-slate-500">{event.marketplace || "Unknown channel"} · Review and match</p></Link>)}
        </div>
      </section>}

      <p className="text-[11px] leading-5 text-slate-500">Google Shopping is a product listing surface, not a buyer inbox. Google submissions are shown as pending review until a separate status confirms eligibility. eBay uses its seller API for questions and offers; Amazon Seller Central, OnBuy, Facebook Marketplace and Vinted inbox actions run through the authenticated Chrome worker. Amazon’s API messaging actions are order-specific. Marketplace email notices open in Email Events.</p>
    </main>
  );
}
