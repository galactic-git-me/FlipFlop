'use client';

import React, { useEffect, useRef } from 'react';

export function TwinklingStars() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const updateSize = () => {
      if (!canvas.parentElement) return;
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    };

    updateSize();

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

    let animationFrameId: number;
    let time = 0;

    const animate = () => {
      const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
      gradient.addColorStop(0, '#0a0e27');
      gradient.addColorStop(0.5, '#0f1535');
      gradient.addColorStop(1, '#0a0a1a');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      stars.forEach((star) => {
        const twinkle = Math.sin(time * star.twinkleSpeed) * 0.5 + 0.5;
        const finalOpacity = star.opacity * twinkle;

        ctx.fillStyle = `rgba(255, 255, 255, ${finalOpacity})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = `rgba(100, 150, 255, ${finalOpacity * 0.3})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      time += 1;
      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    const handleResize = () => {
      updateSize();
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
      className="w-full h-full block"
      style={{ display: 'block' }}
    />
  );
}
