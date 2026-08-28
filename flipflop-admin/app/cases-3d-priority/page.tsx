"use client";

import { useEffect, useState } from "react";
import { Box, Check, AlertCircle, RefreshCw, LockKeyhole } from "lucide-react";
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
                    </div>
                  </div>
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
