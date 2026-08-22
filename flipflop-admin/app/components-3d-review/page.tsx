"use client";

import { useEffect, useState, useRef } from "react";
import { Check } from "lucide-react";

const gradientStyle = `
  @keyframes gradientShift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  @keyframes bgShift {
    0% { background: linear-gradient(135deg, #C97A3A 0%, #A0624D 30%, #4A5F7F 70%, #1a3a52 100%); }
    50% { background: linear-gradient(135deg, #D4843F 0%, #B07052 30%, #5A6F8F 70%, #2a4a62 100%); }
    100% { background: linear-gradient(135deg, #C97A3A 0%, #A0624D 30%, #4A5F7F 70%, #1a3a52 100%); }
  }
`;

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
  const mouseRef = useRef({ x: 0, y: 0, isDown: false });
  const modelRef = useRef<any>(null);
  const cameraRef = useRef<any>(null);
  const zoomRef = useRef(1);

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
          scene.background = null;


          // Matrix green perspective grid lines - smaller squares
          const gridHelper = new THREE.GridHelper(200, 40, 0x00ff00, 0x00aa00);
          gridHelper.position.y = -1.49;
          scene.add(gridHelper);

          const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000);
          camera.position.set(5, 6, 9);
          camera.lookAt(0, 0, 0);
          cameraRef.current = camera;

          const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, premultipliedAlpha: true });
          renderer.setSize(width, height);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
          renderer.setClearColor(0xffffff, 0);
          renderer.domElement.style.position = "absolute";
          renderer.domElement.style.top = "0";
          renderer.domElement.style.left = "0";
          renderer.domElement.style.background = "transparent";
          renderer.domElement.style.backgroundColor = "transparent";

          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild);
          }
          containerRef.current.appendChild(renderer.domElement);

          const ambientLight = new THREE.AmbientLight(0xffffff, 2.0);
          scene.add(ambientLight);

          const pointLight = new THREE.PointLight(0xffffff, 2.5);
          pointLight.position.set(5, 5, -5);
          scene.add(pointLight);

          const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
          directionalLight.position.set(3, 5, 2);
          scene.add(directionalLight);

          const fillLight = new THREE.PointLight(0xccddff, 1.5);
          fillLight.position.set(-5, 2, 5);
          scene.add(fillLight);

          const backLight = new THREE.PointLight(0xffffff, 2.5);
          backLight.position.set(0, 3, -8);
          scene.add(backLight);


          const loader = new GLTFLoader();
          const filename = glbUrl.split("/").pop();
          const proxyUrl = `/api/glb-proxy/${filename}`;

          loader.load(
            proxyUrl,
            (gltf) => {
              const model = gltf.scene;
              scene.add(model);

              const box = new THREE.Box3().setFromObject(model);
              const size = box.getSize(new THREE.Vector3());
              const maxDim = Math.max(size.x, size.y, size.z);
              const scale = 10.5 / maxDim;
              model.scale.multiplyScalar(scale);

              const center = box.getCenter(new THREE.Vector3());
              model.position.sub(center.multiplyScalar(scale));

              modelRef.current = model;

              let isAutoRotating = true;
              let animationId: number;

              const animate = () => {
                animationId = requestAnimationFrame(animate);

                if (isAutoRotating) {
                  model.rotation.y += 0.005;
                } else if (mouseRef.current.isDown) {
                  model.rotation.y += mouseRef.current.x * 0.01;
                  model.rotation.x += mouseRef.current.y * 0.01;
                  mouseRef.current.x *= 0.95;
                  mouseRef.current.y *= 0.95;
                }

                renderer.render(scene, camera);
              };
              animate();

              const container = containerRef.current!;
              container.addEventListener("mousedown", () => {
                isAutoRotating = false;
                mouseRef.current.isDown = true;
              });
              container.addEventListener("mousemove", (e) => {
                if (mouseRef.current.isDown) {
                  mouseRef.current.x = e.movementX;
                  mouseRef.current.y = e.movementY;
                }
              });
              container.addEventListener("mouseup", () => {
                mouseRef.current.isDown = false;
                isAutoRotating = true;
              });
              container.addEventListener("mouseleave", () => {
                mouseRef.current.isDown = false;
                isAutoRotating = true;
              });
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

  return <div ref={containerRef} className="w-full h-full rounded border border-slate-700/50 bg-white" />;
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
        console.log("Fetching /api/assets-3d");
        const response = await fetch("/api/assets-3d");
        console.log("Response status:", response.status);
        const data = await response.json();
        console.log("Response data type:", typeof data, "Is array:", Array.isArray(data), "Length:", Array.isArray(data) ? data.length : "n/a");

        if (data.detail) {
          console.error("API Error:", data.detail);
          setAssets([]);
          return;
        }

        if (data.error) {
          console.error("API returned error:", data.error);
          setAssets([]);
          return;
        }

        const assets = Array.isArray(data) ? data : (data.data || data.assets || []);
        console.log("Processed assets count:", assets.length);
        setAssets(assets as Component3DAsset[]);
        const firstDraft = assets.find((a: Component3DAsset) => a.status === "meshy_draft");
        if (firstDraft) setSelectedAsset(firstDraft);
      } catch (error) {
        console.error("Error loading assets:", error);
        setAssets([]);
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
    <>
      <style>{gradientStyle}</style>
      <div style={{ height: "100vh", animation: "bgShift 8s ease-in-out infinite" }} className="w-full flex flex-col gap-3 p-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-slate-100">3D Asset Review</h1>
          <div className="text-xs text-slate-400 mt-1">
            <span className="text-orange-400">{draftCount} Draft</span>
            <span className="mx-2">•</span>
            <span className="text-purple-400">{validatedCount} Valid</span>
            <span className="mx-2">•</span>
            <span className="text-[#00dc82]">{finalCount} Final</span>
            <span className="mx-2">•</span>
            <span className="text-slate-300">{assets.length} Total</span>
          </div>
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

      <div style={{ flex: 1, minHeight: 0 }} className="flex gap-3">
        {/* LEFT: Asset grid */}
        <div style={{ width: "280px", minHeight: "400px" }} className="border border-[#1e2d45] rounded-lg overflow-y-auto p-3 bg-[#0a1119]">
          <div className="grid grid-cols-2 gap-3 auto-rows-max">
            {filteredAssets.map((asset) => {
              const getStatusIcon = () => {
                if (asset.status === "final") return { icon: "✓", color: "bg-[#00dc82]" };
                if (asset.status === "rejected") return { icon: "✗", color: "bg-red-500" };
                if (asset.status === "meshy_draft") return { icon: "?", color: "bg-amber-500" };
                return { icon: "?", color: "bg-slate-600" };
              };
              const statusIcon = getStatusIcon();
              return (
                <button
                  key={asset.id}
                  onClick={() => setSelectedAsset(asset)}
                  className={`rounded border overflow-hidden cursor-pointer transition hover:scale-105 relative flex flex-col ${selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""} ${statusColors[asset.status] || ""}`}
                  style={{ width: "120px", height: "120px", backgroundImage: asset.source_image_refs && asset.source_image_refs.length > 0 ? `url('${asset.source_image_refs[0]}')` : undefined, backgroundSize: "cover", backgroundPosition: "center", backgroundColor: "#1a3a52" }}
                >
                  {/* Status badge overlay */}
                  {asset.glb_ref && (
                    <div className={`absolute top-1 right-1 w-5 h-5 rounded-full ${statusIcon.color} flex items-center justify-center text-white text-[10px] font-bold shadow-lg`}>
                      {statusIcon.icon}
                    </div>
                  )}
                  <div className="flex-1"></div>
                  <div className="w-full bg-black/70 text-center py-2 px-1">
                    <div className="text-xs font-bold text-white">{asset.family_key}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* CENTER+RIGHT: 3D Viewer with overlays */}
        <div className="flex-1 flex flex-col min-h-0">
          {selectedAsset ? (
            <div className="border border-[#1e2d45] rounded-lg overflow-hidden flex-1 flex flex-col relative" style={{ background: "transparent" }}>
              <div className="flex-1 min-h-0 relative">
                <Viewer3D glbUrl={selectedAsset.glb_ref} />

                {/* Title overlay - top center */}
                <div className="absolute top-0 left-0 right-0 flex justify-center pt-8 pointer-events-none">
                  <h1 className="text-5xl font-black text-white text-center drop-shadow-lg" style={{ textShadow: "0 2px 20px rgba(0,0,0,0.8)" }}>
                    {selectedAsset.family_key}
                  </h1>
                </div>

                {/* Details overlay - bottom right */}
                <div className="absolute bottom-3 right-3 w-64 bg-[#0a1119]/70 backdrop-blur-md border border-[#1e2d45]/50 rounded-lg p-2 pointer-events-auto overflow-y-auto max-h-72 shadow-2xl">
                  <div className="space-y-1 text-xs">
                    <div className="pb-1 border-b border-[#1e2d45]/30">
                      <p className="text-slate-500 text-[10px]">ID {selectedAsset.id} v{selectedAsset.version}</p>
                      <p className="text-slate-100 font-semibold text-sm">{selectedAsset.category}</p>
                    </div>

                    {selectedAsset.file_size_kb && (
                      <p className="text-slate-400"><span className="text-slate-500">Size:</span> {Math.round(selectedAsset.file_size_kb / 1024)}MB</p>
                    )}

                    {selectedAsset.poly_count && (
                      <p className="text-slate-400"><span className="text-slate-500">Polys:</span> {(selectedAsset.poly_count / 1000).toFixed(1)}k</p>
                    )}

                    {selectedAsset.notes && (
                      <div className="p-1 bg-slate-700/20 rounded border border-slate-600/30 text-slate-300 mt-1 text-[10px]">
                        {selectedAsset.notes}
                      </div>
                    )}

                    {/* Approval buttons */}
                    <div className="pt-1 border-t border-[#1e2d45]/30 mt-1">
                      <div className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold mb-1 ${getStatusStyle(selectedAsset.status)}`}>
                        {selectedAsset.status.toUpperCase()}
                      </div>

                      {selectedAsset.status === "meshy_draft" && (
                        <div className="flex gap-0.5 flex-wrap">
                          <button onClick={() => handleStatusChange(selectedAsset.id, "rejected")} className="flex-1 min-w-10 px-1 py-0.5 rounded text-[10px] font-semibold bg-red-600/40 text-red-300 border border-red-500/50 hover:bg-red-600/60">
                            Reject
                          </button>
                          <button onClick={() => handleStatusChange(selectedAsset.id, "cleaned")} className="flex-1 min-w-10 px-1 py-0.5 rounded text-[10px] font-semibold bg-blue-600/40 text-blue-300 border border-blue-500/50 hover:bg-blue-600/60">
                            Clean
                          </button>
                          <button onClick={() => handleStatusChange(selectedAsset.id, "validated")} className="flex-1 min-w-10 px-1 py-0.5 rounded text-[10px] font-semibold bg-purple-600/40 text-purple-300 border border-purple-500/50 hover:bg-purple-600/60">
                            Valid
                          </button>
                        </div>
                      )}

                      {selectedAsset.status === "validated" && (
                        <button onClick={() => handleStatusChange(selectedAsset.id, "final")} className="w-full px-1 py-0.5 rounded text-[10px] font-semibold bg-[#00dc82]/40 text-[#00dc82] border border-[#00dc82]/50 hover:bg-[#00dc82]/60">
                          Mark Final
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center flex-1 text-slate-500">
              <div className="text-center">
                <p>Select an asset to review</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
