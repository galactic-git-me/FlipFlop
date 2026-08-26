"use client";

import { useEffect, useRef, useState } from "react";
import { Box, Loader2 } from "lucide-react";
import type { Material, Mesh } from "three";

export function Build3DViewer({ url }: { url: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let disposed = false;
    let cleanup: () => void = () => {};

    (async () => {
      try {
        const THREE = await import("three");
        const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
        const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
        if (disposed) return;

        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x07101f);
        const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 100);
        camera.position.set(2.6, 1.8, 3.2);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.ACESFilmicToneMapping;
        renderer.toneMappingExposure = 1.1;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.domElement.className = "h-full w-full";
        host.replaceChildren(renderer.domElement);

        scene.add(new THREE.HemisphereLight(0xdbeafe, 0x0f172a, 2.5));
        const key = new THREE.DirectionalLight(0xffffff, 3.5);
        key.position.set(4, 6, 4);
        scene.add(key);
        const rim = new THREE.DirectionalLight(0x67e8f9, 2);
        rim.position.set(-4, 2, -3);
        scene.add(rim);

        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 1.25;
        controls.enablePan = false;

        const resize = () => {
          const width = Math.max(host.clientWidth, 1);
          const height = Math.max(host.clientHeight, 1);
          renderer.setSize(width, height, false);
          camera.aspect = width / height;
          camera.updateProjectionMatrix();
        };
        resize();
        const observer = new ResizeObserver(resize);
        observer.observe(host);

        const loadUrl = url.startsWith("http") ? `/api/glb-proxy?url=${encodeURIComponent(url)}` : url;
        const gltf = await new GLTFLoader().loadAsync(loadUrl);
        if (disposed) return;
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3());
        const centre = box.getCenter(new THREE.Vector3());
        const scale = 2 / Math.max(size.x, size.y, size.z, 0.001);
        model.position.sub(centre);
        model.scale.setScalar(scale);
        scene.add(model);
        setState("ready");

        let frame = 0;
        const animate = () => {
          frame = requestAnimationFrame(animate);
          controls.update();
          renderer.render(scene, camera);
        };
        animate();
        cleanup = () => {
          cancelAnimationFrame(frame);
          observer.disconnect();
          controls.dispose();
          scene.traverse((object) => {
            const mesh = object as Mesh;
            mesh.geometry?.dispose?.();
            const materials: Material[] = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
            materials.forEach((material: Material) => material.dispose());
          });
          renderer.dispose();
        };
      } catch {
        if (!disposed) setState("error");
      }
    })();

    return () => {
      disposed = true;
      cleanup();
    };
  }, [url]);

  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-cyan-400/20 bg-slate-950/70">
      <div className="flex items-center justify-between border-b border-white/[0.07] px-3 py-2">
        <span className="flex items-center gap-2 text-xs font-bold text-slate-200"><Box className="h-4 w-4 text-cyan-300" /> Saved 3D model</span>
        <span className="text-[10px] text-slate-500">Drag to rotate · scroll to zoom</span>
      </div>
      <div className="relative h-80" ref={hostRef} aria-label="Interactive 3D model viewer">
        {state === "loading" && <div className="absolute inset-0 grid place-items-center text-xs text-slate-400"><span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Loading textured model…</span></div>}
        {state === "error" && <div className="absolute inset-0 grid place-items-center px-4 text-center text-xs text-red-300">The saved GLB could not be displayed. Use “Open GLB” to inspect the file.</div>}
      </div>
    </div>
  );
}
