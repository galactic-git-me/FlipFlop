"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { createAvatarGLTFLoader } from "@/lib/avatar-gltf-loader";

/** Lightweight Three.js rendering of the same Hermes model used on FlipFlop.shop. */
export default function HermesBotAvatar() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let frameId = 0;
    let model: THREE.Object3D | null = null;
    let renderer: THREE.WebGLRenderer;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(0, 0, 2.6);

    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.setClearColor(0x000000, 0);
      container.appendChild(renderer.domElement);
    } catch {
      return;
    }

    // Lift the model's overall exposure so its details remain visible inside
    // the dark circular launcher as well as in the chat header.
    scene.add(new THREE.AmbientLight(0xffffff, 2.8));
    const warmLight = new THREE.DirectionalLight(0xfff2dd, 3.1);
    warmLight.position.set(2, 3, 3);
    scene.add(warmLight);
    const blueLight = new THREE.DirectionalLight(0x1e7bff, 1.6);
    blueLight.position.set(-2, 1, -2);
    scene.add(blueLight);

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    createAvatarGLTFLoader().load("/media/bot.glb", (gltf) => {
      if (disposed) return;
      model = gltf.scene.clone(true);
      const bounds = new THREE.Box3().setFromObject(model);
      const size = bounds.getSize(new THREE.Vector3());
      const center = bounds.getCenter(new THREE.Vector3());
      const largestSide = Math.max(size.x, size.y, size.z) || 1;
      model.position.sub(center);
      model.scale.setScalar(1.38 / largestSide);
      scene.add(model);
      setReady(true);
    }, undefined, () => {
      if (!disposed) setReady(false);
    });

    const animate = () => {
      frameId = window.requestAnimationFrame(animate);
      if (model) model.rotation.y += 0.28 / 60;
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      if (model) model.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div ref={containerRef} className="relative h-full w-full" role="img" aria-label="Flip">
      {!ready && <Image src="/pics/hermes.gif" alt="" fill sizes="96px" className="object-cover" unoptimized />}
    </div>
  );
}
