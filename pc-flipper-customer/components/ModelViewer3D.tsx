'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  onComponentClick: (slotType: string) => void;
}

export function ModelViewer3D({ build, slots, onComponentClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const modelsRef = useRef<Map<string, THREE.Object3D>>(new Map());

  useEffect(() => {
    if (!containerRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a1a);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(75, containerRef.current.clientWidth / containerRef.current.clientHeight, 0.1, 1000);
    camera.position.set(8, 6, 8);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    renderer.shadowMap.enabled = true;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 10, 10);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // Create case box as base
    const caseGeom = new THREE.BoxGeometry(4, 5, 2.5);
    const caseMat = new THREE.MeshStandardMaterial({ color: 0x222222, metalness: 0.2, roughness: 0.8 });
    const caseMesh = new THREE.Mesh(caseGeom, caseMat);
    caseMesh.position.y = 0;
    scene.add(caseMesh);

    // Load models
    const loader = new GLTFLoader();
    let loadedCount = 0;
    const totalToLoad = Object.values(build.slots).filter(v => v).length;

    Object.entries(build.slots).forEach(([slotType, variant]) => {
      if (!variant) return;

      // Map variant IDs to model numbers (1-3 per component type)
      const variantNum = ((variant.id - 1) % 3) + 1;
      const modelUrl = `/models/${slotType}/variant-${variantNum}.gltf`;
      console.log(`Loading ${slotType}: ${modelUrl}`);
      loader.load(
        modelUrl,
        (gltf) => {
          const model = gltf.scene;
          model.position.set(Math.random() * 2 - 1, 2 + Math.random(), Math.random() * 2 - 1);
          model.scale.set(0.8, 0.8, 0.8);
          model.userData.slotType = slotType;
          scene.add(model);
          modelsRef.current.set(slotType, model);
          loadedCount++;
          if (loadedCount === totalToLoad) setIsLoading(false);
        },
        undefined,
        (error) => {
          console.warn(`Failed to load model for ${slotType}:`, error);
          loadedCount++;
          if (loadedCount === totalToLoad) setIsLoading(false);
        }
      );
    });

    // Animation loop with auto-rotation
    let animationId: number;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      scene.rotation.y += 0.005;
      renderer.render(scene, camera);
    };
    animate();

    // Handle window resize
    const handleResize = () => {
      if (!containerRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    window.addEventListener('resize', handleResize);

    // Handle clicks
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const handleClick = (event: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(scene.children, true);
      if (intersects.length > 0) {
        const clicked = intersects[0].object;
        let obj = clicked as any;
        while (obj.parent && !obj.userData.slotType) {
          obj = obj.parent;
        }
        if (obj.userData.slotType) {
          onComponentClick(obj.userData.slotType);
        }
      }
    };
    containerRef.current.addEventListener('click', handleClick);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
      containerRef.current?.removeEventListener('click', handleClick);
      renderer.dispose();
      containerRef.current?.removeChild(renderer.domElement);
    };
  }, [build, onComponentClick]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full rounded-lg overflow-hidden relative"
      style={{ minHeight: '600px' }}
    >
      {isLoading && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin text-4xl mb-2">⚙️</div>
            <p className="text-white">Loading 3D models...</p>
          </div>
        </div>
      )}
    </div>
  );
}
