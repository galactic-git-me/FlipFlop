"use client";

import { useEffect, useState } from "react";
import { Box, Check, AlertCircle, RefreshCw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
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
  rating?: number;
  review_count?: number;
  sales_velocity?: string;
  keywords?: string[];
  form_factors?: string[];
}

export default function Cases3DPriorityPage() {
  const [cases, setCases] = useState<PriorityCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [completedCount, setCompletedCount] = useState(0);

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
      </div>

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
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-purple-400/10 border border-purple-400/30">
                            <span className="text-sm font-bold text-purple-400">{idx + 1}</span>
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
            1. <strong>Create 3D models</strong> for the priority cases listed above using your mesh allowance.
          </p>
          <p>
            2. <strong>Mark each case as complete</strong> by checking the database (update has_3d_model = true).
          </p>
          <p>
            3. <strong>Refresh this page</strong> to see progress and the next batch.
          </p>
          <p>
            4. <strong>Enable cases in the customer builder</strong> once you have 20-30 models ready.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
