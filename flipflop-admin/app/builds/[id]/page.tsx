"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, CheckCircle2, Circle, Hammer, Sparkles, ExternalLink,
  Loader2, ShoppingBag, ImagePlus, Star, X, IdCard, BadgeCheck, Store, Download, Zap,
} from "lucide-react";
import JSZip from "jszip";
import { api, ManualBuild, BuildComponent } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { drawRegistrationPlate, drawSpecCard, canvasToBlob, loadLogo } from "@/lib/build-cards";
import { EbayOffersSection } from "@/components/builds/EbayOffersSection";
import { EbayShippingSection } from "@/components/builds/EbayShippingSection";
import { EbayShipmentBookingSection } from "@/components/builds/EbayShipmentBookingSection";
import { EbaySpecificsSection } from "@/components/builds/EbaySpecificsSection";
import { DescriptionPreview } from "@/components/builds/DescriptionPreview";
import { PricingBreakdown } from "@/components/builds/PricingBreakdown";

// eBay-required Item Specifics for "PC Desktops & All-in-Ones" — mirrors
// EbaySpecificsSection.tsx's own EBAY_ASPECT_FIELDS list (that component owns
// the full field list; this page only needs to know which are required).
const EBAY_REQUIRED_ASPECTS = new Set(["Brand", "Type"]);

const STATUS_LABEL: Record<string, string> = {
  in_progress: "In Progress",
  built: "Built",
  listed: "Listed",
  sold: "Sold",
};

const STATUS_COLOR: Record<string, string> = {
  in_progress: "text-amber-400 border-amber-400/30 bg-amber-400/5",
  built: "text-cyan-400 border-cyan-400/30 bg-cyan-400/5",
  listed: "text-[#00dc82] border-[#00dc82]/30 bg-[#00dc82]/5",
  sold: "text-slate-400 border-slate-400/30 bg-slate-400/5",
};

// eBay's Inventory API condition values actually accepted for the "PC
// Desktops & All-in-Ones" category (179) — confirmed via the Metadata API's
// item condition policy. This category doesn't support the graded
// USED_GOOD/USED_VERY_GOOD/etc values other categories allow.
const EBAY_CONDITIONS: { value: string; label: string }[] = [
  { value: "NEW", label: "New" },
  { value: "NEW_OTHER", label: "Opened — never used" },
  { value: "SELLER_REFURBISHED", label: "Seller Refurbished" },
  { value: "USED_EXCELLENT", label: "Used" },
  { value: "FOR_PARTS_OR_NOT_WORKING", label: "For Parts / Not Working" },
];

