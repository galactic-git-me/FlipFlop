"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, CheckCircle2, Circle, Hammer, Sparkles, ExternalLink,
  Loader2, ShoppingBag, ImagePlus, Star, X, IdCard, BadgeCheck, Store, Download, Zap,
  CalendarClock, Truck, AlertTriangle, PoundSterling, UploadCloud,
  HelpCircle, Shuffle,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import confetti from "canvas-confetti";
import JSZip from "jszip";
import { api, ManualBuild, BuildComponent, ComponentRating, ProductFaq } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { drawRegistrationPlate, drawSpecCard, canvasToBlob, loadLogo } from "@/lib/build-cards";
import { EbayOffersSection } from "@/components/builds/EbayOffersSection";
import { EbayShippingSection } from "@/components/builds/EbayShippingSection";
import { EbayShipmentBookingSection } from "@/components/builds/EbayShipmentBookingSection";
import { EbaySpecificsSection } from "@/components/builds/EbaySpecificsSection";
import { DescriptionPreview } from "@/components/builds/DescriptionPreview";
import { EbayListingHTMLPreview } from "@/components/builds/EbayListingHTMLPreview";
import { PricingIntelligence } from "@/components/builds/PricingIntelligence";
import { CommandPanel } from "@/components/builds/CommandPanel";

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
  { value: "NEW_OTHER", label: "New (other) — opened packaging / tested only" },
  { value: "SELLER_REFURBISHED", label: "Seller Refurbished" },
  { value: "USED_EXCELLENT", label: "Used" },
  { value: "FOR_PARTS_OR_NOT_WORKING", label: "For Parts / Not Working" },
];

const BUILD_3D_TARGETS = [
  { key: "complete_build", label: "Complete build", hint: "Use clean exterior angles of the finished PC." },
] as const;

