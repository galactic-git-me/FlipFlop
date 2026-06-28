"use client";

import { PlaybookIdealBuildComponent } from "@/lib/types";

const COMPONENT_LABELS: Record<string, string> = {
  cpu: "CPU", gpu: "GPU", ram: "RAM", storage: "Storage",
  psu: "PSU", case: "Case", motherboard: "Motherboard",
  cooling: "Cooling", rgb_fans: "RGB Fans",
};

export function IdealBuildPanel({ idealBuild }: { idealBuild: Record<string, PlaybookIdealBuildComponent> }) {
  const entries = Object.entries(idealBuild).filter(([, v]) => v && typeof v === "object");
  if (!entries.length) return <p className="text-xs text-slate-600 py-2">No ideal build defined.</p>;

  return (
    <div className="space-y-2">
      {entries.map(([key, comp]) => (
        <div key={key} className="bg-[#0a1220] border border-[#1e2d45] rounded-lg p-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold text-slate-300">{COMPONENT_LABELS[key] ?? key.toUpperCase()}</span>
            <div className="flex items-center gap-3">
              <span className="text-xs text-[#00dc82]">Target £{comp.target_price}</span>
              <span className="text-xs text-slate-500">Walk-away £{comp.walk_away_price}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-1">
            {(comp.candidate_models ?? []).map(m => (
              <span key={m} className="text-[11px] bg-[#111c2e] border border-[#1e2d45] text-slate-400 px-1.5 py-0.5 rounded font-mono">{m}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
