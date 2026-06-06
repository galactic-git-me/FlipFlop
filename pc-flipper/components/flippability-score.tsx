"use client";

import { SCORE_TIER } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { Listing } from "@/lib/types";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  listing?: Listing | null;
}

function ScoreBreakdown({ listing }: { listing: Listing }) {
  const hasData =
    listing.claude_resale_demand != null &&
    listing.claude_capital_efficiency != null &&
    listing.claude_upgrade_complexity != null;

  const verdictColors: Record<string, string> = {
    GEM:    "text-cyan-400 bg-cyan-400/10 border-cyan-400/30",
    GOOD:   "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
    MAYBE:  "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
    REJECT: "text-red-400 bg-red-400/10 border-red-400/30",
  };
  const verdictStyle = listing.claude_verdict
    ? (verdictColors[listing.claude_verdict] ?? verdictColors.MAYBE)
    : "";

  const profitPotential = listing.claude_roi != null
    ? Math.min(10, Math.max(1, Math.round(listing.claude_roi * 10)))
    : null;

  const upgradePotential = listing.claude_upgrade_complexity != null
    ? 11 - listing.claude_upgrade_complexity
    : null;

  const criteria = [
    { label: "Gaming demand",      value: listing.claude_resale_demand },
    { label: "Ease of resale",     value: listing.claude_capital_efficiency },
    { label: "Upgrade potential",  value: upgradePotential },
    { label: "Profit potential",   value: profitPotential },
  ];

  function barColor(v: number): string {
    if (v >= 8) return "bg-cyan-400";
    if (v >= 6) return "bg-emerald-400";
    if (v >= 4) return "bg-yellow-400";
    return "bg-red-400";
  }

  if (!hasData) {
    return (
      <div className="px-3 py-3 text-xs text-slate-500 italic">
        AI evaluation pending…
      </div>
    );
  }

  return (
    <div className="w-64">
      {/* Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 border-b border-[#1e2d45]">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Flippability Breakdown
        </span>
        {listing.claude_verdict && (
          <span className={cn(
            "text-[10px] font-bold px-2 py-0.5 rounded-full border",
            verdictStyle,
          )}>
            {listing.claude_verdict}
          </span>
        )}
      </div>

      {/* Criteria rows */}
      <div className="px-3 py-2 space-y-2">
        {criteria.map(({ label, value }) => (
          value != null && (
            <div key={label} className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 w-32 flex-shrink-0">{label}</span>
              <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", barColor(value))}
                  style={{ width: `${value * 10}%` }}
                />
              </div>
              <span className="text-[11px] font-semibold text-slate-200 w-8 text-right flex-shrink-0">
                {value}/10
              </span>
            </div>
          )
        ))}
      </div>

      {/* Overall score */}
      {listing.claude_flipability_score != null && (
        <div className="flex items-center justify-between px-3 pt-1.5 pb-2 border-t border-[#1e2d45] mt-1">
          <span className="text-[11px] text-slate-500 uppercase tracking-wider font-semibold">
            Flipability
          </span>
          <span className="text-sm font-black text-[#00dc82]">
            {(listing.claude_flipability_score / 10).toFixed(1)}/10
          </span>
        </div>
      )}

      {/* Reasoning */}
      {listing.claude_reasoning && (
        <div className="px-3 pb-2.5 border-t border-[#1e2d45] pt-2">
          <p className="text-[11px] text-slate-400 leading-relaxed">
            {listing.claude_reasoning}
          </p>
        </div>
      )}

      {/* Main risk */}
      {listing.claude_main_risk && (
        <div className="px-3 pb-3">
          <p className="text-[10px] text-amber-400/80">
            ⚠ {listing.claude_main_risk}
          </p>
        </div>
      )}
    </div>
  );
}

export function FlippabilityScore({
  score,
  size = "md",
  showLabel = true,
  listing,
}: Props) {
  const tier = SCORE_TIER(score);
  const sizes = {
    sm: "w-8 h-8 text-sm",
    md: "w-11 h-11 text-base",
    lg: "w-14 h-14 text-xl",
  };

  const badge = (
    <div className="flex flex-col items-center gap-0.5 cursor-default">
      <div className={cn(
        "rounded-xl border flex items-center justify-center font-black ring-1",
        sizes[size],
        tier.bg,
        tier.color,
        tier.ring,
      )}>
        {tier.label}
      </div>
      {showLabel && (
        <div className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">
          {score.toFixed(0)}<span className="opacity-50">/100</span>
        </div>
      )}
    </div>
  );

  if (!listing) return badge;

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>{badge}</TooltipTrigger>
        <TooltipContent side="right" align="center">
          <ScoreBreakdown listing={listing} />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
