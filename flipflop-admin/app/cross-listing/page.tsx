"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import JSZip from "jszip";
import {
  AlertTriangle, Check, CheckCircle2, ClipboardCopy, Download, ExternalLink,
  Filter, Link2, Loader2, PackageCheck, RefreshCw, Search, Send, ShieldCheck, X, Clock3, History,
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

type GroupedListing = {
  id: string;
  buildId: number;
  title: string;
  imageUrl: string | null;
  quantity: number;
  condition: string;
  updatedAt: string;
  listing: CrossListingSource["listing"];
  primary: CrossListingSource;
  byChannel: Partial<Record<CrossListingChannel, CrossListingSource>>;
};

function groupListings(sources: CrossListingSource[]): GroupedListing[] {
  const groups = new Map<string, GroupedListing>();
  sources.forEach((source) => {
    const key = source.canonicalProductId || String(source.buildId);
    const channel = source.channel ?? source.source;
    const existing = groups.get(key);
    if (existing) {
      existing.byChannel[channel] = source;
      if (source.updatedAt > existing.updatedAt) {
        existing.updatedAt = source.updatedAt;
        existing.primary = source;
      }
      return;
    }
    groups.set(key, {
      id: `product:${key}`,
      buildId: source.buildId,
      title: source.title,
      imageUrl: source.imageUrl,
      quantity: source.quantity,
      condition: source.condition,
      updatedAt: source.updatedAt,
      listing: source.listing,
      primary: source,
      byChannel: { [channel]: source },
    });
  });
  return [...groups.values()];
}

function VendorLogo({ channel }: { channel: CrossListingChannel }) {
  const labels: Record<CrossListingChannel, string> = {
    ebay_uk: "eBay UK",
    flipflop_shop: "FlipFlop.shop",
    onbuy: "OnBuy",
    amazon: "Amazon",
    facebook_catalog: "Facebook catalog",
    vinted: "Vinted",
  };
  return <span>{labels[channel]}</span>;
}

function isLocalDevelopment() {
  return typeof window !== "undefined" && ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

function isDevelopmentMode() {
  return process.env.NEXT_PUBLIC_APP_MODE !== "live";
}

function devListingUrl(source: CrossListingSource, channel: ChannelCapability) {
  // Keep the navigation URL small. Listing descriptions and image URLs can
  // exceed the proxy/browser request-line limit and result in HTTP 431.
  if (typeof window !== "undefined") {
    window.localStorage.setItem(`flipflop-dev-listing:${channel.channel}:${source.buildId}`, JSON.stringify({
      title: source.listing.title,
      description: source.listing.description,
      price: source.listing.price == null ? "" : String(source.listing.price),
      condition: source.listing.condition,
      sku: source.listing.sku,
      image: source.imageUrl ?? "",
    }));
  }
  return `/dev-listings/${channel.channel}/${source.buildId}`;
}

function devStorefrontUrl(buildId: number) {
  const base = process.env.NEXT_PUBLIC_STOREFRONT_DEV_URL || "http://localhost:4313";
  return `${base.replace(/\/$/, "")}/builds/${buildId}`;
}

function listingUrlFor(source?: CrossListingSource) {
  if (!source?.url) return null;
  if (source.source === "ebay_uk" && isLocalDevelopment() && source.externalId !== "not-created") {
    return `https://sandbox.ebay.com/itm/${source.externalId}`;
  }
  return source.url;
}

function ChannelCell({ source }: { source?: CrossListingSource }) {
  if (!source || source.status === "unavailable" || source.status === "ended" || source.status === "sold") {
    return <div className="flex min-h-8 min-w-[76px] items-center justify-center" aria-label="Not listed" />;
  }
  const isLive = source.status === "live";
  const isFailed = source.status === "failed";
  const statusLabel = isFailed ? "Listing failed" : isLive ? "Listed live" : "Listed as draft";
  const statusClass = isFailed ? "text-red-400" : isLive ? "text-emerald-400" : "text-amber-300";
  const statusContent = <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full border text-base font-bold ${isFailed ? "border-red-400/40 bg-red-400/10" : isLive ? "border-emerald-400/40 bg-emerald-400/10" : "border-amber-300/40 bg-amber-300/10"} ${statusClass}`} aria-label={statusLabel}>✓</span>;
  const url = listingUrlFor(source);
  const cell = <div className="flex min-h-8 min-w-[76px] items-center justify-center" title={source.error || undefined}>{url ? <a href={url} target="_blank" rel="noreferrer" className="rounded-full transition-transform hover:scale-110 focus:outline-none focus:ring-1 focus:ring-emerald-400">{statusContent}</a> : statusContent}</div>;
  return cell;
}

type ChannelSchedule = Awaited<ReturnType<typeof api.crossListing.schedules>>[number];

function normalizeScheduleChannel(channel: string): CrossListingChannel | null {
  const aliases: Record<string, CrossListingChannel> = {
    ebay: "ebay_uk",
    ebay_uk: "ebay_uk",
    storefront: "flipflop_shop",
    flipflop_shop: "flipflop_shop",
    onbuy: "onbuy",
    amazon: "amazon",
    facebook_catalog: "facebook_catalog",
    vinted: "vinted",
  };
  return aliases[channel.toLowerCase()] ?? null;
}

function scheduleStatus(status: string): CrossListingSource["status"] {
  if (["published", "active", "updated"].includes(status)) return "live";
  if (["draft", "scheduled", "publishing", "queued", "validating", "ready", "manual_action_required"].includes(status)) return "draft";
  if (status === "failed") return "failed";
  if (["withdrawn", "cancelled", "ended"].includes(status)) return "ended";
  return "unavailable";
}

function mediaFetchUrl(rawUrl: string): string {
  const absoluteApi = rawUrl.match(/^https?:\/\/(?:www\.)?theflipflop\.shop\/api\/(.+)$/);
  if (absoluteApi) return `/proxy-api/${absoluteApi[1]}`;
  if (rawUrl.startsWith("/api/")) return `/proxy-api${rawUrl}`;
  // Use the server-side proxy for shop media and other external assets so
  // logos can be embedded in the downloadable pack without CORS failures.
  if (/^https?:\/\//i.test(rawUrl)) return `/api/proxy-glb?url=${encodeURIComponent(rawUrl)}`;
  return rawUrl;
}

function archiveFilename(rawUrl: string, fallback: string): string {
  try {
    const pathname = new URL(rawUrl, window.location.origin).pathname;
    return decodeURIComponent(pathname.split("/").pop() || fallback).replace(/[^a-zA-Z0-9._-]/g, "_");
  } catch {
    return fallback;
  }
}

type ManualPackResource = {
  source: CrossListingSource;
  build?: ManualBuild;
  media: Array<{ kind: string; url: string; alt?: string }>;
  model3dUrl?: string | null;
};

function createManualPackResource(source: CrossListingSource, build?: ManualBuild): ManualPackResource {
  return {
    source,
    build,
    media: (build?.photos ?? []).filter((photo) => photo.url).map((photo) => ({ kind: photo.kind, url: photo.url })),
    model3dUrl: build?.model_3d_url,
  };
}

async function downloadManualListingPack(resource: ManualPackResource) {
  const { source, build } = resource;
  const listing = source.listing;
  const zip = new JSZip();
  const mediaFiles: string[] = [];
  const usedNames = new Set<string>();
  const addMedia = async (rawUrl: string, kind: string, fallback: string): Promise<string | null> => {
    const response = await fetch(mediaFetchUrl(rawUrl));
    if (!response.ok) return null;
    let filename = archiveFilename(rawUrl, fallback);
    const stem = filename.replace(/\.[^.]+$/, "");
    const extension = filename.includes(".") ? `.${filename.split(".").pop()}` : "";
    let index = 2;
    while (usedNames.has(filename.toLowerCase())) filename = `${stem}-${index++}${extension}`;
    usedNames.add(filename.toLowerCase());
    zip.file(`Media/${filename}`, await response.blob());
    const archivePath = `Media/${filename}`;
    mediaFiles.push(`${kind}: ${archivePath}`);
    return archivePath;
  };

  for (const [index, photo] of resource.media.entries()) {
    await addMedia(photo.url, photo.kind === "video" ? "Video" : "Image", `build-media-${index + 1}`);
  }

  if (resource.model3dUrl) {
    const response = await fetch(`/proxy-api/manual-builds/${source.buildId}/model-3d/download`);
    if (response.ok) {
      const filename = archiveFilename(resource.model3dUrl, `build-${source.buildId}.glb`);
      zip.file(`3D Model/${filename}`, await response.blob());
      mediaFiles.push(`3D model: 3D Model/${filename}`);
    }
  }

  let faqs: Array<{ question: string; answer: string }> = [];
  if (build) {
    const faqResponse = await fetch(`/proxy-api/manual-builds/${source.buildId}/faqs`);
    if (faqResponse.ok) {
      const faqData = await faqResponse.json() as { bank?: Array<{ id: string; question: string; answer: string }>; selected_ids?: string[]; answer_overrides?: Record<string, string> };
      const bank = faqData.bank ?? [];
      const overrides = faqData.answer_overrides ?? {};
      faqs = (faqData.selected_ids ?? []).map((id) => {
        const faq = bank.find((entry) => entry.id === id);
        return faq ? { question: faq.question, answer: overrides[id] || faq.answer } : null;
      }).filter((faq): faq is { question: string; answer: string } => faq !== null);
    }
  }

  // The canonical body contains branded logos and other inline imagery that
  // is not necessarily present in the build photo list. Copy each referenced
  // asset and rewrite the HTML to a relative ZIP path for offline use.
  let canonicalBodyHtml = listing.description;
  const inlineAssetUrls = [...canonicalBodyHtml.matchAll(/\bsrc=["']([^"']+)["']/gi)].map((match) => match[1]);
  for (const [index, rawUrl] of [...new Set(inlineAssetUrls)].entries()) {
    const archivePath = await addMedia(rawUrl, "Canonical HTML asset", `canonical-asset-${index + 1}`);
    if (archivePath) canonicalBodyHtml = canonicalBodyHtml.split(rawUrl).join(archivePath);
  }

  const markdown = [
    "# FlipFlop Manual Listing Pack", "", "- Reusable canonical pack for all listing channels", `- Source: ${source.source === "ebay_uk" ? "eBay UK" : "FlipFlop.shop"}`,
    `- Build ID: ${source.buildId}`, `- SKU: ${listing.sku}`, "", "## Title", listing.title, "", "## Description", listing.description,
    "", "## Bullet points", ...listing.bulletPoints.map((bullet) => `- ${bullet}`), "", "## Price", `${listing.currency} ${listing.price ?? "TBC"}`,
    "", "## Condition", listing.condition, "", "## Item specifics", ...Object.entries(listing.specifications).map(([key, value]) => `- **${key}:** ${value}`),
    "", "## Warranty", listing.warranty, "", "## Shipping", "Delivery only — collection and pickup are not allowed.", listing.shipping,
    "", "## FAQs", ...(faqs.length ? faqs.flatMap((faq) => [`### ${faq.question}`, faq.answer, ""]) : ["No saved FAQs were available."]),
    "", "## Included media", ...(mediaFiles.length ? mediaFiles.map((file) => `- ${file}`) : ["- No downloadable media was available"]),
    "", "## Manual steps", "1. Open the seller dashboard for the chosen channel.", "2. Create or update the listing using the fields above.", "3. Upload the files from the Media and 3D Model folders.", "4. Confirm the returned listing ID and URL in FlipFlop admin.",
  ].join("\n");
  zip.file("listing.md", markdown);
  const itemSpecificsHtml = Object.entries(listing.specifications)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
  const faqsHtml = faqs.length
    ? `<section><h2>Frequently asked questions</h2>${faqs.map((faq) => `<h3>${escapeHtml(faq.question)}</h3><p>${escapeHtml(faq.answer)}</p>`).join("")}</section>`
    : "";
  // Preserve the canonical generated listing body while adding the title and
  // item specifics required by marketplace listing editors. Logos and other
  // inline assets have already been rewritten to local ZIP paths above.
  zip.file("listing-body.html", `<h1>${escapeHtml(listing.title)}</h1><section><h2>Item specifics</h2><dl>${itemSpecificsHtml}</dl></section>${faqsHtml}${canonicalBodyHtml}`);

  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `flipflop-${source.buildId}-manual-pack.zip`; anchor.click();
  URL.revokeObjectURL(url);
}

function ManualPack({ source, build }: { source: CrossListingSource; build?: ManualBuild }) {
  return <button className="inline-flex cursor-pointer items-center gap-1.5 rounded border border-slate-600 px-2.5 py-1.5 text-xs text-slate-200 transition-colors hover:border-emerald-400/50 hover:text-emerald-300" onClick={() => {
    void downloadManualListingPack(createManualPackResource(source, build));
  }}><Download className="h-3.5 w-3.5" /> Manual pack</button>;
}

function ManualPackContents() {
  return <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2.5 text-[11px] text-slate-400">
    <div className="mb-1 font-semibold uppercase tracking-wider text-slate-300">Manual pack includes</div>
    <div className="grid gap-x-5 gap-y-1 sm:grid-cols-2">
      <div><span className="text-slate-200">listing.md</span> — title, specifics, FAQs and instructions</div>
      <div><span className="text-slate-200">listing-body.html</span> — canonical listing body with specifics and FAQs</div>
      <div><span className="text-slate-200">Media/</span> — all listing photos, logos and video</div>
      <div><span className="text-slate-200">3D Model/</span> — the listing&apos;s GLB model, when available</div>
    </div>
  </div>;
}

type BrowserAssistJob = { source: CrossListingSource; channel: ChannelCapability; build?: ManualBuild };
type ListingResult = { buildId?: number; channel: string; status: string; message: string; url?: string; assist?: BrowserAssistJob };
type ProgressJob = { buildId: number; channel: string; status: "pending" | "running" | "success" | "failed"; message?: string };
type BatchRun = { completedAt: string; results: ListingResult[] };
const BATCH_HISTORY_KEY = "flipflop-cross-listing-batch-history";

const sellerUrls: Partial<Record<CrossListingChannel, string>> = {
  onbuy: "https://seller.onbuy.com/",
  amazon: "https://sellercentral.amazon.co.uk/",
  facebook_catalog: "https://www.facebook.com/commerce/manager/",
  vinted: "https://www.vinted.co.uk/",
};

function escapeHtml(value: string): string {
  return value.replace(/[&<>\"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character] ?? character);
}

function openBrowserAssist({ source, channel, build, relist = false }: BrowserAssistJob & { relist?: boolean }) {
  const listing = {
    ...source.listing,
    shipping: "Delivery only — collection and pickup are not allowed.",
    deliveryMode: "delivery_only" as const,
    collectionAllowed: false as const,
    pickupAllowed: false as const,
  };
  const assets = (build?.photos ?? []).filter((photo) => photo.url).map((photo) => ({ kind: photo.kind, url: photo.url }));
  const model3d = build?.model_3d_url ? { kind: "3d_model", url: build.model_3d_url } : null;
  const payload = { schema: "flipflop.browser-assist.listing.v1", destination: channel.channel, buildId: source.buildId, listing, assets, model3d };
  const assistantHtml = `<!doctype html><meta charset="utf-8"><title>Codex listing handoff · ${escapeHtml(channel.label)}</title>
    <style>body{font:14px system-ui;background:#0b121d;color:#e2e8f0;max-width:960px;margin:32px auto;padding:0 20px}h1{font-size:24px}section{border:1px solid #334155;border-radius:10px;padding:16px;margin:14px 0;background:#0f172a}dt{color:#94a3b8;margin-top:10px}dd{white-space:pre-wrap;margin:4px 0 0}img{width:120px;height:90px;object-fit:cover;margin:6px;border-radius:6px;border:1px solid #475569}.safe{color:#6ee7b7;font-weight:600}</style>
    <h1>Codex browser-assist handoff</h1><p>${relist ? `This is a scheduled relisting for ${escapeHtml(channel.label)}. First end the existing listing, then create a brand-new listing using this complete payload.` : `Use this complete payload to create the ${escapeHtml(channel.label)} listing.`} The seller window is open separately.</p><p>If the seller asks you to sign in, complete sign-in in that seller window, then ask Codex to continue. FlipFlop never handles or stores your credentials.</p>
    <p class="safe">Delivery only is enforced. Collection and pickup must remain disabled.</p>
    <section><h2>${escapeHtml(listing.title)}</h2><dl><dt>Description</dt><dd>${escapeHtml(listing.description)}</dd><dt>Price</dt><dd>${escapeHtml(`${listing.currency} ${listing.price ?? "TBC"}`)}</dd><dt>Condition</dt><dd>${escapeHtml(listing.condition)}</dd><dt>Specifications</dt><dd>${escapeHtml(Object.entries(listing.specifications).map(([key, value]) => `${key}: ${value}`).join("\n"))}</dd><dt>Warranty</dt><dd>${escapeHtml(listing.warranty)}</dd><dt>Shipping</dt><dd class="safe">Delivery only — collection and pickup are not allowed.</dd></dl></section>
    <section><h2>Photos (${listing.images.length})</h2>${listing.images.map((image) => `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.alt)}">`).join("")}${model3d ? `<p><strong>3D model:</strong> ${escapeHtml(model3d.url)}</p>` : ""}</section>
    <script type="application/json" id="flipflop-listing-payload">${escapeHtml(JSON.stringify(payload))}</script>`;
  const handoffUrl = URL.createObjectURL(new Blob([assistantHtml], { type: "text/html;charset=utf-8" }));
  // Open the payload first, then the seller page last so Chrome leaves the
  // sign-in/listing window focused. Codex can take control of either tab.
  window.open(handoffUrl, "flipflop-codex-payload", "popup,width=1000,height=900");
  window.open(sellerUrls[channel.channel] ?? channel.officialReference, "flipflop-codex-listing", "popup,width=1200,height=900");
  window.setTimeout(() => URL.revokeObjectURL(handoffUrl), 60_000);
}

export default function CrossListingPage() {
  const [items, setItems] = useState<CrossListingSource[]>([]);
  const [builds, setBuilds] = useState<Record<number, ManualBuild>>({});
  const [connected, setConnected] = useState(false);
  const [amazonConnected, setAmazonConnected] = useState(false);
  const [amazonMessage, setAmazonMessage] = useState<string | undefined>();
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [destinations, setDestinations] = useState<CrossListingChannel[]>([]);
  const [query, setQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState<"all" | CrossListingChannel>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | CrossListingSource["status"]>("all");
  const [sort, setSort] = useState<"updated" | "price" | "title">("updated");
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftDescription, setDraftDescription] = useState("");
  const [draftPrice, setDraftPrice] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [progressJobs, setProgressJobs] = useState<ProgressJob[]>([]);
  const [results, setResults] = useState<ListingResult[]>([]);
  const [batchHistory, setBatchHistory] = useState<BatchRun[]>([]);
  const [actions, setActions] = useState<Awaited<ReturnType<typeof api.crossListing.actions>>>([]);

  const channelCapabilities = useMemo(() => capabilities(connected, amazonConnected, amazonMessage), [connected, amazonConnected, amazonMessage]);
  const tableChannels = channelCapabilities.map((channel) => channel.channel);
  const grouped = useMemo(() => groupListings(items), [items]);
  const selectedGroups = grouped.filter((item) => selected.has(item.id));
  const selectedItems = selectedGroups.map((group) => group.primary);
  const focusedGroup = selectedGroups.length === 1 ? selectedGroups[0] : null;
  const filtered = useMemo(() => grouped.filter((item) => {
    const channelSources = tableChannels.map((channel) => item.byChannel[channel]).filter(Boolean) as CrossListingSource[];
    const matchesQuery = !query || `${item.title} ${item.buildId} ${channelSources.map((source) => source.externalId).join(" ")}`.toLowerCase().includes(query.toLowerCase());
    // The table is grouped by the canonical product. Indirect channels do not
    // have a source listing yet, so filtering by one of them should still show
    // the build with that channel's empty/not-listed cell.
    const matchesSource = sourceFilter === "all" || Boolean(item.byChannel[sourceFilter]);
    const matchesStatus = statusFilter === "all" || channelSources.some((source) => source.status === statusFilter);
    return matchesQuery && matchesSource && matchesStatus;
  }).sort((a, b) => sort === "title" ? a.title.localeCompare(b.title) : sort === "price" ? (b.primary.price ?? 0) - (a.primary.price ?? 0) : b.updatedAt.localeCompare(a.updatedAt)), [grouped, tableChannels, query, sourceFilter, statusFilter, sort]);
  const review = reviewId ? items.find((item) => item.id === reviewId) ?? null : null;

  const refresh = useCallback(async () => {
    setRefreshing(true); setError(null);
    try {
      const [summary, ebay, amazon, scheduleRows, actionRows] = await Promise.all([api.manualBuilds.list(), api.ebayOAuth.status().catch(() => ({ connected: false })), api.crossListing.amazonStatus().catch(() => ({ connected: false, message: "Amazon connection could not be checked." })), api.crossListing.schedules(), api.crossListing.actions()]);
      const detailResults = await Promise.allSettled(summary.map((build) => api.manualBuilds.get(build.id)));
      const nextBuilds: Record<number, ManualBuild> = {};
      const nextItems: CrossListingSource[] = [];
      const nextWarnings: string[] = [];
      detailResults.forEach((result, index) => {
        if (result.status === "fulfilled") { nextBuilds[result.value.id] = result.value; nextItems.push(...sourcesFromBuild(result.value)); }
        else nextWarnings.push(`Build ${summary[index]?.id ?? "unknown"} could not be refreshed.`);
      });
      const failedActionMessages = new Map<string, string>();
      for (const action of actionRows) {
        if (!action.message || !action.event_type.includes("failed")) continue;
        const key = `${action.build_id}:${normalizeScheduleChannel(action.channel) ?? action.channel}`;
        if (!failedActionMessages.has(key)) failedActionMessages.set(key, action.message);
      }
      const canonicalByBuild = new Map<number, CrossListingSource>();
      for (const source of nextItems) if (!canonicalByBuild.has(source.buildId)) canonicalByBuild.set(source.buildId, source);
      for (const schedule of scheduleRows) {
        const channel = normalizeScheduleChannel(schedule.channel);
        const base = canonicalByBuild.get(schedule.build_id);
        if (!channel || !base || channel === "ebay_uk" || channel === "flipflop_shop") continue;
        const status = scheduleStatus(schedule.status);
        const key = `${schedule.build_id}:${channel}`;
        nextItems.push({
          ...base,
          id: `${channel}:${schedule.build_id}`,
          channel,
          source: "flipflop_shop",
          externalId: schedule.external_listing_id || "not-created",
          status,
          url: null,
          updatedAt: schedule.updated_at || base.updatedAt,
          error: status === "failed" ? schedule.last_recreate_message || failedActionMessages.get(key) || "The vendor rejected the listing without returning an error message." : null,
        });
      }
      setBuilds(nextBuilds); setItems(nextItems); setWarnings(nextWarnings); setConnected(ebay.connected); setAmazonConnected(amazon.connected); setAmazonMessage(amazon.message); setRefreshedAt(new Date().toISOString());
      setActions(actionRows);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load source listings."); }
    finally { setRefreshing(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(BATCH_HISTORY_KEY);
      if (!stored) return;
      const history = JSON.parse(stored) as BatchRun[];
      if (Array.isArray(history) && history.length > 0) {
        setBatchHistory(history);
        setResults(history[0].results);
      }
    } catch {
      // Ignore unavailable or invalid browser storage; the live session still works.
    }
  }, []);

  const openScheduledHandoff = (action: Awaited<ReturnType<typeof api.crossListing.actions>>[number]) => {
    const group = grouped.find((item) => item.buildId === action.build_id);
    if (!group) { setError(`Build ${action.build_id} is not available in the current listing view.`); return; }
    const channel = channelCapabilities.find((entry) => entry.channel === action.channel);
    if (!channel) { setError(`No browser-assist configuration exists for ${action.channel}.`); return; }
    openBrowserAssist({ source: group.byChannel[action.channel as CrossListingChannel] ?? group.primary, channel, build: builds[action.build_id], relist: true });
  };

  const recordCodexResult = async (actionId: number, success: boolean) => {
    await api.crossListing.recordCodexResult(actionId, { success, message: success ? "Codex ended the previous listing and created a brand-new listing." : "Codex relisting handoff was not completed." });
    await refresh();
  };

  const toggleAll = () => setSelected((current) => {
    const next = new Set(current); const allSelected = filtered.length > 0 && filtered.every((item) => next.has(item.id));
    filtered.forEach((item) => allSelected ? next.delete(item.id) : next.add(item.id)); return next;
  });
  const toggleDestination = (channel: CrossListingChannel) => setDestinations((current) => current.includes(channel) ? current.filter((item) => item !== channel) : [...current, channel]);
  const selectListing = (item: GroupedListing) => {
    const wasSelected = selected.has(item.id);
    setSelected((current) => {
      const next = new Set(current);
      if (wasSelected) next.delete(item.id); else next.add(item.id);
      return next;
    });
    if (!wasSelected) {
      const needsListing = channelCapabilities
        .filter((channel) => {
          const status = item.byChannel[channel.channel]?.status ?? "unavailable";
          return status === "unavailable" || status === "failed";
        })
        .map((channel) => channel.channel);
      setDestinations(needsListing);
    }
  };

  const openReview = (item: CrossListingSource) => { setReviewId(item.id); setDraftTitle(item.listing.title); setDraftDescription(item.listing.description); setDraftPrice(item.listing.price == null ? "" : String(item.listing.price)); };
  const saveReview = () => { if (!review) return; setItems((current) => current.map((item) => item.buildId === review.buildId ? { ...item, listing: { ...item.listing, title: draftTitle, description: draftDescription, price: draftPrice ? Number(draftPrice) : null }, title: draftTitle, price: draftPrice ? Number(draftPrice) : null } : item)); setReviewId(null); };

  const downloadSelectedPacks = async () => {
    if (!selectedItems.length || !destinations.length) return;
    for (const item of selectedItems) {
      await downloadManualListingPack(createManualPackResource(item, builds[item.buildId]));
    }
  };

  const publish = async () => {
    if (!selectedItems.length || !destinations.length) return;
    setPublishing(true); setResults([]);
    setProgressJobs(selectedItems.flatMap((item) => destinations.map((destination) => ({
      buildId: item.buildId, channel: channelCapabilities.find((entry) => entry.channel === destination)?.label ?? destination, status: "pending" as const,
    }))));
    const nextResults: ListingResult[] = [];
    const addResult = (result: ListingResult) => {
      nextResults.push(result);
      setProgressJobs((current) => current.map((job) => job.buildId === result.buildId && job.channel === result.channel ? { ...job, status: result.status === "failed" ? "failed" : "success", message: result.message } : job));
    };
    for (const item of selectedItems) for (const destination of destinations) {
      const capability = channelCapabilities.find((entry) => entry.channel === destination);
      if (!capability) continue;
      setProgressJobs((current) => current.map((job) => job.buildId === item.buildId && job.channel === capability.label ? { ...job, status: "running" } : job));
      if (capability.mode !== "api") {
        if (destination === "amazon") {
          addResult({ buildId: item.buildId, channel: capability.label, status: "failed", message: capability.note });
        } else if (isDevelopmentMode()) {
          addResult({ buildId: item.buildId, channel: capability.label, status: "published", message: `${capability.label} fake listing created for development. No external marketplace was contacted.`, url: devListingUrl(item, capability) });
        } else {
          addResult({ buildId: item.buildId, channel: capability.label, status: "manual_action_required", message: `${capability.note} Use browser assist to have Codex create the listing with the complete payload and media assets.`, assist: { source: item, channel: capability, build: builds[item.buildId] } });
        }
        continue;
      }
      const build = builds[item.buildId];
      try {
        if (destination === "ebay_uk") {
          const result = await api.manualBuilds.postToEbay(item.buildId, { price: item.listing.price ?? 0, condition: item.listing.condition, publish: true });
          addResult({ buildId: item.buildId, channel: capability.label, status: result.success ? "published" : "failed", message: result.success ? "eBay Sandbox accepted the publish request." : result.error ?? "eBay did not publish the listing.", url: result.url });
        } else if (destination === "amazon") {
          const result = await api.crossListing.publishAmazon(item.buildId, {
            title: item.listing.title,
            description: item.listing.description,
            bullet_points: item.listing.bulletPoints,
            price: item.listing.price ?? 0,
            quantity: item.listing.quantity,
            condition: item.listing.condition,
            images: item.listing.images.map((image) => image.url),
            sku: item.listing.sku,
          });
          addResult({ buildId: item.buildId, channel: capability.label, status: result.success ? "published" : "failed", message: result.message, url: result.listing_url ?? undefined });
        } else if (destination === "flipflop_shop" && build) {
          const result = await api.manualBuilds.listOnStorefront(item.buildId, item.listing.price ?? 0);
          addResult({ buildId: item.buildId, channel: capability.label, status: "published", message: isDevelopmentMode() ? "Listed on the local development storefront. The public storefront was not contacted." : "Linked to the existing storefront product.", url: isDevelopmentMode() ? devStorefrontUrl(item.buildId) : result.storefront_url });
        }
      } catch (cause) { addResult({ buildId: item.buildId, channel: capability.label, status: "failed", message: cause instanceof Error ? cause.message : "Provider request failed." }); }
    }
    const completedBatch: BatchRun = { completedAt: new Date().toISOString(), results: nextResults };
    setResults(nextResults);
    setBatchHistory((current) => {
      const next = [completedBatch, ...current].slice(0, 20);
      try { window.localStorage.setItem(BATCH_HISTORY_KEY, JSON.stringify(next)); } catch { /* best effort */ }
      return next;
    });
    setPublishing(false); await refresh();
  };

  return <div className="mx-auto min-h-full max-w-[1500px] space-y-5 p-4 md:p-6 lg:p-8">
    {publishing && progressJobs.length > 0 && <div role="dialog" aria-modal="true" aria-label="Cross-listing progress" className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"><div className="w-full max-w-2xl rounded-xl border border-emerald-400/30 bg-[#0e1724] p-5 shadow-2xl"><div className="flex items-center justify-between gap-4"><div><h2 className="flex items-center gap-2 text-lg font-semibold text-white"><Loader2 className="h-5 w-5 animate-spin text-emerald-300" /> Cross-listing progress</h2><p className="mt-1 text-xs text-slate-400">Each channel is processed separately. This window closes when the batch finishes.</p></div><span className="text-xs text-slate-400">{progressJobs.filter((job) => job.status === "success" || job.status === "failed").length}/{progressJobs.length} complete</span></div><div className="mt-5 max-h-[55vh] space-y-2 overflow-y-auto">{progressJobs.map((job) => <div key={`${job.buildId}-${job.channel}`} className="flex items-center gap-3 rounded border border-slate-800 bg-slate-900/60 px-3 py-2.5 text-xs"><div className={`h-2.5 w-2.5 shrink-0 rounded-full ${job.status === "success" ? "bg-emerald-400" : job.status === "failed" ? "bg-red-400" : job.status === "running" ? "animate-pulse bg-yellow-300" : "bg-slate-600"}`} /><span className="w-16 shrink-0 text-slate-500">Build {job.buildId}</span><span className="w-32 shrink-0 font-medium text-slate-200">{job.channel}</span><span className={job.status === "failed" ? "text-red-300" : job.status === "success" ? "text-emerald-300" : job.status === "running" ? "text-yellow-200" : "text-slate-500"}>{job.status === "success" ? "Succeeded" : job.status === "failed" ? "Failed" : job.status === "running" ? "In progress…" : "Waiting…"}</span><span className="min-w-0 truncate text-slate-500">{job.message ?? ""}</span></div>)}</div></div></div>}
    <header className="flex flex-col justify-between gap-4 border-b border-slate-700/70 pb-5 lg:flex-row lg:items-end">
      <div><div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-emerald-300"><Link2 className="h-4 w-4" /> Inventory synchronisation</div><h1 className="text-3xl font-semibold text-white">Cross-listing</h1><p className="mt-1 max-w-3xl text-sm text-slate-400">Review canonical build data, prepare channel payloads, and keep unique computers from selling twice.</p></div>
      <button onClick={() => void refresh()} disabled={refreshing} className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-slate-600 bg-slate-900/70 px-4 py-2.5 text-sm text-slate-100 transition-colors hover:border-emerald-400/60 hover:text-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> {refreshing ? "Refreshing…" : "Refresh listings"}</button>
    </header>

    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">{channelCapabilities.map((channel) => { const active = destinations.includes(channel.channel); const listingStatus = focusedGroup?.byChannel[channel.channel]?.status ?? (focusedGroup ? "unavailable" : null); return <button type="button" aria-pressed={active} key={channel.channel} onClick={() => toggleDestination(channel.channel)} className={`cursor-pointer rounded-lg border p-3 text-left transition-colors ${active ? "border-emerald-400/60 bg-emerald-400/[0.07] shadow-[0_0_18px_rgba(52,211,153,0.08)]" : "border-slate-700/80 bg-[#0d1521]/90 opacity-60 hover:border-slate-500 hover:opacity-90"}`}><div className="flex items-start gap-3"><div className="min-w-0 flex-1"><div className="flex min-h-6 items-start justify-between gap-2"><span className="text-sm font-medium leading-6 text-white">{channel.label}</span><span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide ${channel.mode === "api" ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" : channel.mode === "requires_approval" ? "border-yellow-400/30 bg-yellow-400/10 text-yellow-300" : "border-slate-600 bg-slate-800 text-slate-300"}`}>{channel.mode === "api" ? "API" : labelForStatus(channel.mode)}</span></div>{listingStatus && <div className={`mt-2 text-xs font-medium ${listingStatus === "live" ? "text-emerald-300" : listingStatus === "failed" ? "text-red-300" : "text-yellow-200"}`}>{listingStatus === "live" ? "✓ " : ""}{labelForStatus(listingStatus)} for selected listing</div>}<p className="mt-2 min-h-[60px] text-xs leading-5 text-slate-400">{channel.note}</p></div><span className={`shrink-0 text-lg leading-6 ${active ? "text-emerald-300" : "text-slate-600"}`}>{active ? "✓" : "○"}</span></div></button>; })}</section>

    <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4"><h2 className="flex items-center gap-2 text-sm font-semibold text-white"><History className="h-4 w-4 text-emerald-300" /> Recreate action log</h2><p className="mt-1 text-xs text-slate-500">End and recreate attempts are recorded per channel and also emitted as admin notifications.</p><div className="mt-3 space-y-2">{actions.slice(0, 20).map((action) => <div key={action.id} className="flex flex-wrap items-center gap-2 rounded border border-slate-800 px-3 py-2 text-xs"><span className={action.event_type.includes("failed") ? "text-red-300" : action.event_type.includes("created") ? "text-emerald-300" : action.event_type.includes("handoff") ? "text-yellow-300" : "text-slate-300"}>{labelForStatus(action.event_type)}</span><span className="text-cyan-200">{action.channel}</span><span className="text-slate-400">Build {action.build_id}</span><span className="text-slate-500">{action.message}</span>{action.event_type === "recreate_handoff_required" && <><button onClick={() => openScheduledHandoff(action)} className="inline-flex cursor-pointer items-center gap-1 rounded border border-yellow-400/40 px-2 py-1 text-[10px] text-yellow-200 hover:bg-yellow-400/10"><ExternalLink className="h-3 w-3" /> Open pack + seller page for Codex</button><button onClick={() => void recordCodexResult(action.id, true)} className="cursor-pointer rounded border border-emerald-400/40 px-2 py-1 text-[10px] text-emerald-200 hover:bg-emerald-400/10">Mark successful</button><button onClick={() => void recordCodexResult(action.id, false)} className="cursor-pointer rounded border border-red-400/40 px-2 py-1 text-[10px] text-red-200 hover:bg-red-400/10">Mark failed</button></>}<span className="ml-auto text-[10px] text-slate-600">{action.created_at ? new Date(action.created_at).toLocaleString("en-GB") : ""}</span></div>)}{actions.length === 0 && <p className="py-4 text-center text-xs text-slate-500">No recreate actions recorded yet.</p>}</div></section>

    {warnings.length > 0 && <div className="flex items-start gap-3 rounded-lg border border-yellow-400/30 bg-yellow-400/10 p-3 text-sm text-yellow-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" /><div><div className="font-medium">Partial refresh</div>{warnings.map((warning) => <div key={warning} className="text-xs text-yellow-200/80">{warning}</div>)}</div></div>}
    {error && <div className="flex items-center justify-between gap-3 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100"><span>{error}</span><button onClick={() => void refresh()} className="cursor-pointer underline">Retry</button></div>}

    <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 shadow-2xl shadow-black/10">
      <div className="flex flex-col gap-3 border-b border-slate-700/70 p-4 xl:flex-row xl:items-center"><div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" /><input aria-label="Search listings" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, build ID or external ID…" className="w-full rounded-md border border-slate-700 bg-slate-900/80 py-2 pl-9 pr-3 text-sm text-white outline-none transition-colors focus:border-emerald-400/60" /></div><div className="flex flex-wrap gap-2"><select aria-label="Channel filter" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="all">All channels</option>{channelCapabilities.map((channel) => <option key={channel.channel} value={channel.channel}>{channel.label}</option>)}</select><select aria-label="Status filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="all">All statuses</option>{Object.keys(statusStyles).map((status) => <option key={status} value={status}>{labelForStatus(status)}</option>)}</select><select aria-label="Sort listings" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200"><option value="updated">Recently updated</option><option value="price">Highest price</option><option value="title">Title</option></select></div></div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3 text-xs"><button onClick={toggleAll} className="inline-flex cursor-pointer items-center gap-2 text-slate-200 hover:text-emerald-300"><span className={`flex h-4 w-4 items-center justify-center rounded border ${filtered.length > 0 && filtered.every((item) => selected.has(item.id)) ? "border-emerald-400 bg-emerald-400 text-slate-950" : "border-slate-600"}`}>{filtered.length > 0 && filtered.every((item) => selected.has(item.id)) && <Check className="h-3 w-3" />}</span>Select all filtered ({filtered.length})</button><span className="text-slate-500">{selectedItems.length} selected · {refreshedAt ? `refreshed ${new Date(refreshedAt).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "not refreshed"}</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-slate-900/60 text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="w-12 px-4 py-3" /><th className="px-4 py-3">Listing</th>{tableChannels.map((channel) => <th key={channel} className="border-l border-slate-800 px-3 py-3 text-center"><VendorLogo channel={channel} /></th>)}<th className="border-l border-slate-800 px-4 py-3">Updated</th><th className="px-4 py-3" /></tr></thead><tbody className="divide-y divide-slate-800/80">{filtered.map((item) => <tr key={item.id} className={`transition-colors hover:bg-slate-800/30 ${selected.has(item.id) ? "bg-emerald-400/[0.04]" : ""}`}><td className="px-4 py-3"><button aria-label={`Select ${item.title}`} onClick={() => setSelected((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })} className={`flex h-4 w-4 cursor-pointer items-center justify-center rounded border ${selected.has(item.id) ? "border-emerald-400 bg-emerald-400 text-slate-950" : "border-slate-600"}`}>{selected.has(item.id) && <Check className="h-3 w-3" />}</button></td><td className="max-w-[370px] px-4 py-3"><div className="flex items-center gap-3"><div className="h-11 w-14 overflow-hidden rounded border border-slate-700 bg-slate-900">{item.imageUrl ? <img src={item.imageUrl} alt="" className="h-full w-full object-cover" /> : <PackageCheck className="m-3 h-5 w-5 text-slate-600" />}</div><div className="min-w-0"><div className="truncate font-medium text-slate-100">{item.title}</div><div className="mt-1 text-xs text-slate-500">Build {item.buildId} · {tableChannels.map((channel) => item.byChannel[channel]?.externalId).filter(Boolean).join(" · ")}</div></div></div></td>{tableChannels.map((channel) => <td key={`${item.id}-${channel}`} className="border-l border-slate-800/60 px-3 py-3"><ChannelCell source={item.byChannel[channel]} /></td>)}<td className="border-l border-slate-800 px-4 py-3 text-xs text-slate-500">{new Date(item.updatedAt).toLocaleDateString("en-GB")}</td><td className="px-4 py-3 text-right"><button onClick={() => openReview(item.primary)} className="cursor-pointer rounded border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-emerald-400/50 hover:text-emerald-300">Review</button></td></tr>)}</tbody></table>{!refreshing && filtered.length === 0 && <div className="px-6 py-16 text-center"><Filter className="mx-auto h-7 w-7 text-slate-600" /><p className="mt-3 text-sm text-slate-300">No source listings match this view.</p><p className="mt-1 text-xs text-slate-500">Only listings returned by the connected eBay/storefront integrations are shown.</p></div>}{refreshing && <div className="flex items-center justify-center gap-2 px-6 py-16 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Loading source listings…</div>}</div>
    </section>

    <section className="sticky bottom-3 z-20 rounded-xl border border-emerald-400/20 bg-[#0b121d]/95 p-4 shadow-2xl shadow-black/30 backdrop-blur"><div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between"><div className="min-w-0 flex-1"><div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wider text-slate-400"><ShieldCheck className="h-4 w-4 text-emerald-300" /> Destination workflow</div><div className="flex flex-wrap gap-2">{channelCapabilities.map((channel) => <button key={channel.channel} onClick={() => toggleDestination(channel.channel)} className={`cursor-pointer rounded-md border px-3 py-2 text-xs transition-colors ${destinations.includes(channel.channel) ? "border-emerald-400/60 bg-emerald-400/10 text-emerald-200" : "border-slate-700 text-slate-400 hover:border-slate-500"}`}><span className="mr-1.5">{destinations.includes(channel.channel) ? "✓" : "○"}</span>{channel.label}</button>)}</div><div className="mt-2 text-xs text-slate-500">{selectedItems.length} source listing{selectedItems.length === 1 ? "" : "s"} × {destinations.length} destination{destinations.length === 1 ? "" : "s"} = {selectedItems.length * destinations.length} job{selectedItems.length * destinations.length === 1 ? "" : "s"}. Manual-only destinations remain manual_action_required.</div><ManualPackContents /></div><div className="flex flex-wrap gap-2"><button onClick={downloadSelectedPacks} disabled={!selectedItems.length || !destinations.length} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-600 px-3 py-2.5 text-xs text-slate-200 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"><ClipboardCopy className="h-4 w-4" /> Download manual packs</button><button onClick={() => { if (selectedItems.length && destinations.length && window.confirm(`Confirm ${selectedItems.length * destinations.length} cross-listing job(s)? API destinations may create or update live listings.`)) void publish(); }} disabled={publishing || !selectedItems.length || !destinations.length} className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-emerald-400 px-4 py-2.5 text-xs font-semibold text-slate-950 transition-colors hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40">{publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{publishing ? "Submitting…" : "Review & submit"}</button></div></div></section>

    {results.length > 0 && <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4"><h2 className="mb-1 flex items-center gap-2 text-sm font-semibold text-white"><CheckCircle2 className="h-4 w-4 text-emerald-300" /> Batch results</h2><p className="mb-3 text-[11px] text-slate-500">Saved locally so this report remains available when you return to Cross-listing.</p><div className="space-y-2">{results.map((result, index) => <div key={`${result.channel}-${index}`} className="flex flex-col gap-2 rounded border border-slate-800 bg-slate-900/50 p-3 text-xs md:flex-row md:items-center md:justify-between"><div><span className="font-medium text-slate-200">{result.channel}</span><span className={`ml-2 ${result.status === "failed" ? "text-red-300" : result.status === "manual_action_required" || result.status === "blocked_in_development" ? "text-yellow-300" : "text-emerald-300"}`}>{labelForStatus(result.status)}</span><div className="mt-1 text-slate-400">{result.message}</div></div><div className="flex shrink-0 flex-wrap gap-2">{result.assist && <button onClick={() => openBrowserAssist(result.assist!)} className="inline-flex items-center gap-1 rounded border border-emerald-400/40 px-2.5 py-1.5 font-medium text-emerald-300 hover:bg-emerald-400/10">Open Chrome + ask Codex to create listing <ExternalLink className="h-3 w-3" /></button>}{result.url && <a href={result.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-emerald-300 hover:underline">View listing <ExternalLink className="h-3 w-3" /></a>}</div></div>)}</div></section>}
    {batchHistory.length > 1 && <section className="rounded-xl border border-slate-700/80 bg-[#0b121d]/90 p-4"><h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-white"><History className="h-4 w-4 text-emerald-300" /> Previous batch runs</h2><div className="space-y-2">{batchHistory.slice(1).map((batch) => <details key={batch.completedAt} className="rounded border border-slate-800 bg-slate-900/50 p-3 text-xs"><summary className="cursor-pointer text-slate-300">{new Date(batch.completedAt).toLocaleString("en-GB")} · {batch.results.filter((result) => result.status === "failed").length} failed / {batch.results.length} total</summary><div className="mt-3 space-y-1.5">{batch.results.map((result, index) => <div key={`${result.channel}-${index}`}><span className="text-slate-200">{result.channel}</span><span className={`ml-2 ${result.status === "failed" ? "text-red-300" : result.status === "manual_action_required" ? "text-yellow-300" : "text-emerald-300"}`}>{labelForStatus(result.status)}</span><span className="ml-2 text-slate-500">{result.message}</span></div>)}</div></details>)}</div></section>}

    {review && <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/75 p-3 backdrop-blur-sm md:items-center"><div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-slate-700 bg-[#0e1724] p-5 shadow-2xl"><div className="flex items-start justify-between gap-4"><div><div className="text-xs uppercase tracking-wider text-emerald-300">Payload review · {review.source === "ebay_uk" ? "eBay UK" : "FlipFlop.shop"}</div><h2 className="mt-1 text-xl font-semibold text-white">{review.title}</h2><p className="mt-1 text-xs text-slate-500">Canonical build {review.buildId} · edits are local to this review until saved.</p></div><button aria-label="Close review" onClick={() => setReviewId(null)} className="cursor-pointer rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"><X className="h-5 w-5" /></button></div><div className="mt-5 grid gap-4 md:grid-cols-2"><label className="text-xs text-slate-400">Title<input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} maxLength={80} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400/60" /><span className="mt-1 block text-right text-[10px] text-slate-500">{draftTitle.length}/80</span></label><label className="text-xs text-slate-400">Price (GBP)<input type="number" min="0" step="0.01" value={draftPrice} onChange={(event) => setDraftPrice(event.target.value)} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-400/60" /></label></div><label className="mt-2 block text-xs text-slate-400">Description<textarea value={draftDescription} onChange={(event) => setDraftDescription(event.target.value)} rows={8} className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm leading-6 text-slate-200 outline-none focus:border-emerald-400/60" /><span className="mt-1 block text-right text-[10px] text-slate-500">{draftDescription.length} characters</span></label><div className="mt-4 rounded-lg border border-slate-700/80 bg-white p-4 text-sm text-slate-900"><div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Rendered listing HTML</div><div dangerouslySetInnerHTML={{ __html: `<h1>${escapeHtml(draftTitle)}</h1>${draftDescription}` }} /></div><div className="mt-4 rounded-lg border border-slate-700/80 bg-slate-900/50 p-3"><div className="mb-2 text-xs uppercase tracking-wider text-slate-500">Copied and transformed</div><div className="grid gap-2 text-xs text-slate-300 md:grid-cols-2"><div>✓ {review.listing.images.length} public image URL{review.listing.images.length === 1 ? "" : "s"}</div><div>✓ {Object.keys(review.listing.specifications).length} specification fields</div><div>✓ Shared price, stock and condition</div><div>⚠ Platform category and item specifics require destination validation</div></div></div><div className="mt-5 flex flex-wrap justify-end gap-2"><ManualPack source={{ ...review, listing: { ...review.listing, title: draftTitle, description: draftDescription, price: draftPrice ? Number(draftPrice) : null } }} build={builds[review.buildId]} /><button onClick={() => setReviewId(null)} className="cursor-pointer rounded-md border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-slate-400">Cancel</button><button onClick={saveReview} className="cursor-pointer rounded-md bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300">Save review edits</button></div></div></div>}
  </div>;
}
