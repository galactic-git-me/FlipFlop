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
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f0f11);

    // Camera
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 2, 6);
    camera.lookAt(0, 0, 0);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    containerRef.current.appendChild(renderer.domElement);

    // BRIGHT LIGHTS
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
    directionalLight.position.set(5, 8, 5);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0x22c55e, 0.8);
    pointLight.position.set(-5, 3, 3);
    scene.add(pointLight);

    // Fallback colors for components
    const COLORS: Record<string, number> = {
      gpu: 0xff6b35,
      cpu: 0x004e89,
      ram: 0x1b998b,
      storage: 0xc1121f,
    };

    // Load models with fallback to cubes
    const loader = new GLTFLoader();
    let loadedCount = 0;
    const positions = [
      { x: -2, y: 0, z: 0 },
      { x: -0.5, y: 0, z: -2 },
      { x: 1.5, y: 0, z: 0 },
      { x: 0, y: 0, z: 2 },
    ];

    const slotEntries = Object.entries(build.slots).filter(([_, v]) => v).slice(0, 4);
    let loadedCount_final = 0;

    slotEntries.forEach(([slotType, variant], idx) => {
      const variantNum = ((variant.id - 1) % 3) + 1;
      const modelUrl = `/models/${slotType}/variant-${variantNum}.gltf`;

      // Try to load model, with fallback cube
      loader.load(
        modelUrl,
        (gltf) => {
          const model = gltf.scene;
          model.scale.set(1.5, 1.5, 1.5);
          model.position.set(positions[idx].x, positions[idx].y, positions[idx].z);
          model.userData.slotType = slotType;
          scene.add(model);
          loadedCount_final++;
          if (loadedCount_final >= slotEntries.length) setIsLoading(false);
        },
        undefined,
        () => {
          // Fallback: create colored cube
          const geom = new THREE.BoxGeometry(1, 1, 1);
          const mat = new THREE.MeshStandardMaterial({
            color: COLORS[slotType] || 0x888888,
            metalness: 0.5,
            roughness: 0.3,
          });
          const cube = new THREE.Mesh(geom, mat);
          cube.position.set(positions[idx].x, positions[idx].y, positions[idx].z);
          cube.userData.slotType = slotType;
          scene.add(cube);
          loadedCount_final++;
          if (loadedCount_final >= slotEntries.length) setIsLoading(false);
        }
      );
    });

    // Animation loop
    let animationId: number;
    let rotation = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      rotation += 0.003;
      scene.rotation.y = rotation;
      renderer.render(scene, camera);
    };
    animate();

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
        for (const intersection of intersects) {
          let obj = intersection.object as any;
          while (obj.parent && !obj.userData.slotType) {
            obj = obj.parent;
          }
          if (obj.userData.slotType) {
            onComponentClick(obj.userData.slotType);
            break;
          }
        }
      }
    };
    containerRef.current.addEventListener('click', handleClick);

    // Handle resize
    const handleResize = () => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

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
      className="w-full rounded-lg overflow-hidden relative"
      style={{ minHeight: '600px' }}
    >
      {isLoading && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
          <p className="text-white">Loading 3D models...</p>
        </div>
      )}
    </div>
  );
}
