"use client";

import { useEffect, useState, useRef } from "react";
import { Box, Check, AlertCircle, ChevronRight, Zap, HardDrive, Maximize2 } from "lucide-react";
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

function Viewer3D({ glbUrl }: { glbUrl: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !glbUrl) return;

    let animationId: number;

    setTimeout(() => {
      const setupViewer = async () => {
        try {
          const THREE = await import("three");
          const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");

          if (!containerRef.current) return;

          const width = containerRef.current.clientWidth;
          const height = containerRef.current.clientHeight;

          if (width === 0 || height === 0) return;

          // Scene
          const scene = new THREE.Scene();
          scene.background = new THREE.Color(0x0a1119);

          // Camera
          const camera = new THREE.default.PerspectiveCamera(75, width / height, 0.1, 1000);
          camera.position.set(0, 1, 2);

          // Renderer
          const renderer = new THREE.default.WebGLRenderer({ antialias: true, alpha: true });
          renderer.setSize(width, height);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

          // Clear container
          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild);
          }
          containerRef.current.appendChild(renderer.domElement);

          // Lights
          const ambientLight = new THREE.default.AmbientLight(0xffffff, 0.8);
          scene.add(ambientLight);

          const directionalLight = new THREE.default.DirectionalLight(0xffffff, 0.6);
          directionalLight.position.set(5, 8, 5);
          scene.add(directionalLight);

          // Load model
          const loader = new GLTFLoader();
          loader.load(glbUrl, (gltf) => {
            const model = gltf.scene;

            // Scale and center
            const bbox = new THREE.default.Box3().setFromObject(model);
            const center = bbox.getCenter(new THREE.default.Vector3());
            const size = bbox.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 1.5 / maxDim;

            model.position.copy(center).multiplyScalar(-1);
            model.scale.multiplyScalar(scale);
            scene.add(model);

            // Animate
            let rotation = 0;
            const animate = () => {
              animationId = requestAnimationFrame(animate);
              rotation += 0.003;
              model.rotation.y = rotation;
              renderer.render(scene, camera);
            };
            animate();

            sceneRef.current = { scene, renderer, camera, model };
          });
        } catch (error) {
          console.error("3D viewer error:", error);
        }
      };

      setupViewer();
    }, 100);

    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      if (sceneRef.current?.renderer) {
        sceneRef.current.renderer.dispose();
      }
    };
  }, [glbUrl]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full rounded-lg overflow-hidden bg-[#0a1119] border border-[#1e2d45]"
      style={{ minHeight: "380px" }}
    />
  );
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

        // Handle both array and object responses
        const assets = Array.isArray(data) ? data : (data.data || data.assets || []);
        setAssets(assets as Component3DAsset[]);

        // Auto-select first MESHY_DRAFT
        const firstDraft = assets.find((a: Component3DAsset) => a.status === "meshy_draft");
        if (firstDraft) {
          setSelectedAsset(firstDraft);
        }
      } catch (error) {
        console.error("Error loading assets:", error);
        // Note: If backend API returns 404, make sure FastAPI server has reloaded after code changes
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const filteredAssets = filter === "meshy_draft"
    ? assets.filter(a => a.status === "meshy_draft")
    : assets;

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
        if (selectedAsset?.id === assetId) {
          setSelectedAsset(updated);
        }
      }
    } catch (error) {
      console.error("Error updating asset:", error);
    }
  };

  return (
    <div className="p-6 space-y-6 relative overflow-hidden min-h-screen">
      {/* Animated gradient background */}
      <style>{`
        @keyframes gradientShift {
          0% {
            background-position: 0% 50%;
          }
          50% {
            background-position: 100% 50%;
          }
          100% {
            background-position: 0% 50%;
          }
        }

        .animate-gradient-bg {
          background: linear-gradient(
            -45deg,
            #0a1119,
            #1a3a52,
            #ff6b35,
            #0a1119
          );
          background-size: 400% 400%;
          animation: gradientShift 15s ease infinite;
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: -1;
        }
      `}</style>
      <div className="animate-gradient-bg" />

      <div className="relative z-10">
        {/* Header */}
        <div>
        <h1 className="text-lg font-bold text-slate-100">3D Asset Review</h1>
        </div>

        {/* Progress summary - Compact */}
        <div className="grid grid-cols-4 gap-1.5 pb-2 text-center text-xs">
        <div className="bg-orange-400/10 border border-orange-400/30 rounded p-1">
          <div className="text-xl font-bold text-orange-400">{draftCount}</div>
          <div className="text-[10px] text-slate-500">Draft</div>
        </div>
        <div className="bg-purple-400/10 border border-purple-400/30 rounded p-1">
          <div className="text-xl font-bold text-purple-400">{validatedCount}</div>
          <div className="text-[10px] text-slate-500">Valid</div>
        </div>
        <div className="bg-[#00dc82]/10 border border-[#00dc82]/30 rounded p-1">
          <div className="text-xl font-bold text-[#00dc82]">{finalCount}</div>
          <div className="text-[10px] text-slate-500">Final</div>
        </div>
        <div className="bg-slate-600/10 border border-slate-600/30 rounded p-1">
          <div className="text-xl font-bold text-slate-300">{assets.length}</div>
          <div className="text-[10px] text-slate-500">Total</div>
        </div>
      </div>

        {/* Filters */}
        <div className="flex gap-1">
          <button
            onClick={() => setFilter("meshy_draft")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
              filter === "meshy_draft"
                ? "bg-orange-600/30 text-orange-300 border border-orange-500/50"
                : "bg-slate-700/30 text-slate-400 border border-slate-600/50"
            }`}
          >
            Review ({draftCount})
          </button>
          <button
            onClick={() => setFilter("all")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
              filter === "all"
                ? "bg-purple-600/30 text-purple-300 border border-purple-500/50"
                : "bg-slate-700/30 text-slate-400 border border-slate-600/50"
            }`}
          >
            All ({assets.length})
          </button>
        </div>

        {/* Main layout: grid + viewer - Full height */}
        <div className="grid grid-cols-6 gap-3 flex-1 min-h-0">
          {/* Asset list - Grid of squares */}
          <div className="col-span-1 flex flex-col min-h-0">
            <div className="grid grid-cols-2 gap-2 overflow-y-auto flex-1">
              {loading ? (
                <div className="text-center py-8 text-slate-500 text-xs col-span-2">
                  Loading...
                </div>
              ) : filteredAssets.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-xs">
                  <Check className="w-4 h-4 mx-auto mb-2 text-[#00dc82]" />
                  No {filter === "meshy_draft" ? "draft" : ""} assets
                </div>
              ) : (
                filteredAssets.map((asset) => {
                  const statusColors = {
                    missing: "border-slate-600 bg-slate-900/20",
                    meshy_draft: "border-orange-400/30 bg-orange-400/5",
                    cleaned: "border-blue-400/30 bg-blue-400/5",
                    validated: "border-purple-400/30 bg-purple-400/5",
                    final: "border-[#00dc82]/30 bg-[#00dc82]/5",
                    rejected: "border-red-400/30 bg-red-400/5",
                  };

                  const statusIcons = {
                    missing: "?",
                    meshy_draft: "🔄",
                    cleaned: "✨",
                    validated: "✓",
                    final: "🎉",
                    rejected: "✗",
                  };

                  const bgImage = asset.preview_image_ref
                    ? `url('${asset.preview_image_ref}')`
                    : "none";

                  return (
                    <button
                      key={asset.id}
                      onClick={() => setSelectedAsset(asset)}
                      className={`aspect-square w-full rounded-lg border transition-all flex flex-col items-center justify-center p-2 text-center relative overflow-hidden group ${
                        selectedAsset?.id === asset.id
                          ? "border-purple-400/70 ring-2 ring-purple-400/50 shadow-lg shadow-purple-400/50"
                          : "border-slate-600 shadow-lg shadow-black/50 hover:shadow-xl hover:shadow-black/70"
                      }`}
                      style={{
                        backgroundImage: bgImage,
                        backgroundSize: "cover",
                        backgroundPosition: "center",
                      }}
                    >
                      {/* Overlay gradient for readability */}
                      <div className="absolute inset-0 bg-gradient-to-b from-black/30 via-black/50 to-black/70" />

                      {/* Content */}
                      <div className="relative z-10 flex flex-col items-center justify-center h-full w-full">
                        <div className="text-2xl mb-1">{statusIcons[asset.status]}</div>
                        <div className="text-[10px] font-bold text-white truncate w-full">
                          {asset.family_key?.split("_")[1] || asset.family_key}
                        </div>
                        <div className="text-[8px] text-slate-300 mt-0.5">{asset.category}</div>
                        {asset.file_size_kb && (
                          <div className="text-[8px] text-slate-400 mt-1">
                            {Math.round(asset.file_size_kb / 1024)}MB
                          </div>
                        )}
                        {asset.status === "meshy_draft" && (
                          <div className="text-[8px] text-orange-300 mt-1 font-semibold">REVIEW</div>
                        )}
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Detail viewer */}
          <div className="col-span-5 flex flex-col min-h-0">
          {selectedAsset ? (
            <div className="flex flex-col gap-2 flex-1 min-h-0 overflow-y-auto">
              {/* 3D Viewer */}
              <div className="border border-[#1e2d45] rounded-lg overflow-hidden flex-1 min-h-0 flex flex-col">
                <div className="px-3 py-2 border-b border-[#1e2d45] bg-slate-900/30 flex-shrink-0">
                  <div className="text-xs font-semibold text-slate-300">3D Viewer</div>
                </div>
                <div className="flex-1 min-h-0 bg-[#0a1119]">
                  {selectedAsset.glb_ref ? (
                    <Viewer3D glbUrl={selectedAsset.glb_ref} />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-500">
                      <div className="text-center">
                        <Box className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        <p className="text-xs">No 3D model</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Asset details */}
              <Card className="border-[#1e2d45]">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-sm">{selectedAsset.family_key}</CardTitle>
                      <p className="text-xs text-slate-500 mt-1">ID: {selectedAsset.id} v{selectedAsset.version}</p>
                    </div>
                    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold ${
                      selectedAsset.status === "meshy_draft" ? "bg-orange-400/20 text-orange-300 border border-orange-400/50" :
                      selectedAsset.status === "validated" ? "bg-purple-400/20 text-purple-300 border border-purple-400/50" :
                      selectedAsset.status === "final" ? "bg-[#00dc82]/20 text-[#00dc82] border border-[#00dc82]/50" :
                      "bg-slate-600/20 text-slate-300 border border-slate-600/50"
                    }`}>
                      {selectedAsset.status.toUpperCase()}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Info grid */}
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <p className="text-slate-500">Category</p>
                      <p className="text-slate-100 font-semibold">{selectedAsset.category}</p>
                    </div>
                    <div>
                      <p className="text-slate-500">Version</p>
                      <p className="text-slate-100 font-semibold">v{selectedAsset.version}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 flex items-center gap-1">
                        <HardDrive className="w-3 h-3" /> File Size
                      </p>
                      <p className="text-slate-100 font-semibold">
                        {selectedAsset.file_size_kb ? `${Math.round(selectedAsset.file_size_kb / 1024)}MB` : "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-slate-500 flex items-center gap-1">
                        <Maximize2 className="w-3 h-3" /> Polygons
                      </p>
                      <p className="text-slate-100 font-semibold">
                        {selectedAsset.poly_count ? (selectedAsset.poly_count / 1000).toFixed(1) + "k" : "TBD"}
                      </p>
                    </div>
                  </div>

                  {/* Notes */}
                  {selectedAsset.notes && (
                    <div className="p-2 bg-slate-700/30 rounded border border-slate-600 text-xs text-slate-300">
                      <p className="text-slate-500 text-[10px] mb-1 uppercase">Notes</p>
                      {selectedAsset.notes}
                    </div>
                  )}

                  {/* GLB link */}
                  {selectedAsset.glb_ref && (
                    <div className="p-2 bg-blue-900/20 rounded border border-blue-400/20">
                      <p className="text-slate-500 text-xs mb-1">GLB File</p>
                      <a
                        href={selectedAsset.glb_ref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:text-blue-300 break-all flex items-center gap-1"
                      >
                        <Zap className="w-3 h-3 flex-shrink-0" />
                        Download / View
                      </a>
                    </div>
                  )}

                  {/* Created info */}
                  {selectedAsset.created_by && (
                    <div className="text-[10px] text-slate-600">
                      Created by {selectedAsset.created_by}
                      {selectedAsset.created_at && ` on ${new Date(selectedAsset.created_at).toLocaleDateString()}`}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Review actions */}
              {selectedAsset.status === "meshy_draft" && (
                <Card className="border-orange-400/30 bg-orange-400/5">
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-orange-400" /> Ready to review
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-slate-400">
                      Quality checklist: Is the geometry correct? Scale accurate? Textures good? No major errors?
                    </p>
                    <div className="flex gap-2">
                      <Button
                        onClick={() => handleStatusChange(selectedAsset.id, "rejected")}
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                      >
                        Reject (Rework)
                      </Button>
                      <Button
                        onClick={() => handleStatusChange(selectedAsset.id, "cleaned")}
                        size="sm"
                        className="flex-1 bg-blue-600 hover:bg-blue-700"
                      >
                        Cleaned ✨
                      </Button>
                      <Button
                        onClick={() => handleStatusChange(selectedAsset.id, "validated")}
                        size="sm"
                        className="flex-1 bg-purple-600 hover:bg-purple-700"
                      >
                        Validated ✓
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )}

              {selectedAsset.status === "validated" && (
                <Card className="border-purple-400/30 bg-purple-400/5">
                  <CardHeader>
                    <CardTitle className="text-sm">Approved for Production</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-xs text-slate-400">
                      ✓ Scale & orientation checked
                    </p>
                    <Button
                      onClick={() => handleStatusChange(selectedAsset.id, "final")}
                      size="sm"
                      className="w-full bg-[#00dc82] hover:bg-[#00dc82]/90 text-black"
                    >
                      Mark as Final 🎉
                    </Button>
                  </CardContent>
                </Card>
              )}

              {selectedAsset.status === "final" && (
                <Card className="border-[#00dc82]/30 bg-[#00dc82]/5">
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Check className="w-4 h-4 text-[#00dc82]" /> Production Ready
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-[#00dc82]">
                      ✓ This asset is live and can be served to customers.
                    </p>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-500">
              <Box className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>Select an asset to review</p>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