function TabButton({
  label,
  icon: Icon,
  active,
  completed,
  disabled,
  onClick,
}: {
  label: string;
  icon: any;
  active: boolean;
  completed: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-semibold whitespace-nowrap transition-all shrink-0 ${
        disabled
          ? "border-white/[0.02] bg-white/[0.01] text-slate-600 cursor-not-allowed opacity-50 font-medium"
          : active
          ? "border-cyan-500/40 bg-cyan-950/20 text-cyan-400 cursor-pointer"
          : "border-white/[0.05] bg-white/[0.01] text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] cursor-pointer"
      }`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{label}</span>
      {!disabled && (
        completed ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-[#00dc82] shrink-0 font-bold" />
        ) : (
          <Circle className="w-3.5 h-3.5 text-slate-600 shrink-0" />
        )
      )}
    </button>
  );
}

export default function BuildDetailPage() {
  const params = useParams();
  const router = useRouter();
  const buildId = Number(params.id);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const performanceCardInputRef = useRef<HTMLInputElement>(null);
  const model3dInputRef = useRef<HTMLInputElement>(null);
  const hiddenCanvasRef = useRef<HTMLCanvasElement>(null);

  const [build, setBuild] = useState<ManualBuild | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSlot, setSavingSlot] = useState<string | null>(null);
  const [markingBuilt, setMarkingBuilt] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [posting, setPosting] = useState(false);
  const [uploadingPhotos, setUploadingPhotos] = useState(false);
  const [uploading3dModel, setUploading3dModel] = useState(false);
  const [queueing3dModels, setQueueing3dModels] = useState(false);
  const [selected3dPhotos, setSelected3dPhotos] = useState<Record<string, string[]>>({});
  const [savingAspects, setSavingAspects] = useState(false);
  const [generatingSpecifics, setGeneratingSpecifics] = useState(false);
  const [savingEbayConfig, setSavingEbayConfig] = useState(false);
  const [generatingCard, setGeneratingCard] = useState<"spec_card" | "registration_plate" | null>(null);
  const [listingOnStorefront, setListingOnStorefront] = useState(false);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [draggedUrl, setDraggedUrl] = useState<string | null>(null);
  const [dragOverUrl, setDragOverUrl] = useState<string | null>(null);
  const [showEbayPreview, setShowEbayPreview] = useState(false);
  const [showEndEbayConfirm, setShowEndEbayConfirm] = useState(false);
  const [endingEbayListing, setEndingEbayListing] = useState(false);
  const [componentRatings, setComponentRatings] = useState<Record<string, number>>({});
  const [savingRatings, setSavingRatings] = useState(false);
  const [faqBank, setFaqBank] = useState<ProductFaq[]>([]);
  const [selectedFaqIds, setSelectedFaqIds] = useState<string[]>([]);
  const [faqUsesDefaults, setFaqUsesDefaults] = useState(false);
  const [faqAnswerOverrides, setFaqAnswerOverrides] = useState<Record<string, string>>({});
  const [savingFaqs, setSavingFaqs] = useState(false);

  const [price, setPrice] = useState("");
  const [condition, setCondition] = useState("USED_EXCELLENT");
  const [deferredAt, setDeferredAt] = useState("");
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [performanceCardGenerated, setPerformanceCardGenerated] = useState(false);
  const [performanceCardImageUrls, setPerformanceCardImageUrls] = useState<string[]>([]);
  const [performanceCardZipUrl, setPerformanceCardZipUrl] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"build" | "pricing" | "listing" | "media" | "specifics" | "faqs" | "shipping" | "fulfillment">("build");

  const openCustomerPortal = async () => {
    setOpeningPortal(true);
    try {
      const response = await fetch(`/api/manual-builds/${buildId}/portal-preview`, { method: "POST" });
      const payload = await response.json() as { order_id?: number; token?: string; detail?: string };
      if (!response.ok || !payload.order_id || !payload.token) {
        throw new Error(payload.detail || "Could not create a customer portal preview");
      }
      window.open(
        `https://theflipflop.shop/my-builds/${payload.order_id}?preview=${encodeURIComponent(payload.token)}`,
        "_blank",
        "noopener,noreferrer",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not open the customer portal");
    } finally {
      setOpeningPortal(false);
    }
  };

  useEffect(() => {
    api.manualBuilds
      .get(buildId)
      .then((b) => {
        setBuild(b);
        // The declared insurance value and publish price must be the actual
        // saved listing price. The market-evaluation midpoint is only a
        // fallback for a build that has never had a listing price set.
        if (b.ebay_price && b.ebay_price > 0) {
          setPrice(String(b.ebay_price));
        } else if (b.last_evaluation?.mid) {
          setPrice(String(Math.round(b.last_evaluation.mid)));
        }
        if (b.ebay_condition) setCondition(b.ebay_condition);
        if (b.deferred_publish_at) setDeferredAt(b.deferred_publish_at.slice(0, 16));
        
        // Auto-focus active tab based on status
        if (b.status === "in_progress") {
          setActiveTab("build");
        } else if (b.status === "sold") {
          setActiveTab("fulfillment");
        } else if (b.status === "built") {
          setActiveTab("pricing");
        } else {
          setActiveTab("listing");
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [buildId]);

  useEffect(() => {
    api.manualBuilds.getFaqs(buildId).then((result) => {
      setFaqBank(result.bank);
      setSelectedFaqIds(result.selected_ids);
      setFaqUsesDefaults(result.uses_defaults);
      setFaqAnswerOverrides(result.answer_overrides || {});
    }).catch(() => undefined);
  }, [buildId]);

  useEffect(() => {
    const pending = Object.values(build?.model_3d_assets ?? {}).some((asset) =>
      asset.status === "queued" || asset.status === "processing"
    );
    if (!pending) return;
    const timer = window.setInterval(() => {
      api.manualBuilds.get(buildId).then(setBuild).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [buildId, build?.model_3d_assets]);

  const toggleFaq = (faqId: string) => {
    setFaqUsesDefaults(false);
    setSelectedFaqIds((current) => {
      if (current.includes(faqId)) return current.filter((id) => id !== faqId);
      if (current.length >= 10) {
        toast.error("Choose no more than 10 FAQs");
        return current;
      }
      return [...current, faqId];
    });
  };

  const chooseAnotherTenFaqs = () => {
    const shuffled = [...faqBank].sort(() => Math.random() - 0.5);
    setSelectedFaqIds(shuffled.slice(0, 10).map((faq) => faq.id));
    setFaqUsesDefaults(false);
  };

  const saveFaqs = async () => {
    setSavingFaqs(true);
    try {
      await api.manualBuilds.updateFaqs(buildId, selectedFaqIds, faqAnswerOverrides);
      setBuild((current) => current ? { ...current, selected_faq_ids: selectedFaqIds } : current);
      toast.success(`Saved ${selectedFaqIds.length} FAQs and edited answers for eBay and FlipFlop.shop`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save FAQ selection");
    } finally {
      setSavingFaqs(false);
    }
  };

  useEffect(() => {
    if (!build || build.status === "in_progress") return;
    api.manualBuilds.getComponentRatings(buildId).then((ratings) => {
      setComponentRatings(Object.fromEntries(ratings.map((rating) => [rating.component_slot, rating.overall_rating])));
    }).catch(() => undefined);
  }, [buildId, build?.status]);

  const saveRatings = async () => {
    if (!build) return;
    setSavingRatings(true);
    try {
      const ratings: ComponentRating[] = build.components
        .filter((component) => componentRatings[component.slot])
        .map((component) => ({
          component_slot: component.slot,
          component_key: component.name,
          overall_rating: componentRatings[component.slot],
        }));
      const result = await api.manualBuilds.saveComponentRatings(buildId, ratings);
      toast.success(`Saved ${result.saved} ratings${result.preferred_added ? ` · ${result.preferred_added} added to preferred components` : ""}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save component ratings");
    } finally {
      setSavingRatings(false);
    }
  };

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
      setActiveTab("listing");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't mark this build as built: ${msg}`);
    } finally {
      setMarkingBuilt(false);
    }
  };


  const generateListing = async (openPreviewAfter = false) => {
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
      if (openPreviewAfter) setShowEbayPreview(true);
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
      toast.error("Enter an asking price before listing.");
      return;
    }

    setPosting(true);
    try {
      const result = await api.manualBuilds.postToEbay(buildId, { price: priceNum, condition });
      if (result.success) {
        // 🎉 Confetti celebration
        confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });

        // ✅ Success toast
        toast.success("Listing posted to eBay!");

        // 🔗 Open the listing in a new tab if URL is available
        if (result.url) {
          setTimeout(() => window.open(result.url, "_blank"), 300);
        }

        const refreshed = await api.manualBuilds.get(buildId);
        setBuild(refreshed);
      } else {
        toast.error(`eBay rejected the listing: ${result.error ?? "Unknown error"}`);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      toast.error(`Couldn't post to eBay: ${msg}`);
    } finally {
      setPosting(false);
    }
  };

  const handle3dModelUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".glb")) {
      toast.error("Please upload a self-contained .glb model");
      e.target.value = "";
      return;
    }
    setUploading3dModel(true);
    try {
      const saved = await api.manualBuilds.upload3dModel(buildId, file);
      setBuild(saved);
      toast.success("3D model uploaded and ready for the storefront viewer");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not upload the 3D model");
    } finally {
      setUploading3dModel(false);
      if (model3dInputRef.current) model3dInputRef.current.value = "";
    }
  };

  const toggle3dPhoto = (assetType: string, url: string) => {
    setSelected3dPhotos((current) => {
      const selected = current[assetType] ?? [];
      if (selected.includes(url)) return { ...current, [assetType]: selected.filter((item) => item !== url) };
      if (selected.length >= 4) {
        toast.error("Meshy accepts up to four views for each model");
        return current;
      }
      return { ...current, [assetType]: [...selected, url] };
    });
  };

  const queue3dModels = async () => {
    const completeBuildPhotos = selected3dPhotos.complete_build ?? [];
    if (!completeBuildPhotos.length) {
      toast.error("Select at least one photo of the real completed PC");
      return;
    }
    setQueueing3dModels(true);
    try {
      const result = await api.manualBuilds.generate3dAssets(buildId, { complete_build: completeBuildPhotos });
      setBuild((current) => current ? { ...current, model_3d_assets: result.assets } : current);
      toast.success("Complete-build 3D model queued");
      setSelected3dPhotos({});
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not queue 3D generation");
    } finally {
      setQueueing3dModels(false);
    }
  };

  const endEbayListing = async () => {
    if (!build?.ebay_live) return;
    setEndingEbayListing(true);
    try {
      const saved = await api.manualBuilds.endEbayListing(buildId);
      setBuild(saved);
      setDeferredAt("");
      setShowEndEbayConfirm(false);
      toast.success("The eBay listing has ended. This build is ready to edit and relist.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not end the eBay listing");
    } finally {
      setEndingEbayListing(false);
    }
  };

  const saveDeferredSchedule = async () => {
    // The scheduled job runs unattended, so it needs a price already saved
    // on the build (there's no one there to type it in when the time
    // arrives) — persist whatever's currently in the asking-price field
    // alongside the schedule, same as a manual "List on eBay" click would use.
    const priceNum = parseFloat(price);
    if (deferredAt && (!priceNum || priceNum <= 0)) {
      alert("Enter an asking price before scheduling a publish time.");
      return;
    }
    setSavingSchedule(true);
    try {
      const saved = await api.manualBuilds.updateEbayConfig(buildId, {
        deferred_publish_at: deferredAt ? new Date(deferredAt).toISOString() : null,
        ebay_price: priceNum > 0 ? priceNum : undefined,
        ebay_condition: condition,
      });
      setBuild(saved);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      alert(`Couldn't save the publish schedule: ${msg}`);
    } finally {
      setSavingSchedule(false);
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

  // Calculate listing statuses for the command panel
  const listingStatuses = build
    ? [
        {
          platform: "ebay",
          isListed: !!build.ebay_live,
          listingId: build.ebay_listing_id || undefined,
          lastUpdated: build.updated_at,
        },
        {
          platform: "storefront",
          isListed: !!build.storefront_live,
          listingId: build.storefront_product_id ? String(build.storefront_product_id) : undefined,
          lastUpdated: build.updated_at,
        },
      ]
    : [];

  return (
    <>
      <Toaster position="top-right" richColors />
      <div className="min-h-screen bg-[#060d18] text-slate-100 px-4 py-6 md:px-8 max-w-3xl mx-auto">
        {/* offscreen canvas used to render branded cards before uploading them */}
        <canvas ref={hiddenCanvasRef} className="hidden" />

        {/* Command Panel — sticky controls on the right */}
        {build && (
          <CommandPanel
            buildId={String(buildId)}
            buildTitle={build.name}
            listingStatuses={listingStatuses}
            onGenerateDescription={() => generateListing(false)}
            onGenerateTitle={() => generateListing(false)}
            onPreviewEbay={build.generated_title && build.generated_description ? () => setShowEbayPreview(true) : undefined}
            onPublishEbay={postToEbay}
            onUpdateEbay={postToEbay}
            onDeleteEbay={() => setShowEndEbayConfirm(true)}
            onPublishStorefront={canPublish ? listOnStorefront : undefined}
            isLoading={generating || posting || markingBuilt}
            isDeletingEbay={endingEbayListing}
            isPublishingStorefront={listingOnStorefront}
          />
        )}

      <button
        onClick={() => router.push("/builds")}
        className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Pre-Built
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
        {build.status !== "in_progress" && build.model_3d_url && (
          <button
            type="button"
            onClick={() => void openCustomerPortal()}
            disabled={openingPortal}
            className="ml-auto inline-flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-1.5 text-xs font-bold text-cyan-300 transition-colors hover:bg-cyan-400/20 disabled:cursor-wait disabled:opacity-60"
          >
            {openingPortal ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5" />}
            View Customer Portal
          </button>
        )}
        {build.status !== "in_progress" && !build.model_3d_url && (
          <span className="ml-auto text-xs text-slate-500">Customer portal unlocks when the completed 3D model is ready</span>
        )}
      </div>

      {/* Guided Steps Tabs */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-6 border-b border-white/[0.06] no-scrollbar">
        <TabButton
          label="1. Build Checklist"
          icon={Hammer}
          active={activeTab === "build"}
          completed={build.status !== "in_progress"}
          onClick={() => setActiveTab("build")}
        />
        <TabButton
          label="2. Pricing"
          icon={PoundSterling}
          active={activeTab === "pricing"}
          completed={!!build.total_cost && !!build.last_evaluation}
          disabled={!canSell}
          onClick={() => setActiveTab("pricing")}
        />
        <TabButton
          label="3. Listing"
          icon={Sparkles}
          active={activeTab === "listing"}
          completed={!!build.generated_title && parseFloat(price) > 0}
          disabled={!canSell}
          onClick={() => setActiveTab("listing")}
        />
        <TabButton
          label="4. Media & Cards"
          icon={ImagePlus}
          active={activeTab === "media"}
          completed={!!build.hero_photo_url && build.photos.some(p => p.kind === "spec_card") && build.photos.some(p => p.kind === "registration_plate")}
          disabled={!canSell}
          onClick={() => setActiveTab("media")}
        />
        <TabButton
          label="5. Item Specifics"
          icon={IdCard}
          active={activeTab === "specifics"}
          completed={hasRequiredAspects}
          disabled={!canSell}
          onClick={() => setActiveTab("specifics")}
        />
        <TabButton
          label="6. FAQs"
          icon={HelpCircle}
          active={activeTab === "faqs"}
          completed={selectedFaqIds.length > 0}
          disabled={!canSell}
          onClick={() => setActiveTab("faqs")}
        />
        <TabButton
          label="7. Shipping & Offers"
          icon={Truck}
          active={activeTab === "shipping"}
          completed={!!build.ebay_condition}
          disabled={!canSell}
          onClick={() => setActiveTab("shipping")}
        />
        {(build.status === "sold" || !!build.ebay_order_id) && (
          <TabButton
            label="8. Fulfillment"
            icon={ShoppingBag}
            active={activeTab === "fulfillment"}
            completed={!!build.tracking_number}
            onClick={() => setActiveTab("fulfillment")}
          />
        )}
      </div>

      {/* Tab 1: Build Checklist */}
      {activeTab === "build" && (
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

          <div className="mt-3 flex items-center justify-between rounded-lg border border-cyan-400/15 bg-cyan-400/[0.04] px-3 py-3">
            <div>
              <p className="text-xs font-semibold text-slate-200">Total build cost</p>
              <p className="mt-0.5 text-[11px] text-slate-500">Sum of every recorded component purchase</p>
            </div>
            <p className="text-lg font-black text-cyan-300">{formatCurrency(build.total_cost ?? 0)}</p>
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

          {build.status !== "in_progress" && (
            <div className="mt-5 border-t border-white/[0.07] pt-5">
              <div className="mb-3">
                <p className="text-sm font-semibold flex items-center gap-2">
                  <Star className="h-4 w-4 text-amber-400" /> Rate this build&apos;s components
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Five-star components are added to your preferred list and improve future build-fit ranking.
                </p>
              </div>
              <div className="space-y-2">
                {build.components.map((component) => (
                  <div key={component.slot} className="flex flex-col gap-2 rounded-lg border border-white/[0.06] bg-black/20 p-3 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-mono uppercase text-slate-500">{component.slot}</p>
                      <p className="truncate text-sm text-slate-200">{component.name}</p>
                    </div>
                    <div className="flex gap-1" role="radiogroup" aria-label={`Rate ${component.name}`}>
                      {[1, 2, 3, 4, 5].map((rating) => (
                        <button
                          key={rating}
                          type="button"
                          role="radio"
                          aria-checked={(componentRatings[component.slot] ?? 0) === rating}
                          aria-label={`${rating} star${rating === 1 ? "" : "s"}`}
                          onClick={() => setComponentRatings((current) => ({ ...current, [component.slot]: rating }))}
                          className="cursor-pointer rounded p-1 transition-colors duration-200 hover:bg-amber-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                        >
                          <Star className={`h-5 w-5 ${(componentRatings[component.slot] ?? 0) >= rating ? "fill-amber-400 text-amber-400" : "text-slate-600"}`} />
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={saveRatings}
                disabled={savingRatings || Object.keys(componentRatings).length === 0}
                className="mt-3 w-full cursor-pointer rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-black transition-colors duration-200 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-600"
              >
                {savingRatings ? "Saving ratings…" : "Save component ratings"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Pricing intelligence */}
      {canSell && activeTab === "pricing" && (
        <div className="mb-6">
          <PricingIntelligence buildId={buildId} onUsePrice={(recommended) => {
            setPrice(String(Math.round(recommended)));
            setActiveTab("listing");
            toast.success(`Asking price set to ${formatCurrency(recommended)} — review before publishing`);
          }} />
        </div>
      )}

      {/* Tab 3: Listing */}
      {canSell && activeTab === "listing" && (
        <div className="flex flex-col gap-6 mb-6">
          {/* Sell flow */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-4">
            <p className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-slate-500" /> Sell this build
            </p>

            {!build.generated_title ? (
              <p className="text-sm text-slate-400 italic">
                Use the actions in the side menu to generate your eBay listing details.
              </p>
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

        </div>
      )}

      {/* Tab 3: Media & Cards */}
      {canSell && activeTab === "media" && (
        <div className="flex flex-col gap-6 mb-6">
          {/* Photos */}
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
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
                    <div className="pointer-events-none absolute bottom-1 left-1 z-10 max-w-[calc(100%-8px)] truncate rounded-md bg-slate-950/85 px-2 py-1 text-[10px] font-semibold text-white shadow">
                      {photoIdx + 1}. {(["Cover / hero", "Colour-shift angle", "Interior detail", "Performance proof", "Gaming FPS", "Rear connectivity", "Components", "Condition detail", "Included items", "Packaging", "Windows proof", "Extra angle"])[photoIdx] || "Extra view"}
                    </div>
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
              <p className="text-[11px] text-slate-500 mb-3">Drag to reorder. The numbered labels show the recommended buyer journey; the first five images have the greatest selling impact.</p>
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

          {/* Image-to-3D generation */}
          <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/[0.035] p-4 sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="flex items-center gap-2 text-sm font-bold text-slate-100">
                  <Sparkles className="h-4 w-4 text-cyan-300" /> Generate 3D assets from photos
                </p>
                <p className="mt-1 max-w-2xl text-[11px] leading-5 text-slate-400">
                  Select up to four clear photos of the finished PC.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={queue3dModels}
                  disabled={queueing3dModels || regularPhotos.length === 0 || !(selected3dPhotos.complete_build?.length)}
                  className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-2 text-sm font-black text-slate-950 transition-colors hover:bg-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {queueing3dModels ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Generate from photos
                </button>
                <input ref={model3dInputRef} type="file" accept=".glb,model/gltf-binary" onChange={handle3dModelUpload} className="hidden" />
                <button
                  type="button"
                  onClick={() => model3dInputRef.current?.click()}
                  disabled={uploading3dModel}
                  className="inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg border border-cyan-400/25 bg-cyan-400/[0.06] px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors hover:bg-cyan-400/[0.12] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {uploading3dModel ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                  {build.model_3d_url ? "Replace GLB" : "Upload GLB"}
                </button>
                {build.model_3d_url && <a href={build.model_3d_url} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-1 px-2 text-xs font-bold text-emerald-300 hover:text-emerald-200">3D model ready <ExternalLink className="h-3 w-3" /></a>}
              </div>
            </div>

            {regularPhotos.length === 0 ? (
              <p className="mt-4 rounded-lg border border-amber-400/20 bg-amber-400/[0.05] p-3 text-xs text-amber-200">Upload ordinary build photos first.</p>
            ) : (
              <div className="mt-5 space-y-3">
                {BUILD_3D_TARGETS.map((target) => {
                  const selected = selected3dPhotos[target.key] ?? [];
                  const existing = build.model_3d_assets?.[target.key];
                  const pending = existing?.status === "queued" || existing?.status === "processing";
                  return (
                    <section key={target.key} className="rounded-xl border border-white/[0.08] bg-slate-950/45 p-3" aria-labelledby={`asset-${target.key}`}>
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h3 id={`asset-${target.key}`} className="text-xs font-bold text-slate-200">{target.label}</h3>
                          <p className="mt-0.5 text-[10px] text-slate-500">{target.hint}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-slate-500">
                            {selected.length}/4 selected
                          </span>
                          {existing && (
                            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${
                              existing.status === "succeeded" ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-300" :
                              existing.status === "failed" ? "border-red-400/25 bg-red-400/10 text-red-300" :
                              "border-amber-400/25 bg-amber-400/10 text-amber-300"
                            }`}>{pending && <Loader2 className="mr-1 inline h-2.5 w-2.5 animate-spin" />}{existing.status}</span>
                          )}
                          {existing?.glb_url && <a href={existing.glb_url} target="_blank" rel="noreferrer" className="text-[10px] font-bold text-cyan-300 hover:text-cyan-200">Open GLB</a>}
                        </div>
                      </div>
                      <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                          {regularPhotos.map((photo, index) => {
                          const isSelected = selected.includes(photo.url);
                          return (
                            <button
                              key={photo.url}
                              type="button"
                              onClick={() => toggle3dPhoto(target.key, photo.url)}
                              aria-pressed={isSelected}
                              aria-label={`${isSelected ? "Remove" : "Use"} photo ${index + 1} for ${target.label}`}
                              className={`relative h-20 w-20 shrink-0 cursor-pointer overflow-hidden rounded-lg border-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${isSelected ? "border-cyan-300" : "border-white/10 hover:border-white/30"}`}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={photo.url} alt="" className="h-full w-full object-cover" />
                              <span className={`absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full text-[10px] font-black ${isSelected ? "bg-cyan-300 text-slate-950" : "bg-slate-950/80 text-slate-300"}`}>
                                {isSelected ? selected.indexOf(photo.url) + 1 : index + 1}
                              </span>
                            </button>
                            );
                          })}
                      </div>
                      {existing?.error && <p className="mt-2 text-[10px] text-red-300">{existing.error}</p>}
                    </section>
                  );
                })}
              </div>
            )}
          </div>

          {/* Branded cards */}
          {build.generated_title && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3">
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
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3">
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
                      const jsonText = await file.text();
                      const performanceData = JSON.parse(jsonText);
                      // Save the raw data to this build — this is what generate-listing
                      // actually sends to the AI. Save it even if the visual render below fails.
                      const saved = await api.manualBuilds.updateEvidenceData(buildId, "performance_card", performanceData);
                      setBuild(saved);

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
                          const saved = await api.manualBuilds.uploadPhotos(buildId, files, "performance_card");
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
        </div>
      )}

      {/* Tab 4: Item Specifics */}
      {canSell && activeTab === "specifics" && (
        <div className="flex flex-col gap-6 mb-6">
          <EbaySpecificsSection
            build={build}
            onGenerateSpecifics={generateSpecifics}
            onUpdateAspects={saveAspects}
            generating={generatingSpecifics}
            saving={savingAspects}
          />
        </div>
      )}

      {/* Tab 6: Customer FAQs */}
      {canSell && activeTab === "faqs" && (
        <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-5 mb-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-5">
            <div>
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-bold">Customer FAQ bank</h2>
                <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2 py-0.5 text-[11px] font-bold text-cyan-300">
                  {selectedFaqIds.length}/10 selected
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2 max-w-2xl leading-relaxed">
                These answers are included in the eBay description when it is published and appear as an FAQ section on FlipFlop.shop. Ten defaults are chosen for each build; untick any and choose replacements below.
              </p>
              {faqUsesDefaults && <p className="text-[11px] text-emerald-400 mt-2">Using this build&apos;s automatically chosen defaults.</p>}
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={chooseAnotherTenFaqs}
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-cyan-400/40 hover:text-cyan-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <Shuffle className="w-3.5 h-3.5" /> Choose another 10
              </button>
              <button
                type="button"
                onClick={saveFaqs}
                disabled={savingFaqs}
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-cyan-500 px-3 py-2 text-xs font-bold text-slate-950 transition-colors hover:bg-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {savingFaqs ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                Save FAQs
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
            {faqBank.map((faq) => {
              const selected = selectedFaqIds.includes(faq.id);
              return (
                <div
                  key={faq.id}
                  className={`flex items-start gap-3 rounded-xl border p-3.5 transition-colors ${selected ? "border-cyan-400/35 bg-cyan-400/[0.07]" : "border-white/[0.07] bg-black/10 hover:border-white/20"}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleFaq(faq.id)}
                    className="mt-1 h-4 w-4 shrink-0 accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                    aria-label={`Include FAQ: ${faq.question}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-cyan-400/80">{faq.category}</span>
                    <span className="mt-0.5 block text-sm font-semibold text-slate-100">{faq.question}</span>
                    <textarea
                      value={faqAnswerOverrides[faq.id] ?? faq.answer}
                      onChange={(event) => {
                        setFaqUsesDefaults(false);
                        setFaqAnswerOverrides((current) => ({ ...current, [faq.id]: event.target.value }));
                      }}
                      rows={4}
                      aria-label={`Answer for ${faq.question}`}
                      className="mt-2 w-full resize-y rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-xs leading-relaxed text-slate-300 outline-none transition-colors focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/20"
                    />
                    {faqAnswerOverrides[faq.id] !== undefined && (
                      <button
                        type="button"
                        onClick={() => setFaqAnswerOverrides((current) => {
                          const next = { ...current };
                          delete next[faq.id];
                          return next;
                        })}
                        className="mt-1 text-[11px] font-semibold text-slate-500 hover:text-cyan-300"
                      >
                        Restore default answer
                      </button>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 7: Shipping & Offers */}
      {canSell && activeTab === "shipping" && (
        <div className="flex flex-col gap-6 mb-6">
          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <p className="flex items-center gap-2 text-sm font-semibold"><Truck className="h-4 w-4 text-cyan-400" /> Delivery promises</p>
            <p className="mt-1 text-xs text-slate-500">Handling/build time and courier transit are shown separately so customers know exactly what each window means.</p>
            <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead className="border-b border-white/[0.08] text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-2 py-2">Build type</th><th className="px-2 py-2">Handling / build time</th><th className="px-2 py-2">Delivery after dispatch</th><th className="px-2 py-2">Customer wording</th></tr></thead><tbody>
              <tr className="border-b border-white/[0.05] bg-cyan-400/[0.025]"><td className="px-2 py-3 font-semibold text-cyan-300">Ready-to-ship pre-built</td><td className="px-2 py-3">1 working day</td><td className="px-2 py-3">1–2 working days</td><td className="px-2 py-3 text-slate-400">Usually arrives 2–3 working days after ordering</td></tr>
              <tr className="border-b border-white/[0.05]"><td className="px-2 py-3 font-semibold">Curated build</td><td className="px-2 py-3 text-amber-300">Set per build</td><td className="px-2 py-3">1–2 working days</td><td className="px-2 py-3 text-slate-400">Build lead time plus tracked delivery</td></tr>
              <tr><td className="px-2 py-3 font-semibold">Custom build</td><td className="px-2 py-3 text-amber-300">Set per build</td><td className="px-2 py-3">1–2 working days</td><td className="px-2 py-3 text-slate-400">Quoted build lead time plus tracked delivery</td></tr>
            </tbody></table></div>
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
            <p className="text-sm font-semibold">Customer promise shown with this build</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {[
                ["Returns", "30-day returns. Change-of-mind return postage is paid by the customer; FlipFlop pays reasonable return costs for faulty or misdescribed goods."],
                ["Consumer rights", "UK statutory remedies apply. These rights are not reduced by any separate warranty or remaining manufacturer cover."],
                ["Delivery", "One working day handling, followed by an estimated 1–2 working day tracked-delivery window."],
                ["Support", "Direct setup, troubleshooting and upgrade help through the personalised owner portal."],
              ].map(([title, copy]) => <div key={title} className="rounded-lg border border-white/[0.06] bg-black/20 p-3"><p className="text-xs font-semibold text-slate-200">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{copy}</p></div>)}
            </div>
          </div>

          {/* eBay */}
          {build.generated_title && build.status !== "sold" && (
            <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4 flex flex-col gap-3">
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
                  <p className="text-xs text-slate-400 italic">
                    Configure condition and scheduling below. Use the actions in the side menu to publish or update the listing on eBay.
                  </p>
                  {!build.hero_photo_url && (
                    <p className="text-[11px] text-amber-400">Upload at least one photo and choose a hero image first.</p>
                  )}
                  <div>
                    <label className="text-xs text-slate-500 uppercase font-mono">Condition</label>
                    <select
                      value={condition}
                      onChange={(e) => {
                        const nextCondition = e.target.value;
                        setCondition(nextCondition);
                        void updateEbayConfig({ ebay_condition: nextCondition });
                      }}
                      className="mt-1 w-full bg-black/30 border border-white/[0.1] rounded-lg px-3 py-2 text-sm text-slate-200"
                    >
                      {EBAY_CONDITIONS.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Deferred-listing scheduler */}
                  <div className="rounded-lg border border-white/[0.07] bg-black/20 p-3 flex flex-col gap-2">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                      <CalendarClock className="w-3.5 h-3.5" /> Deferred-listing scheduler
                    </p>
                    <label className="text-xs text-slate-500">
                      Publish at (optional — leave blank and use &quot;List on eBay&quot; in side menu instead)
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="datetime-local"
                        value={deferredAt}
                        onChange={(e) => setDeferredAt(e.target.value)}
                        className="flex-1 bg-black/30 border border-white/[0.1] rounded-lg px-3 py-2 text-sm text-slate-200"
                      />
                      <button
                        onClick={saveDeferredSchedule}
                        disabled={savingSchedule}
                        className="px-3 py-2 text-xs font-semibold bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-slate-200 rounded-lg transition-colors disabled:opacity-50"
                      >
                        {savingSchedule ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Save"}
                      </button>
                    </div>
                    {build.deferred_publish_at && (
                      <p className="text-[11px] text-slate-500">
                        Scheduled to publish {new Date(build.deferred_publish_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}.
                        Checked every 15 minutes — publishes automatically once the listing (photos, specifics, price) is ready.
                      </p>
                    )}
                  </div>

                  <div className="flex gap-3">
                    {build.generated_title && build.generated_description && (
                      <button
                        onClick={() => {
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
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
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
        </div>
      )}

      {/* Tab 6: Fulfillment */}
      {(build.status === "sold" || !!build.ebay_order_id) && activeTab === "fulfillment" && (
        <div className="flex flex-col gap-6 mb-6">
          <EbayShipmentBookingSection build={build} onRefresh={refreshBuild} />
        </div>
      )}

      </div>

      {/* eBay Listing Preview Modal */}
      {showEbayPreview && build.generated_title && build.generated_description && (
        <EbayListingHTMLPreview
          title={build.generated_title}
          description={build.generated_description}
          images={build.photos?.filter((p) => p.kind === "photo").map((p) => p.url) || []}
          aspects={build.generated_aspects}
          price={price ? Number(price) : undefined}
          condition={condition}
          shippingCost={build.shipping_cost}
          heroPhotoUrl={build.hero_photo_url}
          onClose={() => setShowEbayPreview(false)}
          isModal={true}
        />
      )}

      {showEndEbayConfirm && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 px-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !endingEbayListing) setShowEndEbayConfirm(false);
          }}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="end-ebay-title"
            aria-describedby="end-ebay-description"
            className="w-full max-w-md rounded-2xl border border-red-500/25 bg-[#0b1422] p-6 shadow-2xl shadow-black/50"
          >
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-red-500/10 text-red-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <h2 id="end-ebay-title" className="text-lg font-bold text-white">End this eBay listing?</h2>
            <p id="end-ebay-description" className="mt-2 text-sm leading-6 text-slate-400">
              Item {build.ebay_listing_id} will stop being available on eBay immediately. Its views and watchers will not carry over to a new listing.
            </p>
            <p className="mt-3 rounded-lg border border-cyan-500/15 bg-cyan-500/[0.06] px-3 py-2.5 text-xs leading-5 text-cyan-100/80">
              The build, photos, listing copy, item specifics and price settings will stay here so you can correct them before relisting.
            </p>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setShowEndEbayConfirm(false)}
                disabled={endingEbayListing}
                className="cursor-pointer rounded-lg border border-white/10 px-4 py-2.5 text-sm font-semibold text-slate-300 transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Keep listing live
              </button>
              <button
                type="button"
                onClick={endEbayListing}
                disabled={endingEbayListing}
                autoFocus
                className="flex cursor-pointer items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {endingEbayListing && <Loader2 className="h-4 w-4 animate-spin" />}
                {endingEbayListing ? "Ending listing…" : "End listing on eBay"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
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
