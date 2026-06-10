"use client";

import { PlaybookSeasonality } from "@/lib/types";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const MONTH_KEYS: (keyof PlaybookSeasonality)[] = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"];
const CURRENT_MONTH = new Date().getMonth(); // 0-indexed

export function SeasonalityChart({ seasonality }: { seasonality: PlaybookSeasonality }) {
  const values = MONTH_KEYS.map(k => Number(seasonality[k] ?? 5));
  const max = Math.max(...values, 1);

  const position = seasonality.current_position ?? "";
  const positionColor =
    position === "in_peak" ? "text-emerald-400" :
    position === "approaching_peak" ? "text-yellow-400" :
    position === "leaving_peak" ? "text-orange-400" :
    position === "slow_season" ? "text-slate-500" : "text-slate-400";

  const positionLabel =
    position === "in_peak" ? "🔥 In Peak Season" :
    position === "approaching_peak" ? "📈 Approaching Peak" :
    position === "leaving_peak" ? "📉 Leaving Peak" :
    position === "slow_season" ? "😴 Slow Season" :
    position === "in_season" ? "✅ In Season" :
    position === "mid_season" ? "📊 Mid Season" : "—";

  return (
    <div>
      <div className="flex items-end gap-0.5 h-12 mb-1">
        {values.map((v, i) => {
          const isCurrentMonth = i === CURRENT_MONTH;
          const isPeak = (seasonality.peak_months ?? []).includes(MONTHS[i].toLowerCase());
          const height = `${Math.max(8, (v / max) * 100)}%`;
          return (
            <div key={i} className="flex-1 flex flex-col items-end justify-end">
              <div
                className={`w-full rounded-sm transition-all ${
                  isCurrentMonth
                    ? "bg-[#00dc82]"
                    : isPeak
                    ? "bg-[#00dc82]/40"
                    : "bg-[#1e2d45]"
                }`}
                style={{ height }}
                title={`${MONTHS[i]}: ${v}/10`}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-0.5">
        {MONTHS.map((m, i) => (
          <div key={m} className={`flex-1 text-center text-[9px] ${i === CURRENT_MONTH ? "text-[#00dc82] font-bold" : "text-slate-600"}`}>
            {m[0]}
          </div>
        ))}
      </div>
      <div className={`text-xs mt-1.5 font-medium ${positionColor}`}>{positionLabel}</div>
      {(seasonality.days_until_peak ?? 0) > 0 && (
        <div className="text-xs text-slate-500">{seasonality.days_until_peak}d until peak</div>
      )}
    </div>
  );
}
