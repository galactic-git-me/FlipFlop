"use client";

import { useEffect, useRef } from "react";

interface Star {
  x: number;
  y: number;
  radius: number;
  opacity: number;
  twinkleDuration: number;
  twinkling: boolean;
  animationDelay: number;
}

export function TwinklingStars() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const animationRef = useRef<number>();
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const updateCanvasSize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    updateCanvasSize();

    // Generate stars
    const starCount = Math.floor((canvas.width * canvas.height) / 8000);
    starsRef.current = Array.from({ length: starCount }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.2,
      opacity: Math.random() * 0.5 + 0.3,
      twinkleDuration: Math.random() * 2000 + 1500,
      twinkling: Math.random() > 0.7,
      animationDelay: Math.random() * 5000,
    }));

    // Animation loop
    let lastFrameTime = Date.now();
    const animate = () => {
      const now = Date.now();
      const deltaTime = now - lastFrameTime;
      lastFrameTime = now;

      timeRef.current += deltaTime;

      // Clear canvas with semi-transparent dark
      ctx.fillStyle = "rgba(15, 23, 42, 0.1)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw stars
      starsRef.current.forEach((star) => {
        const timeSinceDelay = Math.max(0, timeRef.current - star.animationDelay);

        if (star.twinkling) {
          // Oscillate opacity for twinkling effect
          const cyclePosition = (timeSinceDelay % star.twinkleDuration) / star.twinkleDuration;
          const twinkle = Math.sin(cyclePosition * Math.PI * 2);
          star.opacity = 0.2 + (twinkle * 0.3 + 0.3) * 0.5;
        } else {
          // Subtle pulsing for non-twinkling stars
          const slowPulse = (Math.sin(timeSinceDelay / 3000) + 1) / 2;
          star.opacity = 0.3 + slowPulse * 0.4;
        }

        // Draw star
        ctx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fill();

        // Add subtle glow to brighter stars
        if (star.opacity > 0.5) {
          ctx.strokeStyle = `rgba(255, 255, 255, ${star.opacity * 0.3})`;
          ctx.lineWidth = 0.5;
          ctx.beginPath();
          ctx.arc(star.x, star.y, star.radius * 1.5, 0, Math.PI * 2);
          ctx.stroke();
        }
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    // Handle window resize
    const handleResize = () => {
      updateCanvasSize();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{
        zIndex: 0,
        background: "radial-gradient(ellipse at 50% 0%, #1e3a8a 0%, #0f172a 50%, #000000 100%)",
      }}
    />
  );
}
