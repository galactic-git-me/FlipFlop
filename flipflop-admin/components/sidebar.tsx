"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  Search,
  Zap,
  Settings2,
  Package,
  AlertTriangle,
  Box,
  Warehouse,
} from "lucide-react";
import { cn } from "@/lib/utils";

const PRIMARY_NAV = [
  { href: "/sourcing", icon: Search, label: "Sourcing" },
  { href: "/builds", icon: Package, label: "Pre-Built" },
  { href: "/configurator-config", icon: Settings2, label: "Custom Builds" },
  { href: "/pc-builder", icon: Zap, label: "Curated Builds" },
  { href: "/inventory", icon: Warehouse, label: "Inventory" },
  { href: "/components-3d-review", icon: Box, label: "3D Assets" },
  { href: "/problems", icon: AlertTriangle, label: "Problems" },
];

// ─── Twinkling stars canvas ───────────────────────────────────────────────────

interface Star {
  x: number;
  y: number;
  r: number;
  alpha: number;
  speed: number;
  phase: number;
}

function StarsCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width  = W;
    canvas.height = H;

    const COUNT = 80;
    const stars: Star[] = Array.from({ length: COUNT }, () => ({
      x:     Math.random() * W,
      y:     Math.random() * H,
      r:     0.4 + Math.random() * 1.1,
      alpha: Math.random(),
      speed: 0.003 + Math.random() * 0.008,
      phase: Math.random() * Math.PI * 2,
    }));

    let raf: number;
    let t = 0;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      t += 1;
      for (const s of stars) {
        const a = 0.15 + 0.85 * (0.5 + 0.5 * Math.sin(s.phase + t * s.speed));
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(180, 220, 255, ${a})`;
        ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ zIndex: 0 }}
    />
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="node-sidebar" style={{ overflow: "hidden" }}>
      <StarsCanvas />

      {/* All content sits above the canvas */}
      <div className="relative z-10 flex flex-col gap-4 h-full">
        <div className="node-brand-wrap">
          <Image src="/pics/flipflop-glow-transparent.png" alt="FlipFlop" width={1254} height={1254} className="h-[240px] w-auto object-contain" />
        </div>

        <nav className="node-nav">
          {PRIMARY_NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn("node-nav-item-fancy", active && "node-nav-item-fancy-active")}
              >
                <item.icon className="h-4 w-4 flex-shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

      </div>

      <style jsx global>{`
        .node-nav-item-fancy {
          display: flex;
          align-items: center;
          gap: 0.8rem;
          height: 2.7rem;
          text-decoration: none;
          border-radius: 0.2rem;
          padding: 0 0.8rem;
          font-family: var(--font-jetbrains), monospace;
          font-size: 1rem;
          border: 1px solid transparent;
          position: relative;
          color: #c9d3d9;
          overflow: hidden;
          transition: color 0.25s ease, border-color 0.25s ease;
        }

        /* gradient sweep background on hover */
        .node-nav-item-fancy::before {
          content: "";
          position: absolute;
          inset: 0;
          background: linear-gradient(
            105deg,
            rgba(0, 184, 255, 0) 0%,
            rgba(0, 220, 130, 0.12) 40%,
            rgba(164, 100, 255, 0.10) 70%,
            rgba(0, 184, 255, 0) 100%
          );
          background-size: 200% 100%;
          background-position: 120% 0;
          transition: background-position 0.4s ease, opacity 0.3s ease;
          opacity: 0;
          border-radius: inherit;
        }

        .node-nav-item-fancy:hover::before {
          background-position: -20% 0;
          opacity: 1;
        }

        /* gradient text on hover */
        .node-nav-item-fancy:hover {
          color: transparent;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          -webkit-background-clip: text;
          /* painted via a pseudo below; text color gradient via filter workaround */
          border-color: rgba(0, 220, 130, 0.18);
        }

        /* Since background-clip:text conflicts with ::before, use a separate overlay */
        .node-nav-item-fancy::after {
          content: "";
          position: absolute;
          inset: 0;
          background: linear-gradient(
            105deg,
            #00b8ff 0%,
            #00dc82 50%,
            #a855f7 100%
          );
          -webkit-background-clip: text;
          background-clip: text;
          opacity: 0;
          transition: opacity 0.25s ease;
          pointer-events: none;
        }

        .node-nav-item-fancy:hover {
          color: #00dc82;
          -webkit-text-fill-color: unset;
          background-clip: unset;
          -webkit-background-clip: unset;
          filter: drop-shadow(0 0 6px rgba(0, 220, 130, 0.35));
          border-color: rgba(0, 220, 130, 0.2);
        }

        .node-nav-item-fancy:hover svg {
          filter: drop-shadow(0 0 4px rgba(0, 184, 255, 0.7));
          color: #00b8ff;
          transition: color 0.25s ease, filter 0.25s ease;
        }

        /* Active state */
        .node-nav-item-fancy-active {
          color: var(--nf-primary);
          background: rgba(164, 230, 255, 0.08);
          border-color: rgba(164, 230, 255, 0.22);
          filter: drop-shadow(0 0 4px rgba(0, 184, 255, 0.2));
        }

        .node-nav-item-fancy-active::before {
          background: linear-gradient(
            105deg,
            rgba(0, 184, 255, 0.06) 0%,
            rgba(0, 220, 130, 0.10) 50%,
            rgba(164, 100, 255, 0.06) 100%
          );
          background-position: 0% 0;
          opacity: 1;
        }
      `}</style>
    </aside>
  );
}
