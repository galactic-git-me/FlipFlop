"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, Image as ImageIcon, Loader2, Trash2 } from "lucide-react";

import GooglePhotoSearch from "./GooglePhotoSearch";

type Product = {
  media_scope?: "family" | "product"; product_count?: number; media_family_key?: string;
  range_reason?: { kind: string; bucket?: string; rank?: number; cell?: string; requirement?: string };
  variant_id: number; variant_ids: number[]; listing_id: number; title: string; category: string;
  main_photo_url?: string | null; main_photo_approved?: boolean; listing_image_urls: string[];
  curated_for_builds: boolean; custom_for_builds: boolean;
  asset?: { glb_ref?: string | null; status: string; is_active: boolean } | null;
};
async function read<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { cache: "no-store", ...init });
  const data = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not complete the request");
  return data as T;
}
function imageLoads(url: string): Promise<boolean> {
  return new Promise(resolve => {
    const image = new Image();
    const finish = (ok: boolean) => { window.clearTimeout(timer); image.onload = null; image.onerror = null; resolve(ok); };
    const timer = window.setTimeout(() => finish(false), 12000);
    image.onload = () => finish(image.naturalWidth > 0 && image.naturalHeight > 0);
    image.onerror = () => finish(false);
    image.src = url;
  });
}

