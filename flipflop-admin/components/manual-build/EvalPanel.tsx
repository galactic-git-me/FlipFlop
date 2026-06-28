// pc-flipper/components/manual-build/EvalPanel.tsx
"use client";

import { ManualBuildEvaluation } from "@/lib/api";
import { Lightbulb, TrendingUp } from "lucide-react";

interface EvalPanelProps {
  evaluation: ManualBuildEvaluation;
  totalCost: number;
}

export function EvalPanel({ evaluation, totalCost }: EvalPanelProps) {
  const tiers: { label: string; price: number; colour: string }[] = [
    { label: "LOW",  price: evaluation.low,  colour: "#86efac" },
    { label: "MID",  price: evaluation.mid,  colour: "#00dc82" },
    { label: "HIGH", price: evaluation.high, colour: "#34d399" },
  ];

  return (
    <div className="border border-[#00dc82]/30 rounded-lg bg-[#021b12] p-4 space-y-4">
      {/* Price tiers */}
      <div>
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2 font-mono">
          🤖 AI Resale Assessment
        </p>
        <div className="grid grid-cols-3 gap-2">
          {tiers.map((t) => {
            const profit = t.price - totalCost;
            return (
              <div
                key={t.label}
                className="rounded-md bg-[#0a2010] border border-[#1a3a20] p-3 text-center"
              >
                <p className="text-[10px] font-mono uppercase text-slate-400 mb-1">{t.label}</p>
                <p className="text-xl font-bold font-mono" style={{ color: t.colour }}>
                  £{Math.round(t.price)}
                </p>
                <p
                  className="text-[10px] font-mono mt-0.5"
                  style={{ color: profit >= 0 ? "#4ade80" : "#f87171" }}
                >
                  {profit >= 0 ? "+" : ""}£{Math.round(profit)} profit
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Narrative */}
      {evaluation.narrative && (
        <p className="text-xs text-slate-400 leading-relaxed border-t border-slate-800 pt-3">
          {evaluation.narrative}
        </p>
      )}

      {/* Suggestions */}
      {evaluation.suggestions.length > 0 && (
        <div className="border-t border-slate-800 pt-3 space-y-2">
          <p className="text-[10px] uppercase tracking-widest text-slate-500 font-mono flex items-center gap-1">
            <Lightbulb className="w-3 h-3" /> Enhancement suggestions
          </p>
          {evaluation.suggestions.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
              <TrendingUp className="w-3 h-3 text-[#00dc82] mt-0.5 flex-shrink-0" />
              <span>{s.text}</span>
              {s.uplift > 0 && (
                <span className="ml-auto text-[#00dc82] font-mono text-[10px] whitespace-nowrap">
                  +£{s.uplift}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
