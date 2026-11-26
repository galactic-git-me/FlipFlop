"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Check, Clock3, ExternalLink, Megaphone, Plus, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { apiUrl } from "@/lib/api";

type Post = {
  id: number;
  status: string;
  platforms: string[];
  source_type?: string;
  source_ref?: string;
  scheduled_for: string | null;
  needs_attention: string;
  revision?: { copy: string; media_asset_ids: number[]; link_url: string };
};
type ContentAsset = { id: number; kind: string; title: string; url: string; approved: boolean };
type Account = { id: number; platform: string; health: string; status: string; capability: string };
type Centre = {
  approvals_pending: number;
  drafts: number;
  scheduled_today: number;
  published: number;
  account_health: Account[];
  dispatch_control: { is_paused: boolean; reason: string; updated_by: string; updated_at: string | null };
  analytics: { website_sessions: number; utm_visits: number; freshness: string | null };
};

const CAMPAIGN = {
  destinations: [
    { id: "direct", label: "Direct shop", url: "https://theflipflop.shop/ready-to-ship/2" },
    { id: "ebay", label: "eBay", url: "https://www.ebay.co.uk/itm/198815946965" },
  ],
  channels: [
    {
      id: "facebook-feed",
      platform: "facebook",
      label: "Facebook",
      mediaTitle: "Prometheus Black Friday · Meta feed",
      mediaKind: "image",
      copy: "Meet Prometheus, the first FlipFlop build: Ryzen 7 7800X3D, GeForce RTX 3070, 32GB DDR5 and 1TB NVMe. RRP £1,700. Black Friday: £1,399 on eBay or £1,349 direct for eligible new website customers, including £50 off. Only one remaining. Fast-track next-day delivery is available, subject to postcode and checkout availability.",
    },
    {
      id: "instagram-feed",
      platform: "instagram",
      label: "Instagram · Feed",
      mediaTitle: "Prometheus Black Friday · Meta feed",
      mediaKind: "image",
      copy: "Introducing Prometheus: the first FlipFlop build. Ryzen 7 7800X3D, RTX 3070, 32GB DDR5 and 1TB NVMe. RRP £1,700. Black Friday: £1,399 on eBay or £1,349 direct for eligible new website customers (includes £50 off). One remaining. Fast-track next-day delivery available, subject to postcode and checkout availability.\n\n#FlipFlop #PrometheusPC #GamingPC #BlackFriday #PCGaming",
    },
    {
      id: "instagram-reels",
      platform: "instagram",
      label: "Instagram · Reels / Stories",
      mediaTitle: "Prometheus Black Friday · vertical showcase",
      mediaKind: "video",
      copy: "Meet Prometheus, the first FlipFlop build. Full specification and current availability are at the link in this post. Fast-track next-day delivery is available, subject to postcode and checkout availability.\n\n#FlipFlop #PrometheusPC #GamingPC #BlackFriday",
    },
    {
      id: "x-feed",
      platform: "x",
      label: "X",
      mediaTitle: "Prometheus Black Friday · X feed",
      mediaKind: "image",
      copy: "Meet Prometheus, FlipFlop's first build: Ryzen 7 7800X3D, RTX 3070, 32GB DDR5, 1TB NVMe. RRP £1,700. Black Friday: £1,399 eBay or £1,349 direct for eligible new customers (includes £50 off). One remaining. Fast-track next-day delivery available.",
    },
  ],
};

async function growth<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(`/growth${path}`), { headers: { "Content-Type": "application/json" }, ...init });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || "Growth Engine request failed");
  return response.json();
}

