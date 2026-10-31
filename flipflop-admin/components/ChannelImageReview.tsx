"use client";

import { useEffect, useRef, useState } from "react";

export type ImageReviewRequest = { buildId: number; title: string; channel: string; urls: string[] };
type PreviewImage = { id: string; policy_version: number; url: string; source_url: string; width: number; height: number; upscaled: boolean; square_crop_safe: boolean };
type Preview = ImageReviewRequest & { images: PreviewImage[] };
const imageSrc = (url: string) => url.replace(/^https:\/\/(?:www\.)?theflipflop\.shop\/api\//, "/proxy-api/");

export default function ChannelImageReview({ requests, onCancel, onApproved }: {
  requests: ImageReviewRequest[]; onCancel: () => void; onApproved: (urls: Record<string, string[]>) => void;
}) {
  const [previews, setPreviews] = useState<Preview[]>([]);
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement;
    dialogRef.current?.focus();
    return () => { if (previous instanceof HTMLElement) previous.focus(); };
  }, []);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clean, setClean] = useState(false);
  const [white, setWhite] = useState(false);
  const [loadedImages, setLoadedImages] = useState<Set<string>>(new Set());
  const [imageError, setImageError] = useState(false);
  const [cleanKey, setCleanKey] = useState("");
  const [whiteKey, setWhiteKey] = useState("");
  const previewKey = JSON.stringify(previews.map((preview) => [preview.buildId, preview.channel, preview.images.map((image) => [image.id, image.policy_version])]));
  const cleanChecked = clean && cleanKey === previewKey;
  const whiteChecked = white && whiteKey === previewKey;
  const previewsCurrent = previews.length === requests.length && previews.every((preview, index) => preview.buildId === requests[index].buildId && preview.channel === requests[index].channel && JSON.stringify(preview.urls) === JSON.stringify(requests[index].urls));
  const imageKey = (preview: Preview, image: PreviewImage, index: number) => `${preview.buildId}:${preview.channel}:${image.id}:${image.policy_version}:${index}`;
  const imagesLoaded = previews.length > 0 && previews.every((preview) => preview.images.every((image, index) => loadedImages.has(imageKey(preview, image, index))));
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const result: Preview[] = [];
        for (const request of requests) {
          const response = await fetch("/proxy-api/cross-listing/images/preview", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ build_id: request.buildId, channel: request.channel, urls: request.urls }), signal: controller.signal });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || "Could not prepare photograph previews");
          result.push({ ...request, images: data.images });
        }
        setPreviews(result);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load previews");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [requests]);
  const approve = async () => {
    if (!previewsCurrent || !imagesLoaded || imageError || !cleanChecked || (requests.some((request) => request.channel === "amazon") && !whiteChecked)) return;
    setSaving(true); setError("");
    try {
      const approved: Record<string, string[]> = {};
      for (const preview of previews) {
        const response = await fetch("/proxy-api/cross-listing/images/approve", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ build_id: preview.buildId, channel: preview.channel, urls: preview.urls, image_ids: preview.images.map((image) => image.id), policy_version: preview.images[0]?.policy_version, clean_photographs: cleanChecked, white_background: whiteChecked }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Could not approve photographs");
        approved[`${preview.buildId}:${preview.channel}`] = data.images;
      }
      onApproved(approved);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not approve photographs"); }
    finally { setSaving(false); }
  };
  const needsWhite = requests.some((request) => request.channel === "amazon");
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" role="dialog" aria-modal="true" aria-labelledby="channel-image-title">
    <div ref={dialogRef} tabIndex={-1} onKeyDown={(event) => {
      if (event.key === "Escape" && !saving) onCancel();
      if (event.key !== "Tab") return;
      const controls = dialogRef.current?.querySelectorAll<HTMLElement>("button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]");
      if (!controls?.length) return;
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }} className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl border border-slate-700 bg-slate-950 p-6">
      <h2 id="channel-image-title" className="text-xl font-semibold text-white">Review channel photographs</h2>
      <p className="mt-2 text-sm text-slate-400">Originals stay uncropped. These previews show the files each channel will receive. Promotional stickers stay separate on the website.</p>
      {loading && <p role="status" className="mt-4 text-slate-300">Preparing photographs…</p>}
      {error && <p role="alert" className="mt-4 text-red-300">{error}</p>}
      {imageError && <p role="alert" className="mt-4 text-red-300">A preview photograph could not load. Reopen the review after fixing the image link.</p>}
      {previews.map((preview) => <section key={`${preview.buildId}:${preview.channel}`} className="mt-5">
        <h3 className="font-medium text-white">{preview.title} · {preview.channel.replaceAll("_", " ")}</h3>
        <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">{preview.images.map((image, index) => <figure key={`${image.id}-${index}`}>
          <div className="relative overflow-hidden rounded bg-white" style={{ aspectRatio: `${image.width}/${image.height}` }}>
            <img src={imageSrc(image.url)} alt={`${preview.title}, ${preview.channel} photograph ${index + 1}`} className="h-full w-full object-contain" onLoad={() => setLoadedImages((current) => new Set(current).add(imageKey(preview, image, index)))} onError={() => setImageError(true)} />
            {image.square_crop_safe && <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-[12.5%] right-[12.5%] border-x-2 border-dashed border-orange-500" />}
          </div>
          <figcaption className="mt-1 text-xs text-slate-400">{image.width} × {image.height}{image.square_crop_safe && " · square crop guide"}{image.upscaled && " · low-resolution source enlarged"}</figcaption>
          <a href={imageSrc(image.url)} download={`${preview.channel}-${index + 1}.jpg`} className="mt-1 inline-block text-xs text-cyan-300 underline">Download channel photograph</a>
        </figure>)}</div>
      </section>)}
      {!loading && previews.length > 0 && <div className="mt-5 space-y-3 text-sm text-slate-200">
        <label className="flex items-start gap-2"><input type="checkbox" checked={cleanChecked} onChange={(event) => { setClean(event.target.checked); setCleanKey(previewKey); }} />I reviewed these photographs: the complete product is visible, with no added promotional text, stickers or watermarks.</label>
        {needsWhite && <label className="flex items-start gap-2"><input type="checkbox" checked={whiteChecked} onChange={(event) => { setWhite(event.target.checked); setWhiteKey(previewKey); }} />The Amazon photographs have a pure-white background around the actual product and strong product coverage. A white border around a room photograph is insufficient.</label>}
      </div>}
      <div className="mt-6 flex justify-end gap-3"><button onClick={onCancel} disabled={saving} className="rounded border border-slate-600 px-4 py-2 text-slate-200">Cancel</button>
        <button onClick={approve} disabled={loading || saving || !cleanChecked || (needsWhite && !whiteChecked) || !previewsCurrent || !imagesLoaded || imageError} className="rounded bg-emerald-400 px-4 py-2 font-medium text-slate-950 disabled:opacity-40">{saving ? "Approving…" : "Approve photographs & continue"}</button></div>
    </div>
  </div>;
}
