"use client";
/* eslint-disable @next/next/no-img-element */

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Link2, Camera, X, Upload, RefreshCw, CheckCircle, AlertCircle, Gem } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { Listing } from "@/lib/types";
import { CLASSIFICATION_CONFIG, SCORE_TIER } from "@/lib/types";
import { formatCurrency } from "@/lib/utils";

type Tab = "url" | "photo";
type State = "idle" | "loading" | "success" | "error";

function ResultCard({ listing }: { listing: Listing }) {
  const cls  = CLASSIFICATION_CONFIG[listing.classification] ?? CLASSIFICATION_CONFIG.unclassified;
  const tier = SCORE_TIER(listing.gem_score);
  const profit = listing.estimated_profit ?? 0;

  return (
    <div className="rounded-xl border border-[#1e2d45] bg-[#0d1726] overflow-hidden">
      <div className="flex gap-3 p-3">
        {/* Thumbnail */}
        <div className="w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-[#080c14]">
          {listing.image_urls?.[0] ? (
            <img src={listing.image_urls[0]} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center opacity-20">
              <Gem className="w-7 h-7 text-slate-400" />
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Title */}
          {listing.url ? (
            <a href={listing.url} target="_blank" rel="noopener noreferrer"
              className="text-sm font-semibold text-slate-100 line-clamp-2 hover:text-[#00dc82] transition-colors block">
              {listing.title}
            </a>
          ) : (
            <p className="text-sm font-semibold text-slate-100 line-clamp-2">{listing.title}</p>
          )}

          {/* Specs */}
          <div className="flex flex-wrap gap-1 mt-1.5">
            {[listing.cpu, listing.ram_gb && `${listing.ram_gb}GB`, listing.gpu].filter(Boolean).map((s, i) => (
              <span key={i} className="text-[10px] text-slate-400 bg-white/[0.05] border border-white/[0.07] rounded px-1.5 py-0.5">{s}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Financials */}
      <div className="grid grid-cols-3 divide-x divide-[#1e2d45] border-t border-[#1e2d45]">
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Buy Price</div>
          <div className="text-sm font-bold text-slate-200">{formatCurrency(listing.price)}</div>
        </div>
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Est. Resale</div>
          <div className="text-sm font-bold text-slate-200">{listing.estimated_resale ? formatCurrency(listing.estimated_resale) : "—"}</div>
        </div>
        <div className="px-3 py-2 text-center">
          <div className="text-xs text-slate-500">Est. Profit</div>
          <div className={`text-sm font-bold ${profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
            {profit > 0 ? "+" : ""}{formatCurrency(profit)}
          </div>
        </div>
      </div>

      {/* Classification + score */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-[#1e2d45]">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${cls.bg} ${cls.color}`}>
          {cls.emoji} {cls.label}
        </span>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${tier.bg} ${tier.color}`}>
          {tier.label} — {listing.gem_score.toFixed(0)}
        </span>
        {listing.gem_signals?.length > 0 && (
          <span className="text-[10px] text-slate-500 ml-auto">
            {listing.gem_signals.slice(0, 3).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}


interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess?: (listing: Listing) => void;
}

export function ManualSubmitModal({ open, onClose, onSuccess }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("url");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string>("");
  const [result, setResult] = useState<Listing | null>(null);

  // URL tab
  const [url, setUrl] = useState("");
  const [priceOverride, setPriceOverride] = useState("");

  // Photo tab
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [photoTitle, setPhotoTitle] = useState("");
  const [photoPrice, setPhotoPrice] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = useCallback(() => {
    setState("idle");
    setError("");
    setResult(null);
    setUrl("");
    setPriceOverride("");
    setImageFile(null);
    setImagePreview("");
    setPhotoTitle("");
    setPhotoPrice("");
  }, []);

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleImageFile = (file: File) => {
    if (!file.type.startsWith("image/")) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = e => setImagePreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleImageFile(file);
  }, []);

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) handleImageFile(file);
        break;
      }
    }
  }, []);

  const submitUrl = async () => {
    if (!url.trim()) return;
    setState("loading");
    setError("");
    try {
      const override = priceOverride ? parseFloat(priceOverride) : undefined;
      const listing = await api.manual.submitUrl(url.trim(), override);
      setResult(listing);
      setState("success");
      onSuccess?.(listing);
    } catch (e: unknown) {
      setState("error");
      setError(e instanceof Error ? e.message : "Submission failed");
    }
  };

  const submitImage = async () => {
    if (!imageFile) return;
    if (!photoPrice && !imageFile) return;
    setState("loading");
    setError("");
    try {
      const price = photoPrice ? parseFloat(photoPrice) : undefined;
      const listing = await api.manual.submitImage(imageFile, photoTitle || undefined, price);
      setResult(listing);
      setState("success");
      onSuccess?.(listing);
    } catch (e: unknown) {
      setState("error");
      setError(e instanceof Error ? e.message : "Submission failed");
    }
  };

  const goToOpportunities = () => {
    handleClose();
    router.push("/opportunities");
  };

  const goToBuildWizard = () => {
    if (!result) return;
    handleClose();
    router.push(`/chat?listing_id=${result.id}`);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onPaste={handlePaste}>
      <div className="w-full max-w-lg bg-[#0d1726] border border-[#1e2d45] rounded-2xl shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e2d45]">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Submit a Listing</h2>
            <p className="text-xs text-slate-500 mt-0.5">URL or photo → full pipeline analysis in seconds</p>
          </div>
          <button onClick={handleClose} className="text-slate-500 hover:text-slate-200 p-1 rounded-lg hover:bg-white/5 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-3 pb-0">
          {([
            { key: "url" as Tab,   label: "Paste a URL",  Icon: Link2   },
            { key: "photo" as Tab, label: "Upload Photo", Icon: Camera  },
          ] as const).map(({ key, label, Icon }) => (
            <button key={key} onClick={() => { setTab(key); setError(""); }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === key
                  ? "bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20"
                  : "text-slate-500 hover:text-slate-300 border border-transparent"
              }`}>
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-5 space-y-4">

          {/* ── URL tab ── */}
          {tab === "url" && state !== "success" && (
            <>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Listing URL</label>
                <input
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && submitUrl()}
                  placeholder="https://www.ebay.co.uk/itm/... or gumtree.com/..."
                  disabled={state === "loading"}
                  className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                />
                <p className="text-[10px] text-slate-600 mt-1">
                  Supports eBay, Gumtree, Preloved, Facebook Marketplace, and most listing sites.
                </p>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">
                  Price override <span className="text-slate-600">(optional — leave blank to auto-detect)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">£</span>
                  <input
                    type="number"
                    value={priceOverride}
                    onChange={e => setPriceOverride(e.target.value)}
                    placeholder="e.g. 149"
                    disabled={state === "loading"}
                    className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg pl-7 pr-3 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50"
                  />
                </div>
              </div>
            </>
          )}

          {/* ── Photo tab ── */}
          {tab === "photo" && state !== "success" && (
            <>
              {/* Drop zone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className={`relative rounded-xl border-2 border-dashed cursor-pointer transition-colors ${
                  dragging ? "border-[#00dc82] bg-[#00dc82]/5" :
                  imagePreview ? "border-[#1e2d45]" : "border-[#1e2d45] hover:border-[#2a3d5c]"
                }`}
              >
                {imagePreview ? (
                  <div className="relative">
                    <img src={imagePreview} alt="Preview" className="w-full max-h-52 object-contain rounded-xl" />
                    <button
                      onClick={e => { e.stopPropagation(); setImageFile(null); setImagePreview(""); }}
                      className="absolute top-2 right-2 bg-black/60 rounded-full p-1 text-white hover:bg-black/80 transition-colors">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-10 gap-2 text-slate-500">
                    <Upload className="w-8 h-8 opacity-40" />
                    <p className="text-sm">Drop photo here, click to browse, or <kbd className="text-xs bg-white/10 px-1 rounded">Ctrl+V</kbd> to paste</p>
                    <p className="text-xs text-slate-600">JPEG, PNG, WebP — max 15 MB</p>
                  </div>
                )}
                <input ref={fileRef} type="file" accept="image/*" className="hidden"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleImageFile(f); }} />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">Title / description <span className="text-slate-600">(optional)</span></label>
                  <input value={photoTitle} onChange={e => setPhotoTitle(e.target.value)}
                    placeholder="e.g. Dell OptiPlex i7 no GPU"
                    disabled={state === "loading"}
                    className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50" />
                </div>
                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">Price <span className="text-[#00dc82]">*</span></label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">£</span>
                    <input type="number" value={photoPrice} onChange={e => setPhotoPrice(e.target.value)}
                      placeholder="e.g. 80"
                      disabled={state === "loading"}
                      className="w-full bg-[#111c2e] border border-[#1e2d45] rounded-lg pl-7 pr-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-[#00dc82]/50 focus:outline-none disabled:opacity-50" />
                  </div>
                </div>
              </div>
              {!photoPrice && (
                <p className="text-[10px] text-amber-400/70">
                  ⚠ Price is required for photo submissions (AI may not be able to read it from the image).
                </p>
              )}
            </>
          )}

          {/* ── Result ── */}
          {state === "success" && result && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-[#00dc82]">
                <CheckCircle className="w-4 h-4" />
                Listing analysed and added to your database
              </div>
              <ResultCard listing={result} />
            </div>
          )}

          {/* ── Error ── */}
          {state === "error" && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-400">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Submission failed</p>
                <p className="text-xs mt-0.5 text-red-400/70">{error}</p>
              </div>
            </div>
          )}

          {/* Loading indicator */}
          {state === "loading" && (
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[#111c2e] border border-[#1e2d45] text-sm text-slate-400">
              <RefreshCw className="w-4 h-4 animate-spin text-[#00dc82]" />
              <span>
                {tab === "url" ? "Fetching page & running pipeline…" : "Analysing photo with AI vision…"}
              </span>
              <span className="text-xs text-slate-600 ml-auto">up to 30s</span>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="flex items-center gap-2 px-5 py-4 border-t border-[#1e2d45]">
          {state === "success" ? (
            <>
              <Button variant="ghost" onClick={reset} className="text-slate-400">Submit another</Button>
              <Button
                variant="ghost"
                onClick={goToBuildWizard}
                className="text-[#00dc82] border border-[#00dc82]/30 hover:bg-[#00dc82]/10"
              >
                Build system from this →
              </Button>
              <Button onClick={goToOpportunities}
                className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold">
                View in Opportunities →
              </Button>
            </>
          ) : state === "error" ? (
            <>
              <Button variant="ghost" onClick={() => setState("idle")} className="text-slate-400">Try again</Button>
              <Button variant="ghost" onClick={handleClose} className="ml-auto text-slate-400">Close</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={handleClose} className="text-slate-400" disabled={state === "loading"}>Cancel</Button>
              {tab === "url" ? (
                <Button onClick={submitUrl}
                  disabled={state === "loading" || !url.trim()}
                  className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold">
                  {state === "loading" ? <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
                  Analyse URL
                </Button>
              ) : (
                <Button onClick={submitImage}
                  disabled={state === "loading" || !imageFile || !photoPrice}
                  className="ml-auto bg-[#00dc82] text-black hover:bg-[#00dc82]/90 font-semibold">
                  {state === "loading" ? <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> : null}
                  Analyse Photo
                </Button>
              )}
            </>
          )}
        </div>

      </div>
    </div>
  );
}