export default function AdvertisingGrowthPage() {
  const [centre, setCentre] = useState<Centre | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [copy, setCopy] = useState("");
  const [platform, setPlatform] = useState("instagram");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [pauseWorking, setPauseWorking] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [dashboard, postRows, assetRows] = await Promise.all([
        growth<Centre>("/command-centre"),
        growth<{ items: Post[] }>("/social/posts"),
        growth<{ items: ContentAsset[] }>("/assets"),
      ]);
      setCentre(dashboard);
      setPosts(postRows.items);
      setAssets(assetRows.items);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load Growth Engine"); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  async function createDraft(event: FormEvent) {
    event.preventDefault();
    if (!copy.trim()) return;
    try {
      await growth("/social/posts", { method: "POST", body: JSON.stringify({ platforms: [platform], copy: copy.trim() }) });
      setCopy(""); setMessage("Draft created. Submit it for validation and approval before publishing."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create draft"); }
  }

  async function createCampaignDraft(channel: typeof CAMPAIGN.channels[number], destination: typeof CAMPAIGN.destinations[number]) {
    const asset = assets.find(item => item.title === channel.mediaTitle && item.approved);
    if (!asset) { setMessage(`The approved ${channel.label} campaign creative is not available yet.`); return; }
    const sourceRef = `prometheus-black-friday:${channel.id}:${destination.id}`;
    if (posts.some(post => post.source_ref === sourceRef)) {
      setMessage(`A ${channel.label} draft for the ${destination.label} destination already exists.`);
      return;
    }
    setWorking(sourceRef);
    try {
      await growth("/social/posts", {
        method: "POST",
        body: JSON.stringify({
          platforms: [channel.platform],
          source_type: "campaign",
          source_ref: sourceRef,
          copy: channel.copy,
          platform_variants: { [channel.platform]: channel.copy },
          media_asset_ids: [asset.id],
          link_url: destination.url,
        }),
      });
      setMessage(`${channel.label} draft created with the ${destination.label} link and campaign artwork. It has not been published.`);
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create campaign draft"); }
    finally { setWorking(null); }
  }

  async function action(post: Post, endpoint: string, body?: object) {
    try { await growth(`/social/posts/${post.id}/${endpoint}`, { method: "POST", body: JSON.stringify(body ?? {}) }); await load(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Action failed"); }
  }

  async function setGlobalPause(paused: boolean) {
    setPauseWorking(true);
    try {
      await growth("/dispatch-control", {
        method: "POST",
        body: JSON.stringify({ is_paused: paused, reason: paused ? "Paused by operator" : "" }),
      });
      setMessage(paused ? "Publishing paused. Scheduled drafts remain queued." : "Publishing resumed. Only approved posts can be dispatched.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update publishing pause");
    } finally {
      setPauseWorking(false);
    }
  }

  const creativeByTitle = useMemo(() => new Map(assets.map(asset => [asset.title, asset])), [assets]);
  const cards = centre ? [
    ["Awaiting approval", centre.approvals_pending], ["Drafts", centre.drafts], ["Scheduled today", centre.scheduled_today], ["Published", centre.published], ["Website sessions", centre.analytics.website_sessions], ["UTM visits", centre.analytics.utm_visits],
  ] : [];
  const accounts = centre?.account_health ?? [];
  const hasLivePublisher = accounts.some(account => account.capability === "full_api" && account.status === "connected");
  const publishHint = hasLivePublisher ? "" : "Provider accounts are not connected for live publishing. Current connectors are fixture or assisted only.";
  const canPublishTo = (platforms: string[]) => platforms.length > 0 && platforms.every(platform =>
    accounts.some(account => account.platform === platform && account.capability === "full_api" && account.status === "connected"),
  );

  return <main className="mx-auto max-w-7xl space-y-6 p-4 text-slate-100 sm:p-6">
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div><div className="flex items-center gap-2"><Megaphone className="h-6 w-6 text-cyan-300" /><h1 className="text-2xl font-bold">Advertising &amp; Growth</h1></div><p className="mt-1 text-sm text-slate-400">Create campaign content, route it through review, and track observed website activity.</p></div>
      <button onClick={() => void load()} className="inline-flex w-fit items-center gap-2 rounded-md border border-cyan-300/25 px-3 py-2 text-sm text-cyan-100 transition-colors hover:bg-cyan-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />Refresh</button>
    </section>
    {message && <p role="status" className="rounded-md border border-cyan-300/20 bg-cyan-300/5 px-3 py-2 text-sm text-cyan-100">{message}</p>}
    {publishHint && <section className="rounded-xl border border-amber-300/30 bg-amber-950/30 p-4" role="status"><h2 className="flex items-center gap-2 font-semibold text-amber-100"><ShieldCheck className="h-4 w-4" />Live publishing is not connected</h2><p className="mt-1 text-sm text-amber-100/80">Drafts and review are available here. The configured social adapters are fixtures or assisted workflows, so this page will not present them as live provider publishing. Paid advertising also remains gated until an approved ad-account connector is configured.</p></section>}
    {centre && <section className={`flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between ${centre.dispatch_control.is_paused ? "border-amber-300/30 bg-amber-950/30" : "border-emerald-300/30 bg-emerald-950/20"}`} aria-live="polite">
      <div><h2 className="font-semibold">{centre.dispatch_control.is_paused ? "Publishing paused" : "Publishing gate open"}</h2><p className="mt-1 text-sm text-slate-300">{centre.dispatch_control.is_paused ? centre.dispatch_control.reason || "Scheduled items will not be dispatched." : "Dispatch still requires an approved revision and a verified live provider."}</p></div>
      <button type="button" disabled={pauseWorking || !hasLivePublisher} title={!hasLivePublisher ? "A verified live provider is required before dispatch can be resumed." : ""} onClick={() => void setGlobalPause(!centre.dispatch_control.is_paused)} className="rounded-md border border-white/20 px-3 py-2 text-sm font-medium hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 disabled:cursor-not-allowed disabled:opacity-50">{pauseWorking ? "Updating…" : centre.dispatch_control.is_paused ? "Resume publishing" : "Pause publishing"}</button>
    </section>}
    <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">{cards.map(([label, value]) => <div key={String(label)} className="rounded-xl border border-white/10 bg-slate-950/70 p-4"><p className="text-xs text-slate-400">{label}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p></div>)}</section>
    <section className="rounded-xl border border-white/10 bg-slate-950/70 p-4" aria-label="Analytics connection status"><h2 className="font-semibold">Analytics source</h2><p className="mt-1 text-sm text-slate-300">First-party events received by FlipFlop are shown above. Google Analytics 4 is not configured, so GA4 reports and attributed revenue are unavailable.</p></section>

    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Social profile connections">{accounts.map(account => <article key={account.id} className="rounded-xl border border-white/10 bg-slate-950/70 p-4"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold capitalize">{account.platform}</h2><p className="mt-1 text-sm text-slate-400">{account.status === "connected" && account.capability === "full_api" ? "Connected" : account.status === "disabled" ? "Disabled" : "Not configured"}</p></div><span className="rounded-full border border-amber-300/25 px-2 py-1 text-xs text-amber-100">{account.capability === "fixture" ? "Fixture only" : account.capability === "assisted" ? "Assisted" : account.capability}</span></div><p className="mt-3 text-xs text-slate-500">No provider credentials or live connection are verified for this profile.</p></article>)}</section>

    <section className="space-y-4 rounded-xl border border-orange-300/20 bg-slate-950/70 p-4 sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-orange-300">Ready-made campaign</p><h2 className="mt-1 text-xl font-bold">Prometheus · Black Friday</h2><p className="mt-1 max-w-3xl text-sm text-slate-400">Use the prepared platform artwork and copy to create tracked, reviewable drafts for either listing.</p></div><span className="w-fit rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-1 text-xs text-amber-100">Draft only · not live</span></div>
      <div className="rounded-lg border border-amber-300/20 bg-amber-950/20 p-3 text-sm leading-relaxed text-amber-100/90">Before submitting a draft for approval, confirm that the £1,700 reference price, £1,399 eBay price, £1,349 direct new-customer price, one-unit stock and next-day delivery terms are current on the destination listing.</div>
      <div className="grid gap-4 lg:grid-cols-3">{CAMPAIGN.channels.map(channel => {
        const asset = creativeByTitle.get(channel.mediaTitle);
        const existingForChannel = CAMPAIGN.destinations.filter(destination => posts.some(post => post.source_ref === `prometheus-black-friday:${channel.id}:${destination.id}`));
        return <article key={channel.id} className="min-w-0 overflow-hidden rounded-lg border border-white/10 bg-slate-900/60">
          <div className="aspect-[4/3] bg-black">{channel.mediaKind === "video" ? <video src={asset?.url} className="h-full w-full object-contain" controls muted playsInline /> : <img src={asset?.url} alt={`${channel.label} Prometheus Black Friday campaign creative`} className="h-full w-full object-contain" />}</div>
          <div className="space-y-3 p-4"><h3 className="font-semibold">{channel.label}</h3><p className="line-clamp-4 whitespace-pre-line text-xs leading-relaxed text-slate-300">{channel.copy}</p><div className="grid grid-cols-1 gap-2 sm:grid-cols-2">{CAMPAIGN.destinations.map(destination => {
            const exists = existingForChannel.some(item => item.id === destination.id);
            const sourceRef = `prometheus-black-friday:${channel.id}:${destination.id}`;
            return <button key={destination.id} type="button" disabled={exists || working === sourceRef || !asset?.approved} onClick={() => void createCampaignDraft(channel, destination)} className="inline-flex items-center justify-center gap-1.5 rounded-md border border-cyan-300/25 px-2 py-2 text-xs font-medium text-cyan-100 transition-colors hover:bg-cyan-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 disabled:cursor-not-allowed disabled:opacity-50">{exists ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}{exists ? `${destination.label} draft added` : `Draft · ${destination.label}`}</button>;
          })}</div></div>
        </article>;
      })}</div>
      <p className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400"><a className="inline-flex items-center gap-1 hover:text-cyan-200" href={CAMPAIGN.destinations[0].url} target="_blank" rel="noreferrer">Direct listing <ExternalLink className="h-3 w-3" /></a><a className="inline-flex items-center gap-1 hover:text-cyan-200" href={CAMPAIGN.destinations[1].url} target="_blank" rel="noreferrer">eBay listing <ExternalLink className="h-3 w-3" /></a><a className="inline-flex items-center gap-1 hover:text-cyan-200" href="/api/builds/002/social-ad/platform-previews/review.html" target="_blank" rel="noreferrer">All platform previews <ExternalLink className="h-3 w-3" /></a></p>
      <p className="text-xs text-slate-500">Creating a draft does not publish a post or start paid spend. Link tracking is added by the Growth Engine.</p>
    </section>

    <section className="grid gap-6 xl:grid-cols-[.85fr_1.15fr]">
      <form onSubmit={createDraft} className="space-y-4 rounded-xl border border-white/10 bg-slate-950/70 p-5"><h2 className="flex items-center gap-2 font-semibold"><Plus className="h-4 w-4 text-cyan-300" />New social draft</h2><label className="block text-sm">Platform<select value={platform} onChange={e => setPlatform(e.target.value)} className="mt-1 w-full rounded-md border border-white/15 bg-slate-900 px-3 py-2"><option value="instagram">Instagram</option><option value="facebook">Facebook</option><option value="x">X</option></select></label><label className="block text-sm">Post copy<textarea value={copy} onChange={e => setCopy(e.target.value)} required rows={5} className="mt-1 w-full rounded-md border border-white/15 bg-slate-900 px-3 py-2" placeholder="Write a factual, on-brand post…" /></label><button className="inline-flex items-center gap-2 rounded-md bg-cyan-300 px-3 py-2 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-200"><Plus className="h-4 w-4" />Create draft</button></form>
      <div className="rounded-xl border border-white/10 bg-slate-950/70 p-5"><h2 className="mb-4 flex items-center gap-2 font-semibold"><Clock3 className="h-4 w-4 text-cyan-300" />Content calendar</h2><div className="space-y-3">{posts.length === 0 ? <p className="text-sm text-slate-400">No social posts yet.</p> : posts.map(post => {
        const postAssets = (post.revision?.media_asset_ids ?? []).map(id => assets.find(asset => asset.id === id)).filter((asset): asset is ContentAsset => Boolean(asset));
        return <article key={post.id} className="rounded-lg border border-white/10 bg-slate-900/60 p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0 flex-1"><p className="whitespace-pre-wrap text-sm text-slate-200">{post.revision?.copy || "Untitled draft"}</p><p className="mt-1 text-xs text-slate-400">{post.platforms.join(", ")} · {post.status}{post.scheduled_for ? ` · ${new Date(post.scheduled_for).toLocaleString()}` : ""}</p>{post.needs_attention && <p className="mt-1 text-xs text-amber-200">{post.needs_attention}</p>}{post.revision?.link_url && <a className="mt-1 inline-flex items-center gap-1 break-all text-xs text-cyan-200 hover:text-cyan-100" href={post.revision.link_url} target="_blank" rel="noreferrer">Open destination <ExternalLink className="h-3 w-3 shrink-0" /></a>}{postAssets.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{postAssets.map(asset => asset.kind === "video" ? <video key={asset.id} src={asset.url} controls muted playsInline className="max-h-48 max-w-full rounded border border-white/10" /> : <img key={asset.id} src={asset.url} alt={asset.title} className="max-h-48 max-w-full rounded border border-white/10 object-contain" />)}</div>}</div><div className="flex gap-2">{["draft", "validation_failed"].includes(post.status) && <button onClick={() => void action(post, "submit")} className="rounded border border-white/15 px-2 py-1 text-xs hover:bg-white/10">Submit for review</button>}{post.status === "review" && <button onClick={() => void action(post, "approval", { approve: true })} className="inline-flex items-center gap-1 rounded border border-emerald-300/30 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-300/10"><Check className="h-3 w-3" />Approve</button>}{post.status === "approved" && <button disabled={!canPublishTo(post.platforms)} title={canPublishTo(post.platforms) ? "Publish" : publishHint || "No live publisher is connected for every selected platform."} onClick={() => void action(post, "execute")} className="inline-flex items-center gap-1 rounded border border-cyan-300/30 px-2 py-1 text-xs text-cyan-100 hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-40"><Send className="h-3 w-3" />Publish</button>}</div></div></article>;
      })}</div></div>
    </section>
    <section className="rounded-xl border border-white/10 bg-slate-950/70 p-5"><h2 className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-4 w-4 text-cyan-300" />Paid advertising activation</h2><p className="mt-2 text-sm text-slate-400">The Prometheus creative can now be prepared as tracked social drafts. Turning on paid campaigns is still gated: no verified Meta, Instagram, Google or eBay paid-ad connector, spend cap, or profitability approval is configured in this release.</p></section>
  </main>;
}
