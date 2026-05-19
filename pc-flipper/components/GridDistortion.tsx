"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import "./GridDistortion.css";

const vertexShader = `
uniform float time;
varying vec2 vUv;
varying vec3 vPosition;

void main() {
  vUv = uv;
  vPosition = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const fragmentShader = `
uniform sampler2D uDataTexture;
uniform sampler2D uTexture;
uniform vec4 resolution;
uniform float time;
varying vec2 vUv;

void main() {
  vec2 uv = vUv;
  // Data texture is stored in 0..1 range with neutral center at 0.5
  vec2 offset = texture2D(uDataTexture, vUv).rg - vec2(0.5);
  // Autonomous wave + radial pulse so distortion remains visible at rest.
  vec2 wave = vec2(
    sin(vUv.y * 26.0 + time * 1.1),
    cos(vUv.x * 24.0 + time * 1.0)
  ) * 0.006;
  vec2 c = vUv - vec2(0.5);
  float ring = sin(length(c) * 36.0 - time * 1.4) * 0.004;
  vec2 radial = normalize(c + vec2(0.0001)) * ring;
  gl_FragColor = texture2D(uTexture, uv - 0.14 * offset + wave + radial);
}`;

interface GridDistortionProps {
  grid?: number;
  mouse?: number;
  strength?: number;
  relaxation?: number;
  imageSrc: string;
  className?: string;
  onTextureReady?: (ready: boolean) => void;
}

const GridDistortion = ({
  grid = 15,
  mouse = 0.1,
  strength = 0.15,
  relaxation = 0.9,
  imageSrc,
  className = "",
  onTextureReady,
}: GridDistortionProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const animationIdRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    let mounted = true;

    const scene = new THREE.Scene();
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);

    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const camera = new THREE.OrthographicCamera(0, 0, 0, 0, -1000, 1000);
    camera.position.z = 2;

    const uniforms: Record<string, THREE.IUniform> = {
      time: { value: 0 },
      resolution: { value: new THREE.Vector4() },
      uTexture: { value: null },
      uDataTexture: { value: null },
    };

    let imageAspect = 1;

    const size = grid;
    // Use Uint8 texture for broad compatibility (works without float texture extensions)
    const data = new Uint8Array(4 * size * size);
    for (let i = 0; i < size * size; i++) {
      // Neutral center (128, 128) means zero distortion at rest
      data[i * 4] = 128;
      data[i * 4 + 1] = 128;
      data[i * 4 + 2] = 0;
      data[i * 4 + 3] = 255;
    }

    const dataTexture = new THREE.DataTexture(
      data,
      size,
      size,
      THREE.RGBAFormat,
      THREE.UnsignedByteType
    );
    dataTexture.minFilter = THREE.LinearFilter;
    dataTexture.magFilter = THREE.LinearFilter;
    dataTexture.wrapS = THREE.ClampToEdgeWrapping;
    dataTexture.wrapT = THREE.ClampToEdgeWrapping;
    dataTexture.needsUpdate = true;
    uniforms.uDataTexture.value = dataTexture;

    const material = new THREE.ShaderMaterial({
      side: THREE.DoubleSide,
      uniforms,
      vertexShader,
      fragmentShader,
      transparent: true,
    });

    const geometry = new THREE.PlaneGeometry(1, 1, size - 1, size - 1);
    const plane = new THREE.Mesh(geometry, material);
    scene.add(plane);

    const handleResize = () => {
      const rect = container.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      if (width === 0 || height === 0) return;

      const containerAspect = width / height;
      renderer.setSize(width, height);
      plane.scale.set(containerAspect, 1, 1);

      const frustumHeight = 1;
      const frustumWidth = frustumHeight * containerAspect;
      camera.left = -frustumWidth / 2;
      camera.right = frustumWidth / 2;
      camera.top = frustumHeight / 2;
      camera.bottom = -frustumHeight / 2;
      camera.updateProjectionMatrix();

      uniforms.resolution.value.set(width, height, 1, 1);
    };

    const textureLoader = new THREE.TextureLoader();
    textureLoader.load(
      imageSrc,
      (texture) => {
        if (!mounted) { texture.dispose(); return; }
        texture.minFilter = THREE.LinearFilter;
        texture.magFilter = THREE.LinearFilter;
        texture.wrapS = THREE.ClampToEdgeWrapping;
        texture.wrapT = THREE.ClampToEdgeWrapping;
        imageAspect = texture.image.width / texture.image.height;
        void imageAspect;
        uniforms.uTexture.value = texture;
        handleResize();
        onTextureReady?.(true);
      },
      undefined,
      () => {
        onTextureReady?.(false);
      }
    );

    resizeObserverRef.current = new ResizeObserver(handleResize);
    resizeObserverRef.current.observe(container);
    handleResize();

    const mouseState = { x: 0, y: 0, prevX: 0, prevY: 0, vX: 0, vY: 0 };

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = 1 - (e.clientY - rect.top) / rect.height;
      mouseState.vX = x - mouseState.prevX;
      mouseState.vY = y - mouseState.prevY;
      Object.assign(mouseState, { x, y, prevX: x, prevY: y });
    };

    // Listen on window so pointer-events:none on parent doesn't block events
    window.addEventListener("mousemove", handleMouseMove);

    const animate = () => {
      animationIdRef.current = requestAnimationFrame(animate);
      uniforms.time.value += 0.05;

      const texData = dataTexture.image.data as Uint8Array;
      for (let i = 0; i < size * size; i++) {
        const rIdx = i * 4;
        const gIdx = rIdx + 1;
        // Relax back toward neutral center (128)
        texData[rIdx] = Math.max(0, Math.min(255, Math.round(128 + (texData[rIdx] - 128) * relaxation)));
        texData[gIdx] = Math.max(0, Math.min(255, Math.round(128 + (texData[gIdx] - 128) * relaxation)));
      }

      const gridMouseX = size * mouseState.x;
      const gridMouseY = size * mouseState.y;
      const maxDist = size * mouse;

      for (let i = 0; i < size; i++) {
        for (let j = 0; j < size; j++) {
          const distSq =
            Math.pow(gridMouseX - i, 2) + Math.pow(gridMouseY - j, 2);
          if (distSq < maxDist * maxDist) {
            const index = 4 * (i + size * j);
            const power = Math.min(maxDist / Math.sqrt(distSq), 10);
            const dx = strength * 360 * mouseState.vX * power;
            const dy = strength * 360 * mouseState.vY * power;
            texData[index] = Math.max(0, Math.min(255, texData[index] + dx));
            texData[index + 1] = Math.max(0, Math.min(255, texData[index + 1] - dy));
          }
        }
      }

      dataTexture.needsUpdate = true;
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      mounted = false;
      if (animationIdRef.current) cancelAnimationFrame(animationIdRef.current);
      resizeObserverRef.current?.disconnect();
      window.removeEventListener("mousemove", handleMouseMove);
      renderer.dispose();
      renderer.forceContextLoss();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      geometry.dispose();
      material.dispose();
      dataTexture.dispose();
      if (uniforms.uTexture.value) uniforms.uTexture.value.dispose();
      onTextureReady?.(false);
    };
  }, [grid, mouse, strength, relaxation, imageSrc, onTextureReady]);

  return (
    <div
      ref={containerRef}
      className={`distortion-container ${className}`.trim()}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        minWidth: 0,
        minHeight: 0,
      }}
    />
  );
};

export default GridDistortion;
