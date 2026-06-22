'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';
import { PCBuilderScene, initScene } from '@/lib/model-helpers';

interface Props {
  build: BuildState;
  slots: PublicSlotWithVariants[];
  onComponentClick: (slotType: string) => void;
}

export function ModelViewer3D({ build, slots, onComponentClick }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<PCBuilderScene | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize scene on mount
  useEffect(() => {
    if (!containerRef.current) return;

    try {
      const scene = initScene(containerRef.current);
      sceneRef.current = scene;

      // Position case (conceptual centerpiece)
      const caseGroup = new THREE.Group();
      const caseGeometry = new THREE.BoxGeometry(5, 6, 3);
      const caseMaterial = new THREE.MeshStandardMaterial({
        color: 0x18181b,
        metalness: 0.1,
        roughness: 0.8,
      });
      const caseMesh = new THREE.Mesh(caseGeometry, caseMaterial);
      caseMesh.position.set(0, 0, 0);
      caseMesh.castShadow = true;
      caseMesh.receiveShadow = true;
      caseGroup.add(caseMesh);
      caseGroup.userData.slotType = 'case';
      scene.scene.add(caseGroup);

      // Load placeholder models for each slot
      const componentPositions: Record<string, THREE.Vector3> = {
        gpu: new THREE.Vector3(2, 0.5, -0.5),
        cpu: new THREE.Vector3(0, 0.5, 0.5),
        ram: new THREE.Vector3(-1.5, 1.2, -1),
        storage: new THREE.Vector3(-2, -1, 0),
        cooling: new THREE.Vector3(0, 2, 0),
      };

      // Load models for visible slots
      slots.forEach((slot) => {
        const position = componentPositions[slot.slot_type] || new THREE.Vector3(0, 0, 0);
        scene.loadModel('', slot.slot_type, position, 0.8);
      });

      // Start render loop
      const animate = () => {
        scene.render();
        animationFrameRef.current = requestAnimationFrame(animate);
      };
      animate();

      setIsLoading(false);

      return () => {
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        scene.dispose();
      };
    } catch (error) {
      console.error('Failed to initialize 3D scene:', error);
      setIsLoading(false);
    }
  }, [slots]);

  // Handle mouse clicks on 3D objects
  useEffect(() => {
    if (!containerRef.current || !sceneRef.current) return;

    const handleCanvasClick = (event: MouseEvent) => {
      const clickedComponent = sceneRef.current!.getClickedComponent(
        event,
        sceneRef.current!.renderer.domElement
      );

      if (clickedComponent && clickedComponent !== 'case') {
        onComponentClick(clickedComponent);
      }
    };

    const canvas = sceneRef.current.renderer.domElement;
    canvas.addEventListener('click', handleCanvasClick);

    return () => {
      canvas.removeEventListener('click', handleCanvasClick);
    };
  }, [onComponentClick]);

  // Update 3D models when build state changes
  useEffect(() => {
    if (!sceneRef.current) return;

    // For each slot, if the selected variant changed, reload the model
    slots.forEach((slot) => {
      const current = build.slots[slot.slot_type];
      if (current) {
        // In Phase 2, this will load the actual model based on variant ID
        // For now, placeholder is already positioned
        // Optional: Add subtle animation to indicate update
        const model = sceneRef.current!.models.get(slot.slot_type);
        if (model) {
          // Flash animation to indicate update
          model.mesh.scale.set(1.05, 1.05, 1.05);
          setTimeout(() => {
            model.mesh.scale.set(1, 1, 1);
          }, 200);
        }
      }
    });
  }, [build, slots]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (!containerRef.current || !sceneRef.current) return;
      const width = containerRef.current.clientWidth;
      const height = containerRef.current.clientHeight;
      sceneRef.current.setSize(width, height);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="w-full h-full flex flex-col bg-gradient-to-b from-[var(--color-bg-card)] to-[var(--color-bg)]">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
            <p className="text-sm text-muted">Loading 3D scene...</p>
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        className="w-full flex-1 rounded-xl overflow-hidden border border-[var(--color-border)]"
        style={{ minHeight: '500px' }}
      />
      <div className="text-xs text-muted text-center py-2">
        Click components to swap them
      </div>
    </div>
  );
}
