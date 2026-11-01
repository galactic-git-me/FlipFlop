"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Upload, Video } from "lucide-react";
import { inspectProductPhoto, type PhotoScreeningResult } from "./photo-screening";

type Asset = {
  id: number;
  review_batch_id?: string | null;
  status: string;
  version: number;
  glb_ref: string | null;
  is_active: boolean;
  review_decision?: "approved" | "rejected" | null;
};

type QueueItem = {
  variant_id: number;
  variant_ids: number[];
  listing_id: number;
  source_reference: string;
  title: string;
  category: string;
  display_price: number;
  listing_url: string | null;
  listing_description_preview: string;
  listing_description_length: number;
  product_copy_preview: string;
  product_copy_provider: string | null;
  upsell_copy_count: number;
  upsell_copy_preview: string;
  listing_image_urls: string[];
  listing_image_sources?: Record<string, string>;
  suggested_model_image_urls?: string[];
  listing_video_urls: string[];
  curated_for_builds: boolean;
  custom_for_builds: boolean;
  asset: Asset | null;
  asset_media_review: {
    status: string;
    image_urls?: string[];
    model_image_urls?: string[];
    video_urls?: string[];
    generation?: { status: string; progress: number; task_id?: string | null; error?: string | null; updated_at?: string };
  } | null;
  storefront_ready: boolean;
  storefront_blockers: string[];
};

async function readResponsePayload(response: Response): Promise<unknown> {
  const body = await response.text();
  try {
    return JSON.parse(body);
  } catch {
    return { detail: body.trim() || `Server returned HTTP ${response.status} ${response.statusText}` };
  }
}

function payloadField(payload: unknown, key: string): unknown {
  return payload && typeof payload === "object" && key in payload
    ? (payload as Record<string, unknown>)[key]
    : undefined;
}

function payloadError(payload: unknown, fallback: string): string {
  const detail = payloadField(payload, "detail") ?? payloadField(payload, "error");
  return typeof detail === "string" && detail.trim() ? detail : fallback;
}

function videoPoster(url: string) {
  try {
    const parsed = new URL(url);
    const videoId = parsed.hostname.includes("youtu.be")
      ? parsed.pathname.slice(1)
      : parsed.hostname.includes("youtube.com")
        ? parsed.searchParams.get("v")
        : null;
    return videoId ? `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg` : undefined;
  } catch {
    return undefined;
  }
}

function photoSourceIdentity(url: string) {
  try {
    const parsed = new URL(url);
    const amazonImage = parsed.pathname.match(/\/images\/I\/([^/.]+)/i)?.[1];
    if (amazonImage) return `amazon:${amazonImage}`;
    const ebayImage = parsed.pathname.match(/\/images\/g\/([^/]+)/i)?.[1];
    if (ebayImage) return `ebay:${ebayImage}`;
  } catch {
    // Fall through to the visual comparison for relative or unusual URLs.
  }
  return null;
}

function photoVisualSignature(image: HTMLImageElement): string | null {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 48;
    canvas.height = 48;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return null;
    context.fillStyle = "#fff";
    context.fillRect(0, 0, 48, 48);
    const scale = Math.min(46 / image.naturalWidth, 46 / image.naturalHeight);
    const width = image.naturalWidth * scale;
    const height = image.naturalHeight * scale;
    context.drawImage(image, (48 - width) / 2, (48 - height) / 2, width, height);
    // A small RGB thumbnail signature detects the same photo across different
    // hosts and thumbnail sizes, while retaining colour and composition cues.
    const pixels = context.getImageData(0, 0, 48, 48).data;
    let signature = "";
    for (let index = 0; index < pixels.length; index += 4) {
      signature += String.fromCharCode(pixels[index], pixels[index + 1], pixels[index + 2]);
    }
    return signature;
  } catch {
    // Some third-party hosts may block canvas reads. Keep those thumbnails
    // visible instead of hiding a photo we could not compare.
    return null;
  }
}

function hashesLookLikeSamePhoto(left: string, right: string) {
  const leftSeparator = left.indexOf("|");
  const rightSeparator = right.indexOf("|");
  const leftIdentity = leftSeparator < 0 ? "" : left.slice(0, leftSeparator);
  const rightIdentity = rightSeparator < 0 ? "" : right.slice(0, rightSeparator);
  const leftPixels = leftSeparator < 0 ? left : left.slice(leftSeparator + 1);
  const rightPixels = rightSeparator < 0 ? right : right.slice(rightSeparator + 1);
  if (leftIdentity && rightIdentity && leftIdentity === rightIdentity) return true;
  if (!leftPixels || !rightPixels || leftPixels.length !== rightPixels.length) return false;
  let difference = 0;
  for (let index = 0; index < leftPixels.length; index += 1) {
    difference += Math.abs(leftPixels.charCodeAt(index) - rightPixels.charCodeAt(index));
  }
  return difference / leftPixels.length < 8;
}

