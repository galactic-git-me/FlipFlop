"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Box, Check, AlertCircle, RefreshCw, LockKeyhole, Images, Plus, Sparkles, ExternalLink, Upload, Eye, Star, Heart, Video } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";
import { ThreeDWorkflowNav } from "@/components/three-d-workflow-nav";
import { readJsonResponse } from "@/lib/read-json-response";

interface SourcingStageEvidence {
  status?: string;
  attempts?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

interface PriorityCaseItem {
  id: number;
  name: string;
  brand?: string;
  model?: string;
  price: number;
  rrp?: number;
  source_site?: string;
  source_url?: string;
  image_url?: string;
  bestseller_rank?: number;
  priority_3d_rank?: number;
  priority_3d_batch?: number;
  priority_3d_frozen_at?: string;
  rating?: number;
  review_count?: number;
  sales_velocity?: string;
  keywords?: string[];
  form_factors?: string[];
  is_preferred?: boolean;
  has_3d_model?: boolean;
  model_3d_url?: string;
  sourcing_3d_evidence?: {
    stages?: Record<string, SourcingStageEvidence>;
  };
}

type ReferenceSource = "amazon" | "manufacturer" | "google" | "retailer" | "manual";

interface ReferenceCandidate {
  url: string;
  source: ReferenceSource;
  source_page?: string | null;
  label?: string | null;
}

interface ReferenceCandidateResponse {
  sourcing_ready: boolean;
  candidates: ReferenceCandidate[];
  approved_selection?: { status?: string; images?: ReferenceCandidate[] };
}

const DIRECT_BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4311").replace(/\/$/, "");

const sourcingLabels: Array<[string, string]> = [
  ["product_images", "Images"],
  ["youtube_video", "YouTube"],
  ["meshy_generation", "Meshy"],
];

const knownCaseBrands = [
  "Fractal Design",
  "Cooler Master",
  "Thermaltake",
  "SilverStone",
  "be quiet!",
  "Lian Li",
  "Phanteks",
  "Corsair",
  "Antec",
  "Asus",
  "DeepCool",
  "FOIFKIN",
  "ANSAITE",
  "PCZZOI",
  "HYXN",
  "Montech",
  "NZXT",
  "MSI",
];

const caseColours = [
  "charcoal black",
  "satin black",
  "matte black",
  "black",
  "white",
  "silver",
  "grey",
  "gray",
  "red",
  "blue",
  "green",
  "pink",
];

function caseManufacturer(caseItem: PriorityCaseItem) {
  const fullName = caseItem.name.replaceAll("™", "").replaceAll("®", "").trim();
  return caseItem.brand?.trim() || knownCaseBrands.find(candidate => {
    const escapedBrand = candidate.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escapedBrand}(?=$|[^a-z0-9])`, "i").test(fullName);
  }) || "Unbranded";
}

function compactCaseName(caseItem: PriorityCaseItem) {
  const fullName = caseItem.name.replaceAll("™", "").replaceAll("®", "").trim();
  const brand = caseManufacturer(caseItem);
  const brandIndex = fullName.toLocaleLowerCase().indexOf(brand.toLocaleLowerCase());
  const withoutBrand = brandIndex === 0
    ? fullName.slice(brand.length).trim()
    : brandIndex > 0
      ? fullName.slice(0, brandIndex).trim()
      : fullName;
  const modelSource = caseItem.model?.trim() || withoutBrand;
  const model = modelSource
    .split(/\s(?:RS(?:120)?-?R?|ARGB|Panoramic|Charcoal|Tempered|Compact|ATX|mATX|Micro-ATX|Mid-Tower|Mid Tower|PC Case|Computer Case)\b|\s[–|]\s|\s-\s/i)[0]
    .replace(/[,:;|–-]+$/g, "")
    .trim() || "Case";
  const lowerName = fullName.toLocaleLowerCase();
  const colour = caseColours.find(candidate => new RegExp(`\\b${candidate}\\b`, "i").test(lowerName));

  return [brand, model, colour].filter(Boolean).join("-").toLocaleUpperCase();
}

function hasIncludedFans(caseItem: PriorityCaseItem) {
  const title = caseItem.name;
  if (/(?:fans?\s+(?:included|pre-installed)|pre-installed[^,;–|]{0,60}fans?|includes?\s+\d+\s*(?:x\s*)?(?:\d+\s*mm\s*)?(?:\w+\s+){0,3}fans?|with\s+\d+\s*(?:x\s*)?(?:\d+\s*mm\s*)?(?:\w+\s+){0,3}fans?)/i.test(title)) return true;

  const withoutCapacityClaims = title.replace(/(?:supports?|fits?|capacity(?:\s+for)?)[^,;–|]{0,70}fans?/gi, "");
  return /\b(?:(?:PWM|ARGB|RGB)\s+)+fans?\b/i.test(withoutCapacityClaims);
}

function compatibleBoardFormats(caseItem: PriorityCaseItem) {
  const formats = new Set(
    (caseItem.form_factors || []).map(format => format.trim().toLocaleUpperCase()).filter(Boolean),
  );
  const title = caseItem.name;
  let remainingTitle = title;

  if (/\bE-?ATX\b/i.test(title)) {
    formats.add("E-ATX");
    remainingTitle = remainingTitle.replace(/\bE-?ATX\b/gi, "");
  }
  if (/\b(?:MICRO[- ]?ATX|M-?ATX)\b/i.test(title)) {
    formats.add("MATX");
    remainingTitle = remainingTitle.replace(/\b(?:MICRO[- ]?ATX|M-?ATX)\b/gi, "");
  }
  if (/\b(?:MINI[- ]?ITX|M-?ITX)\b/i.test(title)) {
    formats.add("ITX");
    remainingTitle = remainingTitle.replace(/\b(?:MINI[- ]?ITX|M-?ITX)\b/gi, "");
  }
  if (/\bATX\b/i.test(remainingTitle)) formats.add("ATX");
  if (/\bITX\b/i.test(remainingTitle)) formats.add("ITX");

  return [...formats];
}

function evidenceUrls(stage?: SourcingStageEvidence) {
  const matches = JSON.stringify(stage || {}).match(/https?:\\?\/\\?\/[^"\\\s]+/g) || [];
  return [...new Set(matches.map(url => url.replaceAll("\\/", "/")))];
}

function youtubeEmbedUrl(url: string) {
  try {
    const parsed = new URL(url);
    const videoId = parsed.hostname.includes("youtu.be") ? parsed.pathname.slice(1) : parsed.searchParams.get("v");
    return videoId ? `https://www.youtube.com/embed/${videoId}` : null;
  } catch {
    return null;
  }
}

function statusColour(status = "not_started") {
  if (["found", "complete"].includes(status)) return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  if (status === "blocked") return "border-red-500/50 bg-red-500/10 text-red-200";
  if (status === "searching") return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  if (status === "not_found") return "border-slate-600 bg-slate-800 text-slate-400";
  return "border-amber-500/40 bg-amber-500/10 text-amber-200";
}

function imageSetApproved(caseItem: PriorityCaseItem) {
  const stage = caseItem.sourcing_3d_evidence?.stages?.product_images;
  const selection = stage?.approved_selection as { status?: string } | undefined;
  return stage?.status === "complete" && selection?.status === "approved";
}

function liveStatus(caseItem: PriorityCaseItem) {
  const stages = caseItem.sourcing_3d_evidence?.stages || {};
  const rejected = ["product_images", "youtube_video", "meshy_generation", "validation"].some(key => stages[key]?.status === "blocked");
  if (rejected) return { label: "LIVE", title: "Live status: rejected", colour: "border-red-500/50 bg-red-500/10 text-red-200" };
  const approvalsComplete = imageSetApproved(caseItem)
    && stages.youtube_video?.status === "complete"
    && stages.meshy_generation?.status === "complete"
    && stages.validation?.status === "complete";
  if (approvalsComplete && caseItem.has_3d_model && caseItem.model_3d_url) {
    return { label: "LIVE", title: "Live status: deployed", colour: "border-emerald-500/50 bg-emerald-500/10 text-emerald-300" };
  }
  return { label: "LIVE", title: "Live status: pending", colour: "border-amber-500/50 bg-amber-500/10 text-amber-200" };
}

export default function Cases3DPriorityPage() {
  const router = useRouter();
  const [cases, setCases] = useState<PriorityCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [completedCases, setCompletedCases] = useState<PriorityCaseItem[]>([]);
  const [freezing, setFreezing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceCaseId, setReferenceCaseId] = useState<number | null>(null);
  const [referenceData, setReferenceData] = useState<ReferenceCandidateResponse | null>(null);
  const [selectedReferences, setSelectedReferences] = useState<ReferenceCandidate[]>([]);
  const [referenceBusy, setReferenceBusy] = useState(false);
  const [referenceNotice, setReferenceNotice] = useState<string | null>(null);
  const [newReferenceUrl, setNewReferenceUrl] = useState("");
  const [newReferenceSource, setNewReferenceSource] = useState<ReferenceSource>("manufacturer");
  const [generatedReviewUrl, setGeneratedReviewUrl] = useState<string | null>(null);
  const [generatingCaseId, setGeneratingCaseId] = useState<number | null>(null);
  const [evidenceReview, setEvidenceReview] = useState<{ caseItem: PriorityCaseItem; stage: "product_images" | "youtube_video" | "meshy_generation" } | null>(null);

  const openReferenceSelection = async (caseId: number) => {
    if (referenceCaseId === caseId) {
      setReferenceCaseId(null);
      return;
    }
    setReferenceBusy(true);
    setError(null);
    setReferenceNotice(null);
    try {
      const response = await fetch(`/api/cases/${caseId}/3d-reference-candidates`, { cache: "no-store" });
      const data = await readJsonResponse<ReferenceCandidateResponse & { detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || "Could not load reference pictures");
      setReferenceCaseId(caseId);
      setReferenceData(data);
      setSelectedReferences(data.approved_selection?.images || []);
      setGeneratedReviewUrl(window.localStorage.getItem(`case-3d-review-${caseId}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load reference pictures");
    } finally {
      setReferenceBusy(false);
    }
  };

  const toggleReference = (candidate: ReferenceCandidate) => {
    setReferenceData(current => current ? { ...current, approved_selection: undefined } : current);
    setReferenceNotice(null);
    setSelectedReferences(current => {
      if (current.some(item => item.url === candidate.url)) return current.filter(item => item.url !== candidate.url);
      if (current.length >= 4) return current;
      return [...current, candidate];
    });
  };

  const addReferenceCandidate = () => {
    try {
      const url = new URL(newReferenceUrl).href;
      if (!referenceData || referenceData.candidates.some(item => item.url === url)) return;
      setReferenceData({
        ...referenceData,
        approved_selection: undefined,
        candidates: [...referenceData.candidates, { url, source: newReferenceSource, label: "Manually added reference" }],
      });
      setNewReferenceUrl("");
    } catch {
      setError("Enter a complete http:// or https:// picture URL");
    }
  };

  const uploadReferenceCandidates = async (caseId: number, files: FileList | null) => {
    if (!files?.length) return;
    setReferenceBusy(true);
    setError(null);
    setReferenceNotice(`Uploading ${files.length} picture${files.length === 1 ? "" : "s"}…`);
    try {
      const formData = new FormData();
      Array.from(files).forEach(file => formData.append("files", file));
      const response = await fetch(`/api/cases/${caseId}/3d-reference-candidates/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await readJsonResponse<{ uploaded?: ReferenceCandidate[]; detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || "Could not upload reference pictures");
      const uploaded = data.uploaded || [];
      setReferenceData(current => current ? {
        ...current,
        approved_selection: undefined,
        candidates: [...current.candidates, ...uploaded.filter(candidate => !current.candidates.some(existing => existing.url === candidate.url))],
      } : current);
      setReferenceNotice(`${uploaded.length} uploaded picture${uploaded.length === 1 ? " is" : "s are"} now available to select.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not upload reference pictures");
      setReferenceNotice(null);
    } finally {
      setReferenceBusy(false);
    }
  };

  const approveReferences = async (caseId: number) => {
    if (selectedReferences.length !== 4) return;
    setReferenceBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/cases/${caseId}/3d-reference-selection`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ selected_images: selectedReferences }),
      });
      const data = await readJsonResponse<PriorityCaseItem & { detail?: string }>(response);
      if (!response.ok) throw new Error(data.detail || "Could not approve reference pictures");
      setCases(current => current.map(item => item.id === caseId ? data : item));
      setReferenceData(current => current ? { ...current, approved_selection: { status: "approved", images: selectedReferences } } : current);
      setReferenceNotice("Four reference pictures approved. Picture 1 is the texture and colour master.");
      return true;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not approve reference pictures");
      return false;
    } finally {
      setReferenceBusy(false);
    }
  };

