'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
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
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  // Monitor container size using ResizeObserver
  useLayoutEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        setContainerSize({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });

    observer.observe(containerRef.current);

    // Initial measurement
    setContainerSize({
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    console.log('MotherboardViewer3D: Initial container size check');

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    if (containerSize.width === 0 || containerSize.height === 0) {
      console.log('MotherboardViewer3D: Container not ready', containerSize);
      return;
    }

    console.log('MotherboardViewer3D: Initializing with size', containerSize);

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f0f11);

    // Camera
    const camera = new THREE.PerspectiveCamera(
      75,
      containerSize.width / containerSize.height,
      0.1,
      1000
    );
    camera.position.set(0, 1.5, 2);
    camera.lookAt(0, 0, 0);

    // Renderer
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (err) {
      console.error('MotherboardViewer3D: WebGL error', err);
      setIsLoading(false);
      return;
    }

    renderer.setSize(containerSize.width, containerSize.height);
    renderer.shadowMap.enabled = true;
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';

    containerRef.current.appendChild(renderer.domElement);
    console.log('MotherboardViewer3D: Canvas added to DOM');

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

    // Add test cube
    const testGeometry = new THREE.BoxGeometry(0.8, 0.8, 0.8);
    const testMaterial = new THREE.MeshStandardMaterial({
      color: 0xff6b35,
      metalness: 0.2,
      roughness: 0.8,
    });
    const testCube = new THREE.Mesh(testGeometry, testMaterial);
    testCube.position.set(0, 0, 0);
    scene.add(testCube);
    console.log('MotherboardViewer3D: Test cube added');

    // Animation loop
    let rotation = 0;
    let frameCount = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      rotation += 0.001;
      testCube.rotation.x = rotation;
      testCube.rotation.y = rotation * 0.7;
      renderer.render(scene, camera);
      frameCount++;
      if (frameCount === 1) console.log('MotherboardViewer3D: First frame rendered');
    };
    animate();

    // Load model
    const loader = new GLTFLoader();
    loader.load(
      '/models/motherboard/scene.gltf',
      (gltf) => {
        console.log('MotherboardViewer3D: Model loaded');
        const motherboard = gltf.scene;
        motherboard.scale.set(2, 2, 2);
        motherboard.position.set(0, 0, 0);
        motherboard.rotation.x = Math.PI * 0.05;
        scene.add(motherboard);

        const hotspots: SlotHotspot[] = [
          {
            name: 'CPU',
            slotType: 'cpu',
            position: new THREE.Vector3(0, 0, 0.3),
            size: { x: 0.15, y: 0.15, z: 0.1 },
          },
          {
            name: 'RAM',
            slotType: 'ram',
            position: new THREE.Vector3(0.3, 0, 0),
            size: { x: 0.08, y: 0.08, z: 0.1 },
          },
          {
            name: 'Storage',
            slotType: 'storage',
            position: new THREE.Vector3(0.35, 0, -0.3),
            size: { x: 0.1, y: 0.08, z: 0.1 },
          },
          {
            name: 'GPU',
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
          scene.add(mesh);
          hotspotMeshes.push(mesh);
        });

        setIsLoading(false);

        // Click handler
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
      undefined,
      (error) => {
        console.error('MotherboardViewer3D: Load error', error);
        setIsLoading(false);
      }
    );

    // Resize handler
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
      renderer.dispose();
      if (containerRef.current?.contains(renderer.domElement)) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, [containerSize, onComponentClick]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden relative bg-black"
      style={{ minHeight: '600px', position: 'relative' }}
    >
      {isLoading && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-10">
          <p className="text-white text-sm">Loading 3D model...</p>
        </div>
      )}
    </div>
  );
}
