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
          scene.background = new THREE.Color(0x2a2a2a);

          // Create Blender-style grid floor plane
          const gridGeometry = new THREE.PlaneGeometry(100, 100, 100, 100);
          const gridMaterial = new THREE.LineBasicMaterial({ color: 0x444444 });
          const wireframe = new THREE.LineSegments(gridGeometry, gridMaterial);
          wireframe.position.y = -1;
          scene.add(wireframe);

          // Add darker grid lines (alternating)
          const gridGeometry2 = new THREE.PlaneGeometry(100, 100, 10, 10);
          const gridMaterial2 = new THREE.LineBasicMaterial({ color: 0x333333, linewidth: 2 });
          const wireframe2 = new THREE.LineSegments(gridGeometry2, gridMaterial2);
          wireframe2.position.y = -1.01;
          scene.add(wireframe2);

          const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
          camera.position.set(0, 0, 3);
          cameraRef.current = camera;

          const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
          renderer.setSize(width, height);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild);
          }
          containerRef.current.appendChild(renderer.domElement);

          const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
          scene.add(ambientLight);

          const pointLight = new THREE.PointLight(0xffffff, 1.2);
          pointLight.position.set(5, 5, -5);
          scene.add(pointLight);

          const directionalLight = new THREE.DirectionalLight(0xffffff, 0.7);
          directionalLight.position.set(3, 5, 2);
          scene.add(directionalLight);

          const fillLight = new THREE.PointLight(0x88ccff, 0.5);
          fillLight.position.set(-5, 2, 5);
          scene.add(fillLight);

          // Blender-style grid on ground plane - exact match to Blender viewport
          const gridHelper = new THREE.GridHelper(50, 50, 0x555555, 0x333333);
          gridHelper.position.y = -1;
          gridHelper.scale.set(1.5, 1, 1.5);
          scene.add(gridHelper);

          // RGB axes like Blender (X=red, Y=green, Z=blue)
          const axesHelper = new THREE.AxesHelper(6);
          scene.add(axesHelper);

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
              const scale = 1.6 / maxDim;
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

        if (data.detail) {
          console.error("API Error:", data.detail);
          setAssets([]);
          return;
        }

        const assets = Array.isArray(data) ? data : (data.data || data.assets || []);
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
        {/* LEFT: Asset grid */}
        <div className="w-96 border border-[#1e2d45] rounded-lg overflow-y-auto p-2 bg-[#0a1119]">
          <div className="grid grid-cols-6 gap-2">
            {filteredAssets.map((asset) => (
              <button
                key={asset.id}
                onClick={() => setSelectedAsset(asset)}
                className={`aspect-square rounded border overflow-hidden cursor-pointer transition hover:scale-105 ${selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""} ${statusColors[asset.status] || ""}`}
                style={{ backgroundImage: asset.preview_image_ref ? `url('${asset.preview_image_ref}')` : undefined, backgroundSize: "cover", backgroundPosition: "center" }}
              >
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <div className="font-bold text-[8px] text-white text-center px-1">{asset.family_key}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* CENTER: 3D Viewer */}
        <div className="flex-1 flex flex-col min-h-0">
          {selectedAsset ? (
            <div className="border border-[#1e2d45] rounded-lg overflow-hidden flex-1 flex flex-col bg-[#0a1119]">
              <div className="px-3 py-2 border-b border-[#1e2d45] bg-slate-900/30 text-xs font-semibold text-slate-300">3D Viewer</div>
              <div className="flex-1 min-h-0">
                <Viewer3D glbUrl={selectedAsset.glb_ref} />
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

        {selectedAsset && (
          <div className="w-96 flex flex-col min-h-0 overflow-y-auto gap-2">
            <div className="border border-[#1e2d45] rounded-lg p-4 bg-[#0a1119]">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-100">{selectedAsset.family_key}</h2>
                  <p className="text-xs text-slate-500 mt-1">ID: {selectedAsset.id} v{selectedAsset.version}</p>
                </div>
                <div className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${getStatusStyle(selectedAsset.status)}`}>
                  {selectedAsset.status.toUpperCase()}
                </div>
              </div>

              <div className="space-y-2 text-xs">
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
                <div className="p-2 bg-slate-700/30 rounded border border-slate-600 text-xs text-slate-300 mt-3">
                  <p className="text-slate-500 text-[10px] mb-1 uppercase">Notes</p>
                  {selectedAsset.notes}
                </div>
              )}

              {selectedAsset.glb_ref && (
                <div className="p-2 bg-blue-900/20 rounded border border-blue-400/20 mt-3">
                  <p className="text-slate-500 text-xs mb-1">GLB File</p>
                  <a href={selectedAsset.glb_ref} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:text-blue-300 break-all">
                    Download / View
                  </a>
                </div>
              )}

              {selectedAsset.created_by && (
                <div className="text-[10px] text-slate-600 mt-3">
                  Created by {selectedAsset.created_by}
                  {selectedAsset.created_at && ` on ${new Date(selectedAsset.created_at).toLocaleDateString()}`}
                </div>
              )}

              {selectedAsset.status === "meshy_draft" && (
                <div className="flex gap-2 pt-3">
                  <button onClick={() => handleStatusChange(selectedAsset.id, "rejected")} className="flex-1 px-2 py-1 rounded text-xs font-semibold bg-red-600/30 text-red-300 border border-red-500/50 hover:bg-red-600/50">
                    Reject
                  </button>
                  <button onClick={() => handleStatusChange(selectedAsset.id, "cleaned")} className="flex-1 px-2 py-1 rounded text-xs font-semibold bg-blue-600/30 text-blue-300 border border-blue-500/50 hover:bg-blue-600/50">
                    Cleaned
                  </button>
                  <button onClick={() => handleStatusChange(selectedAsset.id, "validated")} className="flex-1 px-2 py-1 rounded text-xs font-semibold bg-purple-600/30 text-purple-300 border border-purple-500/50 hover:bg-purple-600/50">
                    Validate
                  </button>
                </div>
              )}

              {selectedAsset.status === "validated" && (
                <button onClick={() => handleStatusChange(selectedAsset.id, "final")} className="w-full mt-3 px-2 py-1 rounded text-xs font-semibold bg-[#00dc82]/30 text-[#00dc82] border border-[#00dc82]/50 hover:bg-[#00dc82]/50">
                  Mark as Final
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