type WorkspaceProps = { variantIds?: number[]; onReview?: (batchId?: string) => void };

export default function Catalogue3DAssetsWorkspace({ variantIds, onReview }: WorkspaceProps) {
  const router = useRouter();
  const [catalogue] = useState<"curated" | "custom">("curated");
  const [catalogueReady, setCatalogueReady] = useState(false);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewBatchReady, setReviewBatchReady] = useState<string | null>(null);
  const [selectedModelImages, setSelectedModelImages] = useState<Record<number, string[]>>({});
  const [photoHashes, setPhotoHashes] = useState<Record<number, Record<string, string>>>({});
  const [photoScreenings, setPhotoScreenings] = useState<Record<number, Record<string, PhotoScreeningResult>>>({});
  const [photoScreeningComplete, setPhotoScreeningComplete] = useState<Record<number, boolean>>({});
  const [photoScreeningBusyId, setPhotoScreeningBusyId] = useState<number | null>(null);
  const [includeFilteredPhotos, setIncludeFilteredPhotos] = useState<Set<string>>(new Set());
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [gapsOnly, setGapsOnly] = useState(false);
  const [activeFamilyVariant, setActiveFamilyVariant] = useState<Record<string, number>>({});
  const loadSequence = useRef(0);
  const imageScrollers = useRef<Record<number, HTMLDivElement | null>>({});
  const videoScrollers = useRef<Record<number, HTMLDivElement | null>>({});

  const listingImagesFor = (item: QueueItem) => {
    const uniqueUrls = [...new Set(item.listing_image_urls)];
    const hashes = photoHashes[item.variant_id] ?? {};
    const keptHashes: string[] = [];
    return uniqueUrls.filter(url => {
      const hash = hashes[url];
      if (!hash) return true;
      if (keptHashes.some(existing => hashesLookLikeSamePhoto(existing, hash))) return false;
      keptHashes.push(hash);
      return true;
    });
  };
  const modelImagesFor = (item: QueueItem) => {
    const isAllowed = (url: string) => {
      const screening = photoScreenings[item.variant_id]?.[url];
      return !screening?.reasons.length || includeFilteredPhotos.has(`${item.variant_id}:${url}`);
    };
    const selected = selectedModelImages[item.variant_id];
    if (selected) return selected.filter(isAllowed);

    if (photoScreeningComplete[item.variant_id]) {
      return listingImagesFor(item).filter(isAllowed).slice(0, 4);
    }

    const saved = item.asset_media_review?.model_image_urls;
    if (Array.isArray(saved)) return saved;

    // Older records may only contain image_urls. Treat that as the model set
    // only when it is small enough to have been an explicit 3D selection.
    const legacy = item.asset_media_review?.image_urls;
    if (Array.isArray(legacy) && legacy.length > 0 && legacy.length <= 4) return legacy;

    // These are suggestions only. They are saved as model references only
    // when the operator generates a draft, and each thumbnail stays editable.
    return listingImagesFor(item).slice(0, 4);
  };

  const photoSourceFor = (item: QueueItem, url: string) => item.listing_image_sources?.[url] ?? "Captured listing";

  const toggleFilteredPhoto = (variantId: number, url: string) => {
    const key = `${variantId}:${url}`;
    const include = !includeFilteredPhotos.has(key);
    setIncludeFilteredPhotos(current => {
      const next = new Set(current);
      include ? next.add(key) : next.delete(key);
      return next;
    });
    setSelectedModelImages(current => {
      const selected = current[variantId] ?? [];
      if (include) return { ...current, [variantId]: selected.length < 4 ? [...selected, url] : selected };
      return { ...current, [variantId]: selected.filter(value => value !== url) };
    });
  };

  const screenPhotosFor = async (item: QueueItem): Promise<string[]> => {
    const urls = listingImagesFor(item);
    if (!urls.length) return [];
    setPhotoScreeningBusyId(item.variant_id);
    setError(null);
    const results: Record<string, PhotoScreeningResult> = {};
    let nextIndex = 0;
    const inspectUrl = (url: string) => new Promise<PhotoScreeningResult>(resolve => {
      const image = new Image();
      const timeout = window.setTimeout(() => resolve({ reasons: ["could not inspect automatically"], visualSignature: null }), 15000);
      image.crossOrigin = "anonymous";
      image.onload = () => {
        window.clearTimeout(timeout);
        resolve(inspectProductPhoto(image));
      };
      image.onerror = () => {
        window.clearTimeout(timeout);
        resolve({ reasons: ["could not inspect automatically"], visualSignature: null });
      };
      image.src = url;
    });
    try {
      await Promise.all(Array.from({ length: Math.min(6, urls.length) }, async () => {
        while (nextIndex < urls.length) {
          const index = nextIndex;
          nextIndex += 1;
          const url = urls[index];
          results[url] = await inspectUrl(url);
        }
      }));
      setPhotoScreenings(current => ({ ...current, [item.variant_id]: results }));
      setPhotoScreeningComplete(current => ({ ...current, [item.variant_id]: true }));
      const previousSelection = selectedModelImages[item.variant_id]
        ?? item.asset_media_review?.model_image_urls
        ?? [];
      const allowed = (url: string) => !results[url]?.reasons.length
        || includeFilteredPhotos.has(`${item.variant_id}:${url}`);
      const retained = previousSelection.filter(url => urls.includes(url) && allowed(url)).slice(0, 4);
      const recommended = urls.filter(allowed).slice(0, 4);
      const selected = retained.length ? retained : recommended;
      setSelectedModelImages(current => ({ ...current, [item.variant_id]: selected }));
      const filteredCount = Object.values(results).filter(result => result.reasons.length > 0).length;
      setNotice(`Photo filter checked ${urls.length} images: ${filteredCount} excluded for text overlays, tight crops, or unreadable images; ${selected.length} clean reference${selected.length === 1 ? "" : "s"} selected.`);
      return selected;
    } finally {
      setPhotoScreeningBusyId(null);
    }
  };

  const queueUrl = `/api/assets-3d/catalogue-queue?catalogue=${catalogue}${variantIds ? `&variant_ids=${variantIds.join(",")}` : ""}`;
  const openReview = (batchId?: string) => {
    if (onReview) onReview(batchId);
    else router.push(`/components-3d-review?${batchId ? `batch=${encodeURIComponent(batchId)}` : `${catalogue}Only=1`}&returnTo=${encodeURIComponent(`/catalogue/3d-assets?catalogue=${catalogue}`)}`);
  };
  const load = useCallback(async () => {
    const sequence = ++loadSequence.current;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(queueUrl, { cache: "no-store" });
      const payload = await readResponsePayload(response);
      if (!response.ok) throw new Error(payloadError(payload, "Could not load the catalogue asset queue."));
      if (!Array.isArray(payload)) throw new Error("The catalogue asset queue returned an invalid response.");
      if (sequence === loadSequence.current) setItems(payload as QueueItem[]);
    } catch (caught) {
      if (sequence === loadSequence.current) setError(caught instanceof Error ? caught.message : "Could not load the catalogue asset queue.");
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }, [queueUrl]);

  const refreshGenerationProgress = useCallback(async () => {
    try {
      const response = await fetch(queueUrl, { cache: "no-store" });
      if (!response.ok) return;
      const payload = await readResponsePayload(response);
      if (Array.isArray(payload)) setItems(payload as QueueItem[]);
    } catch {
      // Keep the active generation visible; the next poll can recover.
    }
  }, [queueUrl]);

  const waitForGeneration = async (variantId: number) => {
    const deadline = Date.now() + 12 * 60 * 1000;
    while (Date.now() < deadline) {
      const response = await fetch(queueUrl, { cache: "no-store" });
      const payload = await readResponsePayload(response);
      if (!response.ok) throw new Error(payloadError(payload, "Could not read 3D generation progress."));
      if (!Array.isArray(payload)) throw new Error("The 3D generation progress response was invalid.");
      const queue = payload as QueueItem[];
      setItems(queue);
      const item = queue.find(candidate => candidate.variant_ids.includes(variantId));
      const generation = item?.asset_media_review?.generation;
      if (generation?.status === "DRAFT_CREATED") return;
      if (generation && (generation.status === "SOURCE_IMAGES_INVALID" || generation.status === "FAILED" || generation.status === "CANCELED" || generation.status === "TIMED_OUT" || generation.status.startsWith("SUBMIT_") || generation.status === "CONFIGURATION_ERROR")) {
        throw new Error(generation.error || `3D generation ${generation.status.replaceAll("_", " ").toLowerCase()}.`);
      }
      await new Promise(resolve => window.setTimeout(resolve, 3000));
    }
    throw new Error("3D generation is still running after 12 minutes. Its progress remains saved on the product card; you can leave this page and return later.");
  };

  useEffect(() => {
    setCatalogueReady(true);
  }, []);
  useEffect(() => { if (catalogueReady) void load(); }, [catalogueReady, load]);
  useEffect(() => {
    if (busyId === null) return;
    const timer = window.setInterval(() => { void refreshGenerationProgress(); }, 3000);
    return () => window.clearInterval(timer);
  }, [busyId, refreshGenerationProgress]);

  const upload = async (variantId: number, file?: File) => {
    if (!file) return;
    setBusyId(variantId);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.set("file", file);
      const response = await fetch(`/api/assets-3d/variants/${variantId}/upload-glb`, { method: "POST", body: form });
      const payload = await readResponsePayload(response);
      if (!response.ok) throw new Error(payloadError(payload, "The GLB upload failed."));
      const version = payloadField(payload, "version");
      setNotice(`${items.find(item => item.variant_id === variantId)?.title}: uploaded as version ${String(version ?? "unknown")}. It is waiting for validation and rights review.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The GLB upload failed.");
    } finally {
      setBusyId(null);
    }
  };

  const generate = async (item: QueueItem, comparisonDraft = false) => {
    const imageUrls = listingImagesFor(item);
    if (imageUrls.length === 0) {
      setError("This listing has no captured photos, or you have not selected one to four 3D reference photos yet.");
      return;
    }
    setBusyId(item.variant_id); setError(null); setNotice(null);
    try {
      const modelImageUrls = modelImagesFor(item);
      if (modelImageUrls.length === 0 || modelImageUrls.length > 4) {
        throw new Error("The photo filter found no usable 3D references. Include a filtered photo manually or collect a wider product view.");
      }
      const approval = await fetch(`/api/assets-3d/variants/${item.variant_id}/media-approval`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify({ model_image_urls: modelImageUrls }) });
      const approvalPayload = await readResponsePayload(approval);
      if (!approval.ok) throw new Error(payloadError(approvalPayload, "Could not include the captured listing media and save the model reference selection."));
      const reviewBatchId = crypto.randomUUID();
      const response = await fetch(`/api/assets-3d/variants/${item.variant_id}/generate`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ comparison_draft: comparisonDraft, review_batch_id: reviewBatchId }),
      });
      const payload = await readResponsePayload(response);
      if (!response.ok) throw new Error(payloadError(payload, "Model generation failed."));
      await waitForGeneration(item.variant_id);
      openReview(reviewBatchId);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Model generation failed."); }
    finally { setBusyId(null); }
  };

  const generateSelected = async () => {
    const candidates = visibleItems.filter(item => selectedProducts.has(item.variant_id)
      && modelImagesFor(item).length >= 1 && modelImagesFor(item).length <= 4
      && (!item.asset || item.asset.status === "rejected"));
    const batch = candidates.slice(0, 10);
    if (!batch.length) {
      setError("Select products with one to four 3D reference photos and no model already waiting for review.");
      return;
    }
    const reviewBatchId = crypto.randomUUID();
    setBusyId(-1); setError(null); setNotice(null);
    const failures: string[] = [];
    let generated = 0;
    for (const item of batch) {
      try {
        const modelImageUrls = modelImagesFor(item);
        if (modelImageUrls.length === 0 || modelImageUrls.length > 4) {
          throw new Error("The photo filter found no usable 3D reference photos");
        }
        const approval = await fetch(`/api/assets-3d/variants/${item.variant_id}/media-approval`, {
          method: "PUT", headers: { "content-type": "application/json" },
          body: JSON.stringify({ model_image_urls: modelImageUrls }),
        });
        const approvalPayload = await readResponsePayload(approval);
        if (!approval.ok) throw new Error(payloadError(approvalPayload, "Could not save the model photos"));
        const response = await fetch(`/api/assets-3d/variants/${item.variant_id}/generate`, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ review_batch_id: reviewBatchId }),
        });
        const payload = await readResponsePayload(response);
        if (!response.ok) throw new Error(payloadError(payload, "Model generation failed"));
        await waitForGeneration(item.variant_id);
        generated += 1;
      } catch (caught) {
        failures.push(`${item.title}: ${caught instanceof Error ? caught.message : "Generation failed"}`);
      }
    }
    setBusyId(null);
    if (!generated) {
      setError(failures.join(" · ") || "No models were generated.");
      return;
    }
    setNotice(`${generated} draft model${generated === 1 ? "" : "s"} generated.${batch.length < candidates.length ? ` Generate the next ${Math.min(10, candidates.length - batch.length)} selected products after this review.` : ""}${failures.length ? ` ${failures.length} failed: ${failures.join(" · ")}` : ""}`);
    setReviewBatchReady(reviewBatchId);
  };

  const scrollThumbs = (scrollers: typeof imageScrollers, variantId: number, direction: -1 | 1) => {
    scrollers.current[variantId]?.scrollBy({ left: direction * 220, behavior: "smooth" });
  };

  function familyKeyFor(item: QueueItem) {
    return `${item.category}:${item.title.trim().toLocaleLowerCase()}`;
  }
  const productFamilyCount = new Set(items.map(familyKeyFor)).size;
  const attentionCount = items.filter(item => !item.storefront_ready).length;
  const missingImages = items.filter(item => item.listing_image_urls.length === 0).length;
  const categories = [...new Set(items.map(item => item.category))].sort();
  const visibleItems = items.filter(item => {
    const matchesSearch = !search.trim() || `${item.title} ${item.category}`.toLowerCase().includes(search.trim().toLowerCase());
    const matchesCategory = categoryFilter === "all" || item.category === categoryFilter;
    const hasGap = item.listing_image_urls.length === 0 || !item.storefront_ready;
    return matchesSearch && matchesCategory && (!gapsOnly || hasGap);
  });
  const visibleFamilies = [...visibleItems.reduce((groups, item) => {
    const key = familyKeyFor(item);
    const family = groups.get(key) ?? [];
    family.push(item);
    groups.set(key, family);
    return groups;
  }, new Map<string, QueueItem[]>())].map(([key, familyItems]) => ({
    key,
    items: familyItems,
    active: familyItems.find(item => item.variant_id === activeFamilyVariant[key]) ?? familyItems[0],
  }));
  const selectedVisible = visibleItems.filter(item => selectedProducts.has(item.variant_id));
  const selectedCanGenerate = selectedVisible.filter(item => modelImagesFor(item).length >= 1
    && modelImagesFor(item).length <= 4 && (!item.asset || item.asset.status === "rejected")).length;
  const allVisibleSelected = visibleItems.length > 0 && visibleItems.every(item => selectedProducts.has(item.variant_id));
  const setVisibleSelection = (checked: boolean) => setSelectedProducts(current => {
    const next = new Set(current);
    for (const item of visibleItems) checked ? next.add(item.variant_id) : next.delete(item.variant_id);
    return next;
  });
  return (
    <main className="mx-auto max-w-[1800px] space-y-6 p-6 text-slate-100" onClickCapture={event => {
      if (!onReview || !(event.target instanceof Element)) return;
      const link = event.target.closest('a[href^="/components-3d-review"]');
      if (!link) return;
      event.preventDefault(); event.stopPropagation();
      openReview(new URL(link.getAttribute("href")!, window.location.origin).searchParams.get("batch") ?? undefined);
    }}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          {!variantIds && <Link href="/catalogue" className="text-sm text-cyan-300 hover:underline">← Catalogue</Link>}
          <h1 className="mt-3 text-2xl font-semibold">Shared component 3D assets</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">Each exact product appears once, even when it is used in several Playbook cells. Listing photos and videos are included automatically.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!variantIds && <Link href="/cases-3d-priority" className="rounded-lg border border-white/15 px-4 py-2 text-sm hover:border-cyan-400/50">Case 3D sourcing</Link>}
          <Link href={`/components-3d-review?${catalogue}Only=1&returnTo=${encodeURIComponent(`/catalogue/3d-assets?catalogue=${catalogue}`)}`} className="rounded-lg border border-white/15 px-4 py-2 text-sm hover:border-cyan-400/50">Open 3D review queue</Link>
        </div>
      </div>

      {!variantIds && <nav className="flex gap-2 border-b border-white/10 pb-3" aria-label="Catalogue asset queue">
        <a href="/catalogue/3d-assets?catalogue=curated" aria-current={catalogue === "curated" ? "page" : undefined} className={`rounded-full border px-4 py-2 text-sm ${catalogue === "curated" ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200" : "border-white/10 text-slate-400"}`}>Curated Catalogue</a>
      </nav>}

      <section className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4" aria-label="How to create product models">
        <p className="font-medium text-cyan-100">What to do</p>
        <ol className="mt-2 grid gap-2 text-sm text-slate-300 md:grid-cols-3">
          <li><span className="text-cyan-200">1.</span> Listing media is already included. Review the thumbnails if needed.</li>
          <li><span className="text-cyan-200">2.</span> Select one to four photos marked “Use for 3D”.</li>
          <li><span className="text-cyan-200">3.</span> Select products below and generate up to ten drafts into one review batch.</li>
        </ol>
        <p className="mt-2 text-xs text-slate-400">A generated model is not published until you approve it in the 3D review queue.</p>
      </section>
      <div className="flex flex-wrap gap-2 text-sm text-slate-300">
        <span className="rounded-lg border border-white/10 px-3 py-2">{productFamilyCount} product families · {items.length} source listings</span>
        <span className="rounded-lg border border-amber-300/20 px-3 py-2 text-amber-200">{attentionCount} still need a final 3D model</span>
      </div>
      {error && <p role="alert" className="rounded-lg border border-red-400/30 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
      {notice && <div role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-950/30 p-3 text-sm text-emerald-200">{notice}{reviewBatchReady && <Link className="ml-3 underline" href={`/components-3d-review?batch=${encodeURIComponent(reviewBatchReady)}&returnTo=${encodeURIComponent(`/catalogue/3d-assets?catalogue=${catalogue}`)}`}>Review generated models</Link>}</div>}
      {loading ? <p className="text-sm text-slate-400">Loading catalogue components…</p> : items.length === 0 ? <p className="rounded-xl border border-white/10 p-6 text-sm text-slate-400">No eligible components were returned. Review this build’s catalogue links and component status.</p> : (
        <>
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-[#0b1119] p-3">
          <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search Playbook components…" aria-label="Search Playbook components" className="min-w-64 flex-1 rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500" />
          <select aria-label="Filter by component type" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)} className="rounded-lg border border-white/10 bg-[#111923] px-3 py-2 text-sm"><option value="all">All component types</option>{categories.map(category => <option key={category} value={category}>{category}</option>)}</select>
          <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={gapsOnly} onChange={event => setGapsOnly(event.target.checked)} />Models needing work</label>
          <span className="text-xs text-slate-500">Showing {visibleFamilies.length} product families · {visibleItems.length} listings</span>
        </div>
        <div className="sticky top-2 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-white/10 bg-[#101924]/95 p-3 shadow-lg backdrop-blur">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" checked={allVisibleSelected} onChange={event => setVisibleSelection(event.currentTarget.checked)} /> Select all {visibleItems.length} visible listings
          </label>
          <span className="text-xs text-slate-400">{selectedVisible.length} selected · {selectedCanGenerate} ready to generate</span>
          <button type="button" disabled={busyId === -1 || selectedCanGenerate === 0} onClick={() => void generateSelected()} className="ml-auto rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">{busyId === -1 ? "Generating selected drafts…" : `Generate selected drafts (${Math.min(selectedCanGenerate, 10)})`}</button>
          <button type="button" disabled={!selectedProducts.size} onClick={() => setSelectedProducts(new Set())} className="rounded-lg border border-white/15 px-3 py-2 text-sm text-slate-300 disabled:opacity-40">Clear selection</button>
        </div>
        <div className="space-y-3">
          {visibleFamilies.map(family => {
            const item = family.active;
            const generation = item.asset_media_review?.generation;
            const generationStatus = generation?.status ?? "";
            const generationInProgress = ["STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"].includes(generationStatus);
            const generationFailed = generationStatus === "SOURCE_IMAGES_INVALID" || generationStatus === "FAILED" || generationStatus.startsWith("SUBMIT_") || generationStatus === "CONFIGURATION_ERROR" || generationStatus === "CANCELED" || generationStatus === "TIMED_OUT";
            return (
            <article key={family.key} className="rounded-xl border border-white/10 bg-[#101924] p-4">
              <div className="flex flex-wrap items-start gap-3">
                <input type="checkbox" aria-label={`Select ${item.title}`} checked={selectedProducts.has(item.variant_id)} onChange={event => setSelectedProducts(current => { const next = new Set(current); event.target.checked ? next.add(item.variant_id) : next.delete(item.variant_id); return next; })} className="mt-1 h-4 w-4" />
                <div className="min-w-0 flex-1">
                  <h2 className="font-medium text-slate-100">{item.title}</h2>
                  <p className="mt-1 text-xs capitalize text-slate-400">{item.category} · {family.items.length > 1 ? `${family.items.length} source listings grouped` : `used by ${item.variant_ids.length} Playbook entr${item.variant_ids.length === 1 ? "y" : "ies"}`}</p>
                  {family.items.length > 1 && <label className="mt-2 inline-flex items-center gap-2 text-xs text-slate-300">Source listing
                    <select aria-label={`Choose source listing for ${item.title}`} value={item.variant_id} onChange={event => setActiveFamilyVariant(current => ({ ...current, [family.key]: Number(event.target.value) }))} className="max-w-[28rem] rounded border border-white/15 bg-[#0b1119] px-2 py-1.5 text-slate-100">
                      {family.items.map(option => <option key={option.variant_id} value={option.variant_id}>{option.source_reference} · {option.display_price > 0 ? `£${option.display_price.toFixed(2)}` : "price unavailable"} · {option.listing_image_urls.length} photos</option>)}
                    </select>
                  </label>}
                  {item.listing_url && <a href={item.listing_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-cyan-300 hover:underline">Open source listing</a>}
                </div>
                <span className={item.asset?.status === "final" && item.asset.is_active ? "rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-200" : "rounded-full bg-amber-300/10 px-3 py-1 text-xs text-amber-200"}>{item.asset?.status === "final" && item.asset.is_active ? "Final model approved" : item.asset ? `Model ${item.asset.status.replaceAll("_", " ")}` : "No model yet"}</span>
              </div>
              <section className="mt-4" aria-label="Listing photos">
                {(() => {
                  const photos = listingImagesFor(item);
                  const amazonCount = photos.filter(url => photoSourceFor(item, url) === "Amazon").length;
                  const overclockersCount = photos.filter(url => photoSourceFor(item, url) === "Overclockers").length;
                  const screened = photoScreenings[item.variant_id] ?? {};
                  const filteredCount = Object.values(screened).filter(result => result.reasons.length > 0).length;
                  return <>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-sm font-medium">Listing photos <span className="text-xs font-normal text-emerald-200">{photos.length} distinct · {amazonCount} Amazon · {overclockersCount} Overclockers</span></h3>
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="text-xs text-slate-400">{photoScreeningComplete[item.variant_id] ? `${filteredCount} auto-filtered` : "Filter before sending to Meshy"} · {modelImagesFor(item).length}/4 selected</span>
                        <button type="button" disabled={photoScreeningBusyId === item.variant_id || !photos.length} onClick={() => void screenPhotosFor(item)} className="rounded border border-cyan-300/30 px-2 py-1 text-xs text-cyan-100 disabled:opacity-50">{photoScreeningBusyId === item.variant_id ? "Checking all photos…" : photoScreeningComplete[item.variant_id] ? "Run photo filter again" : "Auto-filter photos for Meshy"}</button>
                      </div>
                    </div>
                    <p className="mt-1 text-[11px] text-slate-500">All captured Amazon and Overclockers photos are included when available. The filter skips text-heavy images and tight crops before generation; use “Include anyway” to override a false positive.</p>
                {listingImagesFor(item).length ? <div className="mt-2 flex items-center gap-2">
                  {listingImagesFor(item).length > 4 && <button type="button" aria-label="Scroll photo thumbnails left" onClick={() => scrollThumbs(imageScrollers, item.variant_id, -1)} className="rounded border border-white/10 px-2 py-2 text-sm">‹</button>}
                  <div ref={node => { imageScrollers.current[item.variant_id] = node; }} className="flex min-w-0 gap-2 overflow-x-auto scroll-smooth pb-2" aria-label={`${listingImagesFor(item).length} listing photo thumbnails`}>
                    {listingImagesFor(item).map((url, index) => {
                      const modelSelected = modelImagesFor(item).includes(url);
                      const screening = screened[url];
                      const manuallyIncluded = includeFilteredPhotos.has(`${item.variant_id}:${url}`);
                      const excluded = Boolean(screening?.reasons.length && !manuallyIncluded);
                      return <div key={url} className={`w-32 shrink-0 rounded-lg border p-1.5 ${excluded ? "border-rose-400/30 bg-slate-900/70 opacity-65" : modelSelected ? "border-cyan-300 bg-cyan-300/10" : "border-emerald-400/20"}`}>
                          <a href={url} target="_blank" rel="noreferrer" title="Open full-size captured photo" onClick={event => event.stopPropagation()}><img src={url} crossOrigin="anonymous" alt={`Listing photo ${index + 1}`} loading="lazy" className={`h-20 w-full rounded bg-white object-contain ${excluded ? "grayscale" : ""}`} onLoad={event => {
                            const sourceIdentity = photoSourceIdentity(url);
                            const signature = photoVisualSignature(event.currentTarget);
                            const hash = sourceIdentity || signature ? `${sourceIdentity ?? ""}|${signature ?? ""}` : null;
                            if (hash) setPhotoHashes(current => ({
                              ...current,
                              [item.variant_id]: { ...current[item.variant_id], [url]: hash },
                            }));
                          }} onError={event => {
                            const image = event.currentTarget;
                            if (image.dataset.corsFallback === "done") return;
                            image.dataset.corsFallback = "done";
                            image.removeAttribute("crossorigin");
                            image.src = url;
                          }} /></a>
                        <span className="mt-1 block truncate text-[10px] text-emerald-200" title={photoSourceFor(item, url)}>{photoSourceFor(item, url)}</span>
                        <span className={`mt-1 block text-[10px] ${excluded ? "text-rose-200" : "text-slate-300"}`}>{screening?.reasons.length ? `Auto-filtered: ${screening.reasons.join(", ")}` : screening ? (modelSelected ? "Selected for 3D" : "Clear for 3D") : "Not screened yet"}</span>
                        <label className="mt-1 flex items-center gap-1 text-[11px] text-slate-100"><input type="checkbox" checked={modelSelected} disabled={excluded || (!modelSelected && modelImagesFor(item).length >= 4)} onChange={event => {
                          const current = modelImagesFor(item);
                          setSelectedModelImages(values => ({ ...values, [item.variant_id]: event.target.checked ? [...current, url] : current.filter(value => value !== url) }));
                        }} />Use for 3D</label>
                        {screening?.reasons.length > 0 && <button type="button" onClick={() => toggleFilteredPhoto(item.variant_id, url)} className="mt-1 text-[10px] text-amber-200 underline">{manuallyIncluded ? "Exclude again" : "Include anyway"}</button>}
                      </div>;
                    })}
                  </div>
                  {listingImagesFor(item).length > 4 && <button type="button" aria-label="Scroll photo thumbnails right" onClick={() => scrollThumbs(imageScrollers, item.variant_id, 1)} className="rounded border border-white/10 px-2 py-2 text-sm">›</button>}
                </div> : <p className="mt-2 text-sm text-amber-200">No captured listing photos. The model cannot be generated until photos are collected.</p>}
                  </>;
                })()}
              </section>
              <section className="mt-4 border-t border-white/10 pt-3" aria-label="Listing videos">
                <h3 className="text-sm font-medium">Listing videos <span className="text-xs font-normal text-emerald-200">{item.listing_video_urls.length} auto-included</span></h3>
                {item.listing_video_urls.length ? <div ref={node => { videoScrollers.current[item.variant_id] = node; }} className="mt-2 flex gap-2 overflow-x-auto pb-2">
                  {item.listing_video_urls.map((url, index) => {
                    const poster = videoPoster(url);
                    return <div key={url} className="w-36 shrink-0 overflow-hidden rounded-lg border border-emerald-400/20 bg-black/30">
                      {poster ? <a href={url} target="_blank" rel="noreferrer" title="Open captured listing video"><img src={poster} alt={`Listing video ${index + 1} thumbnail`} loading="lazy" className="h-24 w-full object-cover" /></a> : <video src={url} controls muted preload="metadata" aria-label={`Listing video ${index + 1}`} className="h-24 w-full object-cover" />}
                      <span className="flex items-center gap-1 px-2 py-1 text-[10px] text-emerald-200"><Video className="h-3 w-3" />Auto-included video {index + 1}</span>
                    </div>;
                  })}
                </div> : <p className="mt-1 text-xs text-slate-400">No listing videos have been captured for this product yet.</p>}
              </section>
              {generation && <section role="status" aria-live="polite" className={`mt-4 rounded-lg border p-3 ${generationFailed ? "border-red-400/30 bg-red-950/20" : generationStatus === "DRAFT_CREATED" ? "border-emerald-400/30 bg-emerald-950/20" : "border-violet-400/25 bg-violet-950/15"}`}>
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className={generationFailed ? "text-red-200" : generationStatus === "DRAFT_CREATED" ? "text-emerald-200" : "text-violet-100"}>
                    {generationInProgress ? `Generating 3D draft · ${generationStatus === "STARTING" ? "Submitting to Meshy" : generationStatus === "RESUMING" ? `Resuming Meshy task · ${generation.progress}%` : generationStatus === "PUBLISHING" ? "Saving generated model" : `${generation.progress}%`}` : generationFailed ? `Generation failed${generation.error ? ` · ${generation.error}` : ""}` : generationStatus === "DRAFT_CREATED" ? "Draft created · ready for review" : `Last generation · ${generationStatus.replaceAll("_", " ").toLowerCase()}`}
                  </span>
                  {generationStatus === "DRAFT_CREATED" && item.asset?.review_batch_id && <Link href={`/components-3d-review?batch=${encodeURIComponent(item.asset.review_batch_id)}&returnTo=${encodeURIComponent(`/catalogue/3d-assets?catalogue=${catalogue}`)}`} className="rounded border border-emerald-300/40 px-2 py-1 font-semibold text-emerald-200 hover:bg-emerald-300/10">{item.asset.review_decision === "approved" ? "Open approved draft" : item.asset.review_decision === "rejected" ? "Open review batch" : "Open draft review"}</Link>}
                  {generation.task_id && <span className="text-slate-400">Task {generation.task_id}</span>}
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/40" role="progressbar" aria-label={`3D draft generation progress for ${item.title}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={generation.progress}>
                  <div className={`h-full rounded-full bg-gradient-to-r from-[#ff6600] via-[#ff8800] to-[#0099ff] transition-all duration-500 ${generationStatus === "STARTING" ? "w-1/12 animate-pulse" : ""}`} style={generationStatus === "STARTING" ? undefined : { width: `${generation.progress}%` }} />
                </div>
              </section>}
              <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-white/10 pt-3">
                <span className="text-xs text-slate-400">{item.storefront_blockers.join(" · ") || "The model is ready for customer listings."}</span>
                <div className="ml-auto flex flex-wrap gap-2">
                  {(!item.asset || item.asset.status === "rejected") && <button type="button" disabled={busyId !== null || listingImagesFor(item).length === 0} onClick={() => void generate(item)} className="rounded-lg border border-violet-400/30 px-3 py-2 text-xs text-violet-100 disabled:opacity-40">Generate this draft</button>}
                  {item.asset && item.asset.status !== "rejected" && !item.asset.is_active && item.asset.status !== "final" && <button type="button" disabled={busyId !== null || listingImagesFor(item).length === 0} onClick={() => void generate(item, true)} className="rounded-lg border border-amber-400/30 px-3 py-2 text-xs text-amber-100 disabled:opacity-40">Generate comparison draft</button>}
                  <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-cyan-400/30 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-400/10">
                    <Upload className="h-4 w-4 shrink-0" aria-hidden="true" /> Upload GLB
                    <input className="sr-only" type="file" accept=".glb,model/gltf-binary" disabled={busyId !== null} onChange={event => { void upload(item.variant_id, event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} />
                  </label>
                </div>
              </div>
            </article>
            );
          })}
        </div>
        </>
      )}
    </main>
  );
}
