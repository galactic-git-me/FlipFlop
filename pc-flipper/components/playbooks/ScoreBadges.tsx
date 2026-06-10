"use client";

import { TrendingUp, TrendingDown, Minus, Zap, Users, BarChart2, Clock, AlertTriangle } from "lucide-react";

function ScoreBar({ value, max = 10, colorClass }: { value: number; max?: number; colorClass: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex-1 h-1 bg-[#1e2d45] rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

interface ScorePlaybook {
  profit_opportunity_score?: number;
  market_size_score?: number;
  resellability_score?: number;
  liquidity_score?: number;
  risk_score?: number;
  composite_rank_score?: number;
  market_growth_direction?: string | null;
}

export function ScoreBadges({ playbook }: { playbook: ScorePlaybook }) {
  const GrowthIcon = playbook.market_growth_direction === "Growing" ? TrendingUp :
                     playbook.market_growth_direction === "Shrinking" ? TrendingDown : Minus;
  const growthColor = playbook.market_growth_direction === "Growing" ? "text-emerald-400" :
                      playbook.market_growth_direction === "Shrinking" ? "text-red-400" : "text-slate-400";

  const rows = [
    { icon: <Zap className="w-3 h-3" />, label: "Profit Opp.", value: playbook.profit_opportunity_score ?? 0, colorClass: "bg-[#00dc82]/80" },
    { icon: <Users className="w-3 h-3" />, label: "Market Size", value: playbook.market_size_score ?? 0, colorClass: "bg-blue-400/80" },
    { icon: <BarChart2 className="w-3 h-3" />, label: "Resellability", value: playbook.resellability_score ?? 0, colorClass: "bg-purple-400/80" },
    { icon: <Clock className="w-3 h-3" />, label: "Liquidity", value: playbook.liquidity_score ?? 0, colorClass: "bg-yellow-400/80" },
    { icon: <AlertTriangle className="w-3 h-3" />, label: "Risk", value: playbook.risk_score ?? 0, colorClass: "bg-red-400/80" },
  ];

  return (
    <div className="space-y-1.5">
      {rows.map(row => (
        <div key={row.label} className="flex items-center gap-2">
          <span className="text-slate-500 w-3.5 shrink-0">{row.icon}</span>
          <span className="text-xs text-slate-500 w-24 shrink-0">{row.label}</span>
          <ScoreBar value={row.value} colorClass={row.colorClass} />
          <span className="text-xs font-bold w-6 text-right text-slate-300">{row.value.toFixed(0)}</span>
        </div>
      ))}
      <div className="flex items-center gap-2 pt-1 border-t border-[#1e2d45]">
        <GrowthIcon className={`w-3.5 h-3.5 ${growthColor}`} />
        <span className={`text-xs font-medium ${growthColor}`}>{playbook.market_growth_direction ?? "Stable"}</span>
        <span className="ml-auto text-xs font-bold text-[#00dc82]">
          Score: {(playbook.composite_rank_score ?? 0).toFixed(1)}
        </span>
      </div>
    </div>
  );
}
