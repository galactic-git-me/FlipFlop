"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight, CirclePlay, Images, RefreshCw, ScanSearch, Plus, Trash2, Save } from "lucide-react";
import { ThreeDWorkflowNav } from "@/components/three-d-workflow-nav";
import { readJsonResponse } from "@/lib/read-json-response";
import { detectRgbFans } from "./fan-detection";

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

interface Component3DAsset {
  id: number;
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

function Viewer3D({ glbUrl, fanLayout, caseHeightMm }: { glbUrl: string | null; fanLayout: FanLayout | null; caseHeightMm: number }) {
  // 3D Viewer Configuration:
  // - Camera position: (5, 6, 9) — controls zoom/perspective from the model
  // - Model scale: 10.5 — scales loaded GLB to viewport size
  // - Grid: 200x200 with 40 divisions, matrix green lines (0x00ff00, 0x00aa00)
  // - Lights: ambient (3.5), point (4.0), directional (3.0), fill (2.5), back (3.5)
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
    cameraRef.current = null;
    modelRef.current = null;
    initialModelRotationRef.current = null;
    zoomRef.current = 1;
    let disposed = false;
    let disposeViewer: (() => void) | undefined;

    const setupTimer = window.setTimeout(() => {
      const setupViewer = async () => {
        try {
          const THREE = await import("three");
          const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
          const { MeshoptDecoder } = await import("three/examples/jsm/libs/meshopt_decoder.module.js");

          if (!containerRef.current || !canvasRef.current || disposed) return;

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

          const renderer = new THREE.WebGLRenderer({
            canvas: canvasRef.current,
            antialias: true,
            alpha: true,
            premultipliedAlpha: true,
          });
          let animationId = 0;
          renderer.outputColorSpace = THREE.SRGBColorSpace;
          renderer.toneMapping = THREE.ACESFilmicToneMapping;
          renderer.toneMappingExposure = 1.3;
          renderer.setSize(width, height);
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
          renderer.setClearColor(0x000000, 0);
          renderer.domElement.style.position = "absolute";
          renderer.domElement.style.top = "0";
          renderer.domElement.style.left = "0";
          renderer.domElement.style.background = "transparent";
          renderer.domElement.style.backgroundColor = "transparent";
          renderer.domElement.style.zIndex = "2";

          const ambientLight = new THREE.AmbientLight(0xffffff, 2.0);
          scene.add(ambientLight);
          const hemisphereLight = new THREE.HemisphereLight(0xe7f1ff, 0x342014, 1.2);
          scene.add(hemisphereLight);

          const pointLight = new THREE.PointLight(0xffead8, 8.0);
          pointLight.position.set(5, 5, -5);
          scene.add(pointLight);

          const directionalLight = new THREE.DirectionalLight(0xffffff, 3.0);
          directionalLight.position.set(3, 5, 2);
          scene.add(directionalLight);

          const fillLight = new THREE.PointLight(0x9fc7ff, 4.0);
          fillLight.position.set(-5, 2, 5);
          scene.add(fillLight);

          const backLight = new THREE.PointLight(0xff8a32, 3.0);
          backLight.position.set(0, 3, -8);
          scene.add(backLight);


          const loader = new GLTFLoader();
          loader.setMeshoptDecoder(MeshoptDecoder);
          loader.crossOrigin = "anonymous";

          // Handle CORS by proxying through local backend
          const loadUrl = glbUrl.startsWith("http") && !glbUrl.includes("localhost")
            ? `/api/proxy-glb?url=${encodeURIComponent(glbUrl)}`
            : glbUrl;

          loader.load(
            loadUrl,
            (gltf) => {
              if (disposed) return;
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
              if (!disposed) setLoadError("This model could not be loaded. Try opening its GLB directly or regenerate the cleaned asset.");
            }
          );

          renderer.render(scene, camera);
          disposeViewer = () => {
            window.cancelAnimationFrame(animationId);
            applyFanLayoutRef.current = null;
            renderer.setAnimationLoop(null);
            renderer.dispose();
            renderer.forceContextLoss();
          };
        } catch (error) {
          console.error("Error setting up 3D viewer:", error);
          if (!disposed) {
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
      {loadError && <div role="alert" className="absolute inset-x-4 top-20 z-50 rounded border border-red-400/50 bg-red-950/90 p-3 text-sm text-red-100">{loadError}</div>}
    </div>
  );
}

export default function Components3DReviewPage() {
  const router = useRouter();
  const [assets, setAssets] = useState<Component3DAsset[]>([]);
  const [caseRecords, setCaseRecords] = useState<PriorityCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAsset, setSelectedAsset] = useState<Component3DAsset | null>(null);
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
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [curatedOnly, setCuratedOnly] = useState(false);
  const [customOnly, setCustomOnly] = useState(false);
  const [scaleConfirmed, setScaleConfirmed] = useState(false);
  const [regeneratingCaseId, setRegeneratingCaseId] = useState<number | null>(null);
  const [regenerationProgress, setRegenerationProgress] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setFanLayout(selectedAsset?.fan_layout_json || null);
    setSelectedFanId(selectedAsset?.fan_layout_json?.fans[0]?.id || null);
    setFanPhotoChoice("asset:0");
    setFanEditorMessage(null);
  }, [selectedAsset?.id, selectedAsset?.fan_layout_json]);

  useEffect(() => {
    setRightsConfirmed(Boolean(selectedAsset?.commercial_use_approved && selectedAsset?.redistribution_approved));
    setScaleConfirmed(Boolean(selectedAsset?.scale_validated));
  }, [selectedAsset?.id, selectedAsset?.commercial_use_approved, selectedAsset?.redistribution_approved, selectedAsset?.scale_validated]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const batchId = new URLSearchParams(window.location.search).get("batch");
        const focusCaseId = Number(new URLSearchParams(window.location.search).get("case"));
        const isCuratedOnly = new URLSearchParams(window.location.search).get("curatedOnly") === "1";
        const isCustomOnly = new URLSearchParams(window.location.search).get("customOnly") === "1";
        setCuratedOnly(isCuratedOnly);
        setCustomOnly(isCustomOnly);
        const [response, casesResponse] = await Promise.all([
          fetch(batchId ? `/api/assets-3d/review-batches/${batchId}` : `/api/assets-3d${isCuratedOnly ? "?subject_type=variant&curated_only=true" : isCustomOnly ? "?subject_type=variant&custom_only=true" : ""}`),
          fetch("/api/cases/priority-for-3d?limit=100"),
        ]);
        const data = await readJsonResponse<Component3DAsset[] | { detail?: string; error?: string; data?: Component3DAsset[]; assets?: Component3DAsset[] }>(response);
        const priorityCases = casesResponse.ok ? await readJsonResponse<PriorityCaseItem[]>(casesResponse) : [];
        setCaseRecords(priorityCases);

        if (!Array.isArray(data) && data.detail) {
          console.error("API Error:", data.detail);
          setAssets([]);
          return;
        }

        if (!Array.isArray(data) && data.error) {
          console.error("API returned error:", data.error);
          setAssets([]);
          return;
        }

        let loadedAssets = orderAndLabelAssets(
          Array.isArray(data) ? data : (data.data || data.assets || []),
          priorityCases,
        );
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
          if (pendingBatchId) {
            const batchResponse = await fetch(`/api/assets-3d/review-batches/${pendingBatchId}`);
            if (batchResponse.ok) {
              const batchData = await readJsonResponse<ReviewBatch>(batchResponse);
              loadedAssets = orderAndLabelAssets(batchData.assets, priorityCases);
              setBatch({ ...batchData, assets: loadedAssets });
              window.history.replaceState(null, "", `?batch=${pendingBatchId}`);
            }
          }
        }
        setAssets(loadedAssets);
        const caseAsset = Number.isFinite(focusCaseId) && focusCaseId > 0
          ? loadedAssets.find(asset => asset.subject_type === "case" && asset.subject_id === focusCaseId && asset.review_decision === "rejected")
            || loadedAssets.find(asset => asset.subject_type === "case" && asset.subject_id === focusCaseId)
          : undefined;
        setSelectedAsset(caseAsset || loadedAssets[0] || null);
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
        body: JSON.stringify({ size: 10, curated_only: curatedOnly, custom_only: customOnly }),
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

  const decideAsset = async (decision: "approved" | "rejected") => {
    if (!batch || !selectedAsset) return;
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
      const updatedAssets = batch.assets.map(asset => asset.id === data.id ? reviewedAsset : asset);
      const updatedBatch = { ...batch, assets: updatedAssets, decided: updatedAssets.filter(asset => asset.review_decision).length };
      updatedBatch.complete = updatedBatch.decided === updatedBatch.size;
      setBatch(updatedBatch);
      setAssets(updatedAssets);
      setSelectedAsset(reviewedAsset);
      setReviewNotes("");
      if (data.regeneration?.message) setActionNotice(data.regeneration.message);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not save decision");
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

  const savePublishingChecks = async () => {
    if (!selectedAsset || !rightsConfirmed || !scaleConfirmed) return;
    setActionBusy(true);
    setActionError(null);
    setActionNotice(null);
    try {
      const response = await fetch(`/api/assets-3d/${selectedAsset.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provenance_status: "original-recreation",
          commercial_use_approved: true,
          redistribution_approved: true,
          scale_validated: true,
        }),
      });
      const data = await readJsonResponse<Component3DAsset & { detail?: string; error?: string }>(response);
      if (!response.ok) throw new Error(data.detail || data.error || "Could not save publishing checks");
      const updatedAssets = assets.map(asset => asset.id === data.id ? { ...asset, ...data } : asset);
      setAssets(updatedAssets);
      setSelectedAsset(current => current?.id === data.id ? { ...current, ...data } : current);
      setBatch(current => current ? { ...current, assets: current.assets.map(asset => asset.id === data.id ? { ...asset, ...data } : asset) } : current);
      setActionNotice("Publishing rights and scale checks saved. This approved model can now be published.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not save publishing checks");
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
      const data = await readJsonResponse<ReviewBatch & { detail?: string; error?: string }>(response);
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
        <div className="flex items-center gap-3">
          <h1 className="whitespace-nowrap text-lg font-bold text-slate-100">3D Assets</h1>
          <ThreeDWorkflowNav compact />
        </div>
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
      {actionError && <div role="alert" className="rounded-md border border-red-500/60 bg-red-950/80 px-4 py-2 text-sm text-red-200">{actionError}</div>}
      {actionNotice && <div role="status" className="rounded-md border border-sky-500/60 bg-sky-950/80 px-4 py-2 text-sm text-sky-100">{actionNotice}</div>}

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
                      if (asset.status === "cleaned") return { icon: "C", color: "bg-blue-500" };
                      if (asset.status === "validated") return { icon: "V", color: "bg-purple-500" };
                      return { icon: "?", color: "bg-slate-600" };
                    };
                    const statusIcon = getStatusIcon();
                    return (
                      <button
                        key={asset.id}
                        onClick={() => setSelectedAsset(asset)}
                        className={`group rounded border overflow-hidden cursor-pointer transition hover:scale-105 relative flex flex-col ${selectedAsset?.id === asset.id ? "ring-2 ring-orange-400" : ""} ${statusColors[asset.status] || ""}`}
                        style={{ width: "120px", height: "120px", backgroundImage: asset.preview_image_ref ? `url('${asset.preview_image_ref}')` : asset.source_image_refs && asset.source_image_refs.length > 0 ? `url('${asset.source_image_refs[0]}')` : undefined, backgroundSize: "cover", backgroundPosition: "center", backgroundColor: "#1a3a52" }}
                      >
                        {/* Status badge overlay */}
                        {asset.glb_ref && (
                          <div className={`absolute top-1 right-1 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 ${statusIcon.color}`}>
                            {statusIcon.icon}
                          </div>
                        )}
                        {asset.rank && <div className="absolute left-1 top-1 rounded bg-black/80 px-1.5 py-0.5 text-[10px] font-bold text-white shadow">#{asset.rank}</div>}
                        <div className="flex-1"></div>
                        <div className="w-full translate-y-1 bg-black/75 px-1 py-1.5 text-center opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
                          <div className="line-clamp-2 text-[10px] font-semibold leading-tight text-white">{asset.subject_name || asset.family_key}</div>
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
                <Viewer3D
                  glbUrl={selectedAsset.glb_ref}
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

                      <div className="space-y-2 relative z-50">
                        <div className="flex gap-1 relative z-50">
                          <button disabled={!batch || actionBusy || Boolean(selectedAsset.review_decision)} onClick={() => decideAsset("rejected")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-red-600/40 text-red-300 border border-red-500/50 hover:bg-red-600/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
                            Reject
                          </button>
                          <button disabled={!batch || actionBusy || Boolean(selectedAsset.review_decision)} onClick={() => decideAsset("approved")} className="flex-1 cursor-pointer px-2 py-1 rounded text-xs font-semibold bg-[#00dc82]/40 text-[#00dc82] border border-[#00dc82]/50 hover:bg-[#00dc82]/60 disabled:cursor-not-allowed disabled:opacity-40 relative z-50">
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
                        {selectedAsset.review_decision === "approved" && (
                          <div className="space-y-2 rounded border border-amber-500/40 bg-amber-950/30 p-2 text-[11px] text-slate-200">
                            <p className="font-semibold text-amber-200">Publishing checks</p>
                            <label className="flex cursor-pointer items-start gap-2">
                              <input type="checkbox" checked={rightsConfirmed} onChange={event => setRightsConfirmed(event.target.checked)} className="mt-0.5" />
                              <span>I confirm this in-house recreation is cleared for commercial use and redistribution.</span>
                            </label>
                            <label className="flex cursor-pointer items-start gap-2">
                              <input type="checkbox" checked={scaleConfirmed} onChange={event => setScaleConfirmed(event.target.checked)} className="mt-0.5" />
                              <span>I confirm its scale and proportions are acceptable for the configurator.</span>
                            </label>
                            <button type="button" disabled={actionBusy || !rightsConfirmed || !scaleConfirmed || Boolean(selectedAsset.commercial_use_approved && selectedAsset.redistribution_approved && selectedAsset.scale_validated)} onClick={savePublishingChecks} className="w-full cursor-pointer rounded border border-amber-400/60 bg-amber-600/30 px-2 py-1 font-semibold text-amber-100 hover:bg-amber-600/50 disabled:cursor-not-allowed disabled:opacity-40">
                              {selectedAsset.commercial_use_approved && selectedAsset.redistribution_approved && selectedAsset.scale_validated ? "Publishing checks saved" : "Save publishing checks"}
                            </button>
                          </div>
                        )}
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
                        href={imageUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="group block cursor-zoom-in overflow-hidden rounded-md border border-slate-700 bg-white transition-colors hover:border-orange-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-300"
                        aria-label={`Open source picture ${index + 1} full size`}
                      >
                        {/* Source URLs can be temporary signed URLs, so Next Image optimisation cannot safely proxy them. */}
                        { }
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
