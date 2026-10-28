"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight, CirclePlay, Images, RefreshCw, ScanSearch, Plus, Trash2, Save, Loader2 } from "lucide-react";
import { ThreeDWorkflowNav } from "@/components/three-d-workflow-nav";
import MeshyGenerationQueue from "@/components/playbooks/MeshyGenerationQueue";
import { readJsonResponse } from "@/lib/read-json-response";
import { detectRgbFans } from "./fan-detection";
import { originalImageUrl } from "@/lib/model-reference-images";

interface Star {
  x: number;
  y: number;
  radius: number;
  opacity: number;
  twinkleDuration: number;
  twinkling: boolean;
  animationDelay: number;
}

function StarfieldBackground({ containerRef }: { containerRef: React.RefObject<HTMLDivElement | null> }) {
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

type ApprovedPhotoItem = {
  variant_id: number; variant_ids: number[]; title: string; category: string;
  media_family_key?: string; main_photo_approved?: boolean; main_photo_url?: string;
  automatic_media_preparation_enabled?: boolean;
  asset?: { id: number } | null;
  asset_media_review?: { generation?: { status?: string; progress?: number; error?: string | null } };
};
const activeModelJobs = new Set(["QUEUED", "PREPARING", "STARTING", "RESUMING", "SUBMITTED", "PENDING", "IN_PROGRESS", "PUBLISHING"]);

interface Component3DAsset {
  id: number;
  catalogue_variant_id?: number;
  generation_status?: string;
  generation_progress?: number;
  generation_error?: string | null;
  generation_enabled?: boolean;
  subject_type?: "case" | "variant" | "category_generic";
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
  dimensions_mm?: { width?: number; height?: number; depth?: number } | null;
  fan_layout_json?: FanLayout | null;
  source_video_refs?: Array<{
    url: string;
    title: string;
    timestamp?: string | null;
  }>;
  review_batch_id?: string | null;
  review_decision?: "approved" | "rejected" | null;
  is_active?: boolean;
  commercial_use_approved?: boolean;
  redistribution_approved?: boolean;
  scale_validated?: boolean;
  regeneration?: {
    status: "queued" | "not_queued";
    asset_id?: number;
    version?: number;
    message: string;
  } | null;
}

function ModelAssetThumbnail({ asset }: { asset: Component3DAsset }) {
  const imageUrls = [asset.preview_image_ref, ...(asset.source_image_refs || [])]
    .filter((url): url is string => Boolean(url))
    .filter((url, index, all) => all.indexOf(url) === index);
  const [imageIndex, setImageIndex] = useState(0);

  useEffect(() => {
    setImageIndex(0);
  }, [asset.id, asset.preview_image_ref, asset.source_image_refs?.join("\n")]);

  if (!imageUrls[imageIndex]) return <div className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-400">No preview</div>;
  return <img
    src={imageUrls[imageIndex]}
    alt=""
    aria-hidden="true"
    className="absolute inset-0 z-0 h-full w-full object-contain"
    onError={() => setImageIndex(index => index + 1)}
  />;
}

type RGBMode = "rainbow" | "static" | "breathing" | "color-cycle" | "off";
type FanFace = "+z" | "-z" | "+x" | "-x";

interface ProceduralFan {
  id: string;
  x: number;
  y: number;
  diameter_mm: number;
  confidence?: number;
  source_image_index?: number;
  source_image_url?: string;
}

interface FanLayout {
  version: 1;
  face: FanFace;
  mode: RGBMode;
  color: string;
  speed: number;
  fans: ProceduralFan[];
}

function youtubeEmbedUrl(url: string) {
  try {
    const parsed = new URL(url);
    const videoId = parsed.hostname.includes("youtu.be")
      ? parsed.pathname.slice(1).split("/")[0]
      : parsed.searchParams.get("v") || parsed.pathname.split("/").filter(Boolean).pop();
    if (!videoId) return null;
    const start = parsed.searchParams.get("t") || parsed.searchParams.get("start");
    return `https://www.youtube-nocookie.com/embed/${videoId}${start ? `?start=${parseInt(start, 10) || 0}` : ""}`;
  } catch {
    return null;
  }
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
  brand?: string | null;
  model?: string | null;
  priority_3d_rank?: number | null;
  sourcing_3d_evidence?: {
    stages?: Record<string, { approved_selection?: unknown }>;
  };
}

const DIRECT_BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4311").replace(/\/$/, "");

function approvedCasePhotoUrls(item: PriorityCaseItem | undefined) {
  const selection = item?.sourcing_3d_evidence?.stages?.product_images?.approved_selection as {
    status?: string;
    images?: Array<{ url?: unknown }>;
  } | undefined;
  const urls = (selection?.images || []).map(image => image.url).filter((url): url is string => typeof url === "string");
  return selection?.status === "approved" && urls.length >= 1 && urls.length <= 4 ? urls : [];
}

const CASE_BRANDS = ["Fractal Design", "Cooler Master", "be quiet!", "Thermaltake", "SilverStone", "Phanteks", "Corsair", "NZXT", "Lian Li", "Montech", "DeepCool", "Antec", "Hyte", "MSI", "ASUS", "APNX", "PCZZOI"];
const CASE_COLOURS = ["Charcoal Black", "ChromaFlair", "Gunmetal Grey", "Satin Black", "Matte Black", "Snow White", "Black", "White", "Grey", "Gray", "Silver", "Red", "Blue"];

function conciseCaseName(item: PriorityCaseItem) {
  const title = item.name.replaceAll("–", "-").replace(/\s+/g, " ").trim();
  const manufacturer = item.brand?.trim() || CASE_BRANDS.find(brand => title.toLowerCase().startsWith(brand.toLowerCase())) || "Case";
  const colour = CASE_COLOURS.find(value => new RegExp(`\\b${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(title));
  let model = item.model?.trim();
  if (!model) {
    const withoutBrand = title.slice(manufacturer === "Case" ? 0 : manufacturer.length).trim();
    model = withoutBrand
      .split(/\s(?:Panoramic|Mid[- ]Tower|Full[- ]Tower|Compact|ATX|Micro[- ]ATX|PC Case|Gaming Case|Tempered|Charcoal|Black|White|Silver)\b|\s*[|,]\s*/i)[0]
      .replace(/\s+-\s*$/, "")
      .trim();
  }
  const displayColour = colour && !model?.toLowerCase().includes(colour.toLowerCase()) ? colour : undefined;
  const parts = [manufacturer, model || undefined, displayColour].filter(Boolean);
  return [...new Set(parts.map(value => value!.toLowerCase()))].map(key => parts.find(value => value!.toLowerCase() === key)).join(" · ");
}

function orderAndLabelAssets(items: Component3DAsset[], cases: PriorityCaseItem[]) {
  const caseById = new Map(cases.map(item => [item.id, item]));
  const labelled = items
    .map(asset => {
      const matchedCase = asset.subject_id ? caseById.get(asset.subject_id) : undefined;
      return {
        ...asset,
        rank: matchedCase?.priority_3d_rank ?? asset.rank ?? null,
        subject_name: matchedCase ? conciseCaseName(matchedCase) : asset.subject_name ?? null,
      };
    });

  // The registry deliberately retains historical versions for audit. The
  // review queue should show only the newest version of each logical asset.
  const newest = new Map<string, Component3DAsset>();
  for (const asset of labelled) {
    const key = [asset.subject_id ?? "generic", asset.category, asset.family_key].join(":");
    const current = newest.get(key);
    if (!current || asset.version > current.version || (asset.version === current.version && asset.id > current.id)) {
      newest.set(key, asset);
    }
  }
  return [...newest.values()].sort((left, right) => (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER));
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

function modelDownloadUrl(url: string) {
  return url.startsWith("http") && !url.includes("localhost") ? `/api/proxy-glb?url=${encodeURIComponent(url)}` : url;
}
// Keep only the next GLB in memory; the active viewer consumes this promise.
let nextModelDownload: { url: string; controller: AbortController; data: Promise<ArrayBuffer> } | null = null;
function preloadNextModel(url: string) {
  const loadUrl = modelDownloadUrl(url);
  if (nextModelDownload?.url === loadUrl) return;
  nextModelDownload?.controller.abort();
  const controller = new AbortController();
  const data = fetch(loadUrl, { signal: controller.signal }).then(response => {
    if (!response.ok) throw new Error(`Model download failed (${response.status})`);
    return response.arrayBuffer();
  });
  const entry = { url: loadUrl, controller, data };
  nextModelDownload = entry;
  void data.catch(() => { if (nextModelDownload === entry) nextModelDownload = null; });
}

let modelLoads = 0;
const modelLoadWaiters: Array<() => void> = [];
async function acquireModelLoad() {
  if (modelLoads >= 2) await new Promise<void>(resolve => modelLoadWaiters.push(resolve));
  else modelLoads += 1;
  let released = false;
  return () => {
    if (released) return;
    released = true;
    const next = modelLoadWaiters.shift();
    if (next) next(); else modelLoads -= 1;
  };
}

function Viewer3D({ glbUrl, fanLayout, caseHeightMm, compact = false, onLoaded }: { onLoaded?: () => void; glbUrl: string | null; fanLayout: FanLayout | null; caseHeightMm: number; compact?: boolean }) {
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;
  // 3D Viewer Configuration:
  // - Camera position: (5, 6, 9) — controls zoom/perspective from the model
  // - Model scale: 10.5 — scales loaded GLB to viewport size
  // - Grid: 200x200 with 40 divisions, matrix green lines (0x00ff00, 0x00aa00)
  // - Lighting: one white directional light attached behind the camera.
  // - Starfield: twinkling background at z-index 0, model canvas at z-index 2
  // - Grid horizon: y = -1.49 (centered in viewport for perspective)
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0, y: 0, isDown: false });
  const modelRef = useRef<any>(null);
  const cameraRef = useRef<any>(null);
  const zoomRef = useRef(1);
  const initialModelRotationRef = useRef<{ x: number; y: number; z: number } | null>(null);
  const fanLayoutRef = useRef<FanLayout | null>(fanLayout);
  const applyFanLayoutRef = useRef<((layout: FanLayout | null) => void) | null>(null);
  const [modelLoading, setModelLoading] = useState(Boolean(glbUrl));
  const [loadProgress, setLoadProgress] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    fanLayoutRef.current = fanLayout;
    applyFanLayoutRef.current?.(fanLayout);
  }, [fanLayout]);

  const changeZoom = (factor: number) => {
    const camera = cameraRef.current;
    if (!camera) return;
    zoomRef.current = Math.min(4, Math.max(0.4, zoomRef.current * factor));
    camera.zoom = zoomRef.current;
    camera.updateProjectionMatrix();
  };

  const resetView = () => {
    zoomRef.current = 1;
    if (cameraRef.current) {
      cameraRef.current.zoom = 1;
      cameraRef.current.updateProjectionMatrix();
    }
    const initialRotation = initialModelRotationRef.current;
    if (modelRef.current && initialRotation) {
      modelRef.current.rotation.set(initialRotation.x, initialRotation.y, initialRotation.z);
    }
  };

  useEffect(() => {
    if (!containerRef.current || !glbUrl) return;
    setLoadError(null);
    setModelLoading(true); setLoadProgress(null);
    cameraRef.current = null;
    modelRef.current = null;
    initialModelRotationRef.current = null;
    zoomRef.current = 1;
    let disposed = false;
    let disposeViewer: (() => void) | undefined;
    let releaseLoad: (() => void) | undefined;

    const setupTimer = window.setTimeout(() => {
      const setupViewer = async () => {
        try {
          releaseLoad = await acquireModelLoad();
          if (disposed) { releaseLoad(); return; }
          const THREE = await import("three");
          const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
          const { MeshoptDecoder } = await import("three/examples/jsm/libs/meshopt_decoder.module.js");

          if (!containerRef.current || !canvasRef.current || disposed) { releaseLoad?.(); return; }

          const width = containerRef.current.clientWidth;
          const height = containerRef.current.clientHeight;

          if (width === 0 || height === 0) { releaseLoad?.(); setModelLoading(false); setLoadError("Viewer has no visible size. Reopen this model."); return; }

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

          // Camera-local +Z is behind the lens; aim forward along local -Z.
          const cameraLight = new THREE.DirectionalLight(0xffffff, 2.0);
          cameraLight.position.set(0, 0, 2);
          cameraLight.target.position.set(0, 0, -1);
          camera.add(cameraLight, cameraLight.target);
          scene.add(camera);

          const renderer = new THREE.WebGLRenderer({
            canvas: canvasRef.current,
            antialias: !compact,
            alpha: true,
            premultipliedAlpha: true,
          });
          let animationId = 0;
          renderer.outputColorSpace = THREE.SRGBColorSpace;
          renderer.toneMapping = THREE.ACESFilmicToneMapping;
          renderer.toneMappingExposure = 1.0;
          renderer.setSize(width, height);
          renderer.setPixelRatio(compact ? 1 : Math.min(window.devicePixelRatio, 1.5));
          renderer.setClearColor(0x000000, 0);
          renderer.domElement.style.position = "absolute";
          renderer.domElement.style.top = "0";
          renderer.domElement.style.left = "0";
          renderer.domElement.style.background = "transparent";
          renderer.domElement.style.backgroundColor = "transparent";
          renderer.domElement.style.zIndex = "2";

          const loader = new GLTFLoader();
          loader.setMeshoptDecoder(MeshoptDecoder);
          loader.crossOrigin = "anonymous";

          // Handle CORS by proxying through local backend
          const loadUrl = modelDownloadUrl(glbUrl);
          const prefetched = nextModelDownload?.url === loadUrl ? nextModelDownload : null;
          if (prefetched) nextModelDownload = null;
          const load: typeof loader.load = (url, success, progress, failure) => {
            if (!prefetched) { loader.load(url, success, progress, failure); return; }
            void prefetched.data.then(bytes => {
              if (disposed) { releaseLoad?.(); return; }
              setLoadProgress(100);
              loader.parse(bytes, new URL(".", new URL(url, window.location.href)).href, success, failure);
            }).catch(() => {
              if (disposed) { releaseLoad?.(); return; }
              loader.load(url, success, progress, failure);
            });
          };

          load(
            loadUrl,
            (gltf) => {
              releaseLoad?.();
              if (!disposed) onLoadedRef.current?.();
              if (disposed) {
                gltf.scene.traverse((node: any) => {
                  node.geometry?.dispose();
                  for (const material of (Array.isArray(node.material) ? node.material : node.material ? [node.material] : [])) {
                    for (const value of Object.values(material) as any[]) if (value?.isTexture) value.dispose();
                    material.dispose();
                  }
                });
                return;
              }
              const model = gltf.scene;

              // Apply bright material to all meshes if they don't have one
              model.traverse((child: any) => {
                if (child.isLight) child.visible = false;
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
              model.updateMatrixWorld(true);
              const inverseModelMatrix = model.matrixWorld.clone().invert();
              const localBounds = new THREE.Box3();
              for (const x of [box.min.x, box.max.x]) {
                for (const y of [box.min.y, box.max.y]) {
                  for (const z of [box.min.z, box.max.z]) {
                    localBounds.expandByPoint(new THREE.Vector3(x, y, z).applyMatrix4(inverseModelMatrix));
                  }
                }
              }
              const size = box.getSize(new THREE.Vector3());
              const maxDim = Math.max(size.x, size.y, size.z);
              const scale = 10.5 / maxDim;
              model.scale.multiplyScalar(scale);

              const center = box.getCenter(new THREE.Vector3());
              const centerY = center.y;
              model.position.sub(center.multiplyScalar(scale));
              // Center the model horizontally and place its lowest point just above the grid.
              model.position.y += gridHelper.position.y - (box.min.y - centerY) * scale + 0.03;

              // Fit the full asset in view so tall cases and their top/bottom fans aren't cropped.
              const fittedBounds = new THREE.Box3().setFromObject(model);
              const fittedSphere = fittedBounds.getBoundingSphere(new THREE.Sphere());
              const verticalHalfFov = THREE.MathUtils.degToRad(camera.fov / 2);
              const horizontalHalfFov = Math.atan(Math.tan(verticalHalfFov) * camera.aspect);
              const limitingHalfFov = Math.min(verticalHalfFov, horizontalHalfFov);
              const cameraDistance = (fittedSphere.radius / Math.sin(limitingHalfFov)) * 1.15;
              const viewDirection = camera.position.clone().normalize();
              camera.position.copy(fittedSphere.center).add(viewDirection.multiplyScalar(cameraDistance));
              camera.lookAt(fittedSphere.center);
              camera.updateProjectionMatrix();

              modelRef.current = model;
              initialModelRotationRef.current = {
                x: model.rotation.x,
                y: model.rotation.y,
                z: model.rotation.z,
              };

              const fanAnimations: Array<{ group: any; ring: any; blades: any; phase: number }> = [];
              const applyFanLayout = (layout: FanLayout | null) => {
                const previous = model.getObjectByName("procedural-rgb-fans");
                if (previous) {
                  previous.traverse((child: any) => {
                    child.geometry?.dispose?.();
                    if (Array.isArray(child.material)) child.material.forEach((material: any) => material.dispose?.());
                    else child.material?.dispose?.();
                  });
                  model.remove(previous);
                }
                fanAnimations.length = 0;
                if (!layout?.fans.length) return;

                const root = new THREE.Group();
                root.name = "procedural-rgb-fans";
                const localSize = localBounds.getSize(new THREE.Vector3());
                const localUnitsPerMm = localSize.y / Math.max(1, caseHeightMm);
                const faceOffset = Math.max(0.004, 0.018 / scale);

                for (const fan of layout.fans) {
                  const radius = Math.max(0.025, fan.diameter_mm * localUnitsPerMm * 0.5);
                  const fanGroup = new THREE.Group();
                  fanGroup.name = `fan-${fan.id}`;
                  const emissiveMaterial = new THREE.MeshStandardMaterial({
                    color: 0x18131b,
                    metalness: 0.45,
                    roughness: 0.35,
                    emissive: new THREE.Color(layout.color),
                    emissiveIntensity: layout.mode === "off" ? 0 : 1.6,
                  });
                  const housingMaterial = new THREE.MeshStandardMaterial({ color: 0x10141a, metalness: 0.65, roughness: 0.52 });
                  const ring = new THREE.Mesh(new THREE.TorusGeometry(radius * 0.9, radius * 0.055, 8, 48), emissiveMaterial);
                  fanGroup.add(ring);
                  fanGroup.add(new THREE.Mesh(new THREE.TorusGeometry(radius * 0.76, radius * 0.025, 6, 40), emissiveMaterial));
                  fanGroup.add(new THREE.Mesh(new THREE.CircleGeometry(radius * 0.72, 40), housingMaterial));

                  const bladeGroup = new THREE.Group();
                  const bladeShape = new THREE.Shape();
                  bladeShape.moveTo(radius * 0.16, radius * 0.1);
                  bladeShape.quadraticCurveTo(radius * 0.62, radius * 0.05, radius * 0.67, radius * 0.34);
                  bladeShape.quadraticCurveTo(radius * 0.43, radius * 0.58, radius * 0.24, radius * 0.39);
                  bladeShape.quadraticCurveTo(radius * 0.13, radius * 0.27, radius * 0.16, radius * 0.1);
                  const bladeGeometry = new THREE.ShapeGeometry(bladeShape, 8);
                  const bladeMaterial = new THREE.MeshStandardMaterial({ color: 0x687080, metalness: 0.35, roughness: 0.38, side: THREE.DoubleSide });
                  for (let bladeIndex = 0; bladeIndex < 7; bladeIndex += 1) {
                    const blade = new THREE.Mesh(bladeGeometry, bladeMaterial);
                    blade.rotation.z = (bladeIndex / 7) * Math.PI * 2;
                    blade.position.z = radius * 0.025;
                    bladeGroup.add(blade);
                  }
                  fanGroup.add(bladeGroup);
                  const hub = new THREE.Mesh(new THREE.CircleGeometry(radius * 0.2, 32), housingMaterial);
                  hub.position.z = radius * 0.06;
                  fanGroup.add(hub);

                  if (layout.face === "+z" || layout.face === "-z") {
                    fanGroup.position.set(
                      localBounds.min.x + (fan.x + 1) * 0.5 * localSize.x,
                      localBounds.min.y + (fan.y + 1) * 0.5 * localSize.y,
                      layout.face === "+z" ? localBounds.max.z + faceOffset : localBounds.min.z - faceOffset,
                    );
                    if (layout.face === "-z") fanGroup.rotation.y = Math.PI;
                  } else {
                    fanGroup.position.set(
                      layout.face === "+x" ? localBounds.max.x + faceOffset : localBounds.min.x - faceOffset,
                      localBounds.min.y + (fan.y + 1) * 0.5 * localSize.y,
                      localBounds.min.z + (fan.x + 1) * 0.5 * localSize.z,
                    );
                    fanGroup.rotation.y = layout.face === "+x" ? Math.PI / 2 : -Math.PI / 2;
                  }
                  root.add(fanGroup);
                  fanAnimations.push({ group: fanGroup, ring: emissiveMaterial, blades: bladeGroup, phase: fanAnimations.length * 0.37 });
                }
                model.add(root);
              };
              applyFanLayoutRef.current = applyFanLayout;
              applyFanLayout(fanLayoutRef.current);

              let isAutoRotating = true;
              const animate = () => {
                animationId = requestAnimationFrame(animate);
                const layout = fanLayoutRef.current;
                const elapsed = performance.now() / 1000;
                for (const fan of fanAnimations) {
                  fan.blades.rotation.z += 0.025 * (layout?.speed || 1);
                  if (!layout || layout.mode === "off") {
                    fan.ring.emissiveIntensity = 0;
                  } else if (layout.mode === "rainbow") {
                    fan.ring.emissive.setHSL((elapsed * 0.16 * layout.speed + fan.phase) % 1, 0.95, 0.55);
                    fan.ring.emissiveIntensity = 1.8;
                  } else if (layout.mode === "color-cycle") {
                    const colors = ["#ff3158", "#ffbd2e", "#36ef86", "#3ca8ff", "#c849ff"];
                    const color = colors[Math.floor((elapsed * layout.speed + fan.phase * 4) % colors.length)];
                    fan.ring.emissive.set(color);
                    fan.ring.emissiveIntensity = 1.8;
                  } else {
                    fan.ring.emissive.set(layout.color);
                    fan.ring.emissiveIntensity = layout.mode === "breathing"
                      ? 0.2 + (0.8 + Math.sin(elapsed * layout.speed * 2.4 + fan.phase) * 0.7)
                      : 1.8;
                  }
                }

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
              setModelLoading(false);

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
            event => {
              if (!disposed && event.total > 0) setLoadProgress(Math.round(event.loaded / event.total * 100));
            },
            (error) => {
              releaseLoad?.();
              if (!disposed) setModelLoading(false);
              console.error("Failed to load GLB:", error, "URL:", glbUrl);
              if (!disposed) setLoadError("This model could not be loaded. Try opening its GLB directly or regenerate the cleaned asset.");
            }
          );

          renderer.render(scene, camera);
          disposeViewer = () => {
            window.cancelAnimationFrame(animationId);
            applyFanLayoutRef.current = null;
            renderer.setAnimationLoop(null);
            scene.traverse((node: any) => {
              node.geometry?.dispose();
              for (const material of (Array.isArray(node.material) ? node.material : node.material ? [node.material] : [])) {
                for (const value of Object.values(material) as any[]) if (value?.isTexture) value.dispose();
                material.dispose();
              }
            });
            scene.clear();
            renderer.dispose();
            renderer.forceContextLoss();
          };
        } catch (error) {
          releaseLoad?.();
          console.error("Error setting up 3D viewer:", error);
          if (!disposed) {
            setModelLoading(false);
            const detail = error instanceof Error ? error.message : String(error);
            setLoadError(`The 3D viewer could not initialise for this asset: ${detail}`);
          }
        }
      };
      void setupViewer();
    }, 100);
    return () => {
      disposed = true;
      window.clearTimeout(setupTimer);
      disposeViewer?.();
    };
  }, [glbUrl, compact]);

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

  return (
    <div ref={containerRef} className="relative h-full w-full rounded border border-slate-700/50 bg-[#080d12]">
      <canvas key={glbUrl ?? "no-model"} ref={canvasRef} className="absolute inset-0 z-10 h-full w-full" aria-label="3D model viewer" />
      <div
        className="absolute right-3 top-3 z-30 flex items-center gap-1 rounded-lg border border-slate-600 bg-slate-950/90 p-1 shadow-lg"
        aria-label="3D view controls"
        onMouseDown={event => event.stopPropagation()}
        onPointerDown={event => event.stopPropagation()}
      >
        <button type="button" aria-label="Zoom in" title="Zoom in" onClick={() => changeZoom(1.25)} className="h-9 w-9 rounded text-xl font-semibold text-slate-100 hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400">+</button>
        <button type="button" aria-label="Zoom out" title="Zoom out" onClick={() => changeZoom(0.8)} className="h-9 w-9 rounded text-xl font-semibold text-slate-100 hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400">−</button>
        <button type="button" aria-label="Reset view" title="Reset view" onClick={resetView} className="h-9 min-w-9 rounded px-2 text-sm font-semibold text-slate-100 hover:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-400">Reset</button>
      </div>
      {modelLoading && !loadError && <div role="status" className="pointer-events-none absolute inset-0 z-40 flex flex-col items-center justify-center gap-3 bg-slate-950/70 text-sm text-slate-100"><Loader2 className="h-8 w-8 animate-spin text-cyan-300" aria-hidden="true" /><span>{loadProgress === null ? "Loading model…" : loadProgress < 100 ? `Loading model · ${loadProgress}%` : "Preparing 3D view…"}</span></div>}
      {loadError && <div role="alert" className="absolute inset-x-4 top-20 z-50 rounded border border-red-400/50 bg-red-950/90 p-3 text-sm text-red-100">{loadError}</div>}
    </div>
  );
}

type WorkspaceProps = { variantIds?: number[]; batchId?: string };

export default function Components3DReviewWorkspace({ variantIds, batchId: requestedBatchId }: WorkspaceProps) {
  const searchParams = useSearchParams();
  const searchQuery = searchParams.toString();
  const router = useRouter();
  const [generationSelection, setGenerationSelection] = useState<Set<number>>(new Set());
  const [queueProgress, setQueueProgress] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [assets, setAssets] = useState<Component3DAsset[]>([]);
  const [caseRecords, setCaseRecords] = useState<PriorityCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAsset, setSelectedAsset] = useState<Component3DAsset | null>(null);
  const [loadedAssetId, setLoadedAssetId] = useState<number | null>(null);
  const [fanLayout, setFanLayout] = useState<FanLayout | null>(null);
  const [selectedFanId, setSelectedFanId] = useState<string | null>(null);
  const [fanPhotoChoice, setFanPhotoChoice] = useState("asset:0");
  const [fanDetectionBusy, setFanDetectionBusy] = useState(false);
  const [fanSaveBusy, setFanSaveBusy] = useState(false);
  const [fanEditorMessage, setFanEditorMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<"meshy_draft" | "all">("all");
  const [batch, setBatch] = useState<ReviewBatch | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [approvalJobs, setApprovalJobs] = useState<Record<number, { asset: Component3DAsset; batchId: string; notes: string; status: "queued" | "saving" | "saved" | "failed"; error?: string }>>({});
  const approvalLocks = useRef(new Set<number>());
  const approvalChain = useRef<Promise<void>>(Promise.resolve());
  const approvalsPending = Object.values(approvalJobs).some(job => job.status === "queued" || job.status === "saving");
  useEffect(() => {
    if (!approvalsPending) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [approvalsPending]);

  const [curatedOnly, setCuratedOnly] = useState(false);
  const [customOnly, setCustomOnly] = useState(false);
  const [returnTo, setReturnTo] = useState<string | null>(null);
  const [regeneratingCaseId, setRegeneratingCaseId] = useState<number | null>(null);
  const [regenerationProgress, setRegenerationProgress] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const loadRevision = useRef(0);

  useEffect(() => {
    setFanLayout(selectedAsset?.fan_layout_json || null);
    setSelectedFanId(selectedAsset?.fan_layout_json?.fans[0]?.id || null);
    setFanPhotoChoice("asset:0");
    setFanEditorMessage(null);
  }, [selectedAsset?.id, selectedAsset?.fan_layout_json]);

  useEffect(() => {
    let cancelled = false;
    setBatch(null);
    if (!selectedAsset?.review_batch_id) return;
    void (async () => {
      try {
        const response = await fetch(`/api/assets-3d/review-batches/${selectedAsset.review_batch_id}`);
        const result = await readJsonResponse<ReviewBatch & { detail?: string }>(response);
        if (!response.ok) throw new Error(result.detail || "Could not load model review");
        if (!cancelled) setBatch(result);
      } catch (error) {
        if (!cancelled) setActionError(error instanceof Error ? error.message : "Could not open model review");
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAsset?.id, selectedAsset?.review_batch_id]);



  useEffect(() => {
    const load = async () => {
      const revision = ++loadRevision.current;
      const isCurrentLoad = () => revision === loadRevision.current;
      setLoading(true);
      try {
        const params = new URLSearchParams(searchQuery);
        let batchId = variantIds ? requestedBatchId : params.get("batch");
        const focusAssetId = Number(params.get("asset_id"));
        const focusCaseId = Number(params.get("case"));
        const isCuratedOnly = !variantIds && params.get("curatedOnly") === "1";
        const isCustomOnly = !variantIds && params.get("customOnly") === "1";
        const requestedReturnTo = variantIds ? null : params.get("returnTo");
        setReturnTo(requestedReturnTo?.startsWith("/catalogue/3d-assets") && !requestedReturnTo.startsWith("//")
          ? requestedReturnTo
          : isCuratedOnly ? "/catalogue/3d-assets?catalogue=curated" : isCustomOnly ? "/catalogue/3d-assets?catalogue=custom" : null);
        setCuratedOnly(isCuratedOnly);
        setCustomOnly(isCustomOnly);
        const queueUrl = `/api/assets-3d${isCuratedOnly ? "?subject_type=variant&curated_only=true" : isCustomOnly ? "?subject_type=variant&custom_only=true" : ""}`;
        const [initialResponse, casesResponse, photoResponse] = await Promise.all([
          fetch(batchId ? `/api/assets-3d/review-batches/${batchId}` : queueUrl),
          fetch("/api/cases/priority-for-3d?limit=100"),
          batchId ? Promise.resolve(null) : fetch("/api/assets-3d/catalogue/photo-queue", { cache: "no-store" }),
        ]);
        if (!isCurrentLoad()) return;
        let response = initialResponse;
        if (batchId && response.status === 404) {
          // A bookmarked batch can disappear when its models are deleted.
          // Return to the current queue without treating deletion as a crash.
          batchId = null;
          setBatch(null);
          setSelectedAsset(null);
          setActionError(null);
          setActionNotice("That review batch no longer exists. Showing the current model approval queue.");
          if (!variantIds) {
            const url = new URL(window.location.href);
            url.searchParams.delete("batch");
            window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
          }
          response = await fetch(queueUrl);
          if (!isCurrentLoad()) return;
        }
        const data = await readJsonResponse<Component3DAsset[] | { detail?: string; error?: string; data?: Component3DAsset[]; assets?: Component3DAsset[] }>(response);
        const priorityCases = casesResponse.ok ? await readJsonResponse<PriorityCaseItem[]>(casesResponse) : [];
        setCaseRecords(priorityCases);

        if (!Array.isArray(data) && data.detail) {
          setActionError(data.detail);
          console.error("API Error:", data.detail);
          setAssets([]);
          return;
        }

        if (!Array.isArray(data) && data.error) {
          setActionError(data.error);
          console.error("API returned error:", data.error);
          setAssets([]);
          return;
        }

        let loadedAssets = orderAndLabelAssets(
          Array.isArray(data) ? data : (data.data || data.assets || []),
          priorityCases,
        );
        if (focusAssetId && !batchId) loadedAssets = loadedAssets.filter(asset => asset.id === focusAssetId);
        if (variantIds && !batchId) {
          loadedAssets = loadedAssets.filter(asset => asset.subject_type === "variant" && typeof asset.subject_id === "number" && variantIds.includes(asset.subject_id));
        }
        if (batchId) {
          setBatch({ ...data, assets: loadedAssets } as ReviewBatch);
        } else {
          // Resume an already-claimed review batch automatically. Previously
          // these assets looked reviewable but both decision buttons remained disabled.
          // Resume batches that still need publication as well as batches with
          // undecided assets. An approved draft has a decision, but remains
          // inactive until Publish approved models is clicked.
          const pendingBatchId = loadedAssets.find(asset =>
            asset.review_batch_id && !asset.is_active && asset.review_decision !== "rejected"
          )?.review_batch_id;
          if (pendingBatchId && (variantIds || focusAssetId || focusCaseId)) {
            const batchResponse = await fetch(`/api/assets-3d/review-batches/${pendingBatchId}`);
            if (!isCurrentLoad()) return;
            if (batchResponse.ok) {
              const batchData = await readJsonResponse<ReviewBatch>(batchResponse);
              loadedAssets = orderAndLabelAssets(batchData.assets, priorityCases);
              setBatch({ ...batchData, assets: loadedAssets });
              if (!variantIds) window.history.replaceState(null, "", `?batch=${pendingBatchId}`);
            }
          }
        }
        const completedModelIds = new Map<number, number>();
        if (!batchId && !focusAssetId && !focusCaseId) {
          if (!photoResponse?.ok) throw new Error("Could not load approved components awaiting 3D models");
          const photos = await readJsonResponse<ApprovedPhotoItem[]>(photoResponse);
          for (const item of photos) if (item.asset) completedModelIds.set(item.variant_id, item.asset.id);
          const missing: Component3DAsset[] = photos.filter(item => item.main_photo_approved
            && (!variantIds || item.variant_ids.some(id => variantIds.includes(id)))
            && !item.asset).map(item => ({
              id: -item.variant_id, catalogue_variant_id: item.variant_id,
              category: item.category, family_key: item.media_family_key || "",
              subject_name: item.title, status: "missing", version: 0,
              glb_ref: null, preview_image_ref: item.main_photo_url || null,
              source_image_refs: item.main_photo_url ? [item.main_photo_url] : [],
              file_size_kb: null, poly_count: null, notes: null, created_by: null, created_at: null,
              generation_enabled: item.automatic_media_preparation_enabled !== false,
              generation_status: item.asset_media_review?.generation?.status,
              generation_progress: item.asset_media_review?.generation?.progress,
              generation_error: item.asset_media_review?.generation?.error,
            }));
          loadedAssets = [...loadedAssets, ...missing];
        }
        setAssets(loadedAssets);
        const caseAsset = Number.isFinite(focusCaseId) && focusCaseId > 0
          ? loadedAssets.find(asset => asset.subject_type === "case" && asset.subject_id === focusCaseId && asset.review_decision === "rejected")
            || loadedAssets.find(asset => asset.subject_type === "case" && asset.subject_id === focusCaseId)
          : undefined;
        setSelectedAsset(current => caseAsset || loadedAssets.find(asset => asset.id === focusAssetId) || loadedAssets.find(asset => asset.id === current?.id) || loadedAssets.find(asset => asset.id === completedModelIds.get(current?.catalogue_variant_id || 0)) || loadedAssets[0] || null);
      } catch (error) {
        if (!isCurrentLoad()) return;
        setActionError(error instanceof Error ? error.message : "Could not load model review");
        console.error("Error loading assets:", error);
        setAssets([]);
      } finally {
        if (isCurrentLoad()) setLoading(false);
      }
    };
    void load();
  }, [variantIds, requestedBatchId, refreshVersion, searchQuery]);

  const generatingMissing = assets.some(asset => activeModelJobs.has(asset.generation_status || ""));
  useEffect(() => {
    if (!generatingMissing) return;
    const timer = window.setInterval(() => setRefreshVersion(value => value + 1), 5000);
    return () => window.clearInterval(timer);
  }, [generatingMissing]);

  const generateMissingModel = async () => {
    if (!selectedAsset?.catalogue_variant_id || actionBusy) return;
    setActionBusy(true); setActionError(null);
    try {
      const response = await fetch(`/api/assets-3d/variants/${selectedAsset.catalogue_variant_id}/auto-prepare`, {
        method: "POST", headers: { "content-type": "application/json" }, body: "{}",
      });
      const result = await readJsonResponse<{ detail?: string }>(response);
      if (!response.ok) throw new Error(result.detail || "Could not start model generation");
      setActionNotice("Model generation started from the approved photo. The textured GLB will appear here when ready.");
      setRefreshVersion(value => value + 1);
    } catch (error) { setActionError(error instanceof Error ? error.message : "Could not generate model"); }
    finally { setActionBusy(false); }
  };

  const canQueueModel = (asset: Component3DAsset) => Boolean(asset.catalogue_variant_id
    && asset.generation_enabled && !asset.glb_ref && !activeModelJobs.has(asset.generation_status || ""));
  const queueSelectedModels = async () => {
    if (actionBusy) return;
    const candidates = assets.filter(asset => canQueueModel(asset) && generationSelection.has(asset.catalogue_variant_id!));
    if (!candidates.length) return;
    setActionBusy(true); setActionError(null); setActionNotice(null);
    const failures: string[] = [];
    let accepted = 0;
    try {
      for (let index = 0; index < candidates.length; index += 1) {
        const asset = candidates[index];
        setQueueProgress(`Adding models to the queue · ${index + 1}/${candidates.length}`);
        try {
          const response = await fetch(`/api/assets-3d/variants/${asset.catalogue_variant_id}/auto-prepare`, {
            method: "POST", headers: { "content-type": "application/json" }, body: "{}",
          });
          const result = await readJsonResponse<{ detail?: string }>(response);
          if (!response.ok) throw new Error(result.detail || "Could not queue model");
          accepted += 1;
          setGenerationSelection(current => { const next = new Set(current); next.delete(asset.catalogue_variant_id!); return next; });
          setAssets(current => current.map(item => item.id === asset.id ? { ...item, generation_status: "PREPARING", generation_progress: 0, generation_error: null } : item));
          setSelectedAsset(current => current?.id === asset.id ? { ...current, generation_status: "PREPARING", generation_progress: 0, generation_error: null } : current);
        } catch (error) {
          failures.push(`${asset.subject_name}: ${error instanceof Error ? error.message : "Could not queue model"}`);
        }
      }
      setActionNotice(`${accepted} model${accepted === 1 ? "" : "s"} queued for Meshy generation. You can leave this page once submission finishes.`);
      if (failures.length) setActionError(`${failures.length} could not be queued: ${failures.join(" · ")}`);
      setRefreshVersion(value => value + 1);
    } finally { setActionBusy(false); setQueueProgress(null); }
  };

  const filteredAssets = filter === "meshy_draft" ? assets.filter(a => a.status === "meshy_draft") : assets;
  useEffect(() => {
    if (!selectedAsset || loadedAssetId !== selectedAsset.id) return;
    const index = filteredAssets.findIndex(asset => asset.id === selectedAsset.id);
    const next = [...filteredAssets.slice(index + 1), ...filteredAssets.slice(0, index)].find(asset =>
      asset.glb_ref && !asset.review_decision && !approvalLocks.current.has(asset.id));
    if (next?.glb_ref) preloadNextModel(next.glb_ref);
    else { nextModelDownload?.controller.abort(); nextModelDownload = null; }
  }, [selectedAsset, loadedAssetId, assets, filter, approvalJobs]);
  useEffect(() => () => { nextModelDownload?.controller.abort(); nextModelDownload = null; }, []);
  const queueableShown = filteredAssets.filter(canQueueModel);
  const selectedForGeneration = assets.filter(asset => canQueueModel(asset) && generationSelection.has(asset.catalogue_variant_id!));
  const draftCount = assets.filter(a => a.status === "meshy_draft").length;
  const validatedCount = assets.filter(a => a.status === "validated").length;
  const finalCount = assets.filter(a => a.status === "final").length;

  const selectApprovalAsset = (asset: Component3DAsset) => {
    setSelectedAsset(asset);
  };

  const handlePreviousAsset = () => {
    const currentIndex = filteredAssets.findIndex(a => a.id === selectedAsset?.id);
    if (currentIndex > 0) {
      void selectApprovalAsset(filteredAssets[currentIndex - 1]);
    }
  };

  const handleNextAsset = () => {
    const currentIndex = filteredAssets.findIndex(a => a.id === selectedAsset?.id);
    if (currentIndex < filteredAssets.length - 1) {
      void selectApprovalAsset(filteredAssets[currentIndex + 1]);
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
    const scopedAssets = assets.filter(asset => !asset.is_active && !asset.review_batch_id
      && (asset.status === "meshy_draft" || asset.status === "cleaned") && asset.glb_ref).slice(0, 10);
    if (variantIds && !scopedAssets.length) {
      setActionError("No unclaimed draft models for this build. Generate a draft from the Photos & generation step first.");
      return;
    }
    setActionBusy(true);
    setActionError(null);
    try {
      const response = await fetch("/api/assets-3d/review-batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size: 10, curated_only: curatedOnly, custom_only: customOnly,
          ...((variantIds || new URLSearchParams(window.location.search).has("asset_id")) ? { asset_ids: scopedAssets.map(asset => asset.id) } : {}),
        }),
      });
      const data = await readJsonResponse<ReviewBatch & { detail?: string; error?: string }>(response);
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

  const queueApproval = (asset: Component3DAsset, batchId: string, notes: string) => {
    if (approvalLocks.current.has(asset.id)) return;
    approvalLocks.current.add(asset.id);
    setApprovalJobs(current => ({ ...current, [asset.id]: { asset, batchId, notes, status: "queued" } }));
    approvalChain.current = approvalChain.current.then(async () => {
      setApprovalJobs(current => ({ ...current, [asset.id]: { asset, batchId, notes, status: "saving" } }));
      try {
        const response = await fetch(`/api/assets-3d/review-batches/${encodeURIComponent(batchId)}/assets/${asset.id}/decision`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision: "approved", notes: notes || null }), signal: AbortSignal.timeout(60000),
        });
        const data = await readJsonResponse<Partial<Component3DAsset> & { detail?: string; error?: string }>(response);
        if (!response.ok) throw new Error(data.detail || data.error || "Could not save approval");
        const reviewed = { ...asset, ...data } as Component3DAsset;
        setAssets(current => current.map(item => item.id === asset.id ? reviewed : item));
        setSelectedAsset(current => current?.id === asset.id ? reviewed : current);
        setBatch(current => {
          if (!current || current.batch_id !== batchId) return current;
          const updated = current.assets.map(item => item.id === asset.id ? reviewed : item);
          const decided = updated.filter(item => item.review_decision).length;
          return { ...current, assets: updated, decided, complete: decided === current.size };
        });
        setApprovalJobs(current => ({ ...current, [asset.id]: { asset, batchId, notes, status: "saved" } }));
      } catch (error) {
        setApprovalJobs(current => ({ ...current, [asset.id]: { asset, batchId, notes, status: "failed", error: error instanceof Error ? error.message : "Could not save approval" } }));
      } finally { approvalLocks.current.delete(asset.id); }
    });
  };

  const decideAsset = async (decision: "approved" | "rejected") => {
    if (!batch || !selectedAsset) return;
    if (decision === "approved") {
      queueApproval(selectedAsset, batch.batch_id, reviewNotes);
      const index = filteredAssets.findIndex(asset => asset.id === selectedAsset.id);
      const next = [...filteredAssets.slice(index + 1), ...filteredAssets.slice(0, index)].find(asset =>
        asset.glb_ref && !asset.review_decision && !approvalLocks.current.has(asset.id) && batch.assets.some(item => item.id === asset.id));
      if (next) setSelectedAsset(next);
      setReviewNotes("");
      return;
    }
    setActionBusy(true);
    setActionError(null);
    setActionNotice(null);
    try {
      const response = await fetch(`/api/assets-3d/review-batches/${batch.batch_id}/assets/${selectedAsset.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, notes: reviewNotes || null }),
      });
      const data = await readJsonResponse<Partial<Component3DAsset> & { id: number; detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(data.detail || data.error || "Could not save decision");
      const reviewedAsset = { ...selectedAsset, ...data } as Component3DAsset;
      setAssets(current => current.map(asset => asset.id === reviewedAsset.id ? reviewedAsset : asset));
      setBatch(current => {
        if (!current || current.batch_id !== batch.batch_id) return current;
        const updatedAssets = current.assets.map(asset => asset.id === reviewedAsset.id ? reviewedAsset : asset);
        const decided = updatedAssets.filter(asset => asset.review_decision).length;
        return { ...current, assets: updatedAssets, decided, complete: decided === current.size };
      });
      setSelectedAsset(current => current?.id === reviewedAsset.id ? reviewedAsset : current);
      setReviewNotes("");
      if (data.regeneration?.message) setActionNotice(data.regeneration.message);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not save decision");
    } finally {
      setActionBusy(false);
    }
  };

  const reopenVisualReview = async () => {
    if (!batch || !selectedAsset || selectedAsset.review_decision !== "approved") return;
    setActionBusy(true);
    setActionError(null);
    setActionNotice(null);
    try {
      const response = await fetch(`/api/assets-3d/review-batches/${batch.batch_id}/assets/${selectedAsset.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "pending" }),
      });
      const data = await readJsonResponse<Partial<Component3DAsset> & { id: number; detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(data.detail || data.error || "Could not reopen visual review");
      const reopenedAsset = { ...selectedAsset, ...data } as Component3DAsset;
      const updatedAssets = batch.assets.map(asset => asset.id === data.id ? reopenedAsset : asset);
      const updatedBatch = { ...batch, assets: updatedAssets, decided: updatedAssets.filter(asset => asset.review_decision).length };
      updatedBatch.complete = updatedBatch.decided === updatedBatch.size;
      setBatch(updatedBatch);
      setAssets(updatedAssets);
      setSelectedAsset(reopenedAsset);
      setActionNotice("Model unapproved and unpublished. You can review it again.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not reopen visual review");
    } finally {
      setActionBusy(false);
    }
  };

  const detectFansFromPhoto = async () => {
    if (!selectedAsset || selectedAsset.subject_type !== "case") return;
    const [sourceSet, sourceIndexText] = fanPhotoChoice.split(":");
    const sourceIndex = Number(sourceIndexText);
    const sourceUrls = sourceSet === "approved"
      ? approvedCasePhotoUrls(caseRecords.find(item => item.id === selectedAsset.subject_id))
      : selectedAsset.source_image_refs || [];
    const imageUrl = sourceUrls[sourceIndex];
    if (!imageUrl) {
      setFanEditorMessage("This asset has no source photo at that position.");
      return;
    }
    setFanDetectionBusy(true);
    setFanEditorMessage(null);
    try {
      const detections = await detectRgbFans(imageUrl);
      if (!detections.length) {
        setFanEditorMessage("No clear RGB rings detected. Choose a front-facing photo or add fans manually.");
        return;
      }
      const caseHeightMm = selectedAsset.dimensions_mm?.height || 500;
      const fans: ProceduralFan[] = detections.map((detection, index) => ({
        id: crypto.randomUUID(),
        // Detection coordinates are normalized to the selected photo. Map that
        // photo frame directly onto the model face; the prior 2.2 multiplier
        // pushed detections near the image edge outside the case bounds.
        x: Math.max(-1, Math.min(1, (detection.centerX - 0.5) * 2)),
        y: Math.max(-1, Math.min(1, (0.5 - detection.centerY) * 2)),
        diameter_mm: Math.max(60, Math.min(200, Math.round((detection.radius * 2 * caseHeightMm) / 10) * 10)),
        confidence: Number(detection.confidence.toFixed(2)),
        source_image_index: sourceIndex,
        source_image_url: imageUrl,
      }));
      setFanLayout(current => ({
        version: 1,
        face: current?.face || "+z",
        mode: current?.mode || "rainbow",
        color: current?.color || "#ff4fb3",
        speed: current?.speed || 1,
        fans,
      }));
      setSelectedFanId(fans[0]?.id || null);
      setFanEditorMessage(`Found ${fans.length} RGB fan candidate${fans.length === 1 ? "" : "s"}. Review their placement and size in the 3D view before saving.`);
    } catch (error) {
      setFanEditorMessage(error instanceof Error ? error.message : "Could not analyse this reference photo.");
    } finally {
      setFanDetectionBusy(false);
    }
  };

  const updateFanLayout = (update: (current: FanLayout) => FanLayout) => {
    setFanLayout(current => current ? update(current) : {
      version: 1,
      face: "+z",
      mode: "rainbow",
      color: "#ff4fb3",
      speed: 1,
      fans: [],
    });
  };

  const addManualFan = () => {
    const fan: ProceduralFan = {
      id: crypto.randomUUID(),
      x: 0,
      y: 0,
      diameter_mm: 120,
    };
    updateFanLayout(current => ({ ...current, fans: [...current.fans, fan] }));
    setSelectedFanId(fan.id);
    setFanEditorMessage("Fan added at the centre of the selected case face. Adjust its position and size, then save.");
  };

  const saveFanLayout = async () => {
    if (!selectedAsset || selectedAsset.subject_type !== "case" || !fanLayout) return;
    setFanSaveBusy(true);
    setFanEditorMessage(null);
    try {
      const response = await fetch(`/api/assets-3d/${selectedAsset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fan_layout_json: fanLayout }),
      });
      const data = await readJsonResponse<Component3DAsset & { detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(data.detail || data.error || "Could not save the fan layout");
      const updatedAssets = assets.map(asset => asset.id === data.id ? { ...asset, ...data } : asset);
      setAssets(updatedAssets);
      setSelectedAsset(current => current?.id === data.id ? { ...current, ...data } : current);
      setBatch(current => current ? { ...current, assets: current.assets.map(asset => asset.id === data.id ? { ...asset, ...data } : asset) } : current);
      setFanEditorMessage("Fan layout saved with this model version.");
    } catch (error) {
      setFanEditorMessage(error instanceof Error ? error.message : "Could not save the fan layout");
    } finally {
      setFanSaveBusy(false);
    }
  };

  const regenerateRejectedCase = async () => {
    if (!selectedAsset || selectedAsset.subject_type !== "case" || selectedAsset.subject_id == null) return;
    const caseId = selectedAsset.subject_id;
    const imageUrls = approvedCasePhotoUrls(caseRecords.find(item => item.id === caseId));
    if (imageUrls.length < 1 || imageUrls.length > 4) {
      setActionError("Approve between one and four reference photos for this case in Photos & generation before regenerating.");
      return;
    }
    const requestId = crypto.randomUUID();
    setRegeneratingCaseId(caseId);
    setRegenerationProgress(0);
    setActionError(null);
    setActionNotice(`Generating a new draft from the ${imageUrls.length} currently approved photo${imageUrls.length === 1 ? "" : "s"}, including photo-guided texturing…`);
    const pollProgress = async () => {
      try {
        const statusResponse = await fetch(
          `${DIRECT_BACKEND_URL}/api/assets-3d/cases/${caseId}/generate-status?request_id=${encodeURIComponent(requestId)}`,
          { credentials: "include", cache: "no-store" },
        );
        if (!statusResponse.ok) return;
        const status = await readJsonResponse<{ request_id: string; progress: number }>(statusResponse);
        if (status.request_id === requestId) {
          setRegenerationProgress(Math.max(0, Math.min(100, Math.round(status.progress))));
        }
      } catch {
        // Keep the active generation moving if a status poll briefly fails.
      }
    };
    void pollProgress();
    const progressTimer = window.setInterval(() => void pollProgress(), 1500);
    try {
      const response = await fetch(`${DIRECT_BACKEND_URL}/api/assets-3d/cases/${caseId}/generate`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          image_urls: imageUrls,
          request_id: requestId,
          notes: `Regenerated from the current owner-approved case photos after rejecting asset ${selectedAsset.id}.`,
        }),
      });
      const result = await readJsonResponse<{ id: number; review_batch_id?: string | null; detail?: string }>(response);
      if (!response.ok) throw new Error(result.detail || "Could not regenerate the case model");
      if (!result.review_batch_id) throw new Error("The draft was created, but its review batch is missing.");
      router.push(`/components-3d-review?batch=${encodeURIComponent(result.review_batch_id)}`);
    } catch (error) {
      setActionNotice(null);
      setActionError(error instanceof Error ? error.message : "Could not regenerate the case model");
    } finally {
      window.clearInterval(progressTimer);
      setRegeneratingCaseId(null);
    }
  };

  const statusColors: Record<string, string> = {
    meshy_draft: "border-amber-500/50", cleaned: "border-blue-500/50",
    validated: "border-purple-500/50", final: "border-emerald-500/50", rejected: "border-red-500/50",
  };
  const getStatusStyle = (status: string) => ({
    meshy_draft: "bg-amber-500/20 text-amber-200", cleaned: "bg-blue-500/20 text-blue-200",
    validated: "bg-purple-500/20 text-purple-200", final: "bg-emerald-500/20 text-emerald-200",
    rejected: "bg-red-500/20 text-red-200",
  }[status] || "bg-slate-700 text-slate-200");

  const reloadModelApproval = () => {
    setActionError(null);
    setBatch(null);
    // Reset selection so its batch is fetched again after a failed read.
    setSelectedAsset(null);
    setRefreshVersion(value => value + 1);
  };

  return (
    <>
      <style>{gradientStyle}</style>
      <div style={{ height: variantIds ? "75vh" : "100vh", animation: "bgShift 8s ease-in-out infinite" }} className="w-full flex flex-col gap-3 p-4 pb-0 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="whitespace-nowrap text-lg font-bold text-slate-100">3D Assets</h1>
          {variantIds && batch?.assets.some(asset => asset.subject_type !== "variant" || typeof asset.subject_id !== "number" || !variantIds.includes(asset.subject_id)) && <p role="status" className="max-w-sm text-xs text-amber-200">This shared review batch also contains products from other builds. All batch models are shown; publishing applies to every approved model in this batch.</p>}
          {!variantIds && <ThreeDWorkflowNav compact onReloadCurrent={reloadModelApproval} />}
          {returnTo && <a href={returnTo} className="whitespace-nowrap rounded-md border border-cyan-500/40 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/10">← Back to product photos</a>}
        </div>
        <div className="flex items-center gap-3">
          {batch ? (
            <>
              <div className="rounded-md border border-slate-600 bg-slate-950/80 px-3 py-2 text-sm text-slate-200" role="status">
                Batch {batch.decided}/{batch.size} reviewed
              </div>
            </>
          ) : (
              <button
                type="button"
                onClick={startReviewBatch}
              disabled={actionBusy || !assets.some(asset => asset.id > 0 && asset.glb_ref && !asset.review_batch_id)}
              className="cursor-pointer rounded-md border border-sky-500 bg-sky-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {curatedOnly ? "Start curated batch" : customOnly ? "Start custom batch" : "Start next batch of 10"}
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
      {Object.keys(approvalJobs).length > 0 && <section aria-label="Approval queue" className="shrink-0 rounded border border-cyan-400/30 bg-slate-950/90 px-4 py-2 text-sm text-slate-100">
        <p role="status">Approvals: {Object.values(approvalJobs).filter(job => job.status === "saved").length} saved · {Object.values(approvalJobs).filter(job => job.status === "queued" || job.status === "saving").length} pending · {Object.values(approvalJobs).filter(job => job.status === "failed").length} failed. {approvalsPending && "Keep this page open while approvals save."}</p>
        {Object.values(approvalJobs).filter(job => job.status === "failed").map(job => <div key={job.asset.id} role="alert" className="mt-1 flex items-center gap-3 text-rose-200"><span>{job.asset.subject_name || job.asset.family_key}: {job.error}</span><button type="button" onClick={() => queueApproval(job.asset, job.batchId, job.notes)} className="rounded border border-rose-300/50 px-2 py-1">Retry approval</button></div>)}
      </section>}
      {actionError && <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-red-500/60 bg-red-950/80 px-4 py-2 text-sm text-red-200"><span>{actionError}</span><button type="button" onClick={reloadModelApproval} disabled={actionBusy} className="shrink-0 rounded border border-red-300/40 px-3 py-1 disabled:opacity-40">Reload model approval</button></div>}
      {actionNotice && <div role="status" className="rounded-md border border-sky-500/60 bg-sky-950/80 px-4 py-2 text-sm text-sky-100">{actionNotice}</div>}

      {assets.some(asset => asset.catalogue_variant_id) && <section aria-label="Queue models from approved photos" className="flex shrink-0 flex-wrap items-center gap-3 rounded-lg border border-cyan-400/30 bg-slate-950/90 px-4 py-3 text-sm text-slate-100">
        <button type="button" disabled={actionBusy || !queueableShown.length} onClick={() => setGenerationSelection(current => new Set([...current, ...queueableShown.map(asset => asset.catalogue_variant_id!)]))} className="rounded border border-slate-500 px-3 py-2 disabled:opacity-40">Select all shown ({queueableShown.length})</button>
        <button type="button" disabled={actionBusy || !generationSelection.size} onClick={() => setGenerationSelection(new Set())} className="px-2 py-2 disabled:opacity-40">Clear selection</button>
        <span>{selectedForGeneration.length} selected · one approved photo per case/family</span>
        <span className="text-xs text-amber-200">Uses Meshy credits</span>
        <button type="button" onClick={() => void queueSelectedModels()} disabled={actionBusy || !selectedForGeneration.length} className="ml-auto rounded bg-cyan-400 px-4 py-2 font-semibold text-slate-950 disabled:opacity-40">{queueProgress || `Queue selected models (${selectedForGeneration.length})`}</button>
      </section>}

      <MeshyGenerationQueue refreshKey={refreshVersion} />

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
                      if (asset.review_decision === "approved" || asset.status === "final") return { icon: "✓", color: "bg-[#00dc82]" };
                      if (asset.status === "rejected") return { icon: "✗", color: "bg-red-500" };
                      if (asset.status === "meshy_draft") return { icon: "?", color: "bg-amber-500" };
                      if (asset.status === "cleaned") return { icon: "C", color: "bg-blue-500" };
                      if (asset.status === "validated") return { icon: "V", color: "bg-purple-500" };
                      return { icon: "?", color: "bg-slate-600" };
                    };
                    const statusIcon = getStatusIcon();
                    return (
                      <div key={asset.id} className={`relative rounded ${asset.catalogue_variant_id && generationSelection.has(asset.catalogue_variant_id) ? "ring-2 ring-cyan-300" : ""}`}>
                      <button
                        onClick={() => void selectApprovalAsset(asset)}
                        className={`group rounded border overflow-hidden cursor-pointer transition hover:scale-105 relative flex flex-col ${selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""} ${statusColors[asset.status] || ""}`}
                        style={{ width: "120px", height: "120px", backgroundColor: "#1a3a52" }}
                      >
                        <ModelAssetThumbnail asset={asset} />
                        {/* Status badge overlay */}
                        {asset.glb_ref && (
                          <div role="img" aria-label={asset.review_decision === "approved" || asset.status === "final" ? "Model approved" : `Model status: ${asset.status}`} title={asset.review_decision === "approved" || asset.status === "final" ? "Model approved" : asset.status} className={`absolute top-1 right-1 flex h-6 w-6 items-center justify-center rounded-full text-sm font-bold text-white shadow-lg ring-1 ring-black/30 ${asset.review_decision === "approved" || asset.status === "final" ? "opacity-100" : "opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"} ${statusIcon.color}`}>
                            {statusIcon.icon}
                          </div>
                        )}
                        {asset.rank && <div className="absolute left-1 top-1 rounded bg-black/80 px-1.5 py-0.5 text-[10px] font-bold text-white shadow">#{asset.rank}</div>}
                        <div className="flex-1"></div>
                        <div className="w-full translate-y-1 bg-black/75 px-1 py-1.5 text-center opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
                          <div className="line-clamp-2 text-[10px] font-semibold leading-tight text-white">{asset.subject_name || asset.family_key}</div>
                        </div>
                      </button>
                      {asset.catalogue_variant_id && <input type="checkbox" aria-label={`Queue model for ${asset.subject_name || asset.family_key}`} checked={generationSelection.has(asset.catalogue_variant_id)} disabled={actionBusy || !canQueueModel(asset)} onChange={event => setGenerationSelection(current => { const next = new Set(current); event.target.checked ? next.add(asset.catalogue_variant_id!) : next.delete(asset.catalogue_variant_id!); return next; })} className="absolute right-2 top-2 z-10 h-5 w-5 accent-cyan-400 disabled:opacity-40" />}
                      {activeModelJobs.has(asset.generation_status || "") && <span role="status" className="absolute inset-x-0 bottom-0 bg-slate-950/90 px-1 py-1 text-center text-[10px] text-cyan-200">{asset.generation_status === "PREPARING" ? "Queued / preparing" : "Generating"} · {asset.generation_progress || 0}%</span>}
                      </div>
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
                <Viewer3D
                  glbUrl={selectedAsset.glb_ref}
                  onLoaded={() => setLoadedAssetId(selectedAsset.id)}
                  fanLayout={selectedAsset.subject_type === "case" ? fanLayout : null}
                  caseHeightMm={selectedAsset.dimensions_mm?.height || 500}
                />

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
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex justify-center px-20 pt-4">
                  <h1 className="max-w-2xl rounded-md bg-black/45 px-3 py-1.5 text-center text-xl font-bold text-white drop-shadow-lg backdrop-blur-sm" style={{ textShadow: "0 2px 12px rgba(0,0,0,0.8)" }}>
                    {selectedAsset.subject_name || selectedAsset.family_key}
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

                      {selectedAsset.catalogue_variant_id && <div className="my-3 space-y-2 rounded border border-cyan-400/30 bg-slate-950/80 p-3 text-xs">
                        <p className="text-cyan-200">Photo approved · 3D model required</p>
                        {selectedAsset.generation_error && <p role="alert" className="text-rose-200">{selectedAsset.generation_error}</p>}
                        {activeModelJobs.has(selectedAsset.generation_status || "") ? <p role="status">Generating textured model · {selectedAsset.generation_progress || 0}%</p> : <button type="button" onClick={() => void generateMissingModel()} disabled={actionBusy || !selectedAsset.generation_enabled} className="w-full rounded bg-cyan-400 px-3 py-2 font-semibold text-slate-950 disabled:opacity-50">{actionBusy ? "Starting…" : "Generate 3D model"}</button>}
                        <p className="text-slate-400">Uses the approved photo and Meshy credits. The model will load in this viewer for approval.</p>
                      </div>}
                      <div className="space-y-2 relative z-50">
                        <div className="flex gap-1 relative z-50">
                          <button disabled={!batch?.assets.some(asset => asset.id === selectedAsset.id) || actionBusy || !selectedAsset.glb_ref || Boolean(selectedAsset.review_decision) || approvalJobs[selectedAsset.id]?.status === "queued" || approvalJobs[selectedAsset.id]?.status === "saving"} onClick={() => decideAsset("rejected")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-red-600/40 text-red-300 border border-red-500/50 hover:bg-red-600/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
                            Reject
                          </button>
                          <button disabled={!batch?.assets.some(asset => asset.id === selectedAsset.id) || actionBusy || !selectedAsset.glb_ref || Boolean(selectedAsset.review_decision) || approvalJobs[selectedAsset.id]?.status === "queued" || approvalJobs[selectedAsset.id]?.status === "saving"} onClick={() => decideAsset("approved")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-[#00dc82]/40 text-[#00dc82] border border-[#00dc82]/50 hover:bg-[#00dc82]/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
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
                        {selectedAsset.review_decision === "approved" && <button type="button" onClick={reopenVisualReview} disabled={actionBusy || approvalsPending} className="w-full rounded border border-amber-400/40 px-2 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-400/10 disabled:opacity-50">Unapprove and unpublish model</button>}
                        <p className="text-[11px] text-slate-400">Approving confirms visual quality, usage rights and scale, and publishes this model for reuse.</p>
                        {selectedAsset.regeneration?.message && (
                          <p className={selectedAsset.regeneration.status === "queued" ? "text-xs text-sky-300" : "text-xs text-amber-300"}>
                            {selectedAsset.regeneration.message}
                          </p>
                        )}
                        {selectedAsset.subject_type === "case" && selectedAsset.subject_id != null && selectedAsset.review_decision === "rejected" && (
                          approvedCasePhotoUrls(caseRecords.find(item => item.id === selectedAsset.subject_id)).length > 0 ? (
                            <>
                              <button
                                type="button"
                                onClick={() => void regenerateRejectedCase()}
                                disabled={regeneratingCaseId === selectedAsset.subject_id}
                                className="w-full cursor-pointer rounded border border-purple-400/60 bg-purple-700/40 px-2 py-2 text-xs font-semibold text-purple-100 hover:bg-purple-700/60 disabled:cursor-wait disabled:opacity-50"
                              >
                                <span className="inline-flex items-center gap-2">
                                  {regeneratingCaseId === selectedAsset.subject_id && <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
                                  Regenerate with approved case photos
                                </span>
                              </button>
                              {regeneratingCaseId === selectedAsset.subject_id && (
                                <div className="space-y-1.5" role="status" aria-live="polite">
                                  <div className="flex justify-between text-[11px] text-slate-300">
                                    <span>Meshy generation progress</span>
                                    <span>{regenerationProgress}%</span>
                                  </div>
                                  <div
                                    className="h-2 overflow-hidden rounded-full bg-slate-700"
                                    role="progressbar"
                                    aria-label="Meshy model generation progress"
                                    aria-valuemin={0}
                                    aria-valuemax={100}
                                    aria-valuenow={regenerationProgress}
                                  >
                                    <div
                                      className="h-full rounded-full bg-purple-400 transition-[width] duration-500"
                                      style={{ width: `${regenerationProgress}%` }}
                                    />
                                  </div>
                                </div>
                              )}
                            </>
                          ) : (
                            <a
                              href={`/cases-3d-priority?case=${selectedAsset.subject_id}${batch?.batch_id ? `&returnBatch=${encodeURIComponent(batch.batch_id)}` : ""}`}
                              className="block text-xs text-cyan-200 underline underline-offset-2"
                            >
                              Approve four case photos to regenerate this model
                            </a>
                          )
                        )}
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

                {(selectedAsset.source_image_refs || []).length ? (
                  <div className="space-y-3">
                    {(selectedAsset.source_image_refs || []).map((imageUrl, index) => (
                      <a
                        key={`${imageUrl}-${index}`}
                        href={originalImageUrl(imageUrl)}
                        target="_blank"
                        rel="noreferrer"
                        className="group block cursor-zoom-in overflow-hidden rounded-md border border-slate-700 bg-white transition-colors hover:border-orange-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-300"
                        aria-label={`Open source picture ${index + 1} full size`}
                      >
                        {/* Source URLs can be temporary signed URLs, so Next Image optimisation cannot safely proxy them. */}
                        { }
                        <img
                          src={originalImageUrl(imageUrl)}
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

                {selectedAsset.subject_type === "case" && (
                  <section className="my-4 rounded-md border border-cyan-500/30 bg-slate-900/70 p-3" aria-label="RGB fan layout editor">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div>
                        <h2 className="text-sm font-bold text-slate-100">RGB fan layout</h2>
                        <p className="mt-1 text-xs text-slate-400">Detect candidates from an asset source photo, then check their position on the model.</p>
                      </div>
                      <span className="rounded bg-slate-800 px-2 py-1 text-xs text-cyan-200">{fanLayout?.fans.length || 0} fans</span>
                    </div>

                    <div className="mb-3 grid grid-cols-[1fr_auto] gap-2">
                      <label className="text-xs text-slate-300">
                        Detection photo
                        <select
                          value={fanPhotoChoice}
                          onChange={event => setFanPhotoChoice(event.target.value)}
                          className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-2 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
                          disabled={!selectedAsset.source_image_refs?.length && !approvedCasePhotoUrls(caseRecords.find(item => item.id === selectedAsset.subject_id)).length}
                        >
                          {(selectedAsset.source_image_refs || []).map((_, index) => <option key={`asset-${index}`} value={`asset:${index}`}>This model · Reference {index + 1}</option>)}
                          {approvedCasePhotoUrls(caseRecords.find(item => item.id === selectedAsset.subject_id)).map((_, index) => <option key={`approved-${index}`} value={`approved:${index}`}>Current approved set · Reference {index + 1}</option>)}
                        </select>
                        {fanPhotoChoice.startsWith("approved:") && <span className="mt-1 block text-[11px] text-amber-200">These photos are newer than this model and were not its generation inputs.</span>}
                      </label>
                      <button
                        type="button"
                        onClick={() => void detectFansFromPhoto()}
                        disabled={fanDetectionBusy || (!selectedAsset.source_image_refs?.length && !approvedCasePhotoUrls(caseRecords.find(item => item.id === selectedAsset.subject_id)).length)}
                        className="mt-5 inline-flex cursor-pointer items-center gap-1.5 rounded border border-cyan-500/50 bg-cyan-950/50 px-2 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-900/70 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
                      >
                        <ScanSearch className={`h-3.5 w-3.5 ${fanDetectionBusy ? "animate-pulse" : ""}`} aria-hidden="true" />
                        {fanDetectionBusy ? "Detecting…" : "Detect RGB fans"}
                      </button>
                    </div>

                    {fanLayout && (
                      <>
                        <div className="mb-3 grid grid-cols-2 gap-2">
                          <label className="text-xs text-slate-300">Face
                            <select value={fanLayout.face} onChange={event => updateFanLayout(current => ({ ...current, face: event.target.value as FanFace }))} className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-2 text-sm text-slate-100">
                              <option value="+z">Front +Z</option><option value="-z">Front -Z</option><option value="+x">Side +X</option><option value="-x">Side -X</option>
                            </select>
                          </label>
                          <label className="text-xs text-slate-300">RGB program
                            <select value={fanLayout.mode} onChange={event => updateFanLayout(current => ({ ...current, mode: event.target.value as RGBMode }))} className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-2 py-2 text-sm text-slate-100">
                              <option value="rainbow">Rainbow</option><option value="color-cycle">Colour cycle</option><option value="breathing">Breathing</option><option value="static">Static colour</option><option value="off">Off</option>
                            </select>
                          </label>
                        </div>
                        {fanLayout.mode === "static" && <label className="mb-3 flex items-center justify-between text-xs text-slate-300">Static colour<input type="color" value={fanLayout.color} onChange={event => updateFanLayout(current => ({ ...current, color: event.target.value }))} className="h-8 w-12 cursor-pointer rounded border border-slate-600 bg-slate-950" /></label>}
                        <label className="mb-3 block text-xs text-slate-300">Program speed · {fanLayout.speed.toFixed(1)}×
                          <input type="range" min="0.1" max="3" step="0.1" value={fanLayout.speed} onChange={event => updateFanLayout(current => ({ ...current, speed: Number(event.target.value) }))} className="mt-2 w-full accent-cyan-400" />
                        </label>

                        <div className="mb-2 flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-200">Fans</span>
                          <button type="button" onClick={addManualFan} className="inline-flex cursor-pointer items-center gap-1 rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:border-cyan-400 hover:text-cyan-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"><Plus className="h-3 w-3" aria-hidden="true" />Add fan</button>
                        </div>
                        <div className="mb-3 flex flex-wrap gap-1.5">
                          {fanLayout.fans.map((fan, index) => (
                            <button key={fan.id} type="button" onClick={() => setSelectedFanId(fan.id)} aria-pressed={selectedFanId === fan.id} className={`cursor-pointer rounded border px-2 py-1 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400 ${selectedFanId === fan.id ? "border-cyan-300 bg-cyan-900/60 text-white" : "border-slate-600 bg-slate-950 text-slate-300"}`}>
                              Fan {index + 1}{fan.confidence != null ? ` · signal ${Math.round(fan.confidence * 100)}%` : ""}
                            </button>
                          ))}
                        </div>

                        {fanLayout.fans.find(fan => fan.id === selectedFanId) && (() => {
                          const selectedFan = fanLayout.fans.find(fan => fan.id === selectedFanId)!;
                          const updateSelectedFan = (patch: Partial<ProceduralFan>) => updateFanLayout(current => ({
                            ...current,
                            fans: current.fans.map(fan => fan.id === selectedFan.id ? { ...fan, ...patch } : fan),
                          }));
                          return (
                            <div className="mb-3 rounded border border-slate-700 bg-slate-950/70 p-2">
                              <div className="mb-2 flex items-center justify-between text-xs text-slate-300"><span>Fan position & size</span><button type="button" aria-label="Remove selected fan" title="Remove selected fan" onClick={() => { const remaining = fanLayout.fans.filter(fan => fan.id !== selectedFan.id); updateFanLayout(current => ({ ...current, fans: remaining })); setSelectedFanId(remaining[0]?.id || null); }} className="cursor-pointer rounded p-1 text-red-300 hover:bg-red-950/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-400"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button></div>
                              <label className="mb-2 block text-xs text-slate-400">Horizontal · {selectedFan.x.toFixed(2)}
                                <input type="range" min="-1" max="1" step="0.01" value={selectedFan.x} onChange={event => updateSelectedFan({ x: Number(event.target.value) })} className="mt-1 w-full accent-cyan-400" />
                              </label>
                              <label className="mb-2 block text-xs text-slate-400">Vertical · {selectedFan.y.toFixed(2)}
                                <input type="range" min="-1" max="1" step="0.01" value={selectedFan.y} onChange={event => updateSelectedFan({ y: Number(event.target.value) })} className="mt-1 w-full accent-cyan-400" />
                              </label>
                              <label className="block text-xs text-slate-400">Diameter
                                <input type="number" min="60" max="200" step="10" value={selectedFan.diameter_mm} onChange={event => updateSelectedFan({ diameter_mm: Math.max(60, Math.min(200, Number(event.target.value) || 120)) })} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1.5 text-sm text-slate-100" />
                              </label>
                            </div>
                          );
                        })()}

                        <button type="button" onClick={() => void saveFanLayout()} disabled={fanSaveBusy || fanDetectionBusy} className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded border border-cyan-400/50 bg-cyan-700/40 px-3 py-2 text-sm font-semibold text-cyan-50 hover:bg-cyan-700/60 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300"><Save className="h-4 w-4" aria-hidden="true" />{fanSaveBusy ? "Saving…" : "Save fan layout"}</button>
                      </>
                    )}
                    {fanEditorMessage && <p role="status" className="mt-2 text-xs leading-relaxed text-cyan-100">{fanEditorMessage}</p>}
                  </section>
                )}

                <div className="my-4 border-t border-[#1e2d45] pt-4">
                  <h2 className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-100">
                    <CirclePlay className="h-4 w-4 text-red-400" aria-hidden="true" />
                    YouTube references
                  </h2>
                  {selectedAsset.source_video_refs?.length ? (
                    <div className="space-y-4">
                      {selectedAsset.source_video_refs.map((video, index) => {
                        const embedUrl = youtubeEmbedUrl(video.url);
                        return (
                          <article key={`${video.url}-${index}`} className="overflow-hidden rounded-md border border-slate-700 bg-slate-950">
                            {embedUrl && (
                              <iframe
                                src={embedUrl}
                                title={`${video.title} — video reference ${index + 1}`}
                                className="aspect-video w-full"
                                loading="lazy"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                                allowFullScreen
                              />
                            )}
                            <div className="p-2">
                              <p className="text-xs leading-relaxed text-slate-300">{video.title}</p>
                              <a
                                href={video.url}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-2 inline-flex cursor-pointer text-xs font-semibold text-red-300 transition-colors hover:text-red-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-300"
                              >
                                Open on YouTube
                              </a>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="rounded-md border border-slate-700 bg-slate-900/60 p-3 text-xs text-slate-400">
                      No exact YouTube reference was found for this item.
                    </p>
                  )}
                </div>

                <p className="mt-4 text-center text-xs text-slate-500">Use the left/right arrow keys to move between items.</p>
              </aside>
            </div>
          ) : (
            <div className="flex items-center justify-center flex-1 text-slate-500">
              <div className="text-center">
                <p className="text-lg font-semibold text-slate-200">{loading ? "Loading 3D model candidates…" : "No components with approved photos or models are waiting for review."}</p>
                {!loading && <><p className="mt-2 max-w-lg text-sm text-slate-400">Approve component photos in the catalogue first. They will appear here for model generation and review.</p><a href={`/catalogue/3d-assets?catalogue=${curatedOnly ? "curated" : "custom"}`} className="mt-4 inline-flex rounded-lg border border-cyan-300/30 px-4 py-2 text-sm font-semibold text-cyan-200 hover:bg-cyan-300/10">Open component asset inventory</a></>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
