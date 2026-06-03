"use client";

import React, { useState } from "react";
import { WizardBuild } from "@/lib/api";

interface ScatterGraphProps {
  builds: WizardBuild[];
  selectedBuild?: WizardBuild;
  onSelectBuild: (build: WizardBuild) => void;
}

export function BuildScatterGraph({
  builds,
  selectedBuild,
  onSelectBuild,
}: ScatterGraphProps) {
  const [hoveredBuild, setHoveredBuild] = useState<WizardBuild | null>(null);

  if (builds.length === 0) return null;

  // Calculate bounds
  const costs = builds.map(b => b.total_cost);
  const profits = builds.map(b => b.estimated_profit);

  const minCost = Math.min(...costs);
  const maxCost = Math.max(...costs);
  const minProfit = Math.min(...profits);
  const maxProfit = Math.max(...profits);

  const costRange = maxCost - minCost || 1;
  const profitRange = maxProfit - minProfit || 1;

  // Chart dimensions
  const width = 700;
  const height = 400;
  const margin = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartWidth = width - margin.left - margin.right;
  const chartHeight = height - margin.top - margin.bottom;

  // Scale functions
  const scaleX = (cost: number) => {
    return margin.left + ((cost - minCost) / costRange) * chartWidth;
  };

  const scaleY = (profit: number) => {
    return margin.top + chartHeight - ((profit - minProfit) / profitRange) * chartHeight;
  };

  // Demand score to color (0=red, 10=green, 5=yellow)
  const getColorFromDemandScore = (score: number = 5) => {
    const normalized = Math.max(0, Math.min(10, score)) / 10;
    if (normalized < 0.5) {
      // Red to yellow (0 to 5)
      const ratio = normalized * 2;
      return `hsl(${40 * ratio}, 100%, 50%)`;
    } else {
      // Yellow to green (5 to 10)
      const ratio = (normalized - 0.5) * 2;
      return `hsl(${40 - (40 * ratio)}, 100%, 50%)`;
    }
  };

  // Risk score to size (0=small, 10=large)
  const getSizeFromRiskScore = (score: number = 5) => {
    const normalized = Math.max(0, Math.min(10, score)) / 10;
    return 4 + normalized * 12; // 4px to 16px radius
  };

  // Tooltip position
  const getTooltipPosition = (x: number, y: number) => {
    const tooltipWidth = 200;
    const tooltipHeight = 100;
    let left = x + 10;
    let top = y - tooltipHeight - 10;

    if (left + tooltipWidth > width) {
      left = x - tooltipWidth - 10;
    }
    if (top < 0) {
      top = y + 10;
    }

    return { left, top };
  };

  const hoveredPoint = hoveredBuild
    ? {
        x: scaleX(hoveredBuild.total_cost),
        y: scaleY(hoveredBuild.estimated_profit),
      }
    : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Build Analysis</h3>
        <p className="text-xs text-slate-500">Cost vs Profit (colored by demand, sized by risk)</p>
      </div>

      <div className="relative">
        <svg
          width={width}
          height={height}
          className="border border-[#1e2d45] rounded-lg bg-[#0a0f1a]"
          style={{ overflow: "visible" }}
        >
          {/* Grid lines */}
          <g className="opacity-10">
            {Array.from({ length: 5 }).map((_, i) => {
              const x = margin.left + (chartWidth / 4) * i;
              const y = margin.top + (chartHeight / 4) * i;
              return (
                <g key={`grid-${i}`}>
                  <line x1={x} y1={margin.top} x2={x} y2={margin.top + chartHeight} stroke="#888" />
                  <line x1={margin.left} y1={y} x2={margin.left + chartWidth} y2={y} stroke="#888" />
                </g>
              );
            })}
          </g>

          {/* Axes */}
          <line x1={margin.left} y1={margin.top + chartHeight} x2={margin.left + chartWidth} y2={margin.top + chartHeight} stroke="#555" strokeWidth="2" />
          <line x1={margin.left} y1={margin.top} x2={margin.left} y2={margin.top + chartHeight} stroke="#555" strokeWidth="2" />

          {/* Axis labels */}
          <text x={width / 2} y={height - 5} textAnchor="middle" className="text-xs fill-slate-500">
            Total Cost (£)
          </text>
          <text x="15" y={height / 2} textAnchor="middle" transform={`rotate(-90, 15, ${height / 2})`} className="text-xs fill-slate-500">
            Estimated Profit (£)
          </text>

          {/* Scale ticks and labels */}
          {Array.from({ length: 5 }).map((_, i) => {
            const costValue = minCost + (costRange / 4) * i;
            const profitValue = minProfit + (profitRange / 4) * i;
            const x = margin.left + (chartWidth / 4) * i;
            const y = margin.top + chartHeight - (chartHeight / 4) * i;

            return (
              <g key={`scales-${i}`}>
                {/* Cost ticks */}
                <line x1={x} y1={margin.top + chartHeight} x2={x} y2={margin.top + chartHeight + 4} stroke="#666" />
                <text x={x} y={margin.top + chartHeight + 16} textAnchor="middle" className="text-xs fill-slate-600">
                  £{costValue.toFixed(0)}
                </text>

                {/* Profit ticks */}
                {i > 0 && (
                  <>
                    <line x1={margin.left - 4} y1={y} x2={margin.left} y2={y} stroke="#666" />
                    <text x={margin.left - 8} y={y + 3} textAnchor="end" className="text-xs fill-slate-600">
                      £{profitValue.toFixed(0)}
                    </text>
                  </>
                )}
              </g>
            );
          })}

          {/* Data points */}
          {builds.map((build, idx) => {
            const x = scaleX(build.total_cost);
            const y = scaleY(build.estimated_profit);
            const size = getSizeFromRiskScore(build.risk_score ?? 5);
            const color = getColorFromDemandScore(build.demand_score ?? 5);
            const isSelected = selectedBuild?.id === build.id;
            const isHovered = hoveredBuild?.id === build.id;

            return (
              <g
                key={build.id}
                onMouseEnter={() => setHoveredBuild(build)}
                onMouseLeave={() => setHoveredBuild(null)}
                onClick={() => onSelectBuild(build)}
                className="cursor-pointer transition-all"
              >
                <circle
                  cx={x}
                  cy={y}
                  r={size}
                  fill={color}
                  opacity={isHovered || isSelected ? 0.9 : 0.7}
                  stroke={isSelected ? "#00dc82" : isHovered ? "#888" : "transparent"}
                  strokeWidth={isSelected ? 2 : isHovered ? 1 : 0}
                />
                {(isHovered || isSelected) && (
                  <circle
                    cx={x}
                    cy={y}
                    r={size + 3}
                    fill="none"
                    stroke="#00dc82"
                    strokeWidth="1"
                    opacity="0.5"
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Tooltip */}
        {hoveredPoint && hoveredBuild && (
          <div
            className="absolute bg-[#0d1320] border border-[#1e2d45] rounded-lg p-3 text-xs z-50 pointer-events-none"
            style={{
              left: `${getTooltipPosition(hoveredPoint.x, hoveredPoint.y).left}px`,
              top: `${getTooltipPosition(hoveredPoint.x, hoveredPoint.y).top}px`,
              width: "200px",
            }}
          >
            <div className="font-semibold text-slate-100 mb-1">{hoveredBuild.name}</div>
            <div className="space-y-0.5 text-slate-400">
              <div>
                Cost: <span className="text-slate-200">£{hoveredBuild.total_cost.toFixed(0)}</span>
              </div>
              <div>
                Profit: <span className="text-[#00dc82]">£{hoveredBuild.estimated_profit.toFixed(0)}</span>
              </div>
              <div>
                Demand:{" "}
                <span className="capitalize text-slate-200">{hoveredBuild.demand_fit}</span>
              </div>
              <div>
                Risk:{" "}
                <span className="capitalize text-slate-200">{hoveredBuild.risk}</span>
              </div>
              <div>
                Margin: <span className="text-slate-200">{hoveredBuild.profit_margin_pct.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-xs mt-3">
        <div className="flex items-center gap-2">
          <span className="text-slate-600">Demand:</span>
          <div className="flex gap-1">
            {["Poor", "Moderate", "Good", "Excellent"].map((label, i) => {
              const score = i * 3.33;
              const color = getColorFromDemandScore(score);
              return (
                <div
                  key={label}
                  className="rounded-full"
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: color,
                  }}
                  title={label}
                />
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-600">Risk:</span>
          <div className="flex gap-1">
            {["Low", "Medium", "High"].map((label, i) => {
              const score = i * 5;
              const size = getSizeFromRiskScore(score);
              return (
                <div
                  key={label}
                  className="rounded-full bg-slate-500"
                  style={{
                    width: `${size * 2}px`,
                    height: `${size * 2}px`,
                  }}
                  title={label}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
