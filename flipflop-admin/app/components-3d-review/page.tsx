"use client";

import { useEffect, useState, useRef } from "react";
import { Check } from "lucide-react";

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

  useEffect(() => {
    if (!containerRef.current || !glbUrl) return;

    setTimeout(() => {
      const setupViewer = async () => {
        try {
          const THREE = await import("three");
          const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");

          if (!containerRef.current) return;

          const width = containerRef.current.clientWidth;
          const height = containerRef.current.clientHeight;

          if (width === 0 || height === 0) return;

          const scene = new THREE.Scene();
          scene.background = new THREE.Color(0x0a1119);

          const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
          camera.position.set(0, 1, 2);

          const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
          renderer.setSize(width, height);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild);
          }
          containerRef.current.appendChild(renderer.domElement);

          const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
          scene.add(ambientLight);

          const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
          directionalLight.position.set(5, 8, 5);
          scene.add(directionalLight);

          const loader = new GLTFLoader();
          const filename = glbUrl.split("/").pop();
          const proxyUrl = `/api/glb-proxy/${filename}`;

          loader.load(
            proxyUrl,
            (gltf) => {
              const model = gltf.scene;
              model.scale.set(1, 1, 1);
              scene.add(model);

              const box = new THREE.Box3().setFromObject(model);
              const center = box.getCenter(new THREE.Vector3());
              model.position.sub(center);

              const animate = () => {
                requestAnimationFrame(animate);
                model.rotation.y += 0.005;
                renderer.render(scene, camera);
              };
              animate();
            },
            undefined,
            (error) => {
              console.error("Failed to load GLB:", error, "URL:", glbUrl);
            }
          );

          renderer.render(scene, camera);
        } catch (error) {
          console.error("Error setting up 3D viewer:", error);
        }
      };
      setupViewer();
    }, 100);
  }, [glbUrl]);

  if (!glbUrl) {
    return (
      <div className="w-full h-full bg-slate-900/50 rounded border border-slate-700/50 flex items-center justify-center text-slate-400">
        <div className="text-center">
          <p className="text-sm">No GLB model available</p>
          <p className="text-xs text-slate-500 mt-1">glb_ref is null</p>
        </div>
      </div>
    );
  }

  return <div ref={containerRef} className="w-full h-full bg-slate-900/50 rounded border border-slate-700/50" />;
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
        console.log("Assets loaded:", { count: assets.length, first: assets[0], glbRef: assets[0]?.glb_ref });
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

  return (
    <div className="w-full h-full flex flex-col gap-3 p-4 bg-gradient-to-br from-slate-950 via-blue-950 to-slate-950">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-100">3D Asset Review</h1>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-2">
        <div className="bg-orange-400/10 border border-orange-400/30 rounded p-2">
          <div className="text-2xl font-bold text-orange-400">{draftCount}</div>
          <div className="text-xs text-slate-500">Draft</div>
        </div>
        <div className="bg-purple-400/10 border border-purple-400/30 rounded p-2">
          <div className="text-2xl font-bold text-purple-400">{validatedCount}</div>
          <div className="text-xs text-slate-500">Valid</div>
        </div>
        <div className="bg-[#00dc82]/10 border border-[#00dc82]/30 rounded p-2">
          <div className="text-2xl font-bold text-[#00dc82]">{finalCount}</div>
          <div className="text-xs text-slate-500">Final</div>
        </div>
        <div className="bg-slate-600/10 border border-slate-600/30 rounded p-2">
          <div className="text-2xl font-bold text-slate-300">{assets.length}</div>
          <div className="text-xs text-slate-500">Total</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
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

      {/* Main layout: left grid + right viewer */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* Left: Asset grid */}
        <div className="w-40 flex flex-col gap-2 min-h-0">
          <div className="overflow-y-auto flex-1">
            <div className="grid grid-cols-2 gap-2">
              {loading ? (
                <div className="col-span-2 text-center py-4 text-slate-500 text-xs">Loading...</div>
              ) : filteredAssets.length === 0 ? (
                <div className="col-span-2 text-center py-4 text-slate-500 text-xs">No assets</div>
              ) : (
                filteredAssets.map((asset) => (
                  <button
                    key={asset.id}
                    onClick={() => setSelectedAsset(asset)}
                    className={`aspect-square rounded border transition ${
                      selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""
                    } ${statusColors[asset.status]}`}
                    style={{
                      backgroundImage: asset.preview_image_ref ? `url('${asset.preview_image_ref}')` : undefined,
                      backgroundSize: "cover",
                      backgroundPosition: "center",
                    }}
                    title={asset.family_key}
                  >
                    <div className="w-full h-full bg-black/40 flex items-center justify-center text-xs font-bold text-white/70">
                      {asset.status === "meshy_draft" && "DRAFT"}
                      {asset.status === "validated" && "✓"}
                      {asset.status === "final" && "✓✓"}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right: Viewer + info */}
        {selectedAsset ? (
          <div className="flex-1 flex flex-col gap-2 min-h-0">
            {/* Viewer */}
            <div className="flex-1 rounded border border-slate-700/50 overflow-hidden min-h-0">
              <Viewer3D glbUrl={selectedAsset.glb_ref} />
            </div>

            {/* Asset info + controls */}
            <div className="bg-slate-900/40 border border-slate-700/50 rounded p-2 space-y-2">
              <div>
                <p className="text-xs font-semibold text-slate-300">{selectedAsset.family_key}</p>
                <p className="text-xs text-slate-500">{selectedAsset.category}</p>
              </div>

              {selectedAsset.status === "meshy_draft" && (
                <div className="flex gap-1">
                  <button
                    onClick={() => handleStatusChange(selectedAsset.id, "cleaned")}
                    className="flex-1 px-2 py-1 text-xs font-semibold bg-blue-600/30 text-blue-300 border border-blue-500/50 rounded hover:bg-blue-600/40 transition"
                  >
                    Clean
                  </button>
                  <button
                    onClick={() => handleStatusChange(selectedAsset.id, "rejected")}
                    className="flex-1 px-2 py-1 text-xs font-semibold bg-red-600/30 text-red-300 border border-red-500/50 rounded hover:bg-red-600/40 transition"
                  >
                    Reject
                  </button>
                </div>
              )}

              {selectedAsset.status === "cleaned" && (
                <div className="flex gap-1">
                  <button
                    onClick={() => handleStatusChange(selectedAsset.id, "validated")}
                    className="flex-1 px-2 py-1 text-xs font-semibold bg-purple-600/30 text-purple-300 border border-purple-500/50 rounded hover:bg-purple-600/40 transition"
                  >
                    Validate
                  </button>
                </div>
              )}

              {selectedAsset.status === "validated" && (
                <div className="flex gap-1">
                  <button
                    onClick={() => handleStatusChange(selectedAsset.id, "final")}
                    className="flex-1 px-2 py-1 text-xs font-semibold bg-[#00dc82]/30 text-[#00dc82] border border-[#00dc82]/50 rounded hover:bg-[#00dc82]/40 transition"
                  >
                    Finalize
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            <Check className="w-8 h-8 opacity-20" />
          </div>
        )}
      </div>
    </div>
  );
}
