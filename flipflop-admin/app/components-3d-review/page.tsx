"use client";

import { useEffect, useState, useRef } from "react";
import { Box, Check, AlertCircle, RefreshCw, ChevronRight, Zap, HardDrive, Maximize2 } from "lucide-react";
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
  const rendererRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !glbUrl) return;

    let animationId: number;

    const loadScene = async () => {
      try {
        // Dynamic imports
        const THREE = (await import("three")).default;
        const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");

        if (!containerRef.current) return;

        const width = containerRef.current.clientWidth;
        const height = containerRef.current.clientHeight;

        // Scene setup
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0a1119);
        scene.add(new THREE.GridHelper(10, 10, 0x444444, 0x222222));

        const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        camera.position.set(0, 1.5, 2.5);
        camera.lookAt(0, 0.5, 0);

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(width, height);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;

        // Clear previous content
        while (containerRef.current.firstChild) {
          containerRef.current.removeChild(containerRef.current.firstChild);
        }
        containerRef.current.appendChild(renderer.domElement);
        rendererRef.current = renderer;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.9);
        directionalLight.position.set(5, 10, 5);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        // Load GLB
        const loader = new GLTFLoader();
        loader.load(
          glbUrl,
          (gltf) => {
            const model = gltf.scene;

            // Center and scale model
            const bbox = new THREE.Box3().setFromObject(model);
            const center = bbox.getCenter(new THREE.Vector3());
            const size = bbox.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 2 / maxDim;

            model.position.copy(center).multiplyScalar(-1);
            model.scale.multiplyScalar(scale);
            scene.add(model);

            // Auto-rotate animation
            let rotation = 0;
            const animate = () => {
              animationId = requestAnimationFrame(animate);
              rotation += 0.005;
              model.rotation.y = rotation;
              renderer.render(scene, camera);
            };
            animate();
          },
          undefined,
          (error) => {
            console.error("Error loading GLB:", error);
          }
        );

        // Handle window resize
        const handleResize = () => {
          if (!containerRef.current) return;
          const w = containerRef.current.clientWidth;
          const h = containerRef.current.clientHeight;
          camera.aspect = w / h;
          camera.updateProjectionMatrix();
          renderer.setSize(w, h);
        };

        window.addEventListener("resize", handleResize);

        return () => {
          window.removeEventListener("resize", handleResize);
          if (animationId) cancelAnimationFrame(animationId);
          renderer.dispose();
          if (containerRef.current && renderer.domElement.parentNode === containerRef.current) {
            containerRef.current.removeChild(renderer.domElement);
          }
        };
      } catch (error) {
        console.error("Error setting up 3D viewer:", error);
      }
    };

    const cleanup = loadScene();
    return () => {
      cleanup?.then((f) => f?.());
    };
  }, [glbUrl]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full rounded-lg overflow-hidden bg-[#0a1119] border border-[#1e2d45]"
      style={{ minHeight: "500px" }}
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
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <Box className="w-6 h-6 text-purple-400" /> Component 3D Asset Review
        </h1>
          <p className="text-sm text-slate-500 mt-1">
            Review Meshy-generated models. Approve for production or reject for rework.
          </p>
        </div>

        {/* Progress summary */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Draft (Review)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-orange-400">{draftCount}</div>
            <p className="text-xs text-slate-500 mt-1">awaiting review</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Validated</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-purple-400">{validatedCount}</div>
            <p className="text-xs text-slate-500 mt-1">scale/orientation checked</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Final</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-[#00dc82]">{finalCount}</div>
            <p className="text-xs text-slate-500 mt-1">ready for production</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-slate-500 uppercase">Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-300">{assets.length}</div>
            <p className="text-xs text-slate-500 mt-1">all assets</p>
          </CardContent>
        </Card>
      </div>

        {/* Filter tabs */}
        <div className="flex gap-2">
        <button
          onClick={() => setFilter("meshy_draft")}
          className={`px-4 py-2 rounded text-xs font-semibold transition-colors ${
            filter === "meshy_draft"
              ? "bg-orange-600/30 text-orange-300 border border-orange-500/50"
              : "bg-slate-700/30 text-slate-400 border border-slate-600/50 hover:border-slate-500"
          }`}
        >
          Review Queue ({draftCount})
        </button>
        <button
          onClick={() => setFilter("all")}
          className={`px-4 py-2 rounded text-xs font-semibold transition-colors ${
            filter === "all"
              ? "bg-purple-600/30 text-purple-300 border border-purple-500/50"
              : "bg-slate-700/30 text-slate-400 border border-slate-600/50 hover:border-slate-500"
          }`}
        >
          All Assets ({assets.length})
        </button>
      </div>

        {/* Main layout: list + viewer */}
        <div className="grid grid-cols-1 lg:grid-cols-6 gap-6">
        {/* Asset list - Grid of squares */}
        <div className="lg:col-span-1">
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold text-slate-100 px-1">Assets ({filteredAssets.length})</h3>
            <div className="grid grid-cols-2 gap-2 max-h-[calc(100vh-300px)] overflow-y-auto pr-2">
              {loading ? (
                <div className="text-center py-8 text-slate-500">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2" />
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
        </div>

        {/* Detail viewer */}
        <div className="lg:col-span-5">
          {selectedAsset ? (
            <div className="space-y-4">
              {/* 3D Viewer */}
              <Card className="border-[#1e2d45]">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm">3D Model Viewer</CardTitle>
                    {selectedAsset.glb_ref && (
                      <span className="text-[10px] text-slate-500">Auto-rotating • Scroll to zoom • Drag to rotate</span>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  {selectedAsset.glb_ref ? (
                    <Viewer3D glbUrl={selectedAsset.glb_ref} />
                  ) : (
                    <div className="w-full h-96 rounded-lg overflow-hidden bg-[#0a1119] flex items-center justify-center text-slate-500">
                      <div className="text-center">
                        <Box className="w-12 h-12 mx-auto mb-2 opacity-30" />
                        <p className="text-xs">No 3D model available</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

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
