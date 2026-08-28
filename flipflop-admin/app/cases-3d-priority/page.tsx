"use client";

import { useEffect, useState } from "react";
import { Box, Check, AlertCircle, RefreshCw, LockKeyhole, Images, Plus, Sparkles, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatCurrency } from "@/lib/utils";

interface PriorityCaseItem {
  id: number;
  name: string;
  brand?: string;
  model?: string;
  price: number;
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
  sourcing_3d_evidence?: {
    stages?: Record<string, { status?: string; attempts?: Array<{ provider?: string; source_url?: string }> }>;
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

const sourcingLabels: Array<[string, string]> = [
  ["manufacturer_3d", "Maker 3D"],
  ["third_party_3d", "Sketchfab / 3rd party"],
  ["product_images", "Images"],
  ["youtube_video", "YouTube"],
  ["meshy_generation", "Meshy"],
  ["validation", "Validation"],
];

function statusColour(status = "not_started") {
  if (["found", "complete"].includes(status)) return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  if (["searching", "blocked"].includes(status)) return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  if (status === "not_found") return "border-slate-600 bg-slate-800 text-slate-400";
  return "border-slate-700 bg-slate-900 text-slate-500";
}

export default function Cases3DPriorityPage() {
  const [cases, setCases] = useState<PriorityCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [completedCount, setCompletedCount] = useState(0);
  const [freezing, setFreezing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [referenceCaseId, setReferenceCaseId] = useState<number | null>(null);
  const [referenceData, setReferenceData] = useState<ReferenceCandidateResponse | null>(null);
  const [selectedReferences, setSelectedReferences] = useState<ReferenceCandidate[]>([]);
  const [referenceBusy, setReferenceBusy] = useState(false);
  const [referenceNotice, setReferenceNotice] = useState<string | null>(null);
  const [newReferenceUrl, setNewReferenceUrl] = useState("");
  const [newReferenceSource, setNewReferenceSource] = useState<ReferenceSource>("manufacturer");

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
      const data = await response.json() as ReferenceCandidateResponse & { detail?: string };
      if (!response.ok) throw new Error(data.detail || "Could not load reference pictures");
      setReferenceCaseId(caseId);
      setReferenceData(data);
      setSelectedReferences(data.approved_selection?.images || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load reference pictures");
    } finally {
      setReferenceBusy(false);
    }
  };

  const toggleReference = (candidate: ReferenceCandidate) => {
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
        candidates: [...referenceData.candidates, { url, source: newReferenceSource, label: "Manually added reference" }],
      });
      setNewReferenceUrl("");
    } catch {
      setError("Enter a complete http:// or https:// picture URL");
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
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not approve reference pictures");
      setCases(current => current.map(item => item.id === caseId ? data : item));
      setReferenceData(current => current ? { ...current, approved_selection: { status: "approved", images: selectedReferences } } : current);
      setReferenceNotice("Four reference pictures approved. Picture 1 is the texture and colour master.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not approve reference pictures");
    } finally {
      setReferenceBusy(false);
    }
  };

  const generateFromApprovedReferences = async (caseId: number) => {
    if (selectedReferences.length !== 4 || referenceData?.approved_selection?.status !== "approved") return;
    setReferenceBusy(true);
    setError(null);
    setReferenceNotice("Generating the textured model. This can take several minutes…");
    try {
      const response = await fetch(`/api/assets-3d/cases/${caseId}/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          image_urls: selectedReferences.map(item => item.url),
          notes: "Generated only from the separately owner-approved four-picture set. Preserve the first picture as the texture and colour master; match case finish and illuminated RGB faithfully.",
        }),
      });
      const asset = await response.json();
      if (!response.ok) throw new Error(asset.detail || "3D generation failed");
      const batchResponse = await fetch("/api/assets-3d/review-batches", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ asset_ids: [asset.id] }),
      });
      const batch = await batchResponse.json();
      if (!batchResponse.ok) throw new Error(batch.detail || "Model generated, but its review batch could not be created");
      window.location.assign(`/components-3d-review?batch=${batch.batch_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "3D generation failed");
      setReferenceNotice(null);
    } finally {
      setReferenceBusy(false);
    }
  };

  const freezeCampaign = async () => {
    setFreezing(true);
    setError(null);
    try {
      const response = await fetch("/api/cases/priority-for-3d", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not freeze campaign");
      setCases(data.cases || []);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not freeze campaign");
    } finally {
      setFreezing(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        // Fetch priority cases for 3D modeling (top 30)
        const response = await fetch("/api/cases/priority-for-3d?limit=30");
        const data = (await response.json()) as PriorityCaseItem[];
        setCases(data);

        // Count how many already have models
        const withModels = await fetch("/api/cases/with-3d-models?limit=1000");
        const completed = (await withModels.json()) as PriorityCaseItem[];
        setCompletedCount(completed.length);
      } catch (error) {
        console.error("Error loading cases:", error);
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Box className="w-6 h-6 text-purple-400" /> 3D Model Priority Queue
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Top 30 popular cases to create 3D models for. Ranked by Amazon bestseller position.
          </p>
        </div>
        <Button onClick={freezeCampaign} disabled={freezing || cases.some(item => item.priority_3d_rank)} className="cursor-pointer focus-visible:ring-2 focus-visible:ring-cyan-300">
          {freezing ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <LockKeyhole className="mr-2 h-4 w-4" />}
          {cases.some(item => item.priority_3d_rank) ? "Top 30 frozen" : "Freeze top 30"}
        </Button>
      </div>
      {error && <div role="alert" className="rounded-md border border-red-500/60 bg-red-950/60 px-4 py-3 text-sm text-red-200">{error}</div>}

      {/* Progress summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Models Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#00dc82]">{completedCount}</div>
            <p className="text-xs text-slate-500 mt-1">cases with 3D models ready</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Priority Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-cyan-400">{cases.length}</div>
            <p className="text-xs text-slate-500 mt-1">waiting for 3D models</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Total Available</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">{completedCount + cases.length}</div>
            <p className="text-xs text-slate-500 mt-1">cases in catalogue</p>
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
          <p className="text-xs text-slate-500 uppercase">Next to create (prioritized by popularity):</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {cases.map((caseItem, idx) => (
              <Card key={caseItem.id} className="border-[#1e2d45] hover:border-[#2a3f5a] transition-colors">
                <CardContent className="pt-4">
                  <div className="flex gap-4">
                    {/* Image */}
                    {caseItem.image_url && (
                      <div className="w-24 h-24 rounded-lg overflow-hidden flex-shrink-0 bg-[#0a1119]">
                        <img
                          src={caseItem.image_url}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      </div>
                    )}

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="min-w-0">
                          <h3 className="font-semibold text-slate-100 text-sm line-clamp-2">
                            {caseItem.name}
                          </h3>
                          <p className="text-xs text-slate-500 mt-0.5">
                            #{caseItem.bestseller_rank ? caseItem.bestseller_rank : "—"} bestseller
                            {caseItem.priority_3d_batch ? ` · Batch ${caseItem.priority_3d_batch}` : ""}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-purple-400/10 border border-purple-400/30">
                            <span className="text-sm font-bold text-purple-400">{caseItem.priority_3d_rank || idx + 1}</span>
                          </div>
                        </div>
                      </div>

                      {/* Stats */}
                      <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                        <div>
                          <span className="text-slate-600">Price:</span>
                          <div className="font-semibold text-[#00dc82]">{formatCurrency(caseItem.price)}</div>
                        </div>
                        {caseItem.rating && (
                          <div>
                            <span className="text-slate-600">Rating:</span>
                            <div className="font-semibold text-amber-400">{caseItem.rating.toFixed(1)}★</div>
                          </div>
                        )}
                      </div>

                      {/* Keywords */}
                      {caseItem.keywords && caseItem.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {caseItem.keywords.slice(0, 2).map((kw) => (
                            <span
                              key={kw}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-300"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="mt-3 flex flex-wrap gap-1.5" aria-label="3D sourcing progress">
                        {sourcingLabels.map(([key, label]) => {
                          const status = caseItem.sourcing_3d_evidence?.stages?.[key]?.status || "not_started";
                          return (
                            <span key={key} title={`${label}: ${status.replaceAll("_", " ")}`} className={`rounded border px-1.5 py-0.5 text-[10px] ${statusColour(status)}`}>
                              {label}: {status.replaceAll("_", " ")}
                            </span>
                          );
                        })}
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        className="mt-3 w-full cursor-pointer border-cyan-500/40 text-cyan-200 hover:bg-cyan-500/10"
                        onClick={() => void openReferenceSelection(caseItem.id)}
                        disabled={referenceBusy}
                      >
                        <Images className="mr-2 h-4 w-4" />
                        {referenceCaseId === caseItem.id ? "Close picture selection" : "Review source pictures"}
                      </Button>
                    </div>
                  </div>

                  {referenceCaseId === caseItem.id && referenceData && (
                    <section className="mt-4 border-t border-slate-700 pt-4" aria-label={`Reference picture approval for ${caseItem.name}`}>
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
                              className={`relative cursor-pointer overflow-hidden rounded-md border text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-300 ${selectedIndex >= 0 ? "border-cyan-300 ring-2 ring-cyan-400/40" : "border-slate-700 hover:border-slate-500"}`}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={candidate.url} alt="" className="h-36 w-full bg-white object-contain" />
                              {selectedIndex >= 0 && <span className="absolute left-2 top-2 rounded-full bg-cyan-500 px-2 py-1 text-xs font-bold text-slate-950">{selectedIndex + 1}</span>}
                              <span className="block truncate bg-slate-950 px-2 py-1 text-[10px] uppercase text-slate-300">{candidate.source}{selectedIndex === 0 ? " · texture master" : ""}</span>
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
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <Button type="button" onClick={() => void approveReferences(caseItem.id)} disabled={referenceBusy || !referenceData.sourcing_ready || selectedReferences.length !== 4} className="cursor-pointer bg-cyan-700 hover:bg-cyan-600">
                          <Check className="mr-2 h-4 w-4" /> Approve these 4 pictures
                        </Button>
                        <Button type="button" onClick={() => void generateFromApprovedReferences(caseItem.id)} disabled={referenceBusy || referenceData.approved_selection?.status !== "approved" || selectedReferences.length !== 4} className="cursor-pointer bg-purple-700 hover:bg-purple-600">
                          {referenceBusy ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />} Generate draft model
                        </Button>
                        <span className="text-xs text-slate-400">{selectedReferences.length}/4 selected</span>
                        {caseItem.source_url && <a href={caseItem.source_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center text-xs text-cyan-300 hover:text-cyan-200">Product page <ExternalLink className="ml-1 h-3 w-3" /></a>}
                      </div>
                      {referenceNotice && <p className="mt-2 text-xs text-emerald-300" role="status">{referenceNotice}</p>}
                    </section>
                  )}
                </CardContent>
              </Card>
            ))}
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
