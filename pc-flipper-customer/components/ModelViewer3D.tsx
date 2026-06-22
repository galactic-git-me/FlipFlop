'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  onComponentClick: (slotType: string) => void;
}

const COMPONENT_COLORS: Record<string, number> = {
  gpu: 0xff6b35,      // Orange
  cpu: 0x004e89,      // Blue
  ram: 0x1b998b,      // Teal
  storage: 0xc1121f,  // Red
};

export function ModelViewer3D({ build, slots, onComponentClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f0f11);
    sceneRef.current = scene;

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
    renderer.shadowMap.type = THREE.PCFShadowMap;
    containerRef.current.appendChild(renderer.domElement);

    // Lights - much brighter
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2);
    directionalLight.position.set(5, 8, 5);
    directionalLight.castShadow = true;
    directionalLight.shadow.mapSize.width = 2048;
    directionalLight.shadow.mapSize.height = 2048;
    scene.add(directionalLight);

    const pointLight = new THREE.PointLight(0x22c55e, 0.8);
    pointLight.position.set(-5, 3, 3);
    scene.add(pointLight);

    // Platform
    const platformGeom = new THREE.CylinderGeometry(5, 5, 0.2, 32);
    const platformMat = new THREE.MeshStandardMaterial({
      color: 0x18181b,
      metalness: 0.3,
      roughness: 0.7
    });
    const platform = new THREE.Mesh(platformGeom, platformMat);
    platform.position.y = -1;
    platform.receiveShadow = true;
    scene.add(platform);

    // Create component shapes
    const components: { mesh: THREE.Mesh; slotType: string }[] = [];
    const positions = [
      { x: -2, y: 0, z: 0 },     // GPU
      { x: -0.5, y: 0, z: -2 },  // CPU
      { x: 1.5, y: 0, z: 0 },    // RAM
      { x: 0, y: 0, z: 2 },      // Storage
    ];

    Object.entries(build.slots).forEach(([slotType, variant], idx) => {
      if (!variant || idx >= 4) return;

      const color = COMPONENT_COLORS[slotType] || 0x888888;
      const geom = new THREE.BoxGeometry(1.2, 1.2, 1.2);
      const mat = new THREE.MeshStandardMaterial({
        color,
        metalness: 0.5,
        roughness: 0.3,
        emissive: color,
        emissiveIntensity: 0.2,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(positions[idx].x, positions[idx].y, positions[idx].z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.userData.slotType = slotType;
      scene.add(mesh);
      components.push({ mesh, slotType });
    });

    // Animation loop
    let animationId: number;
    let rotation = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);

      // Rotate scene
      rotation += 0.003;
      scene.rotation.y = rotation;

      // Bob components
      components.forEach(({ mesh, slotType }, idx) => {
        mesh.position.y = 0.2 * Math.sin(Date.now() * 0.001 + idx);
      });

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
      const intersects = raycaster.intersectObjects(components.map(c => c.mesh));
      if (intersects.length > 0) {
        const clicked = intersects[0].object as any;
        if (clicked.userData.slotType) {
          onComponentClick(clicked.userData.slotType);
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
      className="w-full rounded-lg overflow-hidden"
      style={{ minHeight: '600px' }}
    />
  );
}
