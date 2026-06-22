'use client';

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { BuildState, PublicSlotWithVariants } from '@/lib/types';
import { PCBuilderScene, initScene } from '@/lib/model-helpers';
import { getVariantModelUrl, COMPONENT_POSITIONS, COMPONENT_SCALES, getAllModelUrls } from '@/lib/model-manifest';

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
  const modelUpdateRef = useRef<Map<string, string>>(new Map());

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

      // Preload all possible models
      const allUrls = getAllModelUrls();
      if (allUrls.length > 0) {
        scene.preloadModels(allUrls).catch(err => {
          console.warn('Model preloading partial failure:', err);
        });
      }

      // Load initial models for each slot
      slots.forEach((slot) => {
        const position = new THREE.Vector3(
          COMPONENT_POSITIONS[slot.slot_type]?.x || 0,
          COMPONENT_POSITIONS[slot.slot_type]?.y || 0,
          COMPONENT_POSITIONS[slot.slot_type]?.z || 0
        );
        const scale = COMPONENT_SCALES[slot.slot_type] || 0.8;

        // Load placeholder initially (will be updated when build state changes)
        scene.loadModel('', slot.slot_type, position, scale);
        modelUpdateRef.current.set(slot.slot_type, '');
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

    slots.forEach((slot) => {
      const variant = build.slots[slot.slot_type];
      if (variant) {
        // Get model URL for this variant
        const newUrl = getVariantModelUrl(slot.slot_type, variant.id);
        const previousUrl = modelUpdateRef.current.get(slot.slot_type);

        // Only update if URL changed
        if (newUrl && newUrl !== previousUrl) {
          const scale = COMPONENT_SCALES[slot.slot_type] || 0.8;

          // Update the component in the 3D scene
          sceneRef.current!.updateComponent(slot.slot_type, newUrl, scale).then((success) => {
            if (success) {
              modelUpdateRef.current.set(slot.slot_type, newUrl);
              // Optional: Add animation feedback
              const model = sceneRef.current!.models.get(slot.slot_type);
              if (model) {
                model.mesh.scale.set(
                  model.mesh.scale.x * 1.1,
                  model.mesh.scale.y * 1.1,
                  model.mesh.scale.z * 1.1
                );
                setTimeout(() => {
                  model.mesh.scale.set(scale, scale, scale);
                }, 200);
              }
            }
          });
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
        <div className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm z-10">
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
        Click components to swap them · Models: {slots.length} loaded
      </div>
    </div>
  );
}
