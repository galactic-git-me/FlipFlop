"use client";

import { useEffect, useState, useRef } from "react";
import { ChevronLeft, ChevronRight, Images } from "lucide-react";

interface Star {
  x: number;
  y: number;
  radius: number;
  opacity: number;
  twinkleDuration: number;
  twinkling: boolean;
  animationDelay: number;
}

function StarfieldBackground({ containerRef }: { containerRef: React.RefObject<HTMLDivElement> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const animationRef = useRef<number | null>(null);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const updateCanvasSize = () => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    };

    updateCanvasSize();

    // Generate stars
    const starCount = Math.floor((canvas.width * canvas.height) / 15000);
    starsRef.current = Array.from({ length: starCount }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 0.8,
      opacity: Math.random() * 0.5 + 0.2,
      twinkleDuration: Math.random() * 2000 + 1500,
      twinkling: Math.random() > 0.6,
      animationDelay: Math.random() * 5000,
    }));

    let lastFrameTime = Date.now();
    const animate = () => {
      const now = Date.now();
      const deltaTime = now - lastFrameTime;
      lastFrameTime = now;

      timeRef.current += deltaTime;

      ctx.fillStyle = "rgba(0, 0, 0, 0.02)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      starsRef.current.forEach((star) => {
        const timeSinceDelay = Math.max(0, timeRef.current - star.animationDelay);

        if (star.twinkling) {
          const cyclePosition = (timeSinceDelay % star.twinkleDuration) / star.twinkleDuration;
          const twinkle = Math.sin(cyclePosition * Math.PI * 2);
          star.opacity = 0.15 + (twinkle * 0.25 + 0.25) * 0.4;
        } else {
          const slowPulse = (Math.sin(timeSinceDelay / 3000) + 1) / 2;
          star.opacity = 0.2 + slowPulse * 0.3;
        }

        ctx.fillStyle = `rgba(200, 220, 255, ${star.opacity})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fill();
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    const handleResize = () => {
      updateCanvasSize();
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      resizeObserver.disconnect();
    };
  }, [containerRef]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{
        zIndex: 0,
      }}
    />
  );
}

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
  subject_id?: number | null;
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
  rank?: number | null;
  subject_name?: string | null;
  source_image_refs?: string[];
  review_batch_id?: string | null;
  review_decision?: "approved" | "rejected" | null;
}

interface ReviewBatch {
  batch_id: string;
  size: number;
  decided: number;
  complete: boolean;
  published: boolean;
  assets: Component3DAsset[];
}

interface PriorityCaseItem {
  id: number;
  name: string;
  priority_3d_rank?: number | null;
}

function orderAndLabelAssets(items: Component3DAsset[], cases: PriorityCaseItem[]) {
  const caseById = new Map(cases.map(item => [item.id, item]));
  return items
    .map(asset => {
      const matchedCase = asset.subject_id ? caseById.get(asset.subject_id) : undefined;
      return {
        ...asset,
        rank: matchedCase?.priority_3d_rank ?? asset.rank ?? null,
        subject_name: matchedCase?.name ?? asset.subject_name ?? null,
      };
    })
    .sort((left, right) => (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER));
}

function preserveAssetLabels(items: Component3DAsset[], existing: Component3DAsset[]) {
  const existingById = new Map(existing.map(asset => [asset.id, asset]));
  return items.map(asset => ({
    ...existingById.get(asset.id),
    ...asset,
    rank: existingById.get(asset.id)?.rank ?? asset.rank ?? null,
    subject_name: existingById.get(asset.id)?.subject_name ?? asset.subject_name ?? null,
  }));
}

function Viewer3D({ glbUrl }: { glbUrl: string | null }) {
  // 3D Viewer Configuration:
  // - Camera position: (5, 6, 9) — controls zoom/perspective from the model
  // - Model scale: 10.5 — scales loaded GLB to viewport size
  // - Grid: 200x200 with 40 divisions, matrix green lines (0x00ff00, 0x00aa00)
  // - Lights: ambient (3.5), point (4.0), directional (3.0), fill (2.5), back (3.5)
  // - Starfield: twinkling background at z-index 0, model canvas at z-index 2
  // - Grid horizon: y = -1.49 (centered in viewport for perspective)
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


          // Matrix green grid lines
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
          renderer.setClearColor(0x000000, 0);
          renderer.domElement.style.position = "absolute";
          renderer.domElement.style.top = "0";
          renderer.domElement.style.left = "0";
          renderer.domElement.style.background = "transparent";
          renderer.domElement.style.backgroundColor = "transparent";
          renderer.domElement.style.zIndex = "2";

          while (containerRef.current.firstChild) {
            containerRef.current.removeChild(containerRef.current.firstChild);
          }
          containerRef.current.appendChild(renderer.domElement);

          const ambientLight = new THREE.AmbientLight(0xffffff, 3.5);
          scene.add(ambientLight);

          const pointLight = new THREE.PointLight(0xffffff, 4.0);
          pointLight.position.set(5, 5, -5);
          scene.add(pointLight);

          const directionalLight = new THREE.DirectionalLight(0xffffff, 3.0);
          directionalLight.position.set(3, 5, 2);
          scene.add(directionalLight);

          const fillLight = new THREE.PointLight(0xccddff, 2.5);
          fillLight.position.set(-5, 2, 5);
          scene.add(fillLight);

          const backLight = new THREE.PointLight(0xffffff, 3.5);
          backLight.position.set(0, 3, -8);
          scene.add(backLight);


          const loader = new GLTFLoader();
          loader.crossOrigin = "anonymous";

          // Handle CORS by proxying through local backend
          const loadUrl = glbUrl.startsWith("http") && !glbUrl.includes("localhost")
            ? `/api/glb-proxy?url=${encodeURIComponent(glbUrl)}`
            : glbUrl;

          loader.load(
            loadUrl,
            (gltf) => {
              const model = gltf.scene;

              // Apply bright material to all meshes if they don't have one
              model.traverse((child: any) => {
                if (child.isMesh) {
                  if (!child.material) {
                    child.material = new THREE.MeshStandardMaterial({
                      color: 0xcccccc,
                      roughness: 0.5,
                      metalness: 0.2,
                      emissive: 0x333333,
                    });
                  } else if (child.material.color === undefined) {
                    // If material exists but has no color, add one
                    child.material.color = new THREE.Color(0xcccccc);
                    child.material.roughness = 0.5;
                    child.material.metalness = 0.2;
                    child.material.emissive = new THREE.Color(0x333333);
                  }
                }
              });

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
  const [filter, setFilter] = useState<"meshy_draft" | "all">("all");
  const [batch, setBatch] = useState<ReviewBatch | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const batchId = new URLSearchParams(window.location.search).get("batch");
        const [response, casesResponse] = await Promise.all([
          fetch(batchId ? `/api/assets-3d/review-batches/${batchId}` : "/api/assets-3d"),
          fetch("/api/cases/priority-for-3d?limit=30"),
        ]);
        const data = await response.json();
        const priorityCases = casesResponse.ok ? await casesResponse.json() as PriorityCaseItem[] : [];

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

        const loadedAssets = orderAndLabelAssets(
          (Array.isArray(data) ? data : (data.data || data.assets || [])) as Component3DAsset[],
          priorityCases,
        );
        if (batchId) setBatch({ ...data, assets: loadedAssets } as ReviewBatch);
        setAssets(loadedAssets);
        setSelectedAsset(loadedAssets[0] || null);
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

  const handlePreviousAsset = () => {
    const currentIndex = filteredAssets.findIndex(a => a.id === selectedAsset?.id);
    if (currentIndex > 0) {
      setSelectedAsset(filteredAssets[currentIndex - 1]);
    }
  };

  const handleNextAsset = () => {
    const currentIndex = filteredAssets.findIndex(a => a.id === selectedAsset?.id);
    if (currentIndex < filteredAssets.length - 1) {
      setSelectedAsset(filteredAssets[currentIndex + 1]);
    }
  };

  useEffect(() => {
    const handleKeyboardNavigation = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        handlePreviousAsset();
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        handleNextAsset();
      }
    };

    window.addEventListener("keydown", handleKeyboardNavigation);
    return () => window.removeEventListener("keydown", handleKeyboardNavigation);
  });

  const startReviewBatch = async () => {
    setActionBusy(true);
    setActionError(null);
    try {
      const response = await fetch("/api/assets-3d/review-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size: 10 }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not create review batch");
      const nextBatch = data as ReviewBatch;
      setBatch(nextBatch);
      setAssets(nextBatch.assets);
      setSelectedAsset(nextBatch.assets[0] || null);
      setFilter("all");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not create review batch");
    } finally {
      setActionBusy(false);
    }
  };

  const decideAsset = async (decision: "approved" | "rejected") => {
    if (!batch || !selectedAsset) return;
    setActionBusy(true);
    setActionError(null);
    try {
      const response = await fetch(`/api/assets-3d/review-batches/${batch.batch_id}/assets/${selectedAsset.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, notes: reviewNotes || null }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not save decision");
      const reviewedAsset = { ...selectedAsset, ...data } as Component3DAsset;
      const updatedAssets = batch.assets.map(asset => asset.id === data.id ? reviewedAsset : asset);
      const updatedBatch = { ...batch, assets: updatedAssets, decided: updatedAssets.filter(asset => asset.review_decision).length };
      updatedBatch.complete = updatedBatch.decided === updatedBatch.size;
      setBatch(updatedBatch);
      setAssets(updatedAssets);
      setSelectedAsset(reviewedAsset);
      setReviewNotes("");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not save decision");
    } finally {
      setActionBusy(false);
    }
  };

  const publishBatch = async () => {
    if (!batch) return;
    setActionBusy(true);
    setActionError(null);
    try {
      const response = await fetch(`/api/assets-3d/review-batches/${batch.batch_id}/publish`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || data.error || "Could not publish batch");
      const publishedBatch = data as ReviewBatch;
      const labelledAssets = preserveAssetLabels(publishedBatch.assets, batch.assets);
      setBatch({ ...publishedBatch, assets: labelledAssets });
      setAssets(labelledAssets);
      const selected = labelledAssets.find(asset => asset.id === selectedAsset?.id);
      if (selected) setSelectedAsset(selected);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not publish batch");
    } finally {
      setActionBusy(false);
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
      <div style={{ height: "100vh", animation: "bgShift 8s ease-in-out infinite" }} className="w-full flex flex-col gap-3 p-4 pb-0 overflow-hidden">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-100">3D Asset Review</h1>
        <div className="flex items-center gap-3">
          {batch ? (
            <>
              <div className="rounded-md border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-200" role="status">
                Batch {batch.decided}/{batch.size} reviewed
              </div>
              <button
                type="button"
                onClick={publishBatch}
                disabled={!batch.complete || batch.published || actionBusy}
                className="cursor-pointer rounded-md border border-emerald-500 bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {batch.published ? "Published" : "Publish approved models"}
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={startReviewBatch}
              disabled={actionBusy}
              className="cursor-pointer rounded-md border border-sky-500 bg-sky-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Start next batch of 10
            </button>
          )}
        </div>
        <div className="bg-white/50 rounded-lg px-6 py-2 text-lg font-semibold flex items-center gap-4">
          <span className="text-orange-500">{draftCount} Draft</span>
          <span className="text-purple-500">{validatedCount} Valid</span>
          <span className="text-[#00dc82]">{finalCount} Final</span>
          <span className="text-slate-800">{assets.length} Total</span>
        </div>
      </div>
      {actionError && <div role="alert" className="rounded-md border border-red-500/60 bg-red-950/80 px-4 py-2 text-sm text-red-200">{actionError}</div>}

      <div style={{ flex: 1, minHeight: 0 }} className="flex gap-3 relative">
        {/* LEFT: Asset grid grouped by component */}
        <div style={{ width: "280px", minHeight: "400px" }} className="border border-[#1e2d45] rounded-lg overflow-y-auto p-3 bg-[#0a1119] flex flex-col">
          <div className="flex gap-2 mb-3 justify-end">
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
          <div className="overflow-y-auto flex-1">
          {(() => {
            const grouped = filteredAssets.reduce((acc, asset) => {
              if (!acc[asset.category]) acc[asset.category] = [];
              acc[asset.category].push(asset);
              return acc;
            }, {} as Record<string, typeof filteredAssets>);

            return Object.entries(grouped).map(([category, assets]) => (
              <div key={category} className="mb-4">
                <div className="text-sm font-bold text-slate-100 uppercase px-1 py-3 border-b border-[#1e2d45] mb-3">
                  {category}
                </div>
                <div className="grid grid-cols-2 gap-3 auto-rows-max">
                  {assets.map((asset) => {
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
                        style={{ width: "120px", height: "120px", backgroundImage: asset.preview_image_ref ? `url('${asset.preview_image_ref}')` : asset.source_image_refs && asset.source_image_refs.length > 0 ? `url('${asset.source_image_refs[0]}')` : undefined, backgroundSize: "cover", backgroundPosition: "center", backgroundColor: "#1a3a52" }}
                      >
                        {/* Status badge overlay */}
                        {asset.glb_ref && (
                          <div className={`absolute top-1 right-1 w-5 h-5 rounded-full ${statusIcon.color} flex items-center justify-center text-white text-[10px] font-bold shadow-lg`}>
                            {statusIcon.icon}
                          </div>
                        )}
                        <div className="flex-1"></div>
                        <div className="w-full bg-black/70 text-center py-2 px-1">
                          <div className="text-xs font-bold text-white">{asset.rank ? `#${asset.rank} ` : ""}{asset.subject_name || asset.family_key}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ));
          })()}
          </div>
        </div>

        {/* CENTER+RIGHT: model/reference comparison workspace */}
        <div className="flex-1 flex flex-col min-h-0 z-30 relative">
          {selectedAsset ? (
            <div className="border border-[#1e2d45] rounded-lg overflow-hidden flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_320px] relative z-30 bg-[#050b12]/80">
              <section className="min-h-[420px] lg:min-h-0 relative" ref={containerRef} aria-label="Interactive 3D model">
                <StarfieldBackground containerRef={containerRef} />
                <Viewer3D glbUrl={selectedAsset.glb_ref} />

                <button
                  type="button"
                  onClick={handlePreviousAsset}
                  disabled={filteredAssets.findIndex(a => a.id === selectedAsset.id) <= 0}
                  aria-label="Previous approval item"
                  title="Previous item (Left arrow)"
                  className="absolute left-3 top-1/2 z-[60] -translate-y-1/2 cursor-pointer rounded-full border border-slate-500 bg-slate-950/85 p-3 text-white shadow-xl transition-colors hover:border-orange-400 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-300 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <ChevronLeft className="h-6 w-6" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={handleNextAsset}
                  disabled={filteredAssets.findIndex(a => a.id === selectedAsset.id) >= filteredAssets.length - 1}
                  aria-label="Next approval item"
                  title="Next item (Right arrow)"
                  className="absolute right-3 top-1/2 z-[60] -translate-y-1/2 cursor-pointer rounded-full border border-slate-500 bg-slate-950/85 p-3 text-white shadow-xl transition-colors hover:border-orange-400 hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-300 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  <ChevronRight className="h-6 w-6" aria-hidden="true" />
                </button>

                {/* Title overlay - top center */}
                <div className="absolute top-0 left-0 right-0 flex justify-center pt-8 pointer-events-none z-10">
                  <h1 className="text-5xl font-black text-white text-center drop-shadow-lg" style={{ textShadow: "0 2px 20px rgba(0,0,0,0.8)" }}>
                    {selectedAsset.rank ? `#${selectedAsset.rank} ` : ""}{selectedAsset.subject_name || selectedAsset.family_key}
                  </h1>
                </div>

                {/* Details overlay - bottom left */}
                <div className="absolute bottom-24 left-3 w-64 bg-[#0a1119]/70 backdrop-blur-md border border-[#1e2d45]/50 rounded-lg p-2 pointer-events-auto overflow-y-auto max-h-72 shadow-2xl z-50">
                  <div className="space-y-1 text-sm">
                    <div className="pb-1 border-b border-[#1e2d45]/30">
                      <p className="text-slate-500 text-xs">ID {selectedAsset.id} v{selectedAsset.version}</p>
                      <p className="text-slate-100 font-semibold text-base">{selectedAsset.category}</p>
                      {selectedAsset.rank && (
                        <p className="text-slate-400 text-xs mt-1"><span className="text-slate-500">Rank:</span> #{selectedAsset.rank}</p>
                      )}
                    </div>

                    {selectedAsset.file_size_kb && (
                      <p className="text-slate-400 text-sm"><span className="text-slate-500">Size:</span> {Math.round(selectedAsset.file_size_kb / 1024)}MB</p>
                    )}

                    {selectedAsset.poly_count && (
                      <p className="text-slate-400 text-sm"><span className="text-slate-500">Polys:</span> {(selectedAsset.poly_count / 1000).toFixed(1)}k</p>
                    )}

                    {selectedAsset.notes && (
                      <div className="p-1 bg-slate-700/20 rounded border border-slate-600/30 text-slate-300 mt-1 text-xs">
                        {selectedAsset.notes}
                      </div>
                    )}

                    {/* Approval buttons - high z-index modal */}
                    <div className="pt-1 border-t border-[#1e2d45]/30 mt-1 relative z-50">
                      <div className={`inline-block px-2 py-1 rounded text-xs font-semibold mb-2 ${getStatusStyle(selectedAsset.status)}`}>
                        {selectedAsset.status.toUpperCase()}
                      </div>

                      <div className="space-y-2 relative z-50">
                        <div className="flex gap-1 relative z-50">
                          <button disabled={!batch || actionBusy} onClick={() => decideAsset("rejected")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-red-600/40 text-red-300 border border-red-500/50 hover:bg-red-600/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
                            Reject
                          </button>
                          <button disabled={!batch || actionBusy} onClick={() => decideAsset("approved")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-[#00dc82]/40 text-[#00dc82] border border-[#00dc82]/50 hover:bg-[#00dc82]/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
                            Approve
                          </button>
                        </div>

                        <textarea
                          placeholder="Add guidance comments for regeneration..."
                          aria-label="Review notes"
                          value={reviewNotes}
                          onChange={(event) => setReviewNotes(event.target.value)}
                          className="w-full px-2 py-1 rounded text-xs bg-slate-800/50 text-slate-300 border border-slate-600/50 placeholder-slate-500 resize-none h-16 focus:outline-none focus:border-slate-500/80 relative z-50"
                        />

                        {selectedAsset.review_decision && <p className="text-xs text-slate-300" role="status">Decision: {selectedAsset.review_decision}</p>}
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <aside className="min-h-0 overflow-y-auto border-t border-[#1e2d45] bg-[#07111b] p-3 lg:border-l lg:border-t-0" aria-label="Source reference pictures">
                <div className="mb-3 flex items-start justify-between gap-3 border-b border-[#1e2d45] pb-3">
                  <div>
                    <h2 className="flex items-center gap-2 text-sm font-bold text-slate-100">
                      <Images className="h-4 w-4 text-orange-300" aria-hidden="true" />
                      Source pictures
                    </h2>
                    <p className="mt-1 text-xs text-slate-400">Compare shape, panels, vents and details with the model.</p>
                  </div>
                  <span className="shrink-0 rounded bg-slate-800 px-2 py-1 text-xs text-slate-300">
                    {filteredAssets.findIndex(a => a.id === selectedAsset.id) + 1}/{filteredAssets.length}
                  </span>
                </div>

                {selectedAsset.source_image_refs?.length ? (
                  <div className="space-y-3">
                    {selectedAsset.source_image_refs.map((imageUrl, index) => (
                      <a
                        key={`${imageUrl}-${index}`}
                        href={imageUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="group block cursor-zoom-in overflow-hidden rounded-md border border-slate-700 bg-white transition-colors hover:border-orange-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-300"
                        aria-label={`Open source picture ${index + 1} full size`}
                      >
                        {/* Source URLs can be temporary signed URLs, so Next Image optimisation cannot safely proxy them. */}
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={imageUrl}
                          alt={`Source reference ${index + 1} for ${selectedAsset.subject_name || selectedAsset.family_key}`}
                          className="h-44 w-full object-contain transition-opacity group-hover:opacity-90"
                          loading={index === 0 ? "eager" : "lazy"}
                        />
                        <span className="block border-t border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-300">Reference {index + 1} · open full size</span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-md border border-amber-500/40 bg-amber-950/30 p-4 text-sm text-amber-200" role="note">
                    No source pictures are attached. This item should not be approved until comparison images are supplied.
                  </div>
                )}

                <p className="mt-4 text-center text-xs text-slate-500">Use the left/right arrow keys to move between items.</p>
              </aside>
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
