"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  Search,
  Zap,
  Settings2,
  Package,
  AlertTriangle,
  Box,
  Warehouse,
  ChartNoAxesCombined,
  Repeat2,
  Library,
  Trophy,
  Bell,
  Truck,
  Wrench,
  CalendarDays,
  MonitorPlay,
  ClipboardCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getApprovalSnapshot } from "@/lib/approvals";
import { ServiceHealthPanel } from "./service-health-panel";

const PRIMARY_NAV = [
  { href: "/sourcing", icon: Search, label: "Sourcing" },
  { href: "/best-sellers", icon: Trophy, label: "Best Sellers" },
  { href: "/pricewatch", icon: ChartNoAxesCombined, label: "PriceWatch" },
  { href: "/catalogue", icon: Library, label: "Catalogue" },
  { href: "/build-hub", icon: Package, label: "Builds" },
  { href: "/orders", icon: CalendarDays, label: "Workshop Calendar" },
  { href: "/upgrade-desk", icon: Wrench, label: "Upgrade Desk" },
  { href: "/inventory", icon: Warehouse, label: "Inventory" },
  { href: "/demand", icon: ChartNoAxesCombined, label: "Demand" },
  { href: "/cross-listing", icon: Repeat2, label: "Cross-listing" },
  { href: "/live-builds", icon: MonitorPlay, label: "Live Builds" },
  { href: "/dispatch-zone", icon: Truck, label: "Dispatch Zone" },
  { href: "/email-events", icon: Bell, label: "Email Events" },
  { href: "/advertising-growth", icon: Bell, label: "Advertising & Growth" },
    { href: "/catalogue/3d-assets", icon: Box, label: "Photos & 3D models" },
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
  const [approvalCount, setApprovalCount] = useState<number | null>(null);

  useEffect(() => {
    if (pathname === "/login") return;
    let active = true;
    const refresh = () => void getApprovalSnapshot(true).then(snapshot => {
      if (active) setApprovalCount(snapshot.queues.reduce((sum, queue) => sum + queue.count, 0));
    }).catch(() => { if (active) setApprovalCount(null); });
    refresh();
    const timer = window.setInterval(refresh, 60_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [pathname]);

  return (
    <aside className="node-sidebar" style={{ overflow: "hidden" }}>
      <StarsCanvas />

      {/* All content sits above the canvas */}
      <div className="relative z-10 flex flex-col gap-4 h-full">
        <div className="node-brand-wrap">
          <Image src="/pics/flipflop-glow-transparent.png" alt="FlipFlop" width={1254} height={1254} className="h-[240px] w-auto object-contain" />
        </div>

        <nav className="node-nav">
          <Link
            href="/approvals"
            aria-label={`Approvals${approvalCount === null ? ", count unavailable" : `, ${approvalCount} waiting`}`}
            className={cn("node-nav-item-fancy", pathname === "/approvals" && "node-nav-item-fancy-active", approvalCount !== null && approvalCount > 0 && "approvals-nav-pulse")}
          >
            <ClipboardCheck className={cn("h-4 w-4 flex-shrink-0", approvalCount !== null && approvalCount > 0 && "approvals-nav-icon")} />
            <span className="flex-1">Approvals</span>
            <span aria-hidden="true" className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums", approvalCount !== null && approvalCount > 0 ? "bg-rose-500 text-white" : approvalCount === null ? "bg-amber-500/20 text-amber-200" : "bg-white/10 text-slate-400")}>
              {approvalCount === null ? "!" : approvalCount > 99 ? "99+" : approvalCount}
            </span>
          </Link>
          {PRIMARY_NAV.map((item) => {
            const active = pathname === item.href.split("?")[0] ||
              (item.href.startsWith("/catalogue/3d-assets") && pathname === "/components-3d-review");
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
        <ServiceHealthPanel />

      </div>

      <style jsx global>{`
        @keyframes approvals-nav-pulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 0 rgba(244, 63, 94, 0); }
          50% { transform: scale(1.035); box-shadow: 0 0 16px rgba(244, 63, 94, 0.24); }
        }
        @keyframes approvals-icon-pulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.24); }
        }
        .approvals-nav-pulse { color: #fda4af; border-color: rgba(244, 63, 94, 0.32); animation: approvals-nav-pulse 1.25s ease-in-out infinite; }
        .approvals-nav-icon { color: #fb7185; animation: approvals-icon-pulse 1.25s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) {
          .approvals-nav-pulse, .approvals-nav-icon { animation: none; }
        }
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
