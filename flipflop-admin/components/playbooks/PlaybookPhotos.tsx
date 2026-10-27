"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { originalImageUrl } from "@/lib/model-reference-images";
const Models = dynamic(() => import("@/app/components-3d-review/workspace"), { ssr: false, loading: () => <p role="status">Loading model review…</p> });

type Product = {
  variant_id: number; variant_ids: number[]; catalogue_status?: string; title: string; category: string; listing_image_urls: string[];
  automatic_media_preparation_enabled?: boolean;
  asset: { id: number; status: string; is_active: boolean; glb_ref?: string | null; notes?: string | null; review_batch_id?: string | null } | null;
  asset_media_review: { status?: string; model_image_urls?: string[]; model_references_selected_by?: string;
    generation?: { status: string; progress: number; error?: string | null };
    media_preparation?: { status: string; progress: number; error?: string | null } } | null;
};
const replacementPending = (product: Product) => product.asset?.status === "missing" && !product.asset.notes?.includes("Regeneration failed");
const runningStatuses = new Set(["QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"]);
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { throw new Error(`The server returned an unreadable response (${response.status})`); }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.error || `Request failed (${response.status})`);
  return data as T;
}

export default function PlaybookPhotos({ variantIds }: { variantIds: number[] }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [review, setReview] = useState<{ variantId: number; batchId?: string } | null>(null);
  const reviewVariantIds = useMemo(() => review ? [review.variantId] : [], [review?.variantId]);
  const ids = variantIds.join(",");
  const load = useCallback(async () => {
    try {
      const data = await request<Product[]>(`/api/assets-3d/catalogue-queue?catalogue=curated&variant_ids=${ids}`);
      if (!Array.isArray(data)) throw new Error("The asset inventory returned an invalid response");
      setProducts(data); setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load product photos"); }
    finally { setLoading(false); }
  }, [ids]);
  useEffect(() => { void load(); }, [load]);
  const generating = products.some(product => runningStatuses.has(product.asset_media_review?.generation?.status ?? "") || replacementPending(product));
  useEffect(() => {
    if (!generating) return;
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [generating, load]);
  const references = (product: Product) => product.asset_media_review?.model_references_selected_by ? product.asset_media_review.model_image_urls ?? [] : [];
  const photosApproved = (product: Product) => product.asset_media_review?.status === "approved"
    && Boolean(product.asset_media_review.model_references_selected_by)
    && (product.asset_media_review.model_image_urls?.length ?? 0) >= 1
    && (product.asset_media_review.model_image_urls?.length ?? 0) <= 4;
  const regenerateFromApprovedMedia = async (product: Product) => {
    const modelImageUrls = [...references(product)];
    if (modelImageUrls.length < 1 || modelImageUrls.length > 4) return;
    setBusy(product.variant_id); setError(""); setNotice("");
    try {
      if (!photosApproved(product)) {
        await request(`/api/assets-3d/variants/${product.variant_id}/media-approval`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model_image_urls: modelImageUrls }),
        });
      }
      await request(`/api/assets-3d/variants/${product.variant_id}/generate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ comparison_draft: Boolean(product.asset && product.asset.status !== "rejected") }),
      });
      setNotice(photosApproved(product)
        ? `This component's photos are already approved and shared across every segment that uses it. Model generation is running; you can close this window.`
        : `Photos approved for ${product.title}. That approval is shared across every segment that uses this component. Model generation is running; you can close this window.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not generate the model"); }
    finally { setBusy(null); }
  };
  const prepareMediaAndGenerate = async (product: Product) => {
    setBusy(product.variant_id); setError(""); setNotice("");
    try {
      await request(`/api/assets-3d/variants/${product.variant_id}/auto-prepare`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      });
      setNotice(`The app is preparing a textured GLB for ${product.title} from one photo. Your approved main photo is reused when available. The model will still need your review.`);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not start automatic media preparation"); }
    finally { setBusy(null); }
  };
  const missingIds = variantIds.filter(id => !products.some(product => product.variant_ids.includes(id)));
  return <section className="space-y-4 p-4" aria-label="Build photos and models">
    <a href="/catalogue/3d-assets" className="text-sm text-cyan-300 underline">Approve all catalogue main photos in one grid</a>
    {review ? <>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => { setReview(null); void load(); }} className="rounded border border-white/20 px-3 py-2 text-sm">Back to product photos</button>
        {products.filter(product => product.variant_ids.includes(review.variantId) && !product.asset?.is_active).map(product => <button key={product.variant_id} type="button" disabled={busy !== null || references(product).length === 0} onClick={() => { setReview(null); void regenerateFromApprovedMedia(product); }} className="rounded border border-cyan-400/40 px-3 py-2 text-sm text-cyan-200 disabled:opacity-40">Regenerate from approved media</button>)}
      </div>
      <p className="text-xs text-slate-400">Regeneration uses provider credits and creates a new draft for your approval.</p>
      <p className="text-sm text-slate-400">Inspect the model, approve or reject it, and confirm its rights and scale before publishing. Only your approved models can appear to customers.</p>
      <Models variantIds={reviewVariantIds} batchId={review.batchId} />
    </> : <>
      <p className="text-sm text-slate-300">The app uses your approved main photo to create one textured GLB with Meshy. If no main photo is approved, local Qwen can select a captured hardware photo. The model is shared across every segment using this component. Model generation uses Meshy credits.</p>
      {error && <p role="alert" className="text-rose-200">{error} <button onClick={() => void load()} className="underline">Retry loading</button></p>}
      {notice && <p role="status" className="text-emerald-200">{notice}</p>}
      {loading ? <p role="status">Loading the build’s exact products…</p> : missingIds.map(id => <p key={id} role="alert" className="text-amber-200">Component {id} is missing from the asset inventory. Its catalogue link or status needs repair.</p>)}
      {products.map(product => {
        const refs = references(product);
        const generation = product.asset_media_review?.generation;
        const preparation = product.asset_media_review?.media_preparation;
        const running = runningStatuses.has(generation?.status ?? "") || replacementPending(product);
        const approvedPhotos = photosApproved(product);
        const approved = product.asset?.is_active && product.asset.status === "final";
        return <article key={product.variant_id} className="space-y-3 rounded-lg border border-white/15 p-4">
          <header><p className="text-xs uppercase text-cyan-300">{product.category}</p><h3 className="font-semibold">{product.title}</h3>{product.catalogue_status === "hidden" && <p className="mt-1 text-xs text-amber-200">This catalogue entry is hidden. You can prepare its media; supplier and publication checks still apply.</p>}</header>
          {approvedPhotos && <p className="text-sm text-emerald-200">Model reference photo{refs.length === 1 ? "" : "s"} saved for this component · shared across all segments that use it</p>}
          <div className="flex gap-3 overflow-x-auto pb-2">
            {product.listing_image_urls.map((url, index) => <label key={url} className={`w-40 shrink-0 rounded border p-2 ${refs.includes(url) ? "border-cyan-300" : "border-white/15"}`}>
              <img src={originalImageUrl(url)} alt={`${product.title} photo ${index + 1}`} className="h-32 w-full bg-white object-contain" loading="lazy" />
              <span className={`mt-2 block text-xs ${refs.includes(url) ? "text-emerald-200" : "text-slate-400"}`}>{refs.includes(url) ? "Selected Meshy source photo" : `Captured product photo ${index + 1}`}</span>
            </label>)}
          </div>
          {approvedPhotos && <div className="flex gap-3 overflow-x-auto pb-2" aria-label="Selected 3D model reference photos">
            {refs.map((url, index) => <div key={url} className="w-40 shrink-0 rounded border border-emerald-400/40 p-2">
              <img src={originalImageUrl(url)} alt={`${product.title} selected Meshy source photo`} className="h-32 w-full bg-slate-950 object-contain" loading="lazy" />
              <span className="mt-2 block text-xs text-emerald-200">{refs.length === 1 ? "Single photo sent to Meshy" : "Photo sent to Meshy"}</span>
            </div>)}
          </div>}
          {!product.listing_image_urls.length && <p className="text-amber-200">No captured product photos are available yet. The sourcing engine must collect them before automatic preparation can run.</p>}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {approved ? <span className="text-emerald-200">Model approved and published</span> : product.asset && product.asset.status !== "rejected" && product.asset.glb_ref ? <button type="button" onClick={() => setReview({ variantId: product.variant_id, batchId: product.asset?.review_batch_id ?? undefined })} className="rounded bg-cyan-400 px-3 py-2 font-medium text-slate-950">Review 3D model</button> : product.automatic_media_preparation_enabled === false ? <span className="text-slate-400">Automatic media preparation is DEV-only</span> : <button type="button" disabled={busy !== null || running || product.listing_image_urls.length === 0} onClick={() => void prepareMediaAndGenerate(product)} className="rounded bg-cyan-400 px-3 py-2 font-medium text-slate-950 disabled:opacity-40">{running ? "Selecting photo and generating…" : busy === product.variant_id ? "Starting…" : "Select one photo & generate textured model"}</button>}
            {product.asset && !approved && product.asset.glb_ref && <button type="button" disabled={busy !== null || running || refs.length === 0} onClick={() => void regenerateFromApprovedMedia(product)} className="rounded border border-cyan-400/40 px-3 py-2 text-cyan-200 disabled:opacity-40">Regenerate from approved media</button>}
            {approvedPhotos && <span className="text-slate-400">{refs.length}/1 selected Meshy source photo</span>}
            {running && <span role="status">{generation?.status === "PREPARING" ? `Preparing media · ${preparation?.progress ?? 0}%` : `Generating model · ${generation?.progress ?? 0}%`}</span>}
          </div>
          {preparation?.status && preparation.status !== "READY" && <p role="status" className="text-slate-300">Media workflow: {preparation.status.replaceAll("_", " ").toLowerCase()} · {preparation.progress}%</p>}
          {preparation?.error && <p role="alert" className="text-amber-200">{preparation.error}</p>}
          {generation?.error && <p role="alert" className="text-amber-200">{generation.error}</p>}{product.asset?.notes?.includes("Regeneration failed") && <p role="alert" className="text-amber-200">The replacement model failed. You can regenerate using the approved media.</p>}
        </article>;
      })}
    </>}
  </section>;
}