export default function BuildDetailPage() {
  const params = useParams();
  const router = useRouter();
  const buildId = Number(params.id);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const performanceCardInputRef = useRef<HTMLInputElement>(null);
  const hiddenCanvasRef = useRef<HTMLCanvasElement>(null);

  const [build, setBuild] = useState<ManualBuild | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSlot, setSavingSlot] = useState<string | null>(null);
  const [markingBuilt, setMarkingBuilt] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [posting, setPosting] = useState(false);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [savingAspects, setSavingAspects] = useState(false);
  const [generatingSpecifics, setGeneratingSpecifics] = useState(false);
  const [savingEbayConfig, setSavingEbayConfig] = useState(false);
  const [generatingCard, setGeneratingCard] = useState<"spec_card" | "registration_plate" | null>(null);
  const [listingOnStorefront, setListingOnStorefront] = useState(false);
  const [draggedUrl, setDraggedUrl] = useState<string | null>(null);
  const [dragOverUrl, setDragOverUrl] = useState<string | null>(null);

  const [price, setPrice] = useState("");
  const [condition, setCondition] = useState("USED_EXCELLENT");
  const [performanceCardGenerated, setPerformanceCardGenerated] = useState(false);
  const [performanceCardImageUrls, setPerformanceCardImageUrls] = useState<string[]>([]);
  const [performanceCardZipUrl, setPerformanceCardZipUrl] = useState<string | null>(null);

  useEffect(() => {
    api.manualBuilds
      .get(buildId)
      .then((b) => {
        setBuild(b);
        if (b.last_evaluation?.mid) setPrice(String(Math.round(b.last_evaluation.mid)));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [buildId]);

  const togglePurchased = async (slot: string) => {
    if (!build) return;
    setSavingSlot(slot);
    const updated: BuildComponent[] = build.components.map((c) =>
      c.slot === slot ? { ...c, purchased: !c.purchased } : c
    );
    try {
      const saved = await api.manualBuilds.patch(buildId, { components: updated });
      setBuild(saved);
    } catch (error) {
      console.error("Error updating component:", error);
      alert("Failed to save. Please check the console for details.");
    } finally {
      setSavingSlot(null);
    }
  };

  const markBuilt = async () => {
    setMarkingBuilt(true);
    try {
      const saved = await api.manualBuilds.markBuilt(buildId);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't mark this build as built: ${msg}`);
    } finally {
      setMarkingBuilt(false);
    }
  };


  const generateListing = async () => {
    setGenerating(true);
    try {
      const result = await api.manualBuilds.generateListing(buildId);
      setBuild((prev) =>
        prev
          ? {
              ...prev,
              generated_title: result.titles[0] ?? prev.generated_title,
              generated_description: result.description,
              generated_aspects: result.aspects,
            }
          : prev
      );
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't generate the listing: ${msg}`);
    } finally {
      setGenerating(false);
    }
  };

  const saveAspects = async (aspects: Record<string, string[]>) => {
    setSavingAspects(true);
    try {
      const saved = await api.manualBuilds.updateAspects(buildId, aspects);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't save specifics: ${msg}`);
    } finally {
      setSavingAspects(false);
    }
  };

  const generateSpecifics = async () => {
    setGeneratingSpecifics(true);
    try {
      const result = await api.manualBuilds.generateSpecifics(buildId);
      setBuild((prev) =>
        prev
          ? {
              ...prev,
              generated_aspects: result.aspects,
            }
          : prev
      );
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't generate item specifics: ${msg}`);
    } finally {
      setGeneratingSpecifics(false);
    }
  };

  const updateEbayConfig = async (config: Partial<ManualBuild>) => {
    setSavingEbayConfig(true);
    try {
      const saved = await api.manualBuilds.updateEbayConfig(buildId, config);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't save eBay configuration: ${msg}`);
    } finally {
      setSavingEbayConfig(false);
    }
  };

  // Re-fetches the full build — used by actions whose endpoints return a
  // narrower shape than ManualBuild (e.g. sync-ebay-order, book-shipment)
  // rather than the updated build itself.
  const refreshBuild = async () => {
    const fresh = await api.manualBuilds.get(buildId);
    setBuild(fresh);
  };

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setUploadingPhotos(true);
    try {
      const saved = await api.manualBuilds.uploadPhotos(buildId, files);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't upload photos: ${msg}`);
    } finally {
      setUploadingPhotos(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const setHero = async (url: string) => {
    try {
      const saved = await api.manualBuilds.setHeroPhoto(buildId, url);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't set hero photo: ${msg}`);
    }
  };

  const reorderPhotos = async (draggedUrl: string, targetUrl: string) => {
    if (!build || draggedUrl === targetUrl) return;
    const photoUrls = build.photos.filter((p) => p.kind === "photo").map((p) => p.url);
    const from = photoUrls.indexOf(draggedUrl);
    const to = photoUrls.indexOf(targetUrl);
    if (from === -1 || to === -1) return;

    const reordered = [...photoUrls];
    reordered.splice(from, 1);
    reordered.splice(to, 0, draggedUrl);

    // Optimistic local reorder — non-"photo" entries (branded cards) are untouched.
    const otherPhotos = build.photos.filter((p) => p.kind !== "photo");
    const byUrl = new Map(build.photos.map((p) => [p.url, p]));
    setBuild({ ...build, photos: [...reordered.map((u) => byUrl.get(u)!), ...otherPhotos] });

    try {
      const saved = await api.manualBuilds.reorderPhotos(buildId, reordered);
      setBuild(saved);
    } catch (error) {
      console.error("Error reordering photos:", error);
      const fresh = await api.manualBuilds.get(buildId);
      setBuild(fresh);
    }
  };

  const removePhoto = async (url: string) => {
    try {
      const saved = await api.manualBuilds.removePhoto(buildId, url);
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't remove photo: ${msg}`);
    }
  };

  const generateBrandedCard = useCallback(
    async (kind: "spec_card" | "registration_plate", currentBuild: ManualBuild) => {
      if (!hiddenCanvasRef.current) return;
      setGeneratingCard(kind);
      try {
        const logo = await loadLogo();
        if (kind === "spec_card") await drawSpecCard(hiddenCanvasRef.current, currentBuild, logo);
        else await drawRegistrationPlate(hiddenCanvasRef.current, currentBuild, logo);
        const blob = await canvasToBlob(hiddenCanvasRef.current);
        const saved = await api.manualBuilds.uploadBrandedAsset(buildId, kind, blob);
        setBuild(saved);
        return saved;
      } catch (error) {
        const msg = error instanceof Error ? error.message : "Unknown error";
        alert(`Couldn't generate the ${kind === "spec_card" ? "spec card" : "registration plate"}: ${msg}`);
        return currentBuild;
      } finally {
        setGeneratingCard(null);
      }
    },
    [buildId]
  );

  // Auto-generate both branded cards the moment listing content exists —
  // no manual "Generate" click needed. Runs the two draws sequentially
  // since they share the same offscreen canvas element.
  const autoGenAttempted = useRef(false);
  useEffect(() => {
    if (!build?.generated_title || autoGenAttempted.current) return;
    const hasSpecCard = build.photos.some((p) => p.kind === "spec_card");
    const hasPlate = build.photos.some((p) => p.kind === "registration_plate");
    if (hasSpecCard && hasPlate) return;
    autoGenAttempted.current = true;

    (async () => {
      let current = build;
      if (!hasSpecCard) current = (await generateBrandedCard("spec_card", current)) ?? current;
      if (!hasPlate) current = (await generateBrandedCard("registration_plate", current)) ?? current;
    })();
  }, [build, generateBrandedCard]);

  const postToEbay = async () => {
    if (!build?.generated_title || !build?.generated_description) return;
    const priceNum = parseFloat(price);
    if (!priceNum || priceNum <= 0) {
      alert("Enter an asking price before listing.");
      return;
    }

    setPosting(true);
    try {
      const result = await api.manualBuilds.postToEbay(buildId, { price: priceNum, condition });
      if (result.success) {
        const refreshed = await api.manualBuilds.get(buildId);
        setBuild(refreshed);
      } else {
        alert(`eBay rejected the listing: ${result.error ?? "Unknown error"}`);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't post to eBay: ${msg}`);
    } finally {
      setPosting(false);
    }
  };

  const listOnStorefront = async () => {
    const priceNum = parseFloat(price);
    if (!priceNum || priceNum <= 0) {
      alert("Enter an asking price before listing.");
      return;
    }
    setListingOnStorefront(true);
    try {
      await api.manualBuilds.listOnStorefront(buildId, priceNum);
      const refreshed = await api.manualBuilds.get(buildId);
      setBuild(refreshed);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't list on FlipFlop.shop: ${msg}`);
    } finally {
      setListingOnStorefront(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Loading…</div>
    );
  }

  if (!build) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm">Build not found.</div>
    );
  }

  const purchasedCount = build.components.filter((c) => c.purchased).length;
  const totalCount = build.components.length;
  const allPurchased = totalCount > 0 && purchasedCount === totalCount;
  const canMarkBuilt = allPurchased && build.status === "in_progress";
  const canSell = build.status === "built" || build.status === "listed" || build.status === "sold";
  const hasRequiredAspects = [...EBAY_REQUIRED_ASPECTS].every((name) => !!build.generated_aspects?.[name]?.length);
  const canPublish = canSell && !!build.hero_photo_url && !!build.generated_title && !!build.generated_description && hasRequiredAspects;
  const regularPhotos = build.photos.filter((p) => p.kind === "photo");
  const specCard = build.photos.find((p) => p.kind === "spec_card");
  const registrationPlate = build.photos.find((p) => p.kind === "registration_plate");

  return (
    <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8 max-w-3xl mx-auto">
      {/* offscreen canvas used to render branded cards before uploading them */}
      <canvas ref={hiddenCanvasRef} className="hidden" />

      <button
        onClick={() => router.push("/builds")}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Your Builds
      </button>

      <div className="flex items-center justify-between mb-3">
        <h1 className="text-xl font-black">{build.name}</h1>
        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-bold uppercase tracking-wider ${STATUS_COLOR[build.status]}`}>
          {STATUS_LABEL[build.status]}
        </div>
      </div>

      {/* Channel status — where this build is actually purchasable right now */}
      <div className="flex items-center gap-2 mb-6">
        <ChannelBadge label="eBay" icon={ShoppingBag} live={!!build.ebay_live} />
        <ChannelBadge label="FlipFlop.shop" icon={Store} live={!!build.storefront_live} />
      </div>

      {/* Purchase checklist */}
      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 mb-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold flex items-center gap-2">
            <ShoppingBag className="w-4 h-4 text-slate-500" /> Components purchased
          </p>
          <p className="text-xs text-slate-500 font-mono">{purchasedCount}/{totalCount}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          {build.components.map((c) => (
            <button
              key={c.slot}
              onClick={() => togglePurchased(c.slot)}
              disabled={savingSlot === c.slot || build.status !== "in_progress"}
              className="w-full flex items-center gap-3 p-2.5 rounded-lg hover:bg-white/[0.03] transition-colors text-left disabled:opacity-60 disabled:cursor-default"
            >
              {savingSlot === c.slot ? (
                <Loader2 className="w-4 h-4 text-slate-500 animate-spin shrink-0" />
              ) : c.purchased ? (
                <CheckCircle2 className="w-4 h-4 text-[#00dc82] shrink-0" />
              ) : (
                <Circle className="w-4 h-4 text-slate-600 shrink-0" />
              )}
              <span className="text-xs text-slate-500 uppercase font-mono w-24 shrink-0">{c.slot}</span>
              <span className="text-sm flex-1 truncate">{c.name}</span>
              <span className="text-sm font-semibold text-slate-400">{formatCurrency(c.price_paid)}</span>
            </button>
          ))}
        </div>

        {build.status === "in_progress" && (
          <button
            onClick={markBuilt}
            disabled={!canMarkBuilt || markingBuilt}
            className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-600 text-black rounded-lg transition-colors"
          >
            {markingBuilt ? <Loader2 className="w-4 h-4 animate-spin" /> : <Hammer className="w-4 h-4" />}
            {allPurchased ? "Mark as Built" : `Waiting on ${totalCount - purchasedCount} component${totalCount - purchasedCount === 1 ? "" : "s"}`}
          </button>
        )}
      </div>

      {canSell && (
        <>
          {/* Photos */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 mb-6">
            <p className="text-sm font-semibold flex items-center gap-2 mb-3">
              <ImagePlus className="w-4 h-4 text-slate-500" /> Photos
            </p>

            {regularPhotos.length > 0 && (
              <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 mb-3">
                {regularPhotos.map((p, photoIdx) => (
                  <div
                    key={p.url}
                    draggable
                    onDragStart={() => setDraggedUrl(p.url)}
                    onDragEnter={() => setDragOverUrl(p.url)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (draggedUrl) reorderPhotos(draggedUrl, p.url);
                      setDraggedUrl(null);
                      setDragOverUrl(null);
                    }}
                    onDragEnd={() => {
                      setDraggedUrl(null);
                      setDragOverUrl(null);
                    }}
                    className={`relative group aspect-square rounded-lg overflow-hidden bg-slate-800 border cursor-grab active:cursor-grabbing transition-colors ${
                      dragOverUrl === p.url && draggedUrl !== p.url ? "border-cyan-400" : "border-white/[0.07]"
                    } ${draggedUrl === p.url ? "opacity-40" : ""}`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={p.url}
                      alt={`${build.name} photo ${photoIdx + 1}`}
                      className="w-full h-full object-cover pointer-events-none"
                      draggable={false}
                    />
                    <button
                      onClick={() => setHero(p.url)}
                      title={build.hero_photo_url === p.url ? "Hero photo" : "Set as hero photo"}
                      aria-label={build.hero_photo_url === p.url ? "Hero photo" : "Set as hero photo"}
                      className={`absolute top-1 left-1 p-1 rounded-md ${build.hero_photo_url === p.url ? "bg-[#00dc82] text-black" : "bg-black/60 text-slate-300 opacity-0 group-hover:opacity-100"} transition-opacity`}
                    >
                      <Star className="w-3.5 h-3.5" fill={build.hero_photo_url === p.url ? "currentColor" : "none"} />
                    </button>
                    <button
                      onClick={() => removePhoto(p.url)}
                      title="Remove photo"
                      aria-label="Remove photo"
                      className="absolute top-1 right-1 p-1 rounded-md bg-black/60 text-slate-300 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            {regularPhotos.length > 1 && (
              <p className="text-[11px] text-slate-500 mb-3">Drag a photo onto another to reorder them.</p>
            )}

            <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={handlePhotoUpload} className="hidden" />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingPhotos}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold border border-dashed border-white/[0.15] hover:border-white/[0.3] text-slate-300 rounded-lg transition-colors disabled:opacity-60"
            >
              {uploadingPhotos ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
              Upload photos
            </button>
            {regularPhotos.length > 0 && !build.hero_photo_url && (
              <p className="text-[11px] text-amber-400 mt-2">Click the star on a photo to set it as the hero image.</p>
            )}
          </div>

          {/* Sell flow */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-4 mb-6">
            <p className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-slate-500" /> Sell this build
            </p>

            {!build.generated_title ? (
              <button
                onClick={generateListing}
                disabled={generating}
                className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-black rounded-lg transition-colors"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Generate Title &amp; Description
              </button>
            ) : (
              <div className="flex flex-col gap-3">
                <div>
                  <label className="text-xs text-slate-500 uppercase font-mono">Title</label>
                  <p className="text-sm font-semibold mt-1">{build.generated_title}</p>
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase font-mono mb-2 block">Description Preview</label>
                  <DescriptionPreview html={build.generated_description} />
                </div>
                <button
                  onClick={generateListing}
                  disabled={generating}
                  className="self-start text-xs text-slate-500 hover:text-slate-300 underline decoration-dotted"
                >
                  {generating ? "Regenerating…" : "Regenerate"}
                </button>
              </div>
            )}

            {build.generated_title && (
              <div>
                <label className="text-xs text-slate-500 uppercase font-mono">Asking price (£)</label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className="w-full mt-1 bg-black/30 border border-white/[0.1] rounded-lg px-3 py-2 text-sm text-slate-100"
                  placeholder="e.g. 450"
                />
              </div>
            )}
          </div>

          {/* Pricing Breakdown with Sold Data — cost/delivery figures come from
              the backend (build.total_cost / build.shipping_cost on the
              persisted record), not recomputed client-side; see
              app/api/builds_pricing.py's PricingBreakdown response. */}
          {build && build.generated_title && (
            <PricingBreakdown
              buildId={String(buildId)}
              onPricingUpdate={(newPrice) => setPrice(String(Math.round(newPrice)))}
            />
          )}

          {/* Item Specifics - NEW COMPONENT */}
          {build.generated_title && (
            <>
              <EbaySpecificsSection
                build={build}
                onGenerateSpecifics={generateSpecifics}
                onUpdateAspects={saveAspects}
                generating={generatingSpecifics}
                saving={savingAspects}
              />

              {/* Offers Configuration */}
              <EbayOffersSection
                build={build}
                onUpdate={updateEbayConfig}
                saving={savingEbayConfig}
              />

              {/* Shipping Configuration */}
              <EbayShippingSection
                build={build}
                onUpdate={updateEbayConfig}
                saving={savingEbayConfig}
                askingPrice={parseFloat(price) || 0}
                onAskingPriceUpdate={(newPrice) => setPrice(String(Math.round(newPrice)))}
              />

              {/* Real post-sale shipment: buyer address sync + courier booking */}
              <EbayShipmentBookingSection build={build} onRefresh={refreshBuild} />
            </>
          )}

          {/* Branded cards */}
          {build.generated_title && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3 mb-6">
              <p className="text-sm font-semibold flex items-center gap-2">
                <IdCard className="w-4 h-4 text-slate-500" /> Branded cards
              </p>
              <p className="text-[11px] text-slate-500 -mt-2">
                Generated from this build&apos;s actual components — accompany the eBay listing and storefront page with these.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <BrandedCardTile
                  label="Spec Card"
                  photo={specCard}
                  loading={generatingCard === "spec_card"}
                  onGenerate={() => generateBrandedCard("spec_card", build)}
                />
                <BrandedCardTile
                  label="Registration Plate"
                  photo={registrationPlate}
                  loading={generatingCard === "registration_plate"}
                  onGenerate={() => generateBrandedCard("registration_plate", build)}
                />
              </div>
            </div>
          )}

          {/* Performance Card */}
          {build.generated_title && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3 mb-6">
              <p className="text-sm font-semibold flex items-center gap-2">
                <Zap className="w-4 h-4 text-slate-500" /> Performance Card
              </p>
              <p className="text-[11px] text-slate-500 -mt-2">
                Create a branded benchmark report card with real performance stats from this build.
              </p>

              <div className="flex items-center gap-3">
                <input
                  ref={performanceCardInputRef}
                  type="file"
                  accept=".json"
                  onChange={async (e) => {
                    const file = e.currentTarget.files?.[0];
                    if (!file) return;

                    setGenerating(true);
                    try {
                      const formData = new FormData();
                      formData.append("file", file);

                      const response = await fetch("/api/performance-card/render", {
                        method: "POST",
                        body: formData,
                      });

                      const contentType = response.headers.get("content-type");

                      if (contentType?.includes("application/json")) {
                        const data = await response.json();
                        if (data.success) {
                          alert(`Performance card data saved!\n\n${data.message}`);
                          setPerformanceCardGenerated(false);
                        } else {
                          throw new Error(data.error || "Failed to process");
                        }
                      } else if (response.ok && contentType?.includes("zip")) {
                        const zipBlob = await response.blob();
                        const zip = await JSZip.loadAsync(zipBlob);
                        const partNames = Object.keys(zip.files).sort();
                        const urls = await Promise.all(
                          partNames.map(async (name) => {
                            const partBlob = await zip.files[name].async("blob");
                            return URL.createObjectURL(partBlob);
                          })
                        );
                        setPerformanceCardImageUrls(urls);
                        setPerformanceCardZipUrl(URL.createObjectURL(zipBlob));
                        setPerformanceCardGenerated(true);
                      } else {
                        throw new Error(`Failed to render performance card: ${response.statusText}`);
                      }

                      performanceCardInputRef.current!.value = "";
                    } catch (error) {
                      const msg = error instanceof Error ? error.message : "Unknown error";
                      alert(`Error rendering performance card: ${msg}`);
                    } finally {
                      setGenerating(false);
                    }
                  }}
                  className="hidden"
                />
                <button
                  onClick={() => performanceCardInputRef.current?.click()}
                  disabled={generating}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 text-purple-300 rounded-lg transition-colors disabled:opacity-50"
                >
                  {generating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Rendering...
                    </>
                  ) : (
                    <>
                      <Download className="w-4 h-4" /> Upload performance-data.json
                    </>
                  )}
                </button>
              </div>

              {performanceCardGenerated && performanceCardImageUrls.length > 0 && (
                <div className="mt-4 flex flex-col gap-3">
                  <p className="text-xs text-slate-500">
                    Performance Card — split into {performanceCardImageUrls.length} sections so each one displays properly instead of one tall, skewed image.
                  </p>
                  <div className="grid grid-cols-3 gap-2">
                    {performanceCardImageUrls.map((url, i) => (
                      <img
                        key={url}
                        src={url}
                        alt={`Performance Card part ${i + 1}`}
                        className="w-full rounded-lg border border-white/[0.1] bg-black"
                      />
                    ))}
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={async () => {
                        setUploadingPhotos(true);
                        try {
                          const files = await Promise.all(
                            performanceCardImageUrls.map(async (url, i) => {
                              const blob = await fetch(url).then((r) => r.blob());
                              return new File([blob], `performance-card-part-${i + 1}.png`, { type: "image/png" });
                            })
                          );
                          const saved = await api.manualBuilds.uploadPhotos(buildId, files);
                          setBuild(saved);
                        } catch (error) {
                          const msg = error instanceof Error ? error.message : "Unknown error";
                          alert(`Couldn't add performance card photos: ${msg}`);
                        } finally {
                          setUploadingPhotos(false);
                        }
                      }}
                      disabled={uploadingPhotos}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/30 text-purple-300 rounded transition-colors disabled:opacity-50"
                    >
                      {uploadingPhotos ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
                      Add to Listing Photos
                    </button>
                    <button
                      onClick={() => {
                        if (!performanceCardZipUrl) return;
                        const link = document.createElement("a");
                        link.href = performanceCardZipUrl;
                        link.download = `performance-card-${build?.id || "unknown"}.zip`;
                        link.click();
                      }}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs font-semibold bg-green-500/20 hover:bg-green-500/30 border border-green-500/30 text-green-300 rounded transition-colors"
                    >
                      <Download className="w-4 h-4" /> Download Zip
                    </button>
                    <button
                      onClick={() => setPerformanceCardGenerated(false)}
                      className="flex-1 text-xs text-slate-500 hover:text-slate-300 border border-white/[0.1] rounded px-3 py-2 transition-colors"
                    >
                      Hide
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* eBay */}
          {build.generated_title && build.status !== "sold" && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3 mb-6">
              <p className="text-sm font-semibold flex items-center gap-2">
                <BadgeCheck className="w-4 h-4 text-slate-500" /> List on eBay
              </p>
              {build.status === "listed" && build.ebay_listing_url ? (
                <a
                  href={build.ebay_listing_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-[#00dc82]/15 border border-[#00dc82]/30 text-[#00dc82] rounded-lg"
                >
                  <ExternalLink className="w-4 h-4" /> View live eBay listing
                </a>
              ) : (
                <div className="flex flex-col gap-3">
                  {!build.hero_photo_url && (
                    <p className="text-[11px] text-amber-400">Upload at least one photo and choose a hero image first.</p>
                  )}
                  <div>
                    <label className="text-xs text-slate-500 uppercase font-mono">Condition</label>
                    <select
                      value={condition}
                      onChange={(e) => setCondition(e.target.value)}
                      className="mt-1 w-full bg-black/30 border border-white/[0.1] rounded-lg px-3 py-2 text-sm text-slate-200"
                    >
                      {EBAY_CONDITIONS.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={postToEbay}
                      disabled={posting || !build.hero_photo_url || !hasRequiredAspects}
                      title={!hasRequiredAspects ? "Generate or fill in Item Specifics (Brand, Type) before listing" : undefined}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-[#00dc82] hover:bg-[#00dc82]/90 disabled:opacity-60 text-black rounded-lg transition-colors"
                    >
                      {posting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                      List on eBay
                    </button>
                    {build.generated_title && build.generated_description && (
                      <button
                        onClick={() => {
                          // Re-check inside the handler: the outer JSX guard only
                          // narrows for the render that created this closure, not
                          // for whenever the user actually clicks (build is state
                          // and can change between the two, e.g. after an
                          // unrelated async setBuild call).
                          const { generated_title, generated_description } = build;
                          if (!generated_title || !generated_description) return;

                          const escapeHtml = (text: string) =>
                            text
                              .replace(/&/g, '&amp;')
                              .replace(/</g, '&lt;')
                              .replace(/>/g, '&gt;')
                              .replace(/"/g, '&quot;')
                              .replace(/'/g, '&#39;');

                          const htmlContent = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(generated_title)}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; padding: 20px; }
    .container { max-width: 900px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 32px 24px; text-align: center; }
    .header h1 { font-size: 32px; font-weight: 700; line-height: 1.2; }
    .content { padding: 40px; }
    .hero-image { width: 100%; height: auto; border-radius: 8px; margin-bottom: 32px; display: block; }
    .description { font-size: 15px; line-height: 1.8; color: #333; }
    .description p { margin-bottom: 16px; }
    .description p:last-child { margin-bottom: 0; }
    .footer { background: #f9f9f9; padding: 16px 40px; border-top: 1px solid #eee; font-size: 12px; color: #666; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>${escapeHtml(generated_title)}</h1>
    </div>
    <div class="content">
      ${build.hero_photo_url ? `<img src="${escapeHtml(build.hero_photo_url)}" alt="Product preview" class="hero-image">` : ''}
      <div class="description">
        ${generated_description
                              .split('\n\n')
                              .map(
                                (para) =>
                                  `<p>${escapeHtml(para)
                                    .replace(/\n/g, '<br>')
                                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>`
                              )
                              .join('')}
      </div>
    </div>
    <div class="footer">
      <p>Preview generated by FlipFlop • Windows 11 Pro Activated</p>
    </div>
  </div>
</body>
</html>`;

                          const blob = new Blob([htmlContent], { type: 'text/html' });
                          const url = URL.createObjectURL(blob);
                          window.open(url, '_blank');
                        }}
                        disabled={generating}
                        className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                      >
                        {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        Preview HTML
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* FlipFlop.shop storefront */}
          {build.generated_title && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3">
              <p className="text-sm font-semibold flex items-center gap-2">
                <Store className="w-4 h-4 text-slate-500" /> List on FlipFlop.shop
              </p>
              {build.storefront_product_id ? (
                <p className="text-sm text-[#00dc82]">
                  ✓ Published to the pre-built showcase (product #{build.storefront_product_id}) — it&apos;ll also appear
                  in the homepage gallery now that it has a hero photo.
                </p>
              ) : (
                <>
                  {!canPublish && (
                    <p className="text-[11px] text-amber-400">
                      Needs a hero photo and generated title/description before it can be published.
                    </p>
                  )}
                  <button
                    onClick={listOnStorefront}
                    disabled={!canPublish || listingOnStorefront}
                    className="flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-600 text-black rounded-lg transition-colors"
                  >
                    {listingOnStorefront ? <Loader2 className="w-4 h-4 animate-spin" /> : <Store className="w-4 h-4" />}
                    List on FlipFlop.shop
                  </button>
                </>
              )}
            </div>
          )}
        </>
      )}

    </div>
  );
}

function ChannelBadge({
  label,
  icon: Icon,
  live,
}: {
  label: string;
  icon: typeof ShoppingBag;
  live: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold ${
        live
          ? "border-emerald-700/40 bg-emerald-950/30 text-emerald-300"
          : "border-white/[0.07] bg-white/[0.02] text-slate-500"
      }`}
      title={live ? `Live on ${label}` : `Not currently published to ${label}`}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
      {live ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
      ) : (
        <X className="w-3.5 h-3.5 text-slate-600" />
      )}
    </div>
  );
}

function BrandedCardTile({
  label,
  photo,
  loading,
  onGenerate,
}: {
  label: string;
  photo?: { url: string; kind: string };
  loading: boolean;
  onGenerate: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="aspect-[3/2] rounded-lg overflow-hidden bg-slate-800 border border-white/[0.07] flex items-center justify-center">
        {photo ? (
          <a href={photo.url} target="_blank" rel="noopener noreferrer" title="View full size">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photo.url} alt={label} className="w-full h-full object-cover" />
          </a>
        ) : (
          <IdCard className="w-6 h-6 text-slate-700" />
        )}
      </div>
      <div className="flex gap-1.5">
        <button
          onClick={onGenerate}
          disabled={loading}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold border border-white/[0.1] hover:border-white/[0.25] text-slate-300 rounded-lg transition-colors disabled:opacity-60"
        >
          {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
          {photo ? "Regenerate" : "Generate"} {label}
        </button>
        {photo && (
          <a
            href={photo.url}
            download={`${label.toLowerCase().replace(/\s+/g, "-")}.png`}
            title={`Download ${label}`}
            className="flex items-center justify-center px-2.5 border border-white/[0.1] hover:border-white/[0.25] text-slate-300 rounded-lg transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}
