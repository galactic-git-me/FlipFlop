"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Box, Images } from "lucide-react";

const steps = [
  {
    href: "/cases-3d-priority",
    label: "1. Photos & generation",
    description: "Choose four photos and create the draft",
    icon: Images,
  },
  {
    href: "/components-3d-review",
    label: "2. Model approval",
    description: "Inspect, approve and publish generated models",
    icon: Box,
  },
];

export function ThreeDWorkflowNav({ compact = false }: { compact?: boolean }) {
  const pathname = usePathname();
  return (
    <nav aria-label="3D asset workflow" className={`flex flex-wrap gap-2 ${compact ? "" : "rounded-lg border border-slate-700 bg-slate-950/50 p-2"}`}>
      {steps.map(step => {
        const active = pathname === step.href;
        const Icon = step.icon;
        return (
          <Link
            key={step.href}
            href={step.href}
            aria-current={active ? "step" : undefined}
            className={`flex min-w-48 items-center gap-2 rounded-md border px-3 py-2 transition ${active ? "border-orange-400 bg-orange-500/15 text-orange-100" : "border-slate-700 bg-slate-900/70 text-slate-300 hover:border-cyan-500/60 hover:text-white"}`}
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span>
              <span className="block text-xs font-semibold">{step.label}</span>
              {!compact && <span className="block text-[10px] text-slate-400">{step.description}</span>}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
