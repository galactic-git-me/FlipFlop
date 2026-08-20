"use client";

import React, { useEffect, useState } from "react";
import { Box } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface Component3DAsset {
  id: number;
  category: string;
  family_key: string;
  status: "missing" | "meshy_draft" | "cleaned" | "validated" | "final" | "rejected";
  version: number;
  glb_ref: string | null;
  preview_image_ref: string | null;
  file_size_kb: number | null;
  poly_count: number | null;
  notes: string | null;
  created_by: string | null;
  created_at: string | null;
}

export default function Components3DReviewPage() {
  const [assets, setAssets] = useState<Component3DAsset[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAsset, setSelectedAsset] = useState<Component3DAsset | null>(null);
  const [filter, setFilter] = useState<"meshy_draft" | "all">("meshy_draft");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch("/api/assets-3d");
        const data = await response.json();
        const assets = Array.isArray(data) ? data : (data.data || data.assets || []);
        setAssets(assets as Component3DAsset[]);
        const firstDraft = assets.find((a: Component3DAsset) => a.status === "meshy_draft");
        if (firstDraft) setSelectedAsset(firstDraft);
      } catch (error) {
        console.error("Error loading assets:", error);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const filteredAssets = filter === "meshy_draft" ? assets.filter(a => a.status === "meshy_draft") : assets;
  const draftCount = assets.filter(a => a.status === "meshy_draft").length;
  const validatedCount = assets.filter(a => a.status === "validated").length;
  const finalCount = assets.filter(a => a.status === "final").length;

  const handleStatusChange = async (assetId: number, newStatus: string) => {
    try {
      const response = await fetch(`/api/assets-3d/${assetId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: newStatus,
          commercial_use_approved: newStatus === "validated" || newStatus === "final",
          redistribution_approved: newStatus === "validated" || newStatus === "final",
        }),
      });
      if (response.ok) {
        const updated = (await response.json()) as Component3DAsset;
        setAssets(prev => prev.map(a => a.id === assetId ? updated : a));
        if (selectedAsset?.id === assetId) setSelectedAsset(updated);
      }
    } catch (error) {
      console.error("Error updating asset:", error);
    }
  };

  const statusColors: Record<string, string> = {
    missing: "border-slate-600 bg-slate-900/20",
    meshy_draft: "border-orange-400/30 bg-orange-400/5",
    cleaned: "border-blue-400/30 bg-blue-400/5",
    validated: "border-purple-400/30 bg-purple-400/5",
    final: "border-[#00dc82]/30 bg-[#00dc82]/5",
    rejected: "border-red-400/30 bg-red-400/5",
  };

  const getStatusStyle = (status: string) => {
    if (status === "meshy_draft") return "bg-orange-400/20 text-orange-300 border border-orange-400/50";
    if (status === "validated") return "bg-purple-400/20 text-purple-300 border border-purple-400/50";
    if (status === "final") return "bg-[#00dc82]/20 text-[#00dc82] border border-[#00dc82]/50";
    return "bg-slate-600/20 text-slate-300 border border-slate-600/50";
  };

  return (
    <div className="w-full h-full flex flex-col gap-3 p-4">
      <div>
        <h1 className="text-lg font-bold text-slate-100">3D Asset Review</h1>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="bg-gradient-to-br from-orange-500/20 to-orange-900/20 border border-orange-400/40 rounded-lg p-4">
          <div className="text-3xl font-bold text-orange-400 mb-1">{draftCount}</div>
          <div className="text-xs text-orange-300/70">Draft</div>
        </div>
        <div className="bg-gradient-to-br from-purple-500/20 to-purple-900/20 border border-purple-400/40 rounded-lg p-4">
          <div className="text-3xl font-bold text-purple-400 mb-1">{validatedCount}</div>
          <div className="text-xs text-purple-300/70">Valid</div>
        </div>
        <div className="bg-gradient-to-br from-[#00dc82]/20 to-green-900/20 border border-[#00dc82]/40 rounded-lg p-4">
          <div className="text-3xl font-bold text-[#00dc82] mb-1">{finalCount}</div>
          <div className="text-xs text-[#00dc82]/70">Final</div>
        </div>
        <div className="bg-gradient-to-br from-slate-500/20 to-slate-900/20 border border-slate-400/40 rounded-lg p-4">
          <div className="text-3xl font-bold text-slate-300 mb-1">{assets.length}</div>
          <div className="text-xs text-slate-400/70">Total</div>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setFilter("meshy_draft")}
          className={filter === "meshy_draft" ? "px-2 py-1 rounded text-xs font-semibold bg-orange-600/30 text-orange-300 border border-orange-500/50" : "px-2 py-1 rounded text-xs font-semibold bg-slate-700/30 text-slate-400 border border-slate-600/50"}
        >
          Review ({draftCount})
        </button>
        <button
          onClick={() => setFilter("all")}
          className={filter === "all" ? "px-2 py-1 rounded text-xs font-semibold bg-purple-600/30 text-purple-300 border border-purple-500/50" : "px-2 py-1 rounded text-xs font-semibold bg-slate-700/30 text-slate-400 border border-slate-600/50"}
        >
          All ({assets.length})
        </button>
      </div>

      <div className="flex gap-3 flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-h-0 gap-3">
          {selectedAsset ? (
            <>
              <div className="border border-[#1e2d45] rounded-lg overflow-hidden flex-1 flex flex-col bg-[#0a1119]">
                <div className="px-3 py-2 border-b border-[#1e2d45] bg-slate-900/30 text-xs font-semibold text-slate-300">Preview</div>
                <div className="flex-1 min-h-0 flex items-center justify-center">
                  {selectedAsset.preview_image_ref ? (
                    <img src={selectedAsset.preview_image_ref} alt={selectedAsset.family_key} className="w-full h-full object-contain" />
                  ) : (
                    <div className="text-center text-slate-500">
                      <Box className="w-8 h-8 mx-auto mb-2 opacity-30" />
                      <p className="text-xs">No preview available</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex-1 border border-[#1e2d45] rounded-lg overflow-y-auto p-2 bg-[#0a1119]">
                <div className="grid grid-cols-6 gap-2">
                  {filteredAssets.map((asset) => (
                    <button
                      key={asset.id}
                      onClick={() => setSelectedAsset(asset)}
                      className={`aspect-square rounded border overflow-hidden cursor-pointer transition hover:scale-105 ${selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""} ${statusColors[asset.status] || ""}`}
                      style={{ backgroundImage: asset.preview_image_ref ? `url('${asset.preview_image_ref}')` : undefined, backgroundSize: "cover", backgroundPosition: "center" }}
                    >
                      <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <div className="font-bold text-[8px] text-white text-center">{asset.family_key}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center flex-1 text-slate-500">
              <div className="text-center">
                <Box className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Select an asset to review</p>
              </div>
            </div>
          )}
        </div>

        {selectedAsset && (
          <div className="w-96 flex flex-col min-h-0 overflow-y-auto">
            <Card className="border-[#1e2d45]">
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-sm">{selectedAsset.family_key}</CardTitle>
                    <p className="text-xs text-slate-500 mt-1">ID: {selectedAsset.id} v{selectedAsset.version}</p>
                  </div>
                  <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${getStatusStyle(selectedAsset.status)}`}>
                    {selectedAsset.status.toUpperCase()}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-slate-500">Category</p>
                    <p className="text-slate-100 font-semibold">{selectedAsset.category}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Version</p>
                    <p className="text-slate-100 font-semibold">v{selectedAsset.version}</p>
                  </div>
                  {selectedAsset.file_size_kb && (
                    <div>
                      <p className="text-slate-500">File Size</p>
                      <p className="text-slate-100 font-semibold">{Math.round(selectedAsset.file_size_kb / 1024)}MB</p>
                    </div>
                  )}
                  {selectedAsset.poly_count && (
                    <div>
                      <p className="text-slate-500">Polygons</p>
                      <p className="text-slate-100 font-semibold">{(selectedAsset.poly_count / 1000).toFixed(1)}k</p>
                    </div>
                  )}
                </div>
                {selectedAsset.notes && (
                  <div className="p-2 bg-slate-700/30 rounded border border-slate-600 text-xs text-slate-300">
                    <p className="text-slate-500 text-[10px] mb-1 uppercase">Notes</p>
                    {selectedAsset.notes}
                  </div>
                )}
                {selectedAsset.glb_ref && (
                  <div className="p-2 bg-blue-900/20 rounded border border-blue-400/20">
                    <p className="text-slate-500 text-xs mb-1">GLB File</p>
                    <a href={selectedAsset.glb_ref} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:text-blue-300 break-all">
                      Download / View
                    </a>
                  </div>
                )}
                {selectedAsset.created_by && (
                  <div className="text-[10px] text-slate-600">
                    Created by {selectedAsset.created_by}
                    {selectedAsset.created_at && ` on ${new Date(selectedAsset.created_at).toLocaleDateString()}`}
                  </div>
                )}
                {selectedAsset.status === "meshy_draft" && (
                  <div className="flex gap-2 pt-2">
                    <Button onClick={() => handleStatusChange(selectedAsset.id, "rejected")} variant="secondary" size="sm" className="flex-1">Reject</Button>
                    <Button onClick={() => handleStatusChange(selectedAsset.id, "cleaned")} size="sm" className="flex-1 bg-blue-600 hover:bg-blue-700">Cleaned</Button>
                    <Button onClick={() => handleStatusChange(selectedAsset.id, "validated")} size="sm" className="flex-1 bg-purple-600 hover:bg-purple-700">Validate</Button>
                  </div>
                )}
                {selectedAsset.status === "validated" && (
                  <Button onClick={() => handleStatusChange(selectedAsset.id, "final")} size="sm" className="w-full bg-[#00dc82] hover:bg-[#00dc82]/90 text-black">Mark as Final</Button>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
