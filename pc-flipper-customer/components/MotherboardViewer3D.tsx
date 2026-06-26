'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';

interface SlotHotspot {
  name: string;
  slotType: string;
  position: THREE.Vector3;
  size: { x: number; y: number; z: number };
}

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  onComponentClick: (slotType: string) => void;
}

export function MotherboardViewer3D({
  build,
  slots,
  onComponentClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!containerRef.current) return;

    console.log('MotherboardViewer3D: Initializing scene');

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f0f11);

    // Camera positioned to view motherboard from above-front
    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;
    const camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
    camera.position.set(0, 1.5, 2);
    camera.lookAt(0, 0, 0);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.shadowMap.enabled = true;
    containerRef.current.appendChild(renderer.domElement);

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight.position.set(3, 4, 3);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0x22c55e, 0.6);
    pointLight.position.set(-2, 1, 2);
    scene.add(pointLight);

    let animationId: number;
    const hotspotMeshes: THREE.Mesh[] = [];

    // Start animation loop immediately
    let rotation = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      rotation += 0.0005;
      renderer.render(scene, camera);
    };
    animate();

    // Add a test cube to verify rendering works
    const testGeometry = new THREE.BoxGeometry(1, 1, 1);
    const testMaterial = new THREE.MeshStandardMaterial({ color: 0xff6b35 });
    const testCube = new THREE.Mesh(testGeometry, testMaterial);
    testCube.position.z = 0;
    scene.add(testCube);
    console.log('MotherboardViewer3D: Added test cube');

    // Load motherboard model
    const loader = new GLTFLoader();
    console.log('MotherboardViewer3D: Starting model load from /models/motherboard/scene.gltf');
    loader.load(
      '/models/motherboard/scene.gltf',
      (gltf) => {
        console.log('MotherboardViewer3D: Model loaded successfully', gltf);
        const motherboard = gltf.scene;
        motherboard.scale.set(2, 2, 2);
        motherboard.position.set(0, 0, 0);
        motherboard.rotation.x = Math.PI * 0.05;
        scene.add(motherboard);
        console.log('MotherboardViewer3D: Motherboard added to scene');

        // Create invisible hotspots for each component slot
        // Positions based on typical AM5 motherboard layout
        const hotspots: SlotHotspot[] = [
          {
            name: 'CPU Socket',
            slotType: 'cpu',
            position: new THREE.Vector3(0, 0, 0.3),
            size: { x: 0.15, y: 0.15, z: 0.1 },
          },
          {
            name: 'RAM Slot 1',
            slotType: 'ram',
            position: new THREE.Vector3(0.3, 0, 0),
            size: { x: 0.08, y: 0.08, z: 0.1 },
          },
          {
            name: 'Storage (M.2)',
            slotType: 'storage',
            position: new THREE.Vector3(0.35, 0, -0.3),
            size: { x: 0.1, y: 0.08, z: 0.1 },
          },
          {
            name: 'GPU (PCIe)',
            slotType: 'gpu',
            position: new THREE.Vector3(0.2, -0.2, -0.5),
            size: { x: 0.2, y: 0.12, z: 0.1 },
          },
        ];

        hotspots.forEach((hotspot) => {
          const geometry = new THREE.BoxGeometry(
            hotspot.size.x,
            hotspot.size.y,
            hotspot.size.z
          );
          const material = new THREE.MeshBasicMaterial({
            transparent: true,
            opacity: 0,
          });
          const mesh = new THREE.Mesh(geometry, material);
          mesh.position.copy(hotspot.position);
          mesh.userData.slotType = hotspot.slotType;
          mesh.userData.hotspotName = hotspot.name;
          scene.add(mesh);
          hotspotMeshes.push(mesh);
        });

        setIsLoading(false);

        // Raycasting for clicks
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        const handleClick = (event: MouseEvent) => {
          if (!containerRef.current) return;

          const rect = containerRef.current.getBoundingClientRect();
          mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
          mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

          raycaster.setFromCamera(mouse, camera);
          const intersects = raycaster.intersectObjects(hotspotMeshes);

          if (intersects.length > 0) {
            const obj = intersects[0].object as any;
            if (obj.userData.slotType) {
              onComponentClick(obj.userData.slotType);
            }
          }
        };

        containerRef.current?.addEventListener('click', handleClick);
      },
      (progress) => {
        console.log('MotherboardViewer3D: Model loading progress', progress);
      },
      (error) => {
        console.error('MotherboardViewer3D: Error loading model:', error);
        setIsLoading(false);
      }
    );

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

    // Cleanup
    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
      containerRef.current?.removeEventListener('click', () => {});
      renderer.dispose();
      if (containerRef.current && renderer.domElement.parentElement === containerRef.current) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, [onComponentClick]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden relative"
      style={{ minHeight: '600px' }}
    >
      {isLoading && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10">
          <p className="text-white">Loading 3D motherboard...</p>
        </div>
      )}
    </div>
  );
}
