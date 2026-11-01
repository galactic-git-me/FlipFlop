"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Product = {
  media_scope?: string; product_count?: number;
  variant_id: number; variant_ids: number[]; title: string; category: string; listing_image_urls: string[];
  automatic_media_preparation_enabled?: boolean;
  main_photo_approved?: boolean;
  asset: { id: number; status: string; glb_ref?: string | null; is_active: boolean; review_batch_id?: string | null } | null;
  asset_media_review?: { generation?: { status?: string; progress?: number; error?: string | null }; media_preparation?: { error?: string | null } } | null;
};
type State = "models" | "generating" | "missing" | "attention";
const running = new Set(["QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"]);
function stateOf(product: Product): State {
  if (product.asset?.glb_ref && product.asset.status !== "rejected") return "models";
  const generation = product.asset_media_review?.generation;
  if (running.has(generation?.status || "")) return "generating";
  if (product.asset || generation?.error || product.asset_media_review?.media_preparation?.error || generation?.status === "TIMED_OUT" || generation?.status === "FAILED" || generation?.status === "CANCELED" || generation?.status?.startsWith("SUBMIT_") || !product.listing_image_urls.length) return "attention";
  return "missing";
}
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  const payload = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Could not complete the request");
  return payload as T;
}

export default function ModelInventory({ approvalQueue = false }: { approvalQueue?: boolean } = {}) {
  const catalogue = "curated";
  const [products, setProducts] = useState<Product[]>([]);
  const [filter, setFilter] = useState<State | "all">("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [starting, setStarting] = useState<number | null>(null);
  const load = useCallback(async () => {
    try {
      const rows = await request<Product[]>("/api/assets-3d/catalogue/photo-queue");
      if (!Array.isArray(rows)) throw new Error("The model inventory returned an invalid response");
      setProducts(rows.filter(product => !["os", "os_secondary", "software"].includes(product.category)
        && (!approvalQueue || (product.main_photo_approved && !(product.asset?.is_active && product.asset.status === "final")))));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load model inventory"); }
    finally { setLoading(false); }
  }, [catalogue, approvalQueue]);
  useEffect(() => { setLoading(true); void load(); }, [load]);
  const generate = async (product: Product) => {
    setStarting(product.variant_id); setError(""); setNotice("");
    try {
      await request(`/api/assets-3d/variants/${product.variant_id}/auto-prepare`, {
        method: "POST", headers: { "content-type": "application/json" }, body: "{}",
      });
      // Show accepted work immediately, including while the inventory refreshes.
      setProducts(current => current.map(item => item.variant_id === product.variant_id ? {
        ...item, asset_media_review: { ...item.asset_media_review, generation: { status: "PREPARING", progress: 0 } },
      } : item));
      await load();
      setNotice(`Model generation started for ${product.title}. You can leave this page; the app continues in the background.`);
    } catch (reason) {
      setError(`${product.title}: ${reason instanceof Error ? reason.message : "Could not start generation"}`);
    } finally { setStarting(null); }
  };
  const generating = products.some(product => stateOf(product) === "generating");
  useEffect(() => {
    if (!generating) return;
    const timer = window.setInterval(() => void load(), 10000);
    return () => window.clearInterval(timer);
  }, [generating, load]);
  const counts = { all: products.length, models: 0, generating: 0, missing: 0, attention: 0 };
  for (const product of products) counts[stateOf(product)] += 1;
  const labels = { all: "All components", models: "Has model", generating: "Generating", missing: "Missing model", attention: "Needs attention" };
  const visible = products.filter(product => (filter === "all" || stateOf(product) === filter) && `${product.title} ${product.category}`.toLowerCase().includes(search.toLowerCase()));
  return <main className="mx-auto max-w-[1800px] space-y-5 p-6 text-slate-100">
    <Link href="/catalogue/3d-assets" className="text-sm text-cyan-300 underline">← Main photo approval grid</Link>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><Link href="/catalogue" className="text-sm text-cyan-300">← Catalogue</Link><h1 className="mt-2 text-2xl font-semibold">{approvalQueue ? "3D asset approvals" : "Curated catalogue · 3D models"}</h1><p className="mt-2 text-sm text-slate-400">Individual models for cases; one representative model per family for other hardware. Reused across every segment and the from-scratch builder.</p></div>
      <button onClick={() => void load()} disabled={loading} className="rounded border border-white/20 px-4 py-2">Refresh</button>
    </header>
    {approvalQueue && <p className="text-sm text-cyan-200">Components with approved photos that still need a model or finished-model approval. Generate missing models here, then open the result to review and publish it.</p>}
    <p className="text-sm text-slate-300">Click Generate model beside a missing model to send its approved photo to Meshy and create a textured GLB. This uses Meshy credits. Existing models and running jobs are reused.</p>
    {notice && <p role="status" className="rounded border border-emerald-400/30 p-3 text-emerald-200">{notice}</p>}
    <nav className="flex flex-wrap gap-2" aria-label="Model inventory status">{(Object.keys(labels) as (State | "all")[]).map(key => <button key={key} onClick={() => setFilter(key)} aria-pressed={filter === key} className={`rounded-lg border px-4 py-3 text-left ${filter === key ? "border-cyan-300 bg-cyan-400/10" : "border-white/15"}`}><span className="block text-2xl font-semibold">{loading ? "…" : counts[key]}</span><span className="text-sm">{labels[key]}</span></button>)}</nav>
    {error && <p role="alert" className="rounded border border-rose-400/30 p-3 text-rose-200">{error} <button className="underline" onClick={() => void load()}>Retry</button></p>}
    <label className="block text-sm">Search components<input value={search} onChange={event => setSearch(event.target.value)} className="mt-1 block w-full max-w-xl rounded border border-white/20 bg-slate-950 px-3 py-2" placeholder="Name or category" /></label>
    {loading ? <p role="status">Loading catalogue models…</p> : <div className="overflow-x-auto rounded-lg border border-white/15"><table className="w-full text-left text-sm"><thead className="bg-slate-800"><tr><th className="p-3">Component</th><th className="p-3">3D model</th><th className="p-3">Customer use</th><th className="p-3">Progress / action</th></tr></thead><tbody>{visible.map(product => {
      const state = stateOf(product); const generation = product.asset_media_review?.generation;
      const problem = generation?.error || product.asset_media_review?.media_preparation?.error;
      return <tr key={product.variant_id} className="border-t border-white/10 align-top"><td className="p-3"><p className="text-xs uppercase text-cyan-300">{product.category}</p><p className="mt-1 font-medium">{product.title}</p><p className="mt-1 text-xs text-slate-400">{product.media_scope === "family" ? `Shared by ${product.product_count} products` : "Individual case model"}</p></td><td className="whitespace-nowrap p-3"><span className={state === "models" ? "text-emerald-300" : state === "attention" ? "text-amber-300" : "text-slate-300"}>{labels[state]}</span></td><td className="p-3">{product.asset?.is_active && product.asset.status === "final" ? "In use" : state === "models" ? "Draft · not published" : "—"}</td><td className="max-w-md p-3">{state === "models" ? <Link className="text-cyan-300 underline" href={`/components-3d-review?${product.asset?.review_batch_id ? `batch=${encodeURIComponent(product.asset.review_batch_id)}` : `asset_id=${product.asset?.id}`}&returnTo=${encodeURIComponent(`/catalogue/3d-assets?catalogue=${catalogue}`)}`}>Open model</Link> : state === "generating" ? <span role="status">{generation?.status === "QUEUED" ? "Queued · starts automatically" : `${generation?.status === "PREPARING" ? "Choosing photo" : "Generating model"} · ${generation?.progress ?? 0}%`}</span> : state === "attention" ? <span className="text-amber-200">{problem || (!product.listing_image_urls.length ? "No captured hardware photo" : "Existing task or model needs investigation")}</span> : product.automatic_media_preparation_enabled === false ? <span className="text-slate-400">Generation is available in DEV</span> : product.main_photo_approved ? <button type="button" disabled={starting !== null} onClick={() => void generate(product)} className="rounded bg-cyan-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-50" aria-label={`Generate model for ${product.title}`}>{starting === product.variant_id ? "Starting…" : "Generate model"}</button> : <Link className="text-amber-200 underline" href="/catalogue/3d-assets">Approve photo first</Link>}</td></tr>;
    })}</tbody></table>{!visible.length && <p className="p-6 text-slate-400">{approvalQueue ? "No components with approved photos currently need a model or model approval." : "No components match this view."}</p>}</div>}
    <details className="rounded border border-white/10 p-3 text-sm text-slate-400"><summary className="cursor-pointer">Advanced tools</summary><Link className="mt-3 inline-block text-cyan-300 underline" href={`/catalogue/3d-assets?catalogue=${catalogue}&advanced=1`}>Manual photo selection, uploads and diagnostics</Link></details>
  </main>;
}
