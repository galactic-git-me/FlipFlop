'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  buildPCCase,
  buildGPU,
  buildCooler,
  setupLighting,
  createConfiguratorCamera,
} from '@/lib/three-utils';

interface ConfiguratorProps {
  components: {
    gpu_id: number | null;
    cooler_id: number | null;
    cpu_id?: number | null;
    ram_id?: number | null;
    ssd_id?: number | null;
    psu_id?: number | null;
    case_id?: number | null;
  };
}

export function Configurator3D({ components }: ConfiguratorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.Camera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const autoRotateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const animationIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f1419);
    sceneRef.current = scene;

    // Camera
    const camera = createConfiguratorCamera(
      containerRef.current.clientWidth,
      containerRef.current.clientHeight
    );
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(containerRef.current.clientWidth, containerRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    setupLighting(scene);

    // Model group
    const modelGroup = new THREE.Group();
    scene.add(modelGroup);
    modelGroupRef.current = modelGroup;

    // Load PC case
    const pcCase = buildPCCase();
    modelGroup.add(pcCase);

    // Add initial components
    const gpu = buildGPU(components.gpu_id || undefined);
    gpu.position.set(0.08, -0.15, 0.1);
    modelGroup.add(gpu);

    const cooler = buildCooler(components.cooler_id || undefined);
    cooler.position.set(-0.08, 0.1, 0);
    modelGroup.add(cooler);

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.5;
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enableZoom = true;
    controls.zoomSpeed = 1.2;
    controls.minDistance = 1.5;
    controls.maxDistance = 3;
    controls.enablePan = false;
    controlsRef.current = controls;

    // Auto-rotate timeout
    const resetAutoRotate = () => {
      if (autoRotateTimeoutRef.current) clearTimeout(autoRotateTimeoutRef.current);
      controls.autoRotate = true;

      autoRotateTimeoutRef.current = setTimeout(() => {
        controls.autoRotate = false;
      }, 8000);
    };

    renderer.domElement.addEventListener('pointerdown', resetAutoRotate);
    renderer.domElement.addEventListener('wheel', resetAutoRotate);

    // Animation loop
    const animate = () => {
      animationIdRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Handle resize
    const handleResize = () => {
      if (!containerRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      if (animationIdRef.current) {
        cancelAnimationFrame(animationIdRef.current);
      }
      window.removeEventListener('resize', handleResize);
      renderer.domElement.removeEventListener('pointerdown', resetAutoRotate);
      renderer.domElement.removeEventListener('wheel', resetAutoRotate);
      renderer.dispose();
      if (containerRef.current?.contains(renderer.domElement)) {
        containerRef.current.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Update GPU when it changes
  useEffect(() => {
    if (!modelGroupRef.current) return;

    // Find and remove old GPU
    const oldGPU = modelGroupRef.current.children.find(
      (child) => child.userData?.type === 'gpu'
    );
    if (oldGPU) {
      modelGroupRef.current.remove(oldGPU);
    }

    // Add new GPU
    const newGPU = buildGPU(components.gpu_id || undefined);
    newGPU.position.set(0.08, -0.15, 0.1);
    modelGroupRef.current.add(newGPU);
  }, [components.gpu_id]);

  // Update cooler when it changes
  useEffect(() => {
    if (!modelGroupRef.current) return;

    // Find and remove old cooler
    const oldCooler = modelGroupRef.current.children.find(
      (child) => child.userData?.type === 'cooler'
    );
    if (oldCooler) {
      modelGroupRef.current.remove(oldCooler);
    }

    // Add new cooler
    const newCooler = buildCooler(components.cooler_id || undefined);
    newCooler.position.set(-0.08, 0.1, 0);
    modelGroupRef.current.add(newCooler);
  }, [components.cooler_id]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