  const generateFromApprovedReferences = async (caseId: number) => {
    if (selectedReferences.length !== 4 || referenceData?.approved_selection?.status !== "approved") return;
    setReferenceBusy(true);
    setGeneratingCaseId(caseId);
    setError(null);
    setReferenceNotice("Generating the textured model. Keep this page open — Meshy can take up to 10 minutes. You will be taken to the approval viewer when it finishes.");
    try {
      // Meshy can take up to ten minutes. Calling the backend directly avoids
      // Next's rewrite proxy terminating the long-lived connection.
      const response = await fetch(`${DIRECT_BACKEND_URL}/api/assets-3d/cases/${caseId}/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          image_urls: selectedReferences.map(item => item.url),
          notes: "Generated only from the separately owner-approved four-picture set. Preserve the first picture as the texture and colour master; match case finish and illuminated RGB faithfully.",
        }),
      });
      const asset = await readJsonResponse<{ id: number; review_batch_id?: string | null; detail?: string }>(response);
      if (!response.ok) throw new Error(asset.detail || "3D generation failed");
      let batchId = asset.review_batch_id;
      if (!batchId) {
        const batchResponse = await fetch("/api/assets-3d/review-batches", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ asset_ids: [asset.id] }),
        });
        const batch = await readJsonResponse<{ batch_id: string; detail?: string }>(batchResponse);
        if (!batchResponse.ok) throw new Error(batch.detail || "Model generated, but its review batch could not be created");
        batchId = batch.batch_id;
      }
      const reviewUrl = `/components-3d-review?batch=${batchId}`;
      setGeneratedReviewUrl(reviewUrl);
      window.localStorage.setItem(`case-3d-review-${caseId}`, reviewUrl);
      setReferenceNotice("Draft generated successfully. Opening the 3D approval viewer…");
      router.push(reviewUrl);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "3D generation failed");
      setReferenceNotice(null);
    } finally {
      setReferenceBusy(false);
      setGeneratingCaseId(null);
    }
  };

  const freezeCampaign = async () => {
    setFreezing(true);
    setError(null);
    try {
      const response = await fetch("/api/cases/priority-for-3d", { method: "POST" });
      const data = await readJsonResponse<{ cases?: PriorityCaseItem[]; detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(data.detail || data.error || "Could not freeze campaign");
      setCases(data.cases || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not freeze campaign");
    } finally {
      setFreezing(false);
    }
  };

  const openEvidenceReview = async (caseItem: PriorityCaseItem, stage: "product_images" | "youtube_video" | "meshy_generation") => {
    if (stage === "product_images" || stage === "meshy_generation") await openReferenceSelection(caseItem.id);
    setEvidenceReview({ caseItem, stage });
  };

  const closeEvidenceReview = () => {
    if (evidenceReview?.stage === "product_images" || evidenceReview?.stage === "meshy_generation") setReferenceCaseId(null);
    setEvidenceReview(null);
  };

  const decideEvidenceStage = async (decision: "complete" | "blocked") => {
    if (!evidenceReview) return;
    setReferenceBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/cases/${evidenceReview.caseItem.id}/3d-sourcing`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          stage: evidenceReview.stage,
          status: decision,
          attempt: { owner_decision: decision === "complete" ? "approved" : "declined" },
        }),
      });
      const updated = await readJsonResponse<PriorityCaseItem & { detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(updated.detail || updated.error || "Could not save review decision");
      setCases(current => current.map(item => item.id === updated.id ? updated : item));
      setEvidenceReview(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save review decision");
    } finally {
      setReferenceBusy(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        // Fetch priority cases for 3D modeling (top 30)
        // Include explicitly-added priority exceptions (for example APNX C1 at
        // rank 31) as well as the original frozen top-30 campaign.
        const response = await fetch("/api/cases/priority-for-3d?limit=100");
        const data = await readJsonResponse<PriorityCaseItem[]>(response);
        setCases(data.filter(caseItem => !/raspberry\s*pi|raspberrypi|\brpi\b/i.test(caseItem.name)));

        // Count how many already have models
        const withModels = await fetch("/api/cases/with-3d-models?limit=1000");
        const completed = await readJsonResponse<PriorityCaseItem[]>(withModels);
        setCompletedCases(completed.filter(caseItem => !/raspberry\s*pi|raspberrypi|\brpi\b/i.test(caseItem.name)));
      } catch (error) {
        console.error("Error loading cases:", error);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const meshyQueueCount = cases.filter(caseItem => {
    const status = caseItem.sourcing_3d_evidence?.stages?.meshy_generation?.status || "not_started";
    return imageSetApproved(caseItem) && !["found", "complete", "blocked"].includes(status);
  }).length;
  const allWorkflowCases = [...cases, ...completedCases];
  const photosApprovedCount = allWorkflowCases.filter(imageSetApproved).length;
  const modelReadyCount = allWorkflowCases.filter(caseItem =>
    !caseItem.has_3d_model && caseItem.sourcing_3d_evidence?.stages?.meshy_generation?.status === "found",
  ).length;
  const liveCount = completedCases.filter(caseItem => caseItem.has_3d_model && caseItem.model_3d_url).length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Box className="w-6 h-6 text-purple-400" /> 3D Model Priority Queue
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Frozen priority cases plus manually added exceptions. Select four source pictures before generating a draft model.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => router.push("/components-3d-review")} className="cursor-pointer border-purple-500/40 text-purple-200">
            <Eye className="mr-2 h-4 w-4" /> Open 3D approval viewer
          </Button>
          <Button onClick={freezeCampaign} disabled={freezing || cases.some(item => item.priority_3d_rank)} className="cursor-pointer focus-visible:ring-2 focus-visible:ring-cyan-300">
            {freezing ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <LockKeyhole className="mr-2 h-4 w-4" />}
            {cases.some(item => item.priority_3d_rank) ? "Top 30 frozen" : "Freeze top 30"}
          </Button>
        </div>
      </div>
      <ThreeDWorkflowNav />
      {error && <div role="alert" className="rounded-md border border-red-500/60 bg-red-950/60 px-4 py-3 text-sm text-red-200">{error}</div>}

      {/* Progress summary */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs uppercase text-slate-500">Total Cases</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-100">{cases.length}</div>
            <p className="mt-1 text-xs text-slate-500">cases shown in the priority table</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs uppercase text-slate-500"><Images className="h-3.5 w-3.5 text-cyan-400" /> Photos Approved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-cyan-400">{photosApprovedCount}</div>
            <p className="mt-1 text-xs text-slate-500">four-picture sets approved</p>
          </CardContent>
        </Card>

        <Card className="border-purple-500/30 bg-purple-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs uppercase text-slate-500"><Sparkles className="h-3.5 w-3.5 text-purple-400" /> Meshy Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">{meshyQueueCount}</div>
            <p className="mt-1 text-xs text-slate-500">ready to generate</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs uppercase text-slate-500">
              <Eye className="h-3.5 w-3.5 text-amber-400" /> 3D Model Ready
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-400">{modelReadyCount}</div>
            <p className="mt-1 text-xs text-slate-500">unapproved models ready for review</p>
          </CardContent>
        </Card>

        <Card className="border-[#00dc82]/30 bg-[#00dc82]/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs uppercase text-slate-500"><Eye className="h-3.5 w-3.5 text-[#00dc82]" /> Live</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#00dc82]">{liveCount}</div>
            <p className="mt-1 text-xs text-slate-500">deployed models</p>
          </CardContent>
        </Card>
      </div>

      {/* Cases list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-slate-500">
          <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading priority cases…
        </div>
      ) : cases.length === 0 ? (
        <Card className="bg-[#00dc82]/5 border-[#00dc82]/30">
          <CardContent className="pt-6 text-center">
            <Check className="w-12 h-12 text-[#00dc82] mx-auto mb-3" />
            <p className="text-slate-100 font-semibold">All popular cases have 3D models!</p>
            <p className="text-sm text-slate-500 mt-1">Great work. You can now enable cases in the customer builder.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <p className="text-xs font-medium uppercase tracking-wider text-slate-500">Next to create, ordered by popularity</p>
            <p className="text-xs text-slate-500">{cases.length} cases</p>
          </div>
          <div className="overflow-x-auto rounded-xl border border-[#1e2d45] bg-[#0b121d]">
            <table className="w-full min-w-[1380px] border-collapse text-left text-sm">
              <thead className="sticky top-0 z-10 bg-[#111b2a] text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th scope="col" className="w-16 px-4 py-3 text-center">Rank</th>
                  <th scope="col" className="px-4 py-3">Case</th>
                  <th scope="col" className="w-36 px-4 py-3">Manufacturer</th>
                  <th scope="col" className="w-24 px-4 py-3 text-center">Preferred</th>
                  <th scope="col" className="w-28 px-4 py-3">Price</th>
                  <th scope="col" className="w-40 px-4 py-3">RRP / Discount</th>
                  <th scope="col" className="w-40 px-4 py-3">Product rating</th>
                  <th scope="col" className="w-44 px-4 py-3">Compatible boards</th>
                  <th scope="col" className="w-80 min-w-80 px-4 py-3">Sourcing progress</th>
                  <th scope="col" className="w-52 px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2d45]">
            {cases.map((caseItem, idx) => (
              <Fragment key={caseItem.id}>
                <tr className="transition-colors hover:bg-slate-800/35">
                  <td className="px-4 py-3 text-center align-middle">
                    <span className="inline-flex min-w-8 items-center justify-center rounded-md border border-purple-400/30 bg-purple-400/10 px-2 py-1 font-bold text-purple-300">
                      {caseItem.priority_3d_rank || idx + 1}
                    </span>
                  </td>
                  <td className="px-4 py-3 align-middle">
                    <div className="flex min-w-[260px] items-center gap-3">
                      <div className="h-14 w-14 flex-shrink-0 overflow-hidden rounded-md border border-slate-700 bg-[#0a1119]">
                        {caseItem.image_url ? (
                        <img
                          src={caseItem.image_url}
                          alt={`${caseItem.name} product thumbnail`}
                          className="h-full w-full object-cover"
                        />
                        ) : <Box className="m-4 h-5 w-5 text-slate-600" />}
                      </div>
                      <div className="min-w-0">
                        <p
                          className="max-w-md cursor-help font-semibold text-slate-100 decoration-slate-600 underline-offset-4 hover:underline"
                          title={caseItem.name}
                        >
                          {compactCaseName(caseItem)}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                          {caseItem.keywords?.slice(0, 2).map(keyword => (
                            <span key={keyword} className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] text-slate-300">{keyword}</span>
                          ))}
                          {hasIncludedFans(caseItem) && (
                            <span className="rounded border border-cyan-500/35 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-medium text-cyan-200">
                              FANS INCLUDED
                            </span>
                          )}
                          {/\bARGB\b/i.test(caseItem.name) && (
                            <span className="rounded border border-fuchsia-500/35 bg-fuchsia-500/10 px-1.5 py-0.5 text-[10px] font-medium text-fuchsia-200">
                              ARGB
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 align-middle font-medium uppercase text-slate-300">{caseManufacturer(caseItem)}</td>
                  <td className="px-4 py-3 text-center align-middle">
                    {caseItem.is_preferred ? (
                      <Heart className="mx-auto h-5 w-5 fill-rose-500 text-rose-400" aria-label="Preferred case" />
                    ) : <span className="text-slate-700">—</span>}
                  </td>
                  <td className="px-4 py-3 align-middle font-semibold tabular-nums text-[#00dc82]">{formatCurrency(caseItem.price)}</td>
                  <td className="px-4 py-3 align-middle">
                    {caseItem.rrp && caseItem.rrp > caseItem.price ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="tabular-nums text-slate-400 line-through">{formatCurrency(caseItem.rrp)}</span>
                        <span
                          className="inline-flex rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 font-semibold tabular-nums text-emerald-300"
                          title={`${formatCurrency(caseItem.rrp - caseItem.price)} below RRP`}
                        >
                          {Math.round(((caseItem.rrp - caseItem.price) / caseItem.rrp) * 100)}% OFF
                        </span>
                      </div>
                    ) : caseItem.rrp ? <span className="tabular-nums text-slate-400">{formatCurrency(caseItem.rrp)} <span className="ml-1 text-xs text-slate-600">No sale</span></span> : <span className="text-slate-700">—</span>}
                  </td>
                  <td className="px-4 py-3 align-middle tabular-nums">
                    {caseItem.rating ? (
                      <div className="flex items-center gap-2" aria-label={`${caseItem.rating.toFixed(1)} out of 5 stars`}>
                        <div className="flex gap-0.5" aria-hidden="true">
                          {[1, 2, 3, 4, 5].map(star => (
                            <Star
                              key={star}
                              className={`h-3.5 w-3.5 ${star <= Math.round(caseItem.rating || 0) ? "fill-amber-400 text-amber-400" : "fill-slate-800 text-slate-600"}`}
                            />
                          ))}
                        </div>
                        <span className="font-semibold text-amber-300">{caseItem.rating.toFixed(1)}</span>
                      </div>
                    ) : <span className="text-slate-600">—</span>}
                  </td>
                  <td className="px-4 py-3 align-middle">
                    {compatibleBoardFormats(caseItem).length ? (
                      <div className="flex flex-wrap gap-1">
                        {compatibleBoardFormats(caseItem).map(formFactor => (
                          <span key={formFactor} className="rounded border border-blue-500/30 bg-blue-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-blue-200">
                            {formFactor}
                          </span>
                        ))}
                      </div>
                    ) : <span className="text-slate-600">—</span>}
                  </td>
                  <td className="w-80 min-w-80 px-4 py-3 align-middle">
                    <div className="flex flex-wrap gap-1.5" aria-label="3D sourcing progress">
                        {sourcingLabels.map(([key, label]) => {
                          const status = caseItem.sourcing_3d_evidence?.stages?.[key]?.status || "not_started";
                          const meshyLocked = key === "meshy_generation" && !imageSetApproved(caseItem);
                          return (
                            <button
                              key={key}
                              type="button"
                              title={meshyLocked ? "Approve four product pictures before reviewing or creating a Meshy model" : `Review ${label}: ${status.replaceAll("_", " ")}`}
                              onClick={() => void openEvidenceReview(caseItem, key as "product_images" | "youtube_video" | "meshy_generation")}
                              disabled={meshyLocked}
                              className={`rounded border px-1.5 py-0.5 text-[10px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 disabled:cursor-not-allowed disabled:opacity-40 ${meshyLocked ? "" : "cursor-pointer hover:border-cyan-300"} ${statusColour(status)}`}
                            >
                              {label}
                            </button>
                          );
                        })}
                        {(() => {
                          const live = liveStatus(caseItem);
                          return <span title={live.title} className={`rounded border px-1.5 py-0.5 text-[10px] ${live.colour}`}>{live.label}</span>;
                        })()}
                      </div>
                  </td>
                  <td className="px-4 py-3 text-right align-middle">
                    <div className="flex items-center justify-end gap-1.5" aria-label="Approval actions">
                      <button type="button" title="Approve pictures" aria-label="Approve pictures" onClick={() => void openEvidenceReview(caseItem, "product_images")} className="cursor-pointer rounded-md border border-cyan-500/40 p-2 text-cyan-200 transition-colors hover:bg-cyan-500/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300">
                        <Images className="h-4 w-4" />
                      </button>
                      <button type="button" title="Approve YouTube evidence" aria-label="Approve YouTube evidence" onClick={() => void openEvidenceReview(caseItem, "youtube_video")} className="cursor-pointer rounded-md border border-red-500/40 p-2 text-red-200 transition-colors hover:bg-red-500/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300">
                        <Video className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        title={imageSetApproved(caseItem) ? "Approve Meshy model" : "Approve pictures before creating or approving Meshy"}
                        aria-label={imageSetApproved(caseItem) ? "Approve Meshy model" : "Meshy locked until pictures are approved"}
                        disabled={!imageSetApproved(caseItem)}
                        onClick={() => void openEvidenceReview(caseItem, "meshy_generation")}
                        className="cursor-pointer rounded-md border border-purple-500/40 p-2 text-purple-200 transition-colors hover:bg-purple-500/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-300 disabled:cursor-not-allowed disabled:opacity-35"
                      >
                        <Sparkles className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>

                  {referenceCaseId === caseItem.id && referenceData && (
                    <tr className="bg-slate-900/65">
                      <td colSpan={10} className="px-6 py-5">
                    <section aria-label={`Reference picture approval for ${caseItem.name}`}>
                      <div className="mb-3 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100">
                        Choose exactly four clean pictures of the same empty chassis. They must show useful exterior angles and the interior, with no text panels or noisy backgrounds. Select the best colour/texture view first.
                      </div>
                      {!referenceData.sourcing_ready && (
                        <div className="mb-3 rounded-md border border-red-500/40 bg-red-950/40 p-3 text-xs text-red-200">
                          Finish the manufacturer and licensed third-party 3D-model searches first. Image-to-3D is the fallback only.
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                        {referenceData.candidates.map(candidate => {
                          const selectedIndex = selectedReferences.findIndex(item => item.url === candidate.url);
                          return (
                            <button
                              key={candidate.url}
                              type="button"
                              onClick={() => toggleReference(candidate)}
                              className={`group relative cursor-pointer overflow-hidden rounded-md border text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 ${selectedIndex >= 0 ? "border-cyan-300 ring-2 ring-cyan-400/40" : "border-slate-700 hover:border-slate-500"}`}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={candidate.url} alt="" className="h-36 w-full bg-white object-contain" />
                              {selectedIndex >= 0 && <span className="absolute left-2 top-2 rounded-full bg-cyan-500 px-2 py-1 text-xs font-bold text-slate-950">{selectedIndex + 1}</span>}
                              <span className="pointer-events-none absolute inset-x-0 bottom-0 translate-y-1 bg-slate-950/85 px-1.5 py-0.5 text-[9px] uppercase text-slate-200 opacity-0 backdrop-blur-sm transition group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
                                {candidate.source}{selectedIndex === 0 ? " · texture master" : ""}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                      <div className="mt-3 flex flex-col gap-2 md:flex-row">
                        <select value={newReferenceSource} onChange={event => setNewReferenceSource(event.target.value as ReferenceSource)} className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200">
                          <option value="manufacturer">Manufacturer</option>
                          <option value="amazon">Amazon</option>
                          <option value="google">Google Images</option>
                          <option value="retailer">Other retailer</option>
                          <option value="manual">Manual</option>
                        </select>
                        <input value={newReferenceUrl} onChange={event => setNewReferenceUrl(event.target.value)} placeholder="Paste an additional direct picture URL" className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200" />
                        <Button type="button" variant="outline" onClick={addReferenceCandidate} className="cursor-pointer"><Plus className="mr-1 h-4 w-4" /> Add</Button>
                      </div>
                      <div className="mt-3 rounded-md border border-dashed border-cyan-500/40 bg-cyan-500/5 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-medium text-cyan-100">Upload your own reference pictures</p>
                            <p className="mt-1 text-[11px] text-slate-400">JPG, PNG or WebP, up to 15 MB each. Uploaded pictures join the gallery above.</p>
                          </div>
                          <label className={`inline-flex items-center rounded-md border border-cyan-500/50 px-3 py-2 text-xs font-medium text-cyan-100 hover:bg-cyan-500/10 ${referenceBusy ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}>
                            <Upload className="mr-2 h-4 w-4" /> Choose pictures
                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/webp"
                              multiple
                              className="sr-only"
                              disabled={referenceBusy}
                              onChange={event => {
                                void uploadReferenceCandidates(caseItem.id, event.target.files);
                                event.target.value = "";
                              }}
                            />
                          </label>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button type="button" onClick={() => void approveReferences(caseItem.id)} disabled={referenceBusy || !referenceData.sourcing_ready || selectedReferences.length !== 4} className="cursor-pointer bg-cyan-700 hover:bg-cyan-600">
                          <Check className="mr-2 h-4 w-4" /> Approve these 4 pictures
                        </Button>
                        <Button type="button" onClick={() => void generateFromApprovedReferences(caseItem.id)} disabled={referenceBusy || referenceData.approved_selection?.status !== "approved" || selectedReferences.length !== 4} className="cursor-pointer bg-purple-700 hover:bg-purple-600">
                          {generatingCaseId === caseItem.id ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                          {generatingCaseId === caseItem.id ? "Generating — keep this page open" : "Generate draft model"}
                        </Button>
                        {generatedReviewUrl && (
                          <Button type="button" variant="outline" onClick={() => router.push(generatedReviewUrl)} className="cursor-pointer border-emerald-500/50 text-emerald-200">
                            <Eye className="mr-2 h-4 w-4" /> View and approve generated model
                          </Button>
                        )}
                        <span className="text-xs text-slate-400">{selectedReferences.length}/4 selected</span>
                        {caseItem.source_url && <a href={caseItem.source_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center text-xs text-cyan-300 hover:text-cyan-200">Product page <ExternalLink className="ml-1 h-3 w-3" /></a>}
                      </div>
                      {referenceNotice && <p className="mt-2 text-xs text-emerald-300" role="status">{referenceNotice}</p>}
                    </section>
                      </td>
                    </tr>
                  )}
              </Fragment>
            ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {evidenceReview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="evidence-review-title"
          onMouseDown={event => {
            if (event.target === event.currentTarget) closeEvidenceReview();
          }}
        >
          <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl border border-slate-700 bg-[#0b121d] shadow-2xl">
            <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-700 bg-[#111b2a] px-5 py-4">
              <div>
                <h2 id="evidence-review-title" className="font-semibold text-slate-100">
                  {evidenceReview.stage === "product_images" ? "Review product images" : evidenceReview.stage === "youtube_video" ? "Review YouTube evidence" : "Review Meshy model"}
                </h2>
                <p className="mt-1 text-xs text-slate-400" title={evidenceReview.caseItem.name}>{compactCaseName(evidenceReview.caseItem)}</p>
              </div>
              <Button type="button" variant="outline" onClick={closeEvidenceReview} className="cursor-pointer">Close</Button>
            </div>

            <div className="p-5">
              {evidenceReview.stage === "product_images" && (
                <>
                  <p className="mb-4 text-sm text-slate-300">Select exactly four images. The first selected image is the texture and colour master.</p>
                  {referenceBusy && !referenceData ? (
                    <div className="flex items-center justify-center py-16 text-slate-400"><RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading images…</div>
                  ) : referenceData?.candidates.length ? (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
                      {referenceData.candidates.map(candidate => {
                        const selectedIndex = selectedReferences.findIndex(item => item.url === candidate.url);
                        return (
                          <button
                            key={candidate.url}
                            type="button"
                            onClick={() => toggleReference(candidate)}
                            className={`relative cursor-pointer overflow-hidden rounded-md border bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 ${selectedIndex >= 0 ? "border-cyan-300 ring-2 ring-cyan-400/40" : "border-slate-700 hover:border-slate-500"}`}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={candidate.url} alt={candidate.label || "Case reference"} className="h-44 w-full object-contain" />
                            {selectedIndex >= 0 && <span className="absolute left-2 top-2 rounded-full bg-cyan-500 px-2 py-1 text-xs font-bold text-slate-950">{selectedIndex + 1}</span>}
                          </button>
                        );
                      })}
                    </div>
                  ) : <p className="py-12 text-center text-slate-500">No candidate images have been recorded.</p>}
                </>
              )}

              {evidenceReview.stage === "youtube_video" && (() => {
                const urls = evidenceUrls(evidenceReview.caseItem.sourcing_3d_evidence?.stages?.youtube_video);
                return urls.length ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {urls.map(url => {
                      const embedUrl = youtubeEmbedUrl(url);
                      return embedUrl ? (
                        <div key={url} className="overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
                          <iframe src={embedUrl} title="Case sourcing video" className="aspect-video w-full" allowFullScreen />
                          <a href={url} target="_blank" rel="noreferrer" className="flex items-center px-3 py-2 text-xs text-cyan-300 hover:text-cyan-200">Open on YouTube <ExternalLink className="ml-1 h-3 w-3" /></a>
                        </div>
                      ) : null;
                    })}
                  </div>
                ) : <p className="py-12 text-center text-slate-500">No YouTube evidence has been recorded.</p>;
              })()}

              {evidenceReview.stage === "meshy_generation" && (
                <div className="space-y-4">
                  <div className="rounded-lg border border-purple-500/30 bg-purple-500/5 p-4 text-sm text-slate-300">
                    <p className="font-medium text-purple-200">Generated model evidence</p>
                    <p className="mt-2 text-xs text-slate-400">Review the generated geometry, textures, scale and publishing rights before approving it.</p>
                    {evidenceUrls(evidenceReview.caseItem.sourcing_3d_evidence?.stages?.meshy_generation).map(url => (
                      <a key={url} href={url} target="_blank" rel="noreferrer" className="mt-2 flex items-center break-all text-xs text-cyan-300 hover:text-cyan-200">{url}<ExternalLink className="ml-1 h-3 w-3 flex-none" /></a>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {evidenceReview.caseItem.sourcing_3d_evidence?.stages?.meshy_generation?.status !== "found" && evidenceReview.caseItem.sourcing_3d_evidence?.stages?.meshy_generation?.status !== "complete" && (
                      <Button
                        type="button"
                        disabled={referenceBusy || referenceData?.approved_selection?.status !== "approved" || selectedReferences.length !== 4}
                        onClick={() => void generateFromApprovedReferences(evidenceReview.caseItem.id)}
                        className="cursor-pointer bg-purple-700 hover:bg-purple-600"
                      >
                        {generatingCaseId === evidenceReview.caseItem.id ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                        {generatingCaseId === evidenceReview.caseItem.id ? "Generating model…" : "Create Meshy draft from approved pictures"}
                      </Button>
                    )}
                    <Button type="button" variant="outline" onClick={() => router.push(generatedReviewUrl || "/components-3d-review")} className="cursor-pointer border-purple-500/40 text-purple-200">
                      <Eye className="mr-2 h-4 w-4" /> Open 3D approval viewer
                    </Button>
                  </div>
                </div>
              )}

              <div className="mt-6 flex flex-wrap items-center justify-end gap-2 border-t border-slate-700 pt-4">
                <Button type="button" variant="outline" disabled={referenceBusy} onClick={() => void decideEvidenceStage("blocked")} className="cursor-pointer border-red-500/50 text-red-200 hover:bg-red-500/10">
                  Decline
                </Button>
                {evidenceReview.stage === "product_images" ? (
                  <Button
                    type="button"
                    disabled={referenceBusy || !referenceData?.sourcing_ready || selectedReferences.length !== 4}
                    onClick={async () => {
                      if (await approveReferences(evidenceReview.caseItem.id)) closeEvidenceReview();
                    }}
                    className="cursor-pointer bg-cyan-700 hover:bg-cyan-600"
                  >
                    <Check className="mr-2 h-4 w-4" /> Approve selected 4 ({selectedReferences.length}/4)
                  </Button>
                ) : (
                  <Button
                    type="button"
                    disabled={referenceBusy || (evidenceReview.stage === "meshy_generation" && !["found", "complete"].includes(evidenceReview.caseItem.sourcing_3d_evidence?.stages?.meshy_generation?.status || ""))}
                    onClick={() => void decideEvidenceStage("complete")}
                    className="cursor-pointer bg-emerald-700 hover:bg-emerald-600"
                  >
                    <Check className="mr-2 h-4 w-4" /> Approve
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* How to use */}
      <Card className="bg-slate-700/20 border-slate-600">
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> How to proceed
          </CardTitle>
        </CardHeader>
        <CardContent className="text-xs text-slate-400 space-y-2">
          <p>
            1. <strong>Search the manufacturer</strong> for official CAD or 3D downloads.
          </p>
          <p>
            2. <strong>Search Sketchfab and other third-party libraries</strong> and verify commercial-use and redistribution rights.
          </p>
          <p>
            3. <strong>Collect Meshy-safe chassis images:</strong> the same empty chassis from clean angles, with its included RGB fans installed and illuminated. Reject populated builds, text/dimension overlays, exploded views, removed panels and conflicting configurations. Keep other useful images only as review references.
          </p>
          <p>
            4. <strong>Use Meshy only as the fallback</strong>, then validate and submit each group of ten for owner approval.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