function PhotoThumbnails({ product, active, disabled, onChoose }: { product: Product; active: string; disabled: boolean; onChoose: (url: string) => void }) {
  const strip = useRef<HTMLDivElement>(null);
  const photos = [...new Set([product.main_photo_url, ...product.listing_image_urls].filter((url): url is string => !!url))];
  if (!photos.length) return null;
  return <div className="flex items-center gap-1 bg-slate-950 p-2">
    {photos.length > 3 && <button type="button" aria-label={`Previous photos for ${product.title}`} onClick={() => strip.current?.scrollBy({ left: -160, behavior: "smooth" })} className="shrink-0 rounded py-3 text-slate-300 hover:bg-white/10"><ChevronLeft className="h-4 w-4" /></button>}
    <div ref={strip} className="flex min-w-0 flex-1 snap-x gap-2 overflow-x-auto pb-1" aria-label={`Photo gallery for ${product.title}`}>
      {photos.map((photo, index) => <button type="button" key={photo} disabled={disabled} aria-label={`Use photo ${index + 1} for ${product.title}`} aria-pressed={active === photo} onClick={() => onChoose(photo)} className={`h-12 w-12 shrink-0 snap-start overflow-hidden rounded border-2 bg-white ${active === photo ? "border-cyan-300" : "border-transparent hover:border-slate-400"} disabled:opacity-50`}><img src={photo} alt={`Product photo ${index + 1}`} loading="lazy" className="h-full w-full object-contain" /></button>)}
    </div>
    {photos.length > 3 && <button type="button" aria-label={`Next photos for ${product.title}`} onClick={() => strip.current?.scrollBy({ left: 160, behavior: "smooth" })} className="shrink-0 rounded py-3 text-slate-300 hover:bg-white/10"><ChevronRight className="h-4 w-4" /></button>}
  </div>;
}
export default function CataloguePhotoApproval() {
  const [products, setProducts] = useState<Product[]>([]);
  const [chosenPhotos, setChosenPhotos] = useState<Record<number, string>>({});
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [broken, setBroken] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const sequence = useRef(0);
  const [imageSearchProduct, setImageSearchProduct] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const load = useCallback(async () => {
    const requestId = ++sequence.current;
    try {
      const rows = await read<Product[]>("/api/assets-3d/catalogue/photo-queue");
      if (!Array.isArray(rows)) throw new Error("The catalogue returned an invalid photo inventory");
      const merged = new Map<string, Product>();
      for (const product of rows) {
        const key = `${product.listing_id}:${product.category}`;
        const existing = merged.get(key);
        merged.set(key, existing ? { ...existing, variant_ids: [...new Set([...existing.variant_ids, ...product.variant_ids])], curated_for_builds: existing.curated_for_builds || product.curated_for_builds, custom_for_builds: existing.custom_for_builds || product.custom_for_builds } : product);
      }
      if (sequence.current === requestId) { setProducts([...merged.values()]); setError(""); }
    } catch (reason) { if (sequence.current === requestId) setError(reason instanceof Error ? reason.message : "Could not load catalogue photos"); }
    finally { if (sequence.current === requestId) setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const remove = async (product: Product) => {
    setDeleting(product.listing_id); setError("");
    try {
      await read(`/api/assets-3d/catalogue/components/${product.variant_id}`, { method: "DELETE" });
      setProducts(current => current.filter(item => item.listing_id !== product.listing_id));
      setSelected(current => new Set([...current].filter(id => !product.variant_ids.includes(id))));
      setNotice(`Permanently removed ${product.title} from the catalogue and all segments.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not delete component"); }
    finally { setDeleting(null); }
  };
  const source = (product: Product) => chosenPhotos[product.listing_id] || product.main_photo_url || product.listing_image_urls[0] || "";
  const isApproved = (product: Product) => !!product.main_photo_approved && source(product) === product.main_photo_url;
  const categoryOf = (product: Product) => product.range_reason?.bucket || product.category;
  const missing = (product: Product) => !source(product) || broken.has(source(product));
  const scope = products;
  const visible = scope.filter(product => (category === "all" || categoryOf(product) === category) && `${product.title} ${product.category}`.toLowerCase().includes(search.toLowerCase()) && (filter === "all" || (filter === "approved" ? isApproved(product) : filter === "missing" ? missing(product) : !isApproved(product))));
  const candidates = visible.filter(product => !missing(product) && !isApproved(product));
  const selectedProducts = visible.filter(product => selected.has(product.variant_id) && !missing(product) && !isApproved(product));
  const markBroken = (url: string, id: number) => { setBroken(current => new Set(current).add(url)); setSelected(current => { const next = new Set(current); next.delete(id); return next; }); };
  const approve = async () => {
    setBusy(true); setError(""); setNotice("Checking selected photos…");
    const pending = [...selectedProducts]; const valid: Product[] = []; const failed: Product[] = [];
    let checked = 0;
    try {
      await Promise.all(Array.from({ length: Math.min(8, pending.length) }, async () => {
        while (pending.length) {
          const product = pending.shift()!;
          if (await imageLoads(source(product))) valid.push(product); else { failed.push(product); markBroken(source(product), product.variant_id); }
          checked += 1; setNotice(`Checking photos · ${checked}/${selectedProducts.length}`);
        }
      }));
      let approved = 0; const skipped: string[] = [];
      for (let offset = 0; offset < valid.length; offset += 100) {
        const batch = valid.slice(offset, offset + 100);
        const result = await read<{ approved_count: number; approved_variant_ids: number[]; skipped: { reason: string }[] }>("/api/assets-3d/catalogue/approve-main-photos", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ selections: batch.map(product => ({ variant_id: product.variant_id, photo_url: source(product) })) }),
        });
        approved += result.approved_count; skipped.push(...result.skipped.map(item => item.reason));
        setSelected(current => { const next = new Set(current); result.approved_variant_ids.forEach(id => next.delete(id)); return next; });
        setNotice(`Saving photo approvals · ${approved}/${valid.length}`);
      }
      await load();
      setNotice(`${approved} component photo${approved === 1 ? "" : "s"} approved and shared across Playbooks and the from-scratch builder.${failed.length ? ` ${failed.length} broken or unavailable photos skipped.` : ""}${skipped.length ? ` ${skipped.length} changed galleries skipped; refresh and review them again.` : ""}`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save approvals"); await load(); }
    finally { setBusy(false); }
  };
  return <main className="mx-auto max-w-[1900px] space-y-5 p-6 text-slate-100">
    <header className="flex flex-wrap justify-between gap-4"><div><h1 className="text-2xl font-semibold">Curated catalogue · photo approvals</h1><p className="mt-2 text-sm text-slate-300">Choose a thumbnail to change the main photo. Use pictures of the hardware itself, without its retail box. Select all, deselect anything wrong, then approve once.</p><p className="mt-1 text-xs text-slate-400">One catalogue for Playbook builds and building from scratch. Only cases have individual photos and models. Other hardware shares one representative photo and model per family.</p></div><div className="flex items-start gap-3"><Link className="rounded border border-cyan-300/30 px-3 py-2 text-sm text-cyan-200" href="/components-3d-review">Approve 3D models</Link><button disabled={busy} onClick={() => void load()} className="rounded border border-white/20 px-3 py-2 text-sm">Refresh</button></div></header>

    <div className="flex flex-wrap gap-3 text-sm"><span>{scope.length} media approvals</span><span className="text-emerald-300">{scope.filter(isApproved).length} approved</span><span>{scope.filter(product => !isApproved(product)).length} awaiting photo approval</span><span className="text-amber-300">{scope.filter(missing).length} missing / broken photos</span><span>{scope.filter(product => product.asset?.glb_ref && product.asset.status !== "rejected").length} have 3D models</span></div>
    <div className="flex flex-wrap gap-3"><input aria-label="Search products" value={search} disabled={busy} onChange={event => setSearch(event.target.value)} placeholder="Search products…" className="min-w-64 flex-1 rounded border border-white/20 bg-slate-950 px-3 py-2" /><select aria-label="Category" disabled={busy} value={category} onChange={event => setCategory(event.target.value)} className="rounded border border-white/20 bg-slate-950 px-3 py-2"><option value="all">All categories</option>{[...new Set(scope.map(categoryOf))].sort().map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Photo approval status" disabled={busy} value={filter} onChange={event => setFilter(event.target.value)} className="rounded border border-white/20 bg-slate-950 px-3 py-2"><option value="all">All products</option><option value="pending">Awaiting approval</option><option value="approved">Approved</option><option value="missing">Missing / broken photos</option></select></div>
    <div className="sticky top-0 z-20 flex flex-wrap items-center gap-3 rounded-lg border border-cyan-300/30 bg-slate-950/95 p-3 shadow-xl"><button disabled={busy || !candidates.length} onClick={() => setSelected(current => new Set([...current, ...candidates.map(product => product.variant_id)]))} className="rounded border border-white/25 px-4 py-2 disabled:opacity-40">Select all shown ({candidates.length})</button><button disabled={busy || !selected.size} onClick={() => setSelected(new Set())} className="px-3 py-2 disabled:opacity-40">Clear selection</button><span className="text-sm">{selectedProducts.length} selected</span><button disabled={busy || !selectedProducts.length} onClick={() => void approve()} className="ml-auto rounded bg-cyan-400 px-5 py-2 font-semibold text-slate-950 disabled:opacity-40">{busy ? "Saving…" : `Approve selected photos (${selectedProducts.length})`}</button></div>

    {notice && <p role="status" className="text-emerald-200">{notice}</p>}{error && <p role="alert" className="text-rose-200">{error}</p>}
    {loading ? <p role="status">Loading curated catalogue…</p> : <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-6">{visible.map(product => {
      const url = source(product); const unavailable = missing(product); const approved = isApproved(product); const checked = selected.has(product.variant_id);
      return <article key={`${product.listing_id}:${product.category}`} className={`relative overflow-hidden rounded-xl border-2 ${checked ? "border-cyan-300 ring-2 ring-cyan-400/30" : approved ? "border-emerald-500/50" : "border-white/15"} ${busy || unavailable || approved ? "" : "cursor-pointer"}`}><div className="relative aspect-square bg-white">{url && !broken.has(url) ? <img src={url} alt={product.title} loading="lazy" className="h-full w-full object-contain" onError={() => markBroken(url, product.variant_id)} /> : <div className="flex h-full items-center justify-center p-4 text-center text-slate-700">Photo missing or unavailable</div>}<div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/85 to-transparent px-3 pb-3 pt-12"><p className="line-clamp-3 text-sm font-semibold text-white" title={product.title}>{product.title}</p></div><span className="absolute left-2 top-2 rounded bg-slate-950/85 px-2 py-1 text-xs uppercase text-cyan-200">{categoryOf(product)}</span><input type="checkbox" aria-label={`Approve main photo for ${product.title}`} checked={checked} disabled={busy || unavailable || approved} onChange={event => setSelected(current => { const next = new Set(current); event.target.checked ? next.add(product.variant_id) : next.delete(product.variant_id); return next; })} className="absolute right-3 top-3 h-6 w-6 accent-cyan-400" /></div><PhotoThumbnails product={product} active={url} disabled={busy || deleting !== null} onChoose={photo => { setChosenPhotos(current => ({ ...current, [product.listing_id]: photo })); setSelected(current => { const next = new Set(current); if (product.main_photo_approved && photo === product.main_photo_url) next.delete(product.variant_id); else next.add(product.variant_id); return next; }); }} /><div className="relative min-h-16 space-y-1 bg-slate-900 p-3 pr-20 text-xs"><p className={approved ? "text-emerald-300" : unavailable ? "text-amber-300" : "text-slate-300"}>{approved ? "Photo approved ✓" : unavailable ? "Needs a working main photo" : checked ? "Selected · click to deselect" : "Use checkbox to select"}</p><p className="text-cyan-200">{product.media_scope === "family" ? `Shared by ${product.product_count} products` : "Individual case"}</p><p className="text-slate-400">{product.asset?.glb_ref && product.asset.status !== "rejected" ? product.asset.is_active ? "3D model: in use" : "3D model: saved draft" : "3D model: missing"}</p>{product.range_reason?.kind === "playbook_requirement" && <p className="text-amber-200" title={product.range_reason.requirement}>Needed by {product.range_reason.cell}</p>}<button type="button" disabled={busy || deleting !== null} aria-label={`Search images for ${product.title}`} title="Find a photo with Google Images" onClick={() => setImageSearchProduct(product)} className="absolute bottom-2 right-11 inline-flex h-9 w-9 items-center justify-center rounded text-slate-400 hover:bg-cyan-400/10 hover:text-cyan-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><ImageIcon aria-hidden="true" className="h-4 w-4" /></button>{product.category === "case" && <button type="button" disabled={busy || deleting !== null} aria-label={`Delete ${product.title} from catalogue`} aria-busy={deleting === product.listing_id} title="Permanently remove this component from the curated catalogue and every segment" onClick={() => void remove(product)} className="absolute bottom-2 right-2 inline-flex h-9 w-9 items-center justify-center rounded text-slate-400 transition-colors hover:bg-red-500/10 hover:text-red-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-400 disabled:opacity-40">{deleting === product.listing_id ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Trash2 aria-hidden="true" className="h-4 w-4" />}</button>}</div></article>;
    })}</div>}
    {!loading && !visible.length && <p className="py-8 text-slate-400">No products match these filters.</p>}
    <p className="text-xs text-slate-500">Delete from catalogue permanently removes the entire component from the curated catalogue and every segment, not just its photo. Photo approval saves your chosen picture. It does not start paid model generation or approve a 3D model.</p>
    {imageSearchProduct && <GooglePhotoSearch key={imageSearchProduct.variant_id} variantId={imageSearchProduct.variant_id} title={imageSearchProduct.title} onClose={() => setImageSearchProduct(null)} onSaved={url => {
      const product = imageSearchProduct;
      setChosenPhotos(current => ({ ...current, [product.listing_id]: url }));
      setProducts(current => current.map(item => item.listing_id === product.listing_id ? { ...item, main_photo_url: url, main_photo_approved: false, listing_image_urls: [...new Set([url, ...item.listing_image_urls])] } : item));
      setSelected(current => new Set(current).add(product.variant_id));
      setImageSearchProduct(null);
      setNotice("Photo downloaded and selected. Approve selected photos when ready.");
    }} />}
  </main>;
}
