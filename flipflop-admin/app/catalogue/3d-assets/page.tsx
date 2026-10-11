"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Upload } from "lucide-react";

type Asset = {
  id: number;
  status: string;
  version: number;
  glb_ref: string | null;
  is_active: boolean;
};

type QueueItem = {
  variant_id: number;
  title: string;
  category: string;
  display_price: number;
  curated_for_builds: boolean;
  custom_for_builds: boolean;
  asset: Asset | null;
};

export default function Catalogue3DAssetsPage() {
  const [catalogue, setCatalogue] = useState<"curated" | "custom">("curated");
  const [catalogueReady, setCatalogueReady] = useState(false);
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const loadSequence = useRef(0);

  const load = useCallback(async () => {
    const sequence = ++loadSequence.current;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/assets-3d/catalogue-queue?catalogue=${catalogue}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not load the catalogue asset queue.");
      if (sequence === loadSequence.current) setItems(payload as QueueItem[]);
    } catch (caught) {
      if (sequence === loadSequence.current) setError(caught instanceof Error ? caught.message : "Could not load the catalogue asset queue.");
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }, [catalogue]);

  useEffect(() => {
    setCatalogue(new URLSearchParams(window.location.search).get("catalogue") === "custom" ? "custom" : "curated");
    setCatalogueReady(true);
  }, []);
  useEffect(() => { if (catalogueReady) void load(); }, [catalogueReady, load]);

  const upload = async (variantId: number, file?: File) => {
    if (!file) return;
    setBusyId(variantId);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.set("file", file);
      const response = await fetch(`/api/assets-3d/variants/${variantId}/upload-glb`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "The GLB upload failed.");
      setNotice(`${items.find(item => item.variant_id === variantId)?.title}: uploaded as version ${payload.version}. It is waiting for validation and rights review.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The GLB upload failed.");
    } finally {
      setBusyId(null);
    }
  };

  const attentionCount = items.filter(item => !item.asset || !item.asset.is_active).length;
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6 text-slate-100">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/catalogue" className="text-sm text-cyan-300 hover:underline">← Catalogue</Link>
          <h1 className="mt-3 text-2xl font-semibold">Shared component 3D assets</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">One asset is shared whenever the same catalogue variant appears in Curated and Custom. Uploading adds a version for that component; it remains unavailable to customers until scale, provenance and review gates pass.</p>
        </div>
        <Link href={`/components-3d-review?${catalogue}Only=1`} className="rounded-lg border border-white/15 px-4 py-2 text-sm hover:border-cyan-400/50">Open 3D review queue</Link>
      </div>

      <nav className="flex gap-2 border-b border-white/10 pb-3" aria-label="Catalogue asset queue">
        <a href="/catalogue/3d-assets?catalogue=curated" aria-current={catalogue === "curated" ? "page" : undefined} className={`rounded-full border px-4 py-2 text-sm ${catalogue === "curated" ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200" : "border-white/10 text-slate-400"}`}>Curated Catalogue</a>
        <a href="/catalogue/3d-assets?catalogue=custom" aria-current={catalogue === "custom" ? "page" : undefined} className={`rounded-full border px-4 py-2 text-sm ${catalogue === "custom" ? "border-cyan-400/50 bg-cyan-400/10 text-cyan-200" : "border-white/10 text-slate-400"}`}>Custom Catalogue</a>
      </nav>

      <div className="flex flex-wrap gap-3 text-sm text-slate-300">
        <span className="rounded-lg border border-white/10 px-3 py-2">{items.length} selected components</span>
        <span className="rounded-lg border border-amber-300/20 px-3 py-2 text-amber-200">{attentionCount} need upload or review</span>
      </div>
      {error && <p role="alert" className="rounded-lg border border-red-400/30 bg-red-950/30 p-3 text-sm text-red-200">{error}</p>}
      {notice && <p role="status" className="rounded-lg border border-emerald-400/30 bg-emerald-950/30 p-3 text-sm text-emerald-200">{notice}</p>}
      {loading ? <p className="text-sm text-slate-400">Loading catalogue components…</p> : items.length === 0 ? <p className="rounded-xl border border-white/10 p-6 text-sm text-slate-400">No active variants are currently tagged for this catalogue.</p> : (
        <div className="overflow-hidden rounded-xl border border-white/10">
          <div className="hidden grid-cols-[minmax(0,1fr)_90px_160px_180px] gap-3 bg-white/5 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-400 md:grid">
            <span>Component</span><span>Type</span><span>Asset status</span><span>GLB file</span>
          </div>
          {items.map(item => (
            <article key={item.variant_id} className="grid grid-cols-1 items-center gap-3 border-t border-white/10 px-4 py-3 md:grid-cols-[minmax(0,1fr)_90px_160px_180px]">
              <div className="min-w-0"><p className="break-words font-medium" title={item.title}>{item.title}</p><p className="mt-1 text-xs text-slate-500">Shared variant #{item.variant_id}{item.curated_for_builds && item.custom_for_builds ? " · appears in both catalogues" : ""}</p></div>
              <span className="text-sm capitalize text-slate-300"><span className="mr-1 text-slate-500 md:hidden">Type:</span>{item.category}</span>
              <span className={item.asset?.is_active ? "text-sm text-emerald-300" : item.asset ? "text-sm text-amber-200" : "text-sm text-slate-500"}>{item.asset ? `${item.asset.status.replaceAll("_", " ")} · v${item.asset.version}` : "Waiting for asset"}</span>
              <label className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-cyan-400/30 px-3 py-2 text-center text-xs text-cyan-100 hover:bg-cyan-400/10 md:w-auto">
                <Upload className="h-4 w-4 shrink-0" aria-hidden="true" />
                {busyId === item.variant_id ? "Uploading…" : item.asset ? "Upload / replace GLB" : "Upload GLB"}
                <input className="sr-only" type="file" accept=".glb,model/gltf-binary" disabled={busyId === item.variant_id} onChange={event => { void upload(item.variant_id, event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} />
              </label>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
