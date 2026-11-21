"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  Search,
  Package,
  AlertTriangle,
  Box,
  Warehouse,
  ChartNoAxesCombined,
  Activity,
  Bot,
  Repeat2,
  Library,
  Trophy,
  Bell,
  Truck,
  Wrench,
  CalendarDays,
  MonitorPlay,
  FileText,
  CheckCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ServiceHealthPanel } from "./service-health-panel";

const PRIMARY_NAV_GROUPS = [
  { heading: "Market & Sourcing", items: [
    { href: "/demand", icon: ChartNoAxesCombined, label: "Demand" },
    { href: "/best-sellers", icon: Trophy, label: "Best Sellers" },
    { href: "/pricewatch", icon: Activity, label: "PriceWatch" },
    { href: "/sourcing", icon: Search, label: "Sourcing" },
  ] },
  { heading: "Commercial", items: [
    { href: "/pc-builder?tab=playbook", icon: FileText, label: "The Playbook" },
    { href: "/approvals", icon: CheckCheck, label: "Approvals" },
    { href: "/best-sellers", icon: Trophy, label: "Best Sellers" },
  ] },
  { heading: "Stock & Catalogue", items: [
    { href: "/inventory", icon: Warehouse, label: "Inventory" },
    { href: "/catalogue", icon: Library, label: "Catalogue" },
  ] },
  { heading: "Build & Workshop", items: [
    { href: "/build-hub", icon: Package, label: "Build Queue" },
    { href: "/orders", icon: CalendarDays, label: "Workshop Calendar" },
    { href: "/upgrade-desk", icon: Wrench, label: "Upgrade Desk" },
  ] },
  { heading: "Listings & Growth", items: [
    { href: "/anthropic-tracker", icon: Bot, label: "Anthropic Tracker" },
    { href: "/catalogue/3d-assets", icon: Box, label: "Photos & 3D Models" },
    { href: "/live-builds", icon: MonitorPlay, label: "Live Listings" },
    { href: "/cross-listing", icon: Repeat2, label: "Cross-listing" },
    { href: "/advertising-growth", icon: Bell, label: "Advertising & Growth" },
    { href: "/email-events", icon: Bell, label: "Notifications" },
  ] },
  { heading: "Orders & Dispatch", items: [
    { href: "/dispatch-zone", icon: Truck, label: "Dispatch Zone" },
  ] },
  { heading: "Policies", items: [
    { href: "/policies", icon: FileText, label: "Customer Policies" },
  ] },
];

