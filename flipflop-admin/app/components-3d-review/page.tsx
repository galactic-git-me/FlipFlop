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
          scene.background = new THREE.Color(0x0a1119);

          const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
          camera.position.set(0, 0, 1);
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

          // Blender-style grid on ground plane
          const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
          gridHelper.position.y = -1;
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
              const scale = 1.7 / maxDim;
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
              container.addEventListener("wheel", (e) => {
                e.preventDefault();
                zoomRef.current += e.deltaY > 0 ? 0.05 : -0.05;
                zoomRef.current = Math.max(0.2, Math.min(5, zoomRef.current));
                if (cameraRef.current) {
                  cameraRef.current.position.z = 1 / zoomRef.current;
                }
              }, { passive: false });
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
  const [approvalModal, setApprovalModal] = useState<{ isOpen: boolean; assetId: number | null }>({ isOpen: false, assetId: null });
  const [approvalNotes, setApprovalNotes] = useState("");

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
          notes: approvalNotes || undefined,
        }),
      });
      if (response.ok) {
        const updated = (await response.json()) as Component3DAsset;
        setAssets(prev => prev.map(a => a.id === assetId ? updated : a));
        if (selectedAsset?.id === assetId) setSelectedAsset(updated);
        setApprovalModal({ isOpen: false, assetId: null });
        setApprovalNotes("");
      }
    } catch (error) {
      console.error("Error updating asset:", error);
    }
  };

  const openApprovalModal = (assetId: number) => {
    setApprovalNotes("");
    setApprovalModal({ isOpen: true, assetId });
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
              ) : filteredAssets.filter(a => a.glb_ref).length === 0 ? (
                <div className="col-span-2 text-center py-4 text-slate-500 text-xs space-y-2">
                  <p>No models ready</p>
                  <p className="text-[10px] text-slate-600">Run generate_catalogue_3d_assets.py to import more</p>
                </div>
              ) : (
                filteredAssets.filter(a => a.glb_ref).map((asset) => (
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
                <button
                  onClick={() => openApprovalModal(selectedAsset.id)}
                  className="w-full px-3 py-2 text-xs font-semibold bg-orange-600/30 text-orange-300 border border-orange-500/50 rounded hover:bg-orange-600/40 transition"
                >
                  Review & Approve
                </button>
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

      {/* Approval Modal */}
      {approvalModal.isOpen && approvalModal.assetId && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700/50 rounded-lg p-6 max-w-md w-full mx-4 space-y-4">
            <div>
              <h2 className="text-lg font-bold text-slate-100">Approve 3D Model</h2>
              <p className="text-xs text-slate-500 mt-1">{selectedAsset?.family_key}</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-2">Comments (optional)</label>
              <textarea
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                placeholder="Add notes about this model..."
                className="w-full bg-slate-800/50 border border-slate-700/50 rounded p-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-orange-500/50"
                rows={4}
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => {
                  setApprovalModal({ isOpen: false, assetId: null });
                  setApprovalNotes("");
                }}
                className="flex-1 px-3 py-2 text-xs font-semibold bg-slate-700/30 text-slate-300 border border-slate-600/50 rounded hover:bg-slate-700/40 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => handleStatusChange(approvalModal.assetId, "rejected")}
                className="flex-1 px-3 py-2 text-xs font-semibold bg-red-600/30 text-red-300 border border-red-500/50 rounded hover:bg-red-600/40 transition"
              >
                Redo Model
              </button>
              <button
                onClick={() => handleStatusChange(approvalModal.assetId, "cleaned")}
                className="flex-1 px-3 py-2 text-xs font-semibold bg-green-600/30 text-green-300 border border-green-500/50 rounded hover:bg-green-600/40 transition"
              >
                Accept
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
