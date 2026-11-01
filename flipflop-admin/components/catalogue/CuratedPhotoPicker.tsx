"use client";

import { useState } from "react";
import { readJsonResponse } from "@/lib/read-json-response";

type Media = { url: string; source: string; href: string | null };
type Gallery = { images: Media[]; videos: Media[] };

export default function CuratedPhotoPicker({ category, cpk, title }: { category: string; cpk: string; title: string }) {
  const [open, setOpen] = useState(false);
  const [gallery, setGallery] = useState<Gallery | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set());

  const load = async () => {
    setOpen(true); setBusy(true); setError(""); setGallery(null);
    try {
      const response = await fetch(`/api/curated-builds/bestseller-catalogue/media?${new URLSearchParams({ category, cpk })}`, { cache: "no-store" });
      const data = await readJsonResponse<Gallery & { detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || "Could not load listing photos");
      setGallery(data);
      setFailedImages(new Set());
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load listing photos"); }
    finally { setBusy(false); }
  };

  return <section className="border-t border-white/10 p-4" aria-label={`Catalogue photos for ${title}`}>
    <button type="button" onClick={() => open ? setOpen(false) : void load()} className="rounded border border-cyan-400/40 px-3 py-2 text-sm text-cyan-200">{open ? "Close captured media" : "View captured listing media"}</button>
    {open && <div className="mt-3 space-y-3">
      <p className="text-xs text-slate-400">All captured photos and videos for this approved product match are automatically included in the Playbook listing. Choose four model reference photos in the 3D assets queue.</p>
      {busy && <p role="status" className="text-sm text-slate-300">Loading captured media…</p>}
      {error && <p role="alert" className="text-sm text-rose-200">{error}</p>}
      {gallery && <>
        <p className="text-xs text-emerald-200">{gallery.images.length} photos · {gallery.videos.length} videos auto-included</p>
        {gallery.images.length <= 1 && <p className="text-xs text-amber-200">{gallery.images.length === 0 ? "No product photos have been captured yet." : "Only one photo has been captured. Additional listing photos are not available in this gallery yet."}</p>}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {gallery.images.map((image, index) => <div key={image.url} className="rounded border border-emerald-400/30 p-2">
            <a href={image.url} target="_blank" rel="noreferrer" aria-label={`View photo ${index + 1} full size`}><img src={image.url} alt={`${title} · photo ${index + 1}`} className="h-32 w-full bg-white object-contain" onError={() => setFailedImages(current => new Set(current).add(image.url))}/></a>
            <span className="mt-2 block text-xs text-emerald-200">Included in listing</span>
            <span className="mt-1 block text-[10px] text-slate-400">{image.source}</span>
            {failedImages.has(image.url) && <span className="text-xs text-rose-200">Photo could not load</span>}
          </div>)}
        </div>
        {gallery.videos.map((video, index) => <div key={video.url} className="flex items-center gap-2 text-xs text-emerald-200">Video {index + 1} auto-included <a href={video.url} target="_blank" rel="noreferrer" className="text-cyan-200">Preview video</a></div>)}
      </>}
    </div>}
  </section>;
}