const TERMINAL_PROBLEM_STATUSES = new Set(["resolved", "rejected", "closed"]);

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
  const [openIssueCount, setOpenIssueCount] = useState<number | null>(null);
  const activeGroup = PRIMARY_NAV_GROUPS.find((group) => group.items.some((item) =>
    pathname === item.href.split("?")[0] || (item.href.startsWith("/catalogue/3d-assets") && pathname === "/components-3d-review"),
  ));
  const [openGroup, setOpenGroup] = useState<string | null>(() => activeGroup?.heading ?? null);

  useEffect(() => { setOpenGroup(activeGroup?.heading ?? null); }, [activeGroup]);

  useEffect(() => {
    let active = true;
    const refreshOpenIssueCount = async () => {
      try {
        const response = await fetch("/api/admin/customer-problems", { cache: "no-store" });
        if (!response.ok) return;
        const problems = await response.json() as Array<{ status?: string }>;
        if (active && Array.isArray(problems)) {
          setOpenIssueCount(problems.filter((problem) => !TERMINAL_PROBLEM_STATUSES.has((problem.status ?? "").toLowerCase())).length);
        }
      } catch {
        // Keep the navigation available if issue counts are temporarily unavailable.
      }
    };

    void refreshOpenIssueCount();
    const interval = window.setInterval(() => void refreshOpenIssueCount(), 60_000);
    return () => { active = false; window.clearInterval(interval); };
  }, [pathname]);

  return (
    <aside className="node-sidebar" style={{ overflow: "hidden" }}>
      <StarsCanvas />

      {/* All content sits above the canvas */}
      <div className="relative z-10 flex flex-col gap-4 h-full">
        <div className="node-brand-wrap">
          <Image src="/pics/flipflop-glow-transparent.png" alt="FlipFlop" width={1254} height={1254} className="h-[240px] w-auto object-contain" />
        </div>

        <nav className="node-nav min-h-0" aria-label="Main navigation">
          {PRIMARY_NAV_GROUPS.map((group) => {
            const groupId = `nav-group-${group.heading.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
            const expanded = openGroup === group.heading;
            const GroupIcon = group.items[0].icon;
            return <section key={group.heading} className="node-nav-group">
              <button type="button" id={groupId} className={cn("node-nav-group-trigger", expanded && "node-nav-group-trigger-open")} aria-expanded={expanded} aria-controls={`${groupId}-items`} onClick={() => setOpenGroup((current) => current === group.heading ? null : group.heading)}>
                <span className="node-nav-group-icon"><GroupIcon className="h-5 w-5" /></span>
                <span className="node-nav-group-copy"><span className="node-nav-group-heading">{group.heading}</span></span>
              </button>
              <div id={`${groupId}-items`} className="node-nav-accordion" aria-labelledby={groupId} aria-hidden={!expanded} inert={!expanded} style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}>
                <div className="node-nav-accordion-clip">
                  <div className="node-nav-accordion-items">
              {group.items.map((item) => {
                const active = pathname === item.href.split("?")[0] ||
                  (item.href.startsWith("/catalogue/3d-assets") && pathname === "/components-3d-review");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn("node-nav-item-fancy", active && "node-nav-item-fancy-active")}
                  >
                    <span className="node-nav-link-icon"><item.icon className="h-5 w-5 flex-shrink-0" /></span>
                    <span className="node-nav-link-copy"><span className={cn("node-nav-link-label", active && "admin-lime-title")}>{item.label}</span></span>
                  </Link>
                );
              })}
                  </div>
                </div>
              </div>
            </section>;
          })}
        </nav>
        <div className="node-nav-issue-footer">
          <Link href="/problems" className={cn("node-nav-item-fancy node-nav-issue-item", pathname === "/problems" && "node-nav-item-fancy-active")} aria-label={`Issues & Exceptions${openIssueCount === null ? "" : `, ${openIssueCount} open`}`}>
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span className="node-nav-link-label">Issues &amp; Exceptions</span>
            {openIssueCount !== null && <span className="node-nav-issue-count" aria-label={`${openIssueCount} open issues`}>{openIssueCount > 99 ? "99+" : openIssueCount}</span>}
          </Link>
        </div>
        <ServiceHealthPanel />

      </div>

      <style jsx global>{`
        .node-nav-item-fancy {
          display: flex;
          align-items: center;
          gap: 0.65rem;
          min-height: 3.1rem;
          height: auto;
          text-decoration: none;
          border-radius: 0.45rem;
          padding: 0.4rem 0.5rem;
          border: 0;
          color: #c9d3d9;
          font-family: 'FlipFlopNASA', sans-serif;
          text-transform: uppercase;
          transition: color 0.2s ease, border-color 0.2s ease, background 0.2s ease;
        }

        .node-nav-link-copy {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .node-nav-link-label {
          color: #e5e7eb;
          font-family: 'FlipFlopNASA', sans-serif;
          font-size: 0.9rem;
          font-weight: 600;
          line-height: 1.3;
          letter-spacing: 0.035em;
        }

        .node-nav-link-icon, .node-nav-group-icon {
          width: 2.5rem;
          height: 2.5rem;
          flex: 0 0 2.5rem;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border: 0;
          border-radius: 0;
          color: #b4c2d0;
          background: transparent;
          transition: color 0.2s ease;
        }

        .node-nav-group {
          margin-bottom: 0.3rem;
        }

        .node-nav-group-trigger {
          width: 100%;
          display: flex;
          align-items: center;
          gap: 0.75rem;
          min-height: 3.6rem;
          padding: 0.4rem 0.65rem;
          text-align: left;
          font-family: 'FlipFlopNASA', sans-serif;
          text-transform: uppercase;
          border: 0;
          border-radius: 0;
          background: transparent;
          color: #d1d5db;
          cursor: pointer;
          transition: background 0.2s ease;
        }

        .node-nav-group-trigger:hover,
        .node-nav-group-trigger:focus-visible,
        .node-nav-group-trigger-open {
          background: linear-gradient(110deg, rgba(249, 115, 22, 0.1), rgba(59, 130, 246, 0.12));
        }

        .node-nav-group-trigger:hover .node-nav-group-heading,
        .node-nav-group-trigger:focus-visible .node-nav-group-heading {
          background-image: linear-gradient(100deg, #fb923c 0%, #60a5fa 45%, #f97316 70%, #93c5fd 100%);
          background-size: 260% 100%;
          background-position: 0% 50%;
          background-clip: text;
          -webkit-background-clip: text;
          color: transparent;
          -webkit-text-fill-color: transparent;
          animation: nav-heading-gradient 1.8s linear infinite;
        }

        @keyframes nav-heading-gradient {
          to { background-position: 260% 50%; }
        }

        .node-nav-group-trigger-open .node-nav-group-icon { color: #bfdbfe; }

        .node-nav-group-copy { display: flex; flex: 1; min-width: 0; align-items: center; }
        .node-nav-group-heading { color: #f3f4f6; font-size: 0.92rem; font-weight: 650; line-height: 1.3; letter-spacing: 0.035em; }

        .node-nav-accordion { display: grid; transition: grid-template-rows 0.34s cubic-bezier(0.22, 1, 0.36, 1); }
        .node-nav-accordion-clip { min-height: 0; overflow: hidden; }
        .node-nav-accordion-items { padding: 0.25rem 0 0.45rem 0.55rem; margin-left: 1rem; border-left: 1px solid rgba(96, 165, 250, 0.18); opacity: 1; transform: translateY(0); transition: opacity 0.2s ease, transform 0.28s cubic-bezier(0.22, 1, 0.36, 1); }
        .node-nav-accordion[aria-hidden="true"] .node-nav-accordion-items { opacity: 0; transform: translateY(-0.3rem); }

        .node-nav-item-fancy:hover {
          background: linear-gradient(105deg, rgba(249, 115, 22, 0.1), rgba(59, 130, 246, 0.14));
          color: #fff;
        }

        .node-nav-item-fancy:hover .node-nav-link-icon { color: #bfdbfe; }

        .node-nav-item-fancy-active {
          background: linear-gradient(105deg, rgba(132, 204, 22, 0.09), rgba(101, 163, 13, 0.15));
          box-shadow: inset 2px 0 #84cc16, 0 0 14px rgba(132, 204, 22, 0.1);
        }

        .node-nav-item-fancy-active .node-nav-link-icon { color: #bef264; }

        .node-nav-issue-footer {
          flex-shrink: 0;
          padding-top: 0.45rem;
          border-top: 1px solid rgba(164, 230, 255, 0.14);
        }

        .node-nav-issue-item {
          min-height: 2.7rem;
          height: auto;
          gap: 0.5rem;
          padding: 0 0.55rem;
          font-size: 0.75rem;
        }

        .node-nav-issue-count {
          display: inline-flex;
          min-width: 1.35rem;
          height: 1.35rem;
          align-items: center;
          justify-content: center;
          margin-left: auto;
          padding: 0 0.3rem;
          border: 1px solid rgba(251, 191, 36, 0.35);
          border-radius: 9999px;
          background: rgba(251, 191, 36, 0.12);
          color: #fcd34d;
          font-family: var(--font-jetbrains), monospace;
          font-size: 0.68rem;
          font-weight: 700;
          line-height: 1;
        }

        @media (prefers-reduced-motion: reduce) {
          .node-nav-accordion, .node-nav-accordion-items { transition: none; }
          .node-nav-group-trigger:hover .node-nav-group-heading,
          .node-nav-group-trigger:focus-visible .node-nav-group-heading { animation: none; }
          .node-nav-item-fancy-active .node-nav-link-label { animation: none; background-position: 50% 50%; }
        }
      `}</style>
    </aside>
  );
}
