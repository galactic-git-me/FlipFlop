"use client";

import { Upload, Box, Loader2 } from "lucide-react";
import { useMemo, useRef, useState } from "react";

export type Catalogue3DItem = {
  id: number;
  title: string;
  slot_type: string;
};

export type Shared3DAsset = {
  id: number;
  subject_type: string;
  subject_id: number | null;
  status: string;
  version?: number;
  category?: string | null;
  preview_image_ref?: string | null;
  glb_ref?: string | null;
  review_decision?: string | null;
};

type Props = {
  items: Catalogue3DItem[];
  assets: Shared3DAsset[];
  onUploaded: (asset: Shared3DAsset) => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
};

export default function Shared3DAssetGrid({ items, assets, onUploaded, onMessage, onError }: Props) {
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const inputRefs = useRef(new Map<number, HTMLInputElement>());
  const latestByVariant = useMemo(() => {
    const result = new Map<number, Shared3DAsset>();
    for (const asset of assets) {
      if (asset.subject_id == null) continue;
      const current = result.get(asset.subject_id);
      if (!current || (asset.version ?? 0) > (current.version ?? 0)) result.set(asset.subject_id, asset);
    }
    return result;
  }, [assets]);

  const upload = async (item: Catalogue3DItem, file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".glb")) {
      onError("Choose a self-contained .glb file");
      return;
    }
    setUploadingId(item.id); onError(""); onMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`/api/assets-3d/variants/${item.id}/upload-glb`, { method: "POST", body: form });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.error || "GLB upload failed");
      onUploaded(payload);
      onMessage(`${item.title} uploaded to the shared 3D asset library. Validate it before activation.`);
    } catch (error) {
      onError(error instanceof Error ? error.message : "GLB upload failed");
    } finally {
      setUploadingId(null);
      const input = inputRefs.current.get(item.id);
      if (input) input.value = "";
    }
  };

  if (items.length === 0) return <div className="rounded-xl border border-dashed border-white/10 bg-white/[.02] px-6 py-12 text-center"><Box className="mx-auto h-8 w-8 text-slate-600"/><p className="mt-3 font-semibold text-slate-300">No catalogue components selected</p><p className="mt-1 text-sm text-slate-500">Add products to this catalogue to create its shared 3D asset queue.</p></div>;

  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{items.map(item => {
    const asset = latestByVariant.get(item.id);
    const ready = Boolean(asset?.glb_ref);
    return <article key={item.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#101924]">
      {asset?.preview_image_ref ? <img src={asset.preview_image_ref} alt="Asset preview" className="h-40 w-full bg-black/20 object-contain"/> : <div className="flex h-40 items-center justify-center bg-white/[.02]"><Box className="h-9 w-9 text-slate-700"/></div>}
      <div className="p-3">
        <p className="line-clamp-2 text-sm font-medium">{item.title}</p>
        <p className="mt-1 text-xs text-slate-400">{item.slot_type} · {asset ? asset.status.replaceAll("_", " ") : "missing"} · {ready ? "model uploaded" : "model needed"}</p>
        {asset?.review_decision && <p className="mt-2 text-xs text-emerald-300">Decision: {asset.review_decision}</p>}
        <input ref={node => { if (node) inputRefs.current.set(item.id, node); else inputRefs.current.delete(item.id); }} className="sr-only" type="file" accept=".glb,model/gltf-binary" onChange={event => void upload(item, event.target.files?.[0])}/>
        <button type="button" disabled={uploadingId !== null} onClick={() => inputRefs.current.get(item.id)?.click()} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/15 disabled:cursor-not-allowed disabled:opacity-50">
          {uploadingId === item.id ? <Loader2 className="h-4 w-4 animate-spin"/> : <Upload className="h-4 w-4"/>}{ready ? "Upload new GLB version" : "Upload GLB"}
        </button>
      </div>
    </article>;
  })}</div>;
}
