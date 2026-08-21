'use client';

import React, { useEffect, useRef } from 'react';

export function TwinklingStars() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Create stars array
    const stars: Array<{ x: number; y: number; radius: number; opacity: number; twinkleSpeed: number }> = [];
    const starCount = Math.min(400, Math.floor((canvas.width * canvas.height) / 10000));

    for (let i = 0; i < starCount; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        radius: Math.random() * 1.5,
        opacity: Math.random() * 0.5 + 0.5,
        twinkleSpeed: Math.random() * 0.02 + 0.005,
      });
    }

    // Animation loop
    let animationFrameId: number;
    let time = 0;

    function animate() {
      // Dark gradient background
      const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
      gradient.addColorStop(0, '#0a0e27');
      gradient.addColorStop(0.5, '#0f1535');
      gradient.addColorStop(1, '#0a0a1a');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw and twinkle stars
      stars.forEach((star) => {
        // Twinkle effect using sine wave
        const twinkle = Math.sin(time * star.twinkleSpeed) * 0.5 + 0.5;
        const finalOpacity = star.opacity * twinkle;

        ctx.fillStyle = `rgba(255, 255, 255, ${finalOpacity})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fill();

        // Subtle glow
        ctx.strokeStyle = `rgba(100, 150, 255, ${finalOpacity * 0.3})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      time += 1;
      animationFrameId = requestAnimationFrame(animate);
    }

    animate();

    // Handle window resize
    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed top-0 left-0 w-full h-full"
      style={{ zIndex: 1 }}
    />
  );
}
